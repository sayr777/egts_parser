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

    // IMU state (shared with MethodChannel and listeners)
    private val imuLast = HashMap<String, Any>().apply {
        put("ax", 0.0); put("ay", 0.0); put("az", 9.8)
        put("gx", 0.0); put("gy", 0.0); put("gz", 0.0)
        put("heading", 0.0); put("roll", 0.0); put("pitch", 0.0)
        put("vib_rms", 0.03)
    }
    private var yaw = 0.0
    private var lastGyroTs = 0L
    private lateinit var sensorManager: SensorManager
    private lateinit var accelListener: SensorEventListener
    private lateinit var gyroListener: SensorEventListener

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

        // IMU channel (uses imuLast populated by listeners)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "egts_imu")
            .setMethodCallHandler { call, result ->
                if (call.method == "getImuSample") {
                    try {
                        result.success(HashMap(imuLast))
                    } catch (e: Exception) {
                        result.error("IMU_ERROR", e.message, null)
                    }
                } else {
                    result.notImplemented()
                }
            }

        // Prepare sensor manager and listeners (registration happens in onResume)
        sensorManager = getSystemService(Context.SENSOR_SERVICE) as SensorManager

        accelListener = object : SensorEventListener {
            override fun onSensorChanged(event: SensorEvent) {
                if (event.sensor.type == Sensor.TYPE_ACCELEROMETER && event.values.size >= 3) {
                    imuLast["ax"] = event.values[0].toDouble()
                    imuLast["ay"] = event.values[1].toDouble()
                    imuLast["az"] = event.values[2].toDouble()
                    val mag = Math.sqrt((event.values[0]*event.values[0] + event.values[1]*event.values[1] + event.values[2]*event.values[2]).toDouble())
                    imuLast["vib_rms"] = (mag - 9.8).coerceAtLeast(0.0) * 0.1

                    val ax = event.values[0].toDouble()
                    val ay = event.values[1].toDouble()
                    val az = event.values[2].toDouble()
                    imuLast["roll"] = Math.toDegrees(Math.atan2(ay, Math.sqrt(ax*ax + az*az)))
                    imuLast["pitch"] = Math.toDegrees(Math.atan2(-ax, Math.sqrt(ay*ay + az*az)))
                }
            }
            override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) {}
        }

        gyroListener = object : SensorEventListener {
            override fun onSensorChanged(event: SensorEvent) {
                if (event.sensor.type == Sensor.TYPE_GYROSCOPE && event.values.size >= 3) {
                    val now = System.currentTimeMillis()
                    val gx = event.values[0].toDouble()
                    val gy = event.values[1].toDouble()
                    val gz = event.values[2].toDouble()
                    imuLast["gx"] = gx
                    imuLast["gy"] = gy
                    imuLast["gz"] = gz

                    if (lastGyroTs > 0) {
                        val dt = (now - lastGyroTs) / 1000.0
                        yaw = (yaw + Math.toDegrees(gz) * dt) % 360.0
                        if (yaw < 0) yaw += 360.0
                        imuLast["heading"] = yaw
                    }
                    lastGyroTs = now
                }
            }
            override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) {}
        }
    }

    override fun onResume() {
        super.onResume()
        // Register IMU sensors when activity is visible (saves battery when backgrounded)
        sensorManager.registerListener(accelListener, sensorManager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER), SensorManager.SENSOR_DELAY_NORMAL)
        sensorManager.registerListener(gyroListener, sensorManager.getDefaultSensor(Sensor.TYPE_GYROSCOPE), SensorManager.SENSOR_DELAY_NORMAL)
    }

    override fun onPause() {
        super.onPause()
        // Unregister to prevent leaks and unnecessary power use
        sensorManager.unregisterListener(accelListener)
        sensorManager.unregisterListener(gyroListener)
    }
}
