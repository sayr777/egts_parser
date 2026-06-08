import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:egts_tracker/models/models.dart';

/// Хранилище настроек приложения (SharedPreferences).
class AppPrefs {
  static const _kServer      = 'server_config';
  static const _kNfcList     = 'nfc_whitelist';
  static const _kBeaconList  = 'beacon_whitelist';
  static const _kWifiList    = 'wifi_whitelist';

  final SharedPreferences _prefs;
  AppPrefs._(this._prefs);

  static Future<AppPrefs> load() async {
    final p = await SharedPreferences.getInstance();
    return AppPrefs._(p);
  }

  // ─── Server config ──────────────────────────────────────────────────────

  ServerConfig get serverConfig {
    final s = _prefs.getString(_kServer);
    if (s == null) return const ServerConfig();
    try {
      return ServerConfig.fromJson(jsonDecode(s) as Map<String, dynamic>);
    } catch (_) {
      return const ServerConfig();
    }
  }

  Future<void> saveServerConfig(ServerConfig c) =>
      _prefs.setString(_kServer, jsonEncode(c.toJson()));

  // ─── NFC whitelist ──────────────────────────────────────────────────────

  List<NfcEntry> get nfcWhitelist => _loadList(_kNfcList, NfcEntry.fromJson);
  Future<void> saveNfcWhitelist(List<NfcEntry> list) =>
      _saveList(_kNfcList, list.map((e) => e.toJson()).toList());

  // ─── Beacon whitelist ───────────────────────────────────────────────────

  List<BeaconEntry> get beaconWhitelist => _loadList(_kBeaconList, BeaconEntry.fromJson);
  Future<void> saveBeaconWhitelist(List<BeaconEntry> list) =>
      _saveList(_kBeaconList, list.map((e) => e.toJson()).toList());

  // ─── WiFi whitelist ─────────────────────────────────────────────────────

  List<WifiEntry> get wifiWhitelist => _loadList(_kWifiList, WifiEntry.fromJson);
  Future<void> saveWifiWhitelist(List<WifiEntry> list) =>
      _saveList(_kWifiList, list.map((e) => e.toJson()).toList());

  // ─── Helpers ────────────────────────────────────────────────────────────

  List<T> _loadList<T>(String key, T Function(Map<String, dynamic>) fromJson) {
    try {
      final s = _prefs.getString(key);
      if (s == null) return [];
      return (jsonDecode(s) as List)
          .map((e) => fromJson(e as Map<String, dynamic>))
          .toList();
    } catch (_) {
      return [];
    }
  }

  Future<void> _saveList(String key, List<Map<String, dynamic>> list) =>
      _prefs.setString(key, jsonEncode(list));
}
