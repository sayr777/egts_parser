// LBS (cellular base stations) collector for real LBS data (discussion 18)
// Requires: android.permission.ACCESS_FINE_LOCATION + READ_PHONE_STATE (API<29)
// Real data via Android TelephonyManager.getAllCellInfo() over MethodChannel('lbs').
// Fallback yields demo values so UI and packet building work without native.

import 'dart:async';
import 'package:flutter/services.dart';
import 'package:egts_tracker/models/models.dart';  // LbsEvent is the single source of truth

/// LBS collector. Streams LbsEvent (from models) either from native or demo fallback.
/// Auto-used by TrackerProvider for road-graph LBS packets (SRT 205) on cell change.
class LbsCollector {
  static const MethodChannel _channel = MethodChannel('lbs');

  Stream<LbsEvent> get onLbsUpdate async* {
    // Periodic poll + channel for real Android CellInfo (LTE/GSM/WCDMA).
    // Production: can switch to EventChannel for push-based updates from native.
    while (true) {
      await Future.delayed(const Duration(seconds: 5));
      try {
        final raw = await _channel.invokeMethod<List>('getCellInfo');
        if (raw != null && raw.isNotEmpty) {
          final m = Map<String, dynamic>.from(raw.first as Map);
          yield LbsEvent(
            mcc: (m['mcc'] as int?) ?? 0,
            mnc: (m['mnc'] as int?) ?? 0,
            lac: (m['lac'] as int?) ?? 0,
            cellId: (m['cid'] as int?) ?? 0,
            rssi: (m['rssi'] as int?) ?? 0,
            timingAdvance: (m['ta'] as int?),
            networkType: (m['type'] as String?) ?? (m['tech'] as String?),
            ts: DateTime.now(),
          );
        } else {
          yield _demoLbs();
        }
      } catch (_) {
        // Fallback keeps the feature usable in simulator / without perms / iOS etc.
        yield _demoLbs();
      }
    }
  }

  LbsEvent _demoLbs() => LbsEvent(
        mcc: 250,
        mnc: 1,
        lac: 12345,
        cellId: 1001,
        rssi: -78,
        timingAdvance: 2,
        networkType: 'LTE',
        ts: DateTime.now(),
      );

  /// Optional: native can call this to push (if using direct MethodChannel calls from Kotlin).
  static Future<void> handleNativeLbs(Map<String, dynamic> data) async {
    // In real advanced setup forward via a stream controller or provider hook.
    // Current design: Dart polls the channel; native just responds to 'getCellInfo'.
  }
}