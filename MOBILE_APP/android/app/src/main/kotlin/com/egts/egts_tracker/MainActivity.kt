package com.egts.egts_tracker

import android.annotation.SuppressLint
import android.content.Context
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
                                    val mcc = if (Build.VERSION.SDK_INT >= 28)
                                        id.mccString?.toIntOrNull() ?: 0
                                    else @Suppress("DEPRECATION") id.mcc
                                    val mnc = if (Build.VERSION.SDK_INT >= 28)
                                        id.mncString?.toIntOrNull() ?: 0
                                    else @Suppress("DEPRECATION") id.mnc
                                    mapOf(
                                        "type" to "LTE",
                                        "mcc"  to mcc,
                                        "mnc"  to mnc,
                                        "lac"  to id.tac,
                                        "cid"  to id.ci,
                                        "rssi" to info.cellSignalStrength.dbm,
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
    }
}
