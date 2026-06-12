import 'dart:typed_data';
import 'package:egts_tracker/models/models.dart';
import 'egts_crc.dart';

/// Построитель бинарных EGTS-пакетов (ГОСТ Р 54619-2011).
///
/// SRT-типы в пакете:
///   16  — EGTS_SR_POS_DATA       (GPS координата + курс + скорость)
///   17  — EGTS_SR_EXT_POS_DATA   (HDOP, кол-во спутников)
///   21  — EGTS_SR_STATE_DATA     (состояние устройства)
///  202  — EGTS_SR_CUSTOM_SRT202  (tag identity: iBeacon / NFC / WiFi)
///  203  — EGTS_SR_CUSTOM_SRT203  (тип события: вход в зону / RFID / WiFi AP)
class EgtsBuilder {
  // Эпоха EGTS: 2010-01-01 00:00:00 UTC
  static final _epoch = DateTime.utc(2010, 1, 1);

  static const _ptAppdata = 0x01;
  static const _svcTeledata = 0x02;

  // ─── Public API ──────────────────────────────────────────────────────────

  /// Строит пакет EGTS для события NFC.
  /// Всегда включает GPS и LBS если доступны.
  static Uint8List buildNfcPacket({
    required NfcEvent nfc,
    required GpsData gps,
    LbsEvent? lbs,
    required int terminalId,
    required int packetId,
  }) =>
      _buildPacket(
        gps: gps, lbs: lbs,
        srt202: _buildSrt202NfcTag(nfc),
        srt203: _buildSrt203(eventType: 1, zoneId: 0, ts: nfc.ts),
        terminalId: terminalId, packetId: packetId,
        triggerLabel: 'NFC:${nfc.uid}',
      );

  /// Строит пакет EGTS для события iBeacon.
  static Uint8List buildBeaconPacket({
    required BeaconEvent beacon,
    required GpsData gps,
    LbsEvent? lbs,
    required int terminalId,
    required int packetId,
  }) =>
      _buildPacket(
        gps: gps, lbs: lbs,
        srt202: _buildSrt202Beacon(beacon),
        srt203: _buildSrt203(
            eventType: 1,
            zoneId: (beacon.major << 16) | beacon.minor,
            ts: beacon.ts),
        terminalId: terminalId, packetId: packetId,
        triggerLabel: 'BLE:${beacon.uuid}/${beacon.major}/${beacon.minor}',
      );

  /// Строит пакет EGTS для события WiFi.
  static Uint8List buildWifiPacket({
    required WifiEvent wifi,
    required GpsData gps,
    LbsEvent? lbs,
    required int terminalId,
    required int packetId,
  }) =>
      _buildPacket(
        gps: gps, lbs: lbs,
        srt202: _buildSrt202Wifi(wifi),
        srt203: _buildSrt203(eventType: 1, zoneId: 0, ts: wifi.ts),
        terminalId: terminalId, packetId: packetId,
        triggerLabel: 'WiFi:${wifi.ssid}',
      );

  /// Строит пакет EGTS только с LBS-данными (режим LBS-исследования).
  static Uint8List buildLbsPacket({
    required LbsEvent lbs,
    required GpsData gps,
    required int terminalId,
    required int packetId,
  }) =>
      _buildPacket(
        gps: gps, lbs: lbs,
        srt202: _buildSrt202Lbs(lbs),
        srt203: _buildSrt203(eventType: 1, zoneId: lbs.cellId, ts: gps.ts),
        terminalId: terminalId, packetId: packetId,
        triggerLabel: 'LBS:${lbs.cellId}',
      );

  /// Строит пакет EGTS с IMU / inertial данными (SRT 204).
  /// Используется для отправки ориентации + raw sensors + vibration + fusion hints.
  static Uint8List buildImuPacket({
    required ImuEvent imu,
    required GpsData gps,
    LbsEvent? lbs,
    required int terminalId,
    required int packetId,
  }) =>
      _buildPacket(
        gps: gps, lbs: lbs, imu: imu,
        srt202: _buildSrt202Imu(imu),
        srt203: _buildSrt203(eventType: 2, zoneId: 0, ts: imu.ts), // eventType 2 = inertial
        terminalId: terminalId, packetId: packetId,
        triggerLabel: 'IMU:head${imu.headingDeg.toStringAsFixed(0)}',
      );

  /// Декодирует пакет в читаемую структуру для отображения в UI.
  static Map<String, dynamic> decode(Uint8List packet) {
    if (packet.length < 11) return {'error': 'too short'};
    final buf = ByteData.sublistView(packet);
    final hl  = packet[3];
    final fdl = buf.getUint16(5, Endian.little);
    final pid = buf.getUint16(7, Endian.little);
    final pt  = packet[9];
    final hcs = packet[hl - 1];
    final hcsCalc = crc8(packet, len: hl - 1);

    final result = <String, dynamic>{
      'PRV': packet[0], 'HL': hl, 'FDL': fdl, 'PID': pid,
      'PT': pt == 1 ? 'EGTS_PT_APPDATA' : 'EGTS_PT_RESPONSE',
      'HCS': '0x${hcs.toRadixString(16).padLeft(2, '0').toUpperCase()}',
      'HCS_valid': hcs == hcsCalc,
    };

    if (fdl > 0 && packet.length >= hl + fdl + 2) {
      final crc16val = buf.getUint16(hl + fdl, Endian.little);
      final crc16calc = crc16(packet, offset: hl, len: fdl);
      result['CRC16_valid'] = crc16val == crc16calc;
      result['SDR'] = _decodeSDR(packet, hl, fdl);
    }
    return result;
  }

  // ─── Internal packet assembly ─────────────────────────────────────────────

  static Uint8List _buildPacket({
    required GpsData gps,
    LbsEvent? lbs,
    ImuEvent? imu,
    required Uint8List srt202,
    required Uint8List srt203,
    required int terminalId,
    required int packetId,
    required String triggerLabel,
  }) {
    final subrecords = <int>[];
    subrecords.addAll(_subrecord(16, _buildPosData(gps)));
    if (gps.satellites > 0 || gps.hdop > 0) {
      subrecords.addAll(_subrecord(17, _buildExtPosData(gps)));
    }
    subrecords.addAll(_subrecord(21, _buildStateData()));
    // LBS субзапись (тип 103) — ВСЕГДА присутствует в пакете (legacy)
    subrecords.addAll(_subrecord(103, _buildLbsData(lbs)));
    // SRT 205 — detailed LBS for server-side road graph matching (discussion 18)
    if (lbs != null) {
      subrecords.addAll(_subrecord(205, _buildLbsSrt205(lbs)));
    }
    // SRT 204 — IMU / inertial + fusion outputs (discussion 09/12/13-16)
    if (imu != null) {
      subrecords.addAll(_subrecord(204, _buildSrt204(imu)));
    }
    subrecords.addAll(_subrecord(202, srt202));
    subrecords.addAll(_subrecord(203, srt203));

    final sdr = _buildSDR(
      recordNumber: packetId & 0xFFFF,
      recordData: Uint8List.fromList(subrecords),
      objectId: terminalId,
    );
    return _buildHeader(packetId: packetId, sfrd: sdr);
  }

  // ─── SRT builders ─────────────────────────────────────────────────────────

  static Uint8List _buildPosData(GpsData gps) {
    final buf = ByteData(21);
    final ntm = gps.ts.toUtc().difference(_epoch).inSeconds;
    buf.setUint32(0, ntm.clamp(0, 0xFFFFFFFF), Endian.little);

    final latAbs = gps.lat.abs();
    final lonAbs = gps.lon.abs();
    buf.setUint32(4, (latAbs / 90.0 * 0xFFFFFFFF).toInt(), Endian.little);
    buf.setUint32(8, (lonAbs / 180.0 * 0xFFFFFFFF).toInt(), Endian.little);

    final lohs = gps.lon < 0 ? 1 : 0;
    final lahs = gps.lat < 0 ? 1 : 0;
    final mv   = gps.speedKmh > 1.0 ? 1 : 0;
    final fix  = gps.satellites >= 4 ? 1 : 0;
    final vld  = gps.isValid ? 1 : 0;
    buf.setUint8(12, (lohs << 6) | (lahs << 5) | (mv << 4) | (fix << 1) | vld);

    final spd = ((gps.speedKmh * 10).toInt() & 0x3FFF);
    buf.setUint16(13, spd, Endian.little);
    buf.setUint8(15, gps.courseDeg & 0xFF);
    buf.setUint8(16, 0); buf.setUint8(17, 0); buf.setUint8(18, 0); // ODM
    buf.setUint8(19, 0); // DIN
    buf.setUint8(20, 0); // SRC
    return buf.buffer.asUint8List();
  }

  static Uint8List _buildExtPosData(GpsData gps) {
    final hasHdop = gps.hdop > 0;
    final hasSat  = gps.satellites > 0;
    final flags = (hasSat ? 0x10 : 0) | (hasHdop ? 0x40 : 0);
    final out = <int>[flags];
    if (hasHdop) {
      final h = (gps.hdop * 10).toInt().clamp(0, 0xFFFF);
      out.addAll([h & 0xFF, (h >> 8) & 0xFF]);
    }
    if (hasSat) out.add(gps.satellites & 0xFF);
    return Uint8List.fromList(out);
  }

  static Uint8List _buildStateData() =>
      Uint8List.fromList([0x00, 0x78, 0x00, 0x00, 0x00]); // ST=active, 12.0V

  static Uint8List _buildSrt202Beacon(BeaconEvent b) {
    final tagId = ((b.major << 16) | b.minor) & 0xFFFFFFFF;
    final buf = ByteData(9);
    buf.setUint32(0, tagId, Endian.little);
    buf.setUint16(4, b.major & 0xFFFF, Endian.little);
    buf.setUint16(6, b.minor & 0xFFFF, Endian.little);
    buf.setInt8(8, b.rssi.clamp(-128, 127));
    return buf.buffer.asUint8List();
  }

  static Uint8List _buildSrt202NfcTag(NfcEvent n) {
    final tagId = int.tryParse(n.uid.replaceAll(':', ''), radix: 16) ?? 0;
    final buf = ByteData(9);
    buf.setUint32(0, tagId & 0xFFFFFFFF, Endian.little);
    buf.setUint16(4, 0, Endian.little);
    buf.setUint16(6, 0, Endian.little);
    buf.setInt8(8, 0);
    return buf.buffer.asUint8List();
  }

  // LBS субзапись (тип 103): MCC(2)+MNC(2)+LAC(2)+CID(4)+RSSI(1) = 11 байт
  static Uint8List _buildLbsData(LbsEvent? lbs) {
    final buf = ByteData(11);
    if (lbs != null) {
      buf.setUint16(0, lbs.mcc.clamp(0, 0xFFFF), Endian.little);
      buf.setUint16(2, lbs.mnc.clamp(0, 0xFFFF), Endian.little);
      buf.setUint16(4, lbs.lac.clamp(0, 0xFFFF), Endian.little);
      buf.setUint32(6, lbs.cellId.clamp(0, 0xFFFFFFFF), Endian.little);
      buf.setInt8(10, lbs.rssi.clamp(-128, 127));
    }
    return buf.buffer.asUint8List();
  }

  // SRT 205 — detailed LBS data for server map-matching (discussion 18)
  // Format matches SrCustom205 in SERVICE/egts/models.py
  static Uint8List _buildLbsSrt205(LbsEvent lbs) {
    final buf = ByteData(30);
    buf.setUint32(0, lbs.cellId & 0xFFFFFFFF, Endian.little);
    buf.setUint16(4, lbs.lac & 0xFFFF, Endian.little);
    buf.setUint16(6, lbs.mcc & 0xFFFF, Endian.little);
    buf.setUint16(8, lbs.mnc & 0xFFFF, Endian.little);
    buf.setInt8(10, lbs.rssi.clamp(-128, 127));
    final ta = lbs.timingAdvance ?? 0;
    buf.setUint16(11, (ta < 0 ? 0 : ta) & 0xFFFF); // timing_advance
    // bs_lat/lon left 0 (server-side enrichment from cell DB)
    buf.setInt32(13, 0, Endian.little);
    buf.setInt32(17, 0, Endian.little);
    // raw_lbs as placeholder (server does the real snap using TA/RSSI + graph)
    buf.setInt32(21, (lbs.cellId * 1000).toInt() & 0xFFFFFFFF, Endian.little);
    buf.setInt32(25, 0, Endian.little);
    buf.setUint8(29, 70); // quality
    return buf.buffer.asUint8List(0, 30);
  }

  // SRT202 для LBS-пакета (идентификатор по cellId)
  static Uint8List _buildSrt202Lbs(LbsEvent lbs) {
    final buf = ByteData(9);
    buf.setUint32(0, lbs.cellId & 0xFFFFFFFF, Endian.little);
    buf.setUint16(4, lbs.lac & 0xFFFF, Endian.little);
    buf.setUint16(6, lbs.mcc & 0xFFFF, Endian.little);
    buf.setInt8(8, lbs.rssi.clamp(-128, 127));
    return buf.buffer.asUint8List();
  }

  // SRT 204 — IMU / Inertial data (matches SrCustom204 in SERVICE/egts/models.py)
  static Uint8List _buildSrt204(ImuEvent imu) {
    final buf = ByteData(38); // enough for orientation + raw + vibration + ekf/road hints
    // Orientation (0.01 deg units like the wire format)
    buf.setInt16(0, (imu.headingDeg * 100).toInt(), Endian.little);
    buf.setInt16(2, (imu.rollDeg * 100).toInt(), Endian.little);
    buf.setInt16(4, (imu.pitchDeg * 100).toInt(), Endian.little);
    buf.setInt16(6, 500); // heading_accuracy ~5.0 deg default

    // Raw accel/gyro (scaled *100)
    buf.setInt16(8, (imu.accelX * 100).toInt(), Endian.little);
    buf.setInt16(10, (imu.accelY * 100).toInt(), Endian.little);
    buf.setInt16(12, (imu.accelZ * 100).toInt(), Endian.little);
    buf.setInt16(14, (imu.gyroX * 100).toInt(), Endian.little);
    buf.setInt16(16, (imu.gyroY * 100).toInt(), Endian.little);
    buf.setInt16(18, (imu.gyroZ * 100).toInt(), Endian.little);

    // Vibration + filter type + ekf conf (placeholder)
    final vib = (imu.vibrationRms * 100).toInt() & 0xFFFF;
    buf.setUint16(20, vib, Endian.little);
    buf.setUint16(22, vib, Endian.little); // peak approx
    buf.setUint16(24, 0, Endian.little);   // dominant freq
    buf.setUint8(26, 3);                   // filter_type = 3 (ekf/hybrid)
    buf.setUint8(27, 180);                 // ekf_conf ~0.7

    // cov + road snap placeholders (server or on-device fusion can fill)
    buf.setFloat32(28, 0.0, Endian.little);
    buf.setUint32(32, 0, Endian.little);   // road_segment_id
    buf.setInt32(36, 0, Endian.little);    // partial matched (more fields would need bigger buf or extension)
    // For full fidelity use the exact layout from models.py to_bytes in a future iteration.

    return buf.buffer.asUint8List(0, 38);
  }

  // SRT202 for IMU packet (simple tag using heading)
  static Uint8List _buildSrt202Imu(ImuEvent imu) {
    final buf = ByteData(9);
    final tag = (imu.headingDeg * 100).toInt() & 0xFFFFFFFF;
    buf.setUint32(0, tag, Endian.little);
    buf.setUint16(4, 204, Endian.little); // hint SRT
    buf.setUint16(6, 0, Endian.little);
    buf.setInt8(8, (imu.vibrationRms * 10).toInt().clamp(-128, 127));
    return buf.buffer.asUint8List();
  }

  static Uint8List _buildSrt202Wifi(WifiEvent w) {
    final parts = w.bssid.split(':').map((p) => int.tryParse(p, radix: 16) ?? 0).toList();
    int tagId = 0;
    for (var i = 0; i < parts.length && i < 4; i++) {
      tagId = (tagId << 8) | parts[i];
    }
    final buf = ByteData(9);
    buf.setUint32(0, tagId & 0xFFFFFFFF, Endian.little);
    buf.setUint16(4, w.channel & 0xFFFF, Endian.little);
    buf.setUint16(6, 0, Endian.little);
    buf.setInt8(8, w.rssi.clamp(-128, 127));
    return buf.buffer.asUint8List();
  }

  static Uint8List _buildSrt203({
    required int eventType,
    required int zoneId,
    required DateTime ts,
  }) {
    final ntm = ts.toUtc().difference(_epoch).inSeconds.clamp(0, 0xFFFFFFFF);
    final buf = ByteData(10);
    buf.setUint8(0, eventType & 0xFF);
    buf.setUint32(1, zoneId & 0xFFFFFFFF, Endian.little);
    buf.setUint32(5, ntm, Endian.little);
    buf.setUint8(9, 0);
    return buf.buffer.asUint8List();
  }

  // ─── Structure builders ───────────────────────────────────────────────────

  static List<int> _subrecord(int srt, Uint8List srd) {
    final out = <int>[srt & 0xFF, srd.length & 0xFF, (srd.length >> 8) & 0xFF];
    out.addAll(srd);
    return out;
  }

  static Uint8List _buildSDR({
    required int recordNumber,
    required Uint8List recordData,
    required int objectId,
  }) {
    final out = <int>[];
    // RL
    out.add(recordData.length & 0xFF);
    out.add((recordData.length >> 8) & 0xFF);
    // RN
    out.add(recordNumber & 0xFF);
    out.add((recordNumber >> 8) & 0xFF);
    // FLAGS: OBFE=1
    out.add(0x01);
    // OID
    out.add(objectId & 0xFF);
    out.add((objectId >> 8) & 0xFF);
    out.add((objectId >> 16) & 0xFF);
    out.add((objectId >> 24) & 0xFF);
    // SST, RST
    out.add(_svcTeledata);
    out.add(_svcTeledata);
    out.addAll(recordData);
    return Uint8List.fromList(out);
  }

  static Uint8List _buildHeader({required int packetId, required Uint8List sfrd}) {
    final hdr = <int>[
      0x01, 0x00, 0x00, 11, 0x00,
      sfrd.length & 0xFF, (sfrd.length >> 8) & 0xFF,
      packetId & 0xFF, (packetId >> 8) & 0xFF,
      _ptAppdata,
    ];
    hdr.add(crc8(hdr));
    hdr.addAll(sfrd);
    final c16 = crc16(sfrd);
    hdr.add(c16 & 0xFF);
    hdr.add((c16 >> 8) & 0xFF);
    return Uint8List.fromList(hdr);
  }

  // ─── Decode (for UI display) ──────────────────────────────────────────────

  static List<Map<String, dynamic>> _decodeSDR(Uint8List pkt, int hl, int fdl) {
    final sdrs = <Map<String, dynamic>>[];
    int off = hl;
    final end = hl + fdl;
    while (off + 11 <= end) {
      final buf = ByteData.sublistView(pkt, off);
      final rl  = buf.getUint16(0, Endian.little);
      final rn  = buf.getUint16(2, Endian.little);
      final flg = pkt[off + 4];
      off += 5;
      final obfe = flg & 0x01;
      int? oid;
      if (obfe == 1 && off + 4 <= end) {
        oid = ByteData.sublistView(pkt, off).getUint32(0, Endian.little);
        off += 4;
      }
      final sst = pkt[off++];
      off++; // RST
      final rdEnd = off + rl;
      final subrecords = <Map<String, dynamic>>[];
      while (off + 3 <= rdEnd && rdEnd <= end) {
        final srt = pkt[off];
        final srl = ByteData.sublistView(pkt, off + 1).getUint16(0, Endian.little);
        off += 3;
        final srd = pkt.sublist(off, (off + srl).clamp(0, end));
        off += srl;
        subrecords.add(_decodeSrt(srt, srd));
      }
      off = rdEnd;
      sdrs.add({
        'RN': rn, 'RL': rl,
        'SST': sst == 2 ? 'TELEDATA' : 'AUTH',
        'OID': oid,
        'subrecords': subrecords,
      });
    }
    return sdrs;
  }

  static final _srtNames = <int, String>{
    16: 'POS_DATA', 17: 'EXT_POS_DATA', 21: 'STATE_DATA',
    202: 'CUSTOM_SRT202 (Tag)', 203: 'CUSTOM_SRT203 (Event)',
  };

  static Map<String, dynamic> _decodeSrt(int srt, Uint8List srd) {
    final name = _srtNames[srt] ?? 'SRT_$srt';
    final fields = <String, dynamic>{};
    try {
      if (srt == 16 && srd.length >= 21) {
        final buf = ByteData.sublistView(srd);
        final ntm = buf.getUint32(0, Endian.little);
        final dt = _epoch.add(Duration(seconds: ntm));
        final latR = buf.getUint32(4, Endian.little);
        final lonR = buf.getUint32(8, Endian.little);
        final lat = latR / 0xFFFFFFFF * 90;
        final lon = lonR / 0xFFFFFFFF * 180;
        final spd = (buf.getUint16(13, Endian.little) & 0x3FFF) / 10.0;
        fields['NTM'] = dt.toIso8601String();
        fields['LAT'] = lat.toStringAsFixed(6);
        fields['LONG'] = lon.toStringAsFixed(6);
        fields['SPD_kmh'] = spd;
        fields['VLD'] = (srd[12] & 0x01) == 1;
      } else if (srt == 21 && srd.length >= 5) {
        fields['STATE'] = srd[0];
        fields['MPSV_V'] = (srd[1] * 0.1).toStringAsFixed(1);
        fields['BBV_V']  = (srd[2] * 0.1).toStringAsFixed(1);
      } else if (srt == 202 && srd.length >= 9) {
        final buf = ByteData.sublistView(srd);
        fields['tag_id']  = buf.getUint32(0, Endian.little);
        fields['zone_id'] = buf.getUint16(4, Endian.little);
        fields['rssi']    = srd[8];
      } else if (srt == 203 && srd.length >= 10) {
        final buf = ByteData.sublistView(srd);
        const evts = {0:'none',1:'enter',2:'exit',3:'alarm',4:'low_batt',5:'tamper'};
        final evtCode = srd[0];
        final ntm = buf.getUint32(5, Endian.little);
        fields['event'] = evts[evtCode] ?? 'unknown($evtCode)';
        fields['zone_id'] = buf.getUint32(1, Endian.little);
        fields['time'] = _epoch.add(Duration(seconds: ntm)).toIso8601String();
      }
    } catch (_) {}
    return {
      'SRT': srt, 'name': name, 'SRL': srd.length,
      'hex': srd.map((b) => b.toRadixString(16).padLeft(2,'0')).join(' ').toUpperCase(),
      'fields': fields,
    };
  }
}
