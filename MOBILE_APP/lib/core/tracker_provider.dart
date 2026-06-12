import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';
import 'package:geolocator/geolocator.dart';
import 'package:latlong2/latlong.dart';
import 'package:wifi_scan/wifi_scan.dart';
import 'package:egts_tracker/core/egts/egts_builder.dart';
import 'package:egts_tracker/core/egts/egts_client.dart' show EgtsClient, SendResult;
import 'package:egts_tracker/core/prefs/app_prefs.dart';
import 'package:egts_tracker/models/models.dart';
import 'lbs_collector.dart';
import 'imu_collector.dart';

/// Центральный провайдер состояния приложения.
///
/// Управляет:
///   • GPS-позицией (geolocator)
///   • BLE-сканированием (flutter_blue_plus) → iBeacon
///   • WiFi-сканированием (wifi_scan)
///   • NFC обрабатывается через NfcHandler (platform channel)
///   • Логом событий и EGTS-пакетов
class TrackerProvider extends ChangeNotifier {
  final AppPrefs prefs;

  late ServerConfig      _serverConfig;
  late List<NfcEntry>    _nfcWhitelist;
  late List<BeaconEntry> _beaconWhitelist;
  late List<WifiEntry>   _wifiWhitelist;

  TrackerProvider(this.prefs) {
    _serverConfig    = prefs.serverConfig;
    _nfcWhitelist    = prefs.nfcWhitelist;
    _beaconWhitelist = prefs.beaconWhitelist;
    _wifiWhitelist   = prefs.wifiWhitelist;
  }

  // ─── State ───────────────────────────────────────────────────────────────

  GpsData _gps = GpsData.empty();
  GpsData get gps => _gps;

  final List<NfcEvent>    _nfcEvents    = [];
  final List<BeaconEvent> _beaconEvents = [];
  final List<WifiEvent>   _wifiEvents   = [];
  LbsEvent? _lastLbs;
  ImuEvent? _lastImu;

  List<NfcEvent>    get nfcEvents    => List.unmodifiable(_nfcEvents);
  List<BeaconEvent> get beaconEvents => List.unmodifiable(_beaconEvents);
  List<WifiEvent>   get wifiEvents   => List.unmodifiable(_wifiEvents);
  LbsEvent?         get lastLbs      => _lastLbs;
  ImuEvent?         get lastImu      => _lastImu;

  final List<EgtsPacketInfo> _packets = [];
  List<EgtsPacketInfo> get packets => List.unmodifiable(_packets);

  bool _scanning = false;
  bool get scanning => _scanning;

  String _statusMsg = 'Ожидание';
  String get statusMsg => _statusMsg;

  // ─── Config (mutable from Settings) ───────────────────────────────────

  ServerConfig     get serverConfig    => _serverConfig;
  List<NfcEntry>   get nfcWhitelist    => _nfcWhitelist;
  List<BeaconEntry>get beaconWhitelist => _beaconWhitelist;
  List<WifiEntry>  get wifiWhitelist   => _wifiWhitelist;

  // ─── Internal ────────────────────────────────────────────────────────────

  int _packetCounter = 0;
  StreamSubscription<Position>? _gpsSub;
  StreamSubscription<List<ScanResult>>? _bleSub;
  Timer? _wifiTimer;
  LbsCollector? _lbsCollector;
  StreamSubscription<LbsEvent>? _lbsSub;

  static const _lbsChannel = MethodChannel('lbs');

  final List<LbsEvent> _lbsCells = [];
  List<LbsEvent> get lbsCells => List.unmodifiable(_lbsCells);

  final List<ImuEvent> _imuEvents = [];
  List<ImuEvent> get imuEvents => List.unmodifiable(_imuEvents);

  // ─── Start / Stop ────────────────────────────────────────────────────────

  Future<void> startScanning() async {
    if (_scanning) return;
    _scanning = true;
    _statusMsg = 'Сканирование...';
    notifyListeners();

    await _startGps();
    await _startBle();
    _startWifiPoll();
    _startLbsPoll();
    _startImuPoll();
  }

  void stopScanning() {
    _scanning = false;
    _statusMsg = 'Остановлено';
    _gpsSub?.cancel();
    _bleSub?.cancel();
    _wifiTimer?.cancel();
    _stopLbsPoll();
    _stopImuPoll();
    FlutterBluePlus.stopScan();
    notifyListeners();
  }

  // ─── GPS ─────────────────────────────────────────────────────────────────

  Future<void> _startGps() async {
    bool serviceEnabled = await Geolocator.isLocationServiceEnabled();
    if (!serviceEnabled) return;
    LocationPermission perm = await Geolocator.checkPermission();
    if (perm == LocationPermission.denied) {
      perm = await Geolocator.requestPermission();
      if (perm == LocationPermission.denied) return;
    }
    _gpsSub = Geolocator.getPositionStream(
      locationSettings: const LocationSettings(
        accuracy: LocationAccuracy.high, distanceFilter: 5,
      ),
    ).listen((pos) {
      _gps = GpsData(
        lat: pos.latitude, lon: pos.longitude, alt: pos.altitude,
        speedKmh: (pos.speed * 3.6), courseDeg: pos.heading.toInt(),
        accuracy: pos.accuracy.toDouble(), isValid: true,
        ts: pos.timestamp,
      );
      notifyListeners();
    });
  }

  // ─── BLE iBeacon ─────────────────────────────────────────────────────────

  Future<void> _startBle() async {
    try {
      await FlutterBluePlus.startScan(continuousUpdates: true);
      _bleSub = FlutterBluePlus.scanResults.listen((results) {
        for (final r in results) {
          final adv = r.advertisementData;
          // iBeacon: manufacturer data manufacturer ID = 0x004C (Apple)
          final mfr = adv.manufacturerData[0x004C];
          if (mfr != null && mfr.length >= 23 && mfr[0] == 0x02 && mfr[1] == 0x15) {
            final uuid = _parseIBeaconUuid(mfr);
            final major = (mfr[17] << 8) | mfr[18];
            final minor = (mfr[19] << 8) | mfr[20];
            final beacon = BeaconEvent(
              uuid: uuid, major: major, minor: minor,
              rssi: r.rssi, distance: _estimateDistance(mfr[21], r.rssi),
              mac: r.device.remoteId.str,
            );
            _onBeaconDetected(beacon);
          }
        }
      });
    } catch (e) {
      debugPrint('BLE error: $e');
    }
  }

  String _parseIBeaconUuid(List<int> mfr) {
    final b = mfr.sublist(2, 18).map((x) => x.toRadixString(16).padLeft(2, '0')).join();
    return '${b.substring(0, 8)}-${b.substring(8, 12)}-${b.substring(12, 16)}-${b.substring(16, 20)}-${b.substring(20)}'
        .toUpperCase();
  }

  double _estimateDistance(int txPower, int rssi) {
    if (rssi == 0) return -1;
    final ratio = rssi / txPower;
    return ratio < 1.0
        ? ratio.abs()
        : (0.89976 * (ratio.abs() * 7.7095) + 0.111);
  }

  // ─── WiFi ─────────────────────────────────────────────────────────────────

  void _startWifiPoll() {
    _scanWifi();
    _wifiTimer = Timer.periodic(const Duration(seconds: 15), (_) => _scanWifi());
  }

  // ─── LBS cell towers (discussion 18) ───────────────────────────────────────

  void _startLbsPoll() {
    _lbsCollector = LbsCollector();
    _lbsSub = _lbsCollector!.onLbsUpdate.listen((lbs) {
      _lbsCells.add(lbs);
      if (_lbsCells.length > 20) _lbsCells.removeAt(0); // keep recent
      final isNewCell = _lastLbs == null || _lastLbs!.cellId != lbs.cellId;
      _lastLbs = lbs;
      notifyListeners();

      // Auto-send LBS packet on cell change or first detection (for LBS survey / road matching mode)
      // LBS is used for precise road positioning using base stations + graph (discussion 18)
      if (isNewCell) {
        sendLbsPacket(lbs);
      }
    });
  }

  void _stopLbsPoll() {
    _lbsSub?.cancel();
    _lbsCollector = null;
  }

  // ─── IMU / Inertial (SRT 204) — discussion 12 + 09/13-16 ───────────────────
  ImuCollector? _imuCollector;
  StreamSubscription<ImuEvent>? _imuSub;

  void _startImuPoll() {
    _imuCollector = ImuCollector();
    _imuSub = _imuCollector!.onImuUpdate.listen((imu) {
      _imuEvents.add(imu);
      if (_imuEvents.length > 50) _imuEvents.removeAt(0); // keep recent samples
      _lastImu = imu;
      notifyListeners();

      // Optional: auto-send inertial packet on significant motion / vibration
      // (for now manual via survey or future motion trigger; keeps data volume reasonable)
      // if (imu.vibrationRms > 0.15) { sendImuPacket(imu); }
    });
  }

  void _stopImuPoll() {
    _imuSub?.cancel();
    _imuCollector = null;
  }

  void sendImuPacket(ImuEvent imu) {
    final pid = ++_packetCounter;
    final bytes = EgtsBuilder.buildImuPacket(
      imu: imu,
      gps: _gps,
      lbs: _lastLbs,
      terminalId: _serverConfig.terminalId,
      packetId: pid,
    );
    _sendPacketBytes(bytes, triggerType: 'imu', triggerId: 'imu_${imu.ts.millisecondsSinceEpoch}');
  }

  Future<void> refreshLbs() async {
    // Manual refresh fallback (the collector already streams periodically).
    try {
      final raw = await _lbsChannel.invokeMethod<List>('getCellInfo');
      if (raw != null && raw.isNotEmpty) {
        final m = Map<String, dynamic>.from(raw.first as Map);
        final evt = LbsEvent(
          mcc: (m['mcc'] as int?) ?? 0,
          mnc: (m['mnc'] as int?) ?? 0,
          lac: (m['lac'] as int?) ?? 0,
          cellId: (m['cid'] as int?) ?? 0,
          rssi: (m['rssi'] as int?) ?? 0,
          timingAdvance: (m['ta'] as int?),
          networkType: (m['type'] as String?) ?? (m['tech'] as String?),
        );
        _lastLbs = evt;
        _lbsCells.add(evt);
        if (_lbsCells.length > 20) _lbsCells.removeAt(0);
        notifyListeners();
      }
    } catch (_) {}
  }

  void sendLbsPacket(LbsEvent lbs) {
    final pid = ++_packetCounter;
    final bytes = EgtsBuilder.buildLbsPacket(
      lbs: lbs,
      gps: _gps,
      imu: _lastImu,
      terminalId: _serverConfig.terminalId,
      packetId: pid,
    );
    _sendPacketBytes(bytes, triggerType: 'lbs', triggerId: '${lbs.cellId}');
  }

  Future<void> _sendPacketBytes(Uint8List bytes, {required String triggerType, required String triggerId}) async {
    final hex = bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join('').toUpperCase();
    final decoded = EgtsBuilder.decode(bytes);

    var info = EgtsPacketInfo(
      bytes: bytes, hexStr: hex, decoded: decoded,
      triggerType: triggerType, triggerId: triggerId,
      ts: DateTime.now(),
    );
    _packets.insert(0, info);
    if (_packets.length > 100) _packets.removeLast();
    notifyListeners();

    final result = await EgtsClient(_serverConfig).send(bytes);
    final idx = _packets.indexWhere(
        (p) => p.ts == info.ts && p.triggerId == info.triggerId);
    if (idx >= 0) {
      _packets[idx] = _packets[idx].copyWith(
        sent: result.success,
        sendError: result.error,
      );
    }
    _statusMsg = result.success
        ? 'Отправлено: $triggerType $triggerId'
        : 'Ошибка: ${result.error}';
    notifyListeners();
  }

  Future<void> _scanWifi() async {
    try {
      final can = await WiFiScan.instance.canStartScan();
      if (can != CanStartScan.yes) return;
      await WiFiScan.instance.startScan();
      final aps = await WiFiScan.instance.getScannedResults();
      for (final ap in aps) {
        final evt = WifiEvent(
          ssid: ap.ssid, bssid: ap.bssid,
          rssi: ap.level, frequency: ap.frequency,
        );
        _onWifiDetected(evt);
      }
    } catch (e) {
      debugPrint('WiFi scan error: $e');
    }
  }

  // ─── Event handlers ───────────────────────────────────────────────────────

  /// Вызывается из NfcHandlerWidget при считывании метки
  void onNfcDetected(NfcEvent evt) {
    _nfcEvents.insert(0, evt);
    if (_nfcEvents.length > 50) _nfcEvents.removeLast();
    notifyListeners();

    final match = _nfcWhitelist
        .where((e) => e.uid.toUpperCase() == evt.uid.toUpperCase())
        .firstOrNull;
    if (match != null) {
      _buildAndSendEgts(triggerType: 'nfc', triggerId: evt.uid, nfc: evt);
    }
  }

  void _onBeaconDetected(BeaconEvent evt) {
    // Дедупликация по UUID+major+minor (обновляем, не дублируем)
    _beaconEvents.removeWhere(
        (e) => e.uuid == evt.uuid && e.major == evt.major && e.minor == evt.minor);
    _beaconEvents.insert(0, evt);
    if (_beaconEvents.length > 50) _beaconEvents.removeLast();
    notifyListeners();

    final match = _beaconWhitelist
        .where((e) => e.matches(evt.uuid, evt.major, evt.minor))
        .firstOrNull;
    if (match != null) {
      _buildAndSendEgts(triggerType: 'beacon', triggerId: '${evt.uuid}/${evt.major}/${evt.minor}', beacon: evt);
    }
  }

  void _onWifiDetected(WifiEvent evt) {
    _wifiEvents.removeWhere((e) => e.bssid == evt.bssid);
    _wifiEvents.insert(0, evt);
    if (_wifiEvents.length > 50) _wifiEvents.removeLast();
    notifyListeners();

    final match = _wifiWhitelist.where((e) => e.matches(evt.ssid, evt.bssid)).firstOrNull;
    if (match != null) {
      _buildAndSendEgts(triggerType: 'wifi', triggerId: evt.ssid, wifi: evt);
    }
  }

  // ─── EGTS build + send ────────────────────────────────────────────────────

  Future<void> _buildAndSendEgts({
    required String triggerType,
    required String triggerId,
    NfcEvent?    nfc,
    BeaconEvent? beacon,
    WifiEvent?   wifi,
  }) async {
    final pid = ++_packetCounter;
    late final Uint8List bytes;

    if (nfc != null) {
      bytes = EgtsBuilder.buildNfcPacket(
        nfc: nfc, gps: _gps, lbs: _lastLbs, imu: _lastImu,
        terminalId: _serverConfig.terminalId, packetId: pid,
      );
    } else if (beacon != null) {
      bytes = EgtsBuilder.buildBeaconPacket(
        beacon: beacon, gps: _gps, lbs: _lastLbs, imu: _lastImu,
        terminalId: _serverConfig.terminalId, packetId: pid,
      );
    } else if (wifi != null) {
      bytes = EgtsBuilder.buildWifiPacket(
        wifi: wifi, gps: _gps, lbs: _lastLbs, imu: _lastImu,
        terminalId: _serverConfig.terminalId, packetId: pid,
      );
    } else {
      return;
    }

    final hex = bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join('').toUpperCase();
    final decoded = EgtsBuilder.decode(bytes);

    var info = EgtsPacketInfo(
      bytes: bytes, hexStr: hex, decoded: decoded,
      triggerType: triggerType, triggerId: triggerId,
      ts: DateTime.now(),
    );
    _packets.insert(0, info);
    if (_packets.length > 100) _packets.removeLast();
    notifyListeners();

    // Отправка
    final result = await EgtsClient(_serverConfig).send(bytes);
    final idx = _packets.indexWhere(
        (p) => p.ts == info.ts && p.triggerId == info.triggerId);
    if (idx >= 0) {
      _packets[idx] = _packets[idx].copyWith(
        sent: result.success,
        sendError: result.error,
      );
    }
    _statusMsg = result.success
        ? 'Отправлено: $triggerType $triggerId'
        : 'Ошибка: ${result.error}';
    notifyListeners();
  }

  // ─── Survey (manual send from map) ───────────────────────────────────────

  /// Отправляет пакет с переопределённой координатой (с карты).
  Future<SendResult> sendSurveyPacket({
    required LatLng markerPos,
    NfcEvent?    nfc,
    BeaconEvent? beacon,
    WifiEvent?   wifi,
    LbsEvent?    lbs,
    ImuEvent?    imu,
  }) async {
    // GPS с координатой маркера (исследователь мог сместить)
    final gps = GpsData(
      lat: markerPos.latitude, lon: markerPos.longitude,
      alt: _gps.alt, speedKmh: 0, courseDeg: 0,
      satellites: _gps.satellites, hdop: _gps.hdop,
      accuracy: _gps.accuracy, isValid: true,
      ts: DateTime.now(),
    );

    final pid = ++_packetCounter;
    late final Uint8List bytes;
    late final String triggerType;
    late final String triggerId;

    if (nfc != null) {
      bytes = EgtsBuilder.buildNfcPacket(
          nfc: nfc, gps: gps, lbs: _lastLbs, imu: imu ?? _lastImu,
          terminalId: _serverConfig.terminalId, packetId: pid);
      triggerType = 'nfc'; triggerId = nfc.uid;
    } else if (beacon != null) {
      bytes = EgtsBuilder.buildBeaconPacket(
          beacon: beacon, gps: gps, lbs: _lastLbs, imu: imu ?? _lastImu,
          terminalId: _serverConfig.terminalId, packetId: pid);
      triggerType = 'beacon';
      triggerId = '${beacon.uuid}/${beacon.major}/${beacon.minor}';
    } else if (wifi != null) {
      bytes = EgtsBuilder.buildWifiPacket(
          wifi: wifi, gps: gps, lbs: _lastLbs, imu: imu ?? _lastImu,
          terminalId: _serverConfig.terminalId, packetId: pid);
      triggerType = 'wifi'; triggerId = wifi.ssid;
    } else if (lbs != null) {
      bytes = EgtsBuilder.buildLbsPacket(
          lbs: lbs, gps: gps, imu: imu ?? _lastImu,
          terminalId: _serverConfig.terminalId, packetId: pid);
      triggerType = 'lbs'; triggerId = '${lbs.cellId}';
    } else if (imu != null) {
      bytes = EgtsBuilder.buildImuPacket(
          imu: imu, gps: gps, lbs: _lastLbs,
          terminalId: _serverConfig.terminalId, packetId: pid);
      triggerType = 'imu'; triggerId = 'imu';
    } else {
      return const SendResult(success: false, error: 'Нет данных для отправки');
    }

    final hex = bytes.map((b) => b.toRadixString(16).padLeft(2,'0')).join().toUpperCase();
    final decoded = EgtsBuilder.decode(bytes);
    var info = EgtsPacketInfo(
      bytes: bytes, hexStr: hex, decoded: decoded,
      triggerType: triggerType, triggerId: triggerId,
      ts: DateTime.now(),
    );
    _packets.insert(0, info);
    if (_packets.length > 100) _packets.removeLast();
    notifyListeners();

    final result = await EgtsClient(_serverConfig).send(bytes);
    final idx = _packets.indexWhere(
        (p) => p.ts == info.ts && p.triggerId == info.triggerId);
    if (idx >= 0) {
      _packets[idx] = _packets[idx].copyWith(
          sent: result.success, sendError: result.error);
    }
    _statusMsg = result.success
        ? 'Отправлено [$triggerType] $triggerId'
        : 'Ошибка: ${result.error}';
    notifyListeners();
    return result;
  }

  // ─── Settings update ──────────────────────────────────────────────────────

  Future<void> updateServerConfig(ServerConfig cfg) async {
    _serverConfig = cfg;
    await prefs.saveServerConfig(cfg);
    notifyListeners();
  }

  Future<void> updateNfcWhitelist(List<NfcEntry> list) async {
    _nfcWhitelist = list;
    await prefs.saveNfcWhitelist(list);
    notifyListeners();
  }

  Future<void> updateBeaconWhitelist(List<BeaconEntry> list) async {
    _beaconWhitelist = list;
    await prefs.saveBeaconWhitelist(list);
    notifyListeners();
  }

  Future<void> updateWifiWhitelist(List<WifiEntry> list) async {
    _wifiWhitelist = list;
    await prefs.saveWifiWhitelist(list);
    notifyListeners();
  }

  @override
  void dispose() {
    stopScanning();
    super.dispose();
  }
}
