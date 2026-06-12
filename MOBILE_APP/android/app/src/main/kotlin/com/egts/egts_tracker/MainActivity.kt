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

        // IMU channel for SRT 204 (accel + gyro + basic orientation stub)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "egts_imu")
            .setMethodCallHandler { call, result ->
                if (call.method == "getImuSample") {
                    try {
                        val sm = getSystemService(Context.SENSOR_SERVICE) as SensorManager
                        // We return the *last known* values via a simple listener snapshot.
                        // Real apps should register listeners and push via EventChannel.
                        val last = HashMap<String, Any>()
                        // Lightweight: just return zeros + note that full listener registration belongs in production.
                        // For demo the Dart side falls back to synthetic data.
                        last["ax"] = 0.0
                        last["ay"] = 0.0
                        last["az"] = 9.8
                        last["gx"] = 0.0
                        last["gy"] = 0.0
                        last["gz"] = 0.0
                        last["heading"] = 0.0
                        last["roll"] = 0.0
                        last["pitch"] = 0.0
                        last["vib_rms"] = 0.03
                        result.success(last)
                    } catch (e: Exception) {
                        result.error("IMU_ERROR", e.message, null)
                    }
                } else {
                    result.notImplemented()
                }
            }
    }
}
