// LBS (cellular base stations) collector for real LBS data (discussion 18)
// Requires: android.permission.ACCESS_FINE_LOCATION, READ_PHONE_STATE (for API < 29)
// Use with geolocator + platform channel or telephony package for full CellInfo.

import 'dart:async';
import 'package:flutter/services.dart';

class LbsEntry {
  final int? cellId;
  final int? lacTac;
  final int? mcc;
  final int? mnc;
  final int? rssi;
  final int? timingAdvance;
  final String? networkType; // GSM/UMTS/LTE/5G
  final DateTime timestamp;

  LbsEntry({
    this.cellId,
    this.lacTac,
    this.mcc,
    this.mnc,
    this.rssi,
    this.timingAdvance,
    this.networkType,
    required this.timestamp,
  });

  Map<String, dynamic> toJson() => {
    'cell_id': cellId,
    'lac_tac': lacTac,
    'mcc': mcc,
    'mnc': mnc,
    'rssi_dbm': rssi,
    'ta': timingAdvance,
    'tech': networkType,
    'ts': timestamp.toIso8601String(),
  };
}

/// Example collector (stub - real implementation needs platform channel or telephony 0.5+)
/// On Android: use TelephonyManager.getAllCellInfo() via MethodChannel.
class LbsCollector {
  static const MethodChannel _channel = MethodChannel('egts_lbs');

  Stream<LbsEntry> get onLbsUpdate async* {
    // Placeholder: in real app, listen to native CellInfo updates
    // For demo, yield fake every 5s
    while (true) {
      await Future.delayed(const Duration(seconds: 5));
      yield LbsEntry(
        cellId: 1001,
        lacTac: 12345,
        mcc: 250,
        mnc: 1,
        rssi: -78,
        timingAdvance: 2,
        networkType: "LTE",
        timestamp: DateTime.now(),
      );
    }
  }

  /// Call from native (Kotlin/Java) to push real CellInfo.
  static Future<void> handleNativeLbs(Map<String, dynamic> data) async {
    // Forward to Dart side or store in provider
    print("Real LBS from native: $data");
  }
}

// Usage in tracker_provider.dart (example):
// final lbsCollector = LbsCollector();
// lbsCollector.onLbsUpdate.listen((lbs) => provider.addLbs(lbs)); // then build SRT205 and send.