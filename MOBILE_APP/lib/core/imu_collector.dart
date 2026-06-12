// IMU / Inertial collector for SRT 204 (discussions 09, 12, 13-16)
// Collects raw accel/gyro (+mag) + basic orientation/vibration.
// Real data via Android SensorManager over MethodChannel('egts_imu').
// Fallback yields demo values (consistent with LbsCollector) so packet building and UI work everywhere.

import 'dart:async';
import 'package:flutter/services.dart';
import 'package:egts_tracker/models/models.dart';  // ImuEvent

/// IMU collector. Streams ImuEvent either from native sensors or demo fallback.
/// Can be used by TrackerProvider to send SRT 204 packets (inertial survey / fusion input).
class ImuCollector {
  static const MethodChannel _channel = MethodChannel('egts_imu');

  Stream<ImuEvent> get onImuUpdate async* {
    // Periodic poll (high rate possible; in practice 10-50 Hz from native).
    // Production: EventChannel from native sensor listeners is better for low latency.
    while (true) {
      await Future.delayed(const Duration(milliseconds: 100));  // ~10 Hz demo rate
      try {
        final raw = await _channel.invokeMethod<Map>('getImuSample');
        if (raw != null) {
          final m = Map<String, dynamic>.from(raw);
          yield ImuEvent(
            headingDeg: (m['heading'] as num?)?.toDouble() ?? 0.0,
            rollDeg: (m['roll'] as num?)?.toDouble() ?? 0.0,
            pitchDeg: (m['pitch'] as num?)?.toDouble() ?? 0.0,
            accelX: (m['ax'] as num?)?.toDouble() ?? 0.0,
            accelY: (m['ay'] as num?)?.toDouble() ?? 0.0,
            accelZ: (m['az'] as num?)?.toDouble() ?? 0.0,
            gyroX: (m['gx'] as num?)?.toDouble() ?? 0.0,
            gyroY: (m['gy'] as num?)?.toDouble() ?? 0.0,
            gyroZ: (m['gz'] as num?)?.toDouble() ?? 0.0,
            magX: (m['mx'] as num?)?.toDouble(),
            magY: (m['my'] as num?)?.toDouble(),
            magZ: (m['mz'] as num?)?.toDouble(),
            vibrationRms: (m['vib_rms'] as num?)?.toDouble() ?? 0.0,
            ts: DateTime.now(),
          );
        } else {
          yield _demoImu();
        }
      } catch (_) {
        yield _demoImu();
      }
    }
  }

  ImuEvent _demoImu() => ImuEvent(
        headingDeg: 12.3,
        rollDeg: 0.8,
        pitchDeg: -1.2,
        accelX: 0.01,
        accelY: 0.02,
        accelZ: 9.78,
        gyroX: 0.001,
        gyroY: 0.0005,
        gyroZ: -0.0008,
        vibrationRms: 0.04,
        ts: DateTime.now(),
      );

  static Future<void> handleNativeImu(Map<String, dynamic> data) async {
    // Hook for direct native pushes if using EventChannel or callbacks later.
  }
}
