"""
Main runnable demo for the entire sandbox.

Combines:
- Real GPS seeds from SERVICE/egts_20260607.json (discussion context)
- Synthetic high-rate IMU with vibration
- Madgwick (16) + EKF (14) via fusion_pipeline (13)
- Simple geometric map matching (08/15)
- Vibration pre-filter (10)
- SRT 204 payload construction (09)

Run:
    python demo.py
"""

import numpy as np
from generate_data import load_real_gps_seeds, generate_synthetic_track
from fusion_pipeline import SensorFusionPipeline
from map_matcher import simple_snap_to_road, DEMO_ROADS
from srt204 import SrCustom204


def run_demo(duration_s: float = 6.0):
    print("=" * 70)
    print("EGTS RTLS Sandbox — Full proposed pipeline demo")
    print("Based on discussions 08-17 (reloaded 2026-06-12)")
    print("=" * 70)

    seeds = load_real_gps_seeds()
    track = generate_synthetic_track(seeds, imu_hz=100, duration_s=duration_s)

    pipe = SensorFusionPipeline(imu_dt=1.0 / track["imu_hz"])

    srt204_list = []
    matched_results = []

    gps_ptr = 0
    n = len(track["t"])

    # Force early initialization with the first real GPS seed (critical for EKF)
    if seeds:
        first = seeds[0]
        pipe.process_gps(first["lat"], first["lon"])
        print(f"Initialized EKF with first seed: {first['lat']:.5f}, {first['lon']:.5f}")

    for i in range(n):
        res = pipe.process_imu(
            track["gyro"][i],
            track["accel"][i],
            track["mag"][i],
            prefilter="lpf"
        )

        # Feed subsequent GPS fixes
        if gps_ptr < len(track["gps_times"]) and abs(track["t"][i] - track["gps_times"][gps_ptr]) < 0.01:
            pipe.process_gps(track["gps_lat"][gps_ptr], track["gps_lon"][gps_ptr])
            gps_ptr += 1

        state = res["state"]
        srt = res["srt204"]

        # Apply cheap map matching on the EKF output (Level 3)
        snap = simple_snap_to_road((state["lat"] or track["true_lat"][i],
                                    state["lon"] or track["true_lon"][i]),
                                   DEMO_ROADS)

        # Build a proper SRT 204 object (as it would be sent in EGTS)
        srt204_obj = SrCustom204(
            heading_deg=srt["heading_deg"],
            roll_deg=srt.get("roll_deg", 0),
            pitch_deg=srt.get("pitch_deg", 0),
            accel_x=srt["accel_x"], accel_y=srt["accel_y"], accel_z=srt["accel_z"],
            vibration_rms=srt.get("vibration_rms", 0),
            ekf_confidence=srt["ekf_confidence"],
            matched_lat=snap["matched_lat"],
            matched_lon=snap["matched_lon"],
            snap_confidence=snap["confidence"],
            road_segment_id=snap["road_id"],
            filter_type=srt.get("filter_type", 3),
            timestamp=int(track["t"][i] * 10),   # fake relative ts
        )
        srt204_list.append(srt204_obj)

        if i % 80 == 0:
            print(f"t={track['t'][i]:5.2f}s  "
                  f"EKF lat/lon={state['lat']:.5f},{state['lon']:.5f}  "
                  f"head={state['heading']:.1f}°  conf={state.get('confidence',0):.2f}  "
                  f"snap→ {snap['road_name']} (d={snap['dist_m']}m)")

    print("\n--- Summary ---")
    print(f"Processed {len(srt204_list)} IMU steps")
    print(f"Produced {len([s for s in srt204_list if s.ekf_confidence > 0.6])} high-confidence SRT 204 records")

    # Show one example serialized SRT 204 (what would go into EGTS packet)
    example = srt204_list[len(srt204_list)//2]
    b = example.to_bytes()
    print(f"\nExample SRT 204 (binary len={len(b)}):")
    print("  ", example.to_dict())

    print("\nDemo finished. All ideas came from DOCS/discussions/ (08-17).")
    print("Next: integrate the clean classes into SERVICE/egts/filters/ + models.py")


if __name__ == "__main__":
    run_demo()
