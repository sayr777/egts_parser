"""
Full proposed sensor fusion pipeline (Madgwick → EKF) — heart of discussions 13, 14, 16.

This is the "Level 1 + Level 2" part of the 3-layer architecture.
Map Matching (Level 3) is applied afterwards (see map_matcher.py).

Intended usage after decoding an EGTS packet that contains SRT 16 (GPS) + future SRT 204 (IMU).
"""

import numpy as np
from madgwick import MadgwickFilter
from ekf import EGTS_EKF
from vibration import filter_imu, compute_vibration_metrics
from lbs_map_matcher import lbs_aware_snap_to_road, DEMO_ROADS   # discussion 18


def rotate_accel_to_geo(accel_body: np.ndarray, heading_rad: float) -> tuple[float, float]:
    """Rotate body-frame accel into North/East using current heading (from Madgwick)."""
    c, s = np.cos(heading_rad), np.sin(heading_rad)
    # Simple 2D rotation (Z is gravity)
    ax_n = accel_body[0] * c - accel_body[1] * s
    ay_e = accel_body[0] * s + accel_body[1] * c
    return float(ax_n), float(ay_e)


class SensorFusionPipeline:
    """
    Wires the exact architecture recommended across 13/14/16/10.

    High-rate IMU loop (100 Hz)  : Madgwick + EKF.predict
    Lower-rate GPS updates       : EKF.update_gps
    Heading corrections          : EKF.update_heading (from Madgwick)

    After each step you can read a "SRT 204-like" dict ready for encoding or storage.
    """

    def __init__(self, imu_dt: float = 0.01, gps_dt: float = 1.0):
        self.madgwick = MadgwickFilter(beta=0.033, sample_period=imu_dt)
        self.ekf = EGTS_EKF(dt=imu_dt)
        self.imu_dt = imu_dt
        self._last_gps = None
        self._initialized = False

    def process_imu(self, gyro: np.ndarray, accel: np.ndarray, mag: np.ndarray,
                    prefilter: str = "lpf", lbs_data: dict = None) -> dict:
        """
        Call this at IMU rate.
        lbs_data: optional dict from generate_synthetic_lbs (discussion 18)
        Returns current fused state + recommended SRT 204/205 fields.
        """
        # 1. Optional vibration pre-filter (discussion 10)
        if prefilter != "none":
            filt = filter_imu(accel, gyro, mag, method=prefilter, fs=1.0 / self.imu_dt)
            accel = filt["accel"][-3:] if hasattr(filt["accel"], "__len__") else accel
            gyro = filt["gyro"][-3:] if hasattr(filt["gyro"], "__len__") else gyro
            mag = filt["mag"][-3:] if hasattr(filt["mag"], "__len__") else mag
            vib_metrics = {k: filt[k] for k in ("vibration_rms", "vibration_peak", "dominant_freq_hz")}
        else:
            vib_metrics = compute_vibration_metrics(np.asarray(accel).reshape(1, -1) if np.ndim(accel) == 1 else accel)

        # 2. Madgwick (orientation)
        q = self.madgwick.update(np.asarray(gyro), np.asarray(accel), np.asarray(mag))
        heading_rad = self.madgwick.get_heading_rad()
        roll, pitch, yaw = self.madgwick.get_euler()

        # 3. Rotate accel into geographic frame for EKF
        ax_n, ay_e = rotate_accel_to_geo(np.asarray(accel), heading_rad)

        # 4. EKF predict (dead reckoning)
        if self._initialized:
            self.ekf.predict(ax_n, ay_e)
            self.ekf.update_heading(heading_rad)

        state = self.ekf.get_state() if self._initialized else {
            "lat": 0.0, "lon": 0.0, "speed_ms": 0.0,
            "heading": yaw, "confidence": 0.25, "cov_trace": 999.0
        }

        # 5. Build the "SRT 204" payload proposed in the discussions
        srt204 = {
            "heading_deg": round(yaw, 2),
            "roll_deg": round(roll, 2),
            "pitch_deg": round(pitch, 2),
            "accel_x": round(float(accel[0]), 3),
            "accel_y": round(float(accel[1]), 3),
            "accel_z": round(float(accel[2]), 3),
            "gyro_z": round(float(gyro[2]), 4),
            "ekf_confidence": round(state.get("confidence", 0.0), 3),
            "cov_trace": round(state.get("cov_trace", 0.0), 2),
            **vib_metrics,
            "filter_type": 3 if self._initialized else 2,   # 2=madgwick, 3=ekf hybrid
            "matched_lat": state.get("lat", 0.0),
            "matched_lon": state.get("lon", 0.0),
        }

        # 6. LBS-aware correction (discussion 18) - now properly passed
        lbs_result = None
        if lbs_data:
            try:
                lbs_result = lbs_aware_snap_to_road(lbs_data, DEMO_ROADS)
                # Always use LBS snap for road constraint if available (discussion 18 goal: точная точка на дороге)
                if lbs_result:
                    lbs_lat = lbs_result["matched_lat"]
                    lbs_lon = lbs_result["matched_lon"]
                    if self._initialized:
                        self.ekf.update_gps(lbs_lat, lbs_lon)
                        state = self.ekf.get_state()
                    else:
                        self.ekf.init(lbs_lat, lbs_lon, heading=yaw)
                        self._initialized = True
                        state = self.ekf.get_state()
                    srt204["matched_lat"] = state.get("lat", lbs_lat)
                    srt204["matched_lon"] = state.get("lon", lbs_lon)
                    srt204["lbs_confidence"] = lbs_result.get("confidence", 0)
                    srt204["lbs_road_id"] = lbs_result.get("road_id", 0)
            except Exception:
                pass

        return {"state": state, "srt204": srt204, "heading_rad": heading_rad, "lbs": lbs_result}

    def build_lbs_subrecord(self, lbs_data: dict) -> "SrCustom205":
        """Helper to create a real SrCustom205 from lbs_data dict (for use with SERVICE codec)."""
        import time
        from SERVICE.egts.models import SrCustom205, NeighborCell
        serving = lbs_data.get("serving", {})
        neighbors = [NeighborCell(n.get("cell_id", 0), n.get("rssi_dbm", 0)) for n in lbs_data.get("neighbors", [])]
        return SrCustom205(
            serving_cell_id=serving.get("cell_id", 0),
            rssi_dbm=serving.get("rssi_dbm", 0),
            timing_advance=serving.get("ta", 0),
            bs_lat=serving.get("lat", 0.0),
            bs_lon=serving.get("lon", 0.0),
            raw_lbs_lat=lbs_data.get("raw_lbs_lat", 0.0),
            raw_lbs_lon=lbs_data.get("raw_lbs_lon", 0.0),
            neighbors=neighbors,
            lbs_quality=70,
            technology=3,
            timestamp=int(time.time()),
        )

    def process_gps(self, lat: float, lon: float):
        """Call when you have a fresh GPS fix (1–10 Hz)."""
        if not self._initialized:
            self.ekf.init(lat, lon, heading=self.madgwick.get_heading())
            self._initialized = True
        else:
            self.ekf.update_gps(lat, lon)

        return self.ekf.get_state()


# ------------------------------------------------------------------
# Self-contained demo (uses synthetic IMU + occasional GPS seeds + LBS)
# ------------------------------------------------------------------
if __name__ == "__main__":
    pipe = SensorFusionPipeline(imu_dt=0.01)

    # Simulate 2 seconds @ 100 Hz + GPS every 0.5 s + LBS
    print("Running fusion pipeline demo (synthetic + LBS from discussion 18)...\n")
    for i in range(200):
        # Fake motion: gentle turn
        t = i * 0.01
        heading = 180 + 8 * np.sin(t * 0.8)
        gyro = np.array([0.0, 0.0, np.radians(8 * 0.8 * np.cos(t * 0.8))])
        accel = np.array([0.15 * np.cos(np.radians(heading - 180)),
                          0.15 * np.sin(np.radians(heading - 180)),
                          9.78])
        mag = np.array([18.0, 4.0, -42.0])

        # Simulate LBS data occasionally (discussion 18)
        lbs = None
        if i % 20 == 0:
            # Fake LBS near current position
            fake_lat = 55.718 + (i * 0.00001)
            fake_lon = 37.439 + (i * 0.000005)
            lbs = {
                "serving": {"cell_id": 1001, "lat": 55.7185, "lon": 37.4398, "ta": 2, "rssi_dbm": -75},
                "neighbors": [],
                "raw_lbs_lat": fake_lat + 0.0002,
                "raw_lbs_lon": fake_lon + 0.0001
            }

        res = pipe.process_imu(gyro, accel, mag, prefilter="lpf", lbs_data=lbs)

        if i % 50 == 0:
            # Simulate GPS update (slightly noisy)
            gps_lat = 55.718 + (i * 0.000008)
            gps_lon = 37.439 + (i * 0.000003)
            pipe.process_gps(gps_lat, gps_lon)
            print(f"t={t:5.2f}s  GPS updated  | heading={res['srt204']['heading_deg']:6.1f}°  "
                  f"conf={res['srt204']['ekf_confidence']:.2f}")
            if res.get("lbs"):
                print(f"         LBS snap applied: road conf={res['lbs'].get('confidence')}")

        if i % 40 == 0:
            s = res["srt204"]
            print(f"t={t:5.2f}s  SRT204 heading={s['heading_deg']:6.1f}°  "
                  f"vib_rms={s['vibration_rms']:.3f}  ekf_conf={s['ekf_confidence']:.2f}")
