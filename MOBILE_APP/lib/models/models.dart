import 'dart:typed_data';
import 'package:latlong2/latlong.dart';

// ─── Whitelist entries ────────────────────────────────────────────────────────

class NfcEntry {
  final String uid;       // hex UID метки, напр. "04A3B2C1"
  final String label;     // человекочитаемое название

  const NfcEntry({required this.uid, this.label = ''});

  Map<String, String> toJson() => {'uid': uid, 'label': label};
  factory NfcEntry.fromJson(Map<String, dynamic> j) =>
      NfcEntry(uid: j['uid'] as String, label: (j['label'] as String?) ?? '');
  @override
  String toString() => label.isNotEmpty ? '$label ($uid)' : uid;
  @override
  bool operator ==(Object other) => other is NfcEntry && other.uid.toUpperCase() == uid.toUpperCase();
  @override
  int get hashCode => uid.toUpperCase().hashCode;
}

class BeaconEntry {
  final String uuid;      // iBeacon UUID
  final int? major;       // null = любой
  final int? minor;       // null = любой
  final String label;

  const BeaconEntry({required this.uuid, this.major, this.minor, this.label = ''});

  bool matches(String u, int maj, int min) =>
      u.toUpperCase() == uuid.toUpperCase() &&
      (major == null || major == maj) &&
      (minor == null || minor == min);

  Map<String, dynamic> toJson() =>
      {'uuid': uuid, 'major': major, 'minor': minor, 'label': label};
  factory BeaconEntry.fromJson(Map<String, dynamic> j) => BeaconEntry(
        uuid:  j['uuid'] as String,
        major: j['major'] as int?,
        minor: j['minor'] as int?,
        label: (j['label'] as String?) ?? '',
      );
  @override
  String toString() {
    final m = major != null ? '$major' : '*';
    final n = minor != null ? '$minor' : '*';
    return label.isNotEmpty ? '$label ($uuid $m/$n)' : '$uuid $m/$n';
  }
}

class WifiEntry {
  final String? ssid;
  final String? bssid;    // MAC, напр. "AA:BB:CC:DD:EE:FF"
  final String label;

  const WifiEntry({this.ssid, this.bssid, this.label = ''});

  bool matches(String s, String b) =>
      (ssid != null && ssid == s) ||
      (bssid != null && bssid!.toUpperCase() == b.toUpperCase());

  Map<String, dynamic> toJson() =>
      {'ssid': ssid, 'bssid': bssid, 'label': label};
  factory WifiEntry.fromJson(Map<String, dynamic> j) => WifiEntry(
        ssid:  j['ssid'] as String?,
        bssid: j['bssid'] as String?,
        label: (j['label'] as String?) ?? '',
      );
  @override
  String toString() => label.isNotEmpty
      ? label
      : [if (ssid != null) 'SSID:$ssid', if (bssid != null) 'BSSID:$bssid'].join(' / ');
}

// ─── Scan events (live data) ─────────────────────────────────────────────────

enum ScanType { nfc, beacon, wifi, lbs }

class NfcEvent {
  final String uid;
  final List<String> techList;
  final DateTime ts;
  NfcEvent({required this.uid, this.techList = const [], DateTime? ts})
      : ts = ts ?? DateTime.now();
}

class BeaconEvent {
  final String uuid;
  final int major;
  final int minor;
  final int rssi;
  final double distance;
  final String mac;
  final DateTime ts;
  BeaconEvent({
    required this.uuid, required this.major, required this.minor,
    required this.rssi, required this.distance, this.mac = '',
    DateTime? ts,
  }) : ts = ts ?? DateTime.now();
}

class WifiEvent {
  final String ssid;
  final String bssid;
  final int rssi;
  final int frequency;
  final DateTime ts;
  WifiEvent({
    required this.ssid, required this.bssid,
    required this.rssi, required this.frequency, DateTime? ts,
  }) : ts = ts ?? DateTime.now();

  int get channel {
    if (frequency >= 2412 && frequency <= 2484) return (frequency - 2412) ~/ 5 + 1;
    if (frequency >= 5170 && frequency <= 5825) return (frequency - 5170) ~/ 5 + 34;
    return 0;
  }
}

class LbsEvent {
  final int mcc, mnc, lac, cellId, rssi;
  final int? timingAdvance;     // TA for distance estimation (SRT 205)
  final String? networkType;    // 'LTE' | 'GSM' | 'WCDMA' etc.
  final DateTime ts;

  LbsEvent({
    required this.mcc,
    required this.mnc,
    required this.lac,
    required this.cellId,
    required this.rssi,
    this.timingAdvance,
    this.networkType,
    DateTime? ts,
  }) : ts = ts ?? DateTime.now();
}

// ─── GPS ─────────────────────────────────────────────────────────────────────

class GpsData {
  final double lat, lon, alt, speedKmh;
  final int courseDeg, satellites;
  final double hdop, accuracy;
  final bool isValid;
  final DateTime ts;

  const GpsData({
    this.lat = 0, this.lon = 0, this.alt = 0, this.speedKmh = 0,
    this.courseDeg = 0, this.satellites = 0, this.hdop = 0, this.accuracy = 0,
    this.isValid = false, required this.ts,
  });

  static GpsData empty() => GpsData(ts: DateTime.now());
}

// ─── EGTS packet preview ──────────────────────────────────────────────────────

class EgtsPacketInfo {
  final Uint8List bytes;
  final String hexStr;
  final Map<String, dynamic> decoded;   // структура для отображения
  final String triggerType;             // 'nfc' | 'beacon' | 'wifi'
  final String triggerId;
  final bool sent;
  final String? sendError;
  final DateTime ts;

  const EgtsPacketInfo({
    required this.bytes,
    required this.hexStr,
    required this.decoded,
    required this.triggerType,
    required this.triggerId,
    this.sent = false,
    this.sendError,
    required this.ts,
  });

  EgtsPacketInfo copyWith({bool? sent, String? sendError}) => EgtsPacketInfo(
    bytes: bytes, hexStr: hexStr, decoded: decoded,
    triggerType: triggerType, triggerId: triggerId,
    sent: sent ?? this.sent, sendError: sendError ?? this.sendError, ts: ts,
  );
}

// ─── Marker for survey map ────────────────────────────────────────────────────

class MarkerState {
  final LatLng position;
  final bool userAdjusted;
  const MarkerState({required this.position, this.userAdjusted = false});
}

// ─── Server config ────────────────────────────────────────────────────────────

class ServerConfig {
  final String url;
  final String token;
  final int terminalId;
  final int timeoutMs;

  const ServerConfig({
    this.url = '',
    this.token = '',
    this.terminalId = 1,
    this.timeoutMs = 8000,
  });

  ServerConfig copyWith({String? url, String? token, int? terminalId, int? timeoutMs}) =>
      ServerConfig(
        url:        url        ?? this.url,
        token:      token      ?? this.token,
        terminalId: terminalId ?? this.terminalId,
        timeoutMs:  timeoutMs  ?? this.timeoutMs,
      );

  Map<String, dynamic> toJson() =>
      {'url': url, 'token': token, 'terminalId': terminalId, 'timeoutMs': timeoutMs};
  factory ServerConfig.fromJson(Map<String, dynamic> j) => ServerConfig(
        url:        (j['url']        as String?) ?? '',
        token:      (j['token']      as String?) ?? '',
        terminalId: (j['terminalId'] as int?)    ?? 1,
        timeoutMs:  (j['timeoutMs']  as int?)    ?? 8000,
      );
}
