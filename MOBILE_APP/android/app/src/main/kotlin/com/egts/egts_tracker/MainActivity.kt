package com.egts.egts_tracker

import android.annotation.SuppressLint
import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.os.Build
import android.telephony.*
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {

    @SuppressLint("MissingPermission")
    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "lbs")
            .setMethodCallHandler { call, result ->
                if (call.method == "getCellInfo") {
                    try {
                        val tm = getSystemService(Context.TELEPHONY_SERVICE) as TelephonyManager
                        val cells = tm.allCellInfo
                        val list = cells?.mapNotNull { info ->
                            when (info) {
                                is CellInfoLte -> {
                                    val id = info.cellIdentity
                                    val ss = info.cellSignalStrength
                                    val mcc = if (Build.VERSION.SDK_INT >= 28)
                                        id.mccString?.toIntOrNull() ?: 0
                                    else @Suppress("DEPRECATION") id.mcc
                                    val mnc = if (Build.VERSION.SDK_INT >= 28)
                                        id.mncString?.toIntOrNull() ?: 0
                                    else @Suppress("DEPRECATION") id.mnc
                                    val ta = if (ss.timingAdvance != CellInfo.UNAVAILABLE) ss.timingAdvance else -1
                                    mapOf(
                                        "type" to "LTE",
                                        "mcc"  to mcc,
                                        "mnc"  to mnc,
                                        "lac"  to id.tac,
                                        "cid"  to id.ci,
                                        "rssi" to ss.dbm,
                                        "ta"   to ta,
                                    )
                                }
                                is CellInfoGsm -> {
                                    val id = info.cellIdentity
                                    val mcc = if (Build.VERSION.SDK_INT >= 28)
                                        id.mccString?.toIntOrNull() ?: 0
                                    else @Suppress("DEPRECATION") id.mcc
                                    val mnc = if (Build.VERSION.SDK_INT >= 28)
                                        id.mncString?.toIntOrNull() ?: 0
                                    else @Suppress("DEPRECATION") id.mnc
                                    mapOf(
                                        "type" to "GSM",
                                        "mcc"  to mcc,
                                        "mnc"  to mnc,
                                        "lac"  to id.lac,
                                        "cid"  to id.cid,
                                        "rssi" to info.cellSignalStrength.dbm,
                                    )
                                }
                                is CellInfoWcdma -> {
                                    val id = info.cellIdentity
                                    val mcc = if (Build.VERSION.SDK_INT >= 28)
                                        id.mccString?.toIntOrNull() ?: 0
                                    else @Suppress("DEPRECATION") id.mcc
                                    val mnc = if (Build.VERSION.SDK_INT >= 28)
                                        id.mncString?.toIntOrNull() ?: 0
                                    else @Suppress("DEPRECATION") id.mnc
                                    mapOf(
                                        "type" to "WCDMA",
                                        "mcc"  to mcc,
                                        "mnc"  to mnc,
                                        "lac"  to id.lac,
                                        "cid"  to id.cid,
                                        "rssi" to info.cellSignalStrength.dbm,
                                    )
                                }
                                // CellInfoNr (5G) пропускаем — требует API 29+ с точными аннотациями
                                else -> null
                            }
                        } ?: emptyList<Map<String, Any>>()
                        result.success(list)
                    } catch (e: Exception) {
                        result.error("LBS_ERROR", e.message, null)
                    }
                } else {
                    result.notImplemented()
                }
            }

        // IMU channel for SRT 204 (accel + gyro + basic orientation)
        val imuLast = HashMap<String, Any>()
        imuLast["ax"] = 0.0
        imuLast["ay"] = 0.0
        imuLast["az"] = 9.8
        imuLast["gx"] = 0.0
        imuLast["gy"] = 0.0
        imuLast["gz"] = 0.0
        imuLast["heading"] = 0.0
        imuLast["roll"] = 0.0
        imuLast["pitch"] = 0.0
        imuLast["vib_rms"] = 0.03

        val sensorManager = getSystemService(Context.SENSOR_SERVICE) as SensorManager
        val accelListener = object : SensorEventListener {
            override fun onSensorChanged(event: SensorEvent) {
                if (event.sensor.type == Sensor.TYPE_ACCELEROMETER && event.values.size >= 3) {
                    imuLast["ax"] = event.values[0].toDouble()
                    imuLast["ay"] = event.values[1].toDouble()
                    imuLast["az"] = event.values[2].toDouble()
                    // crude vibration estimate
                    val mag = Math.sqrt((event.values[0]*event.values[0] + event.values[1]*event.values[1] + event.values[2]*event.values[2]).toDouble())
                    imuLast["vib_rms"] = (mag - 9.8).coerceAtLeast(0.0) * 0.1
                }
            }
            override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) {}
        }
        val gyroListener = object : SensorEventListener {
            override fun onSensorChanged(event: SensorEvent) {
                if (event.sensor.type == Sensor.TYPE_GYROSCOPE && event.values.size >= 3) {
                    imuLast["gx"] = event.values[0].toDouble()
                    imuLast["gy"] = event.values[1].toDouble()
                    imuLast["gz"] = event.values[2].toDouble()
                }
            }
            override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) {}
        }

        // Register (low power, suitable for background-ish use in tracker)
        sensorManager.registerListener(accelListener, sensorManager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER), SensorManager.SENSOR_DELAY_NORMAL)
        sensorManager.registerListener(gyroListener, sensorManager.getDefaultSensor(Sensor.TYPE_GYROSCOPE), SensorManager.SENSOR_DELAY_NORMAL)

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "egts_imu")
            .setMethodCallHandler { call, result ->
                if (call.method == "getImuSample") {
                    try {
                        // Return a snapshot of the latest sensor readings
                        result.success(HashMap(imuLast))
                    } catch (e: Exception) {
                        result.error("IMU_ERROR", e.message, null)
                    }
                } else {
                    result.notImplemented()
                }
            }
    }
}
