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
from generate_data import load_real_gps_seeds, generate_synthetic_track, add_lbs_to_track
from fusion_pipeline import SensorFusionPipeline
from map_matcher import simple_snap_to_road, DEMO_ROADS
from srt204 import SrCustom204
from lbs_map_matcher import lbs_aware_snap_to_road, DEMO_ROADS as LBS_ROADS  # discussion 18
from srt205_lbs import SrCustom205
# For real packet building with LBS (discussion 18)
import sys
sys.path.insert(0, '..')
from SERVICE.egts.codec import EGTSPacket, Header, ServiceDataRecord, RecordData
from SERVICE.egts.models import SrCustom205 as RealSrCustom205  # the one in SERVICE


def run_demo(duration_s: float = 6.0):
    print("=" * 70)
    print("EGTS RTLS Sandbox — Full proposed pipeline demo")
    print("Based on discussions 08-17 (reloaded 2026-06-12)")
    print("=" * 70)

    seeds = load_real_gps_seeds()
    track = generate_synthetic_track(seeds, imu_hz=100, duration_s=duration_s)
    track = add_lbs_to_track(track, noise=1.2)   # discussion 18

    pipe = SensorFusionPipeline(imu_dt=1.0 / track["imu_hz"])

    srt204_list = []
    srt205_list = []   # LBS records
    matched_results = []

    gps_ptr = 0
    n = len(track["t"])

    # Force early initialization with the first real GPS seed (critical for EKF)
    if seeds:
        first = seeds[0]
        pipe.process_gps(first["lat"], first["lon"])
        print(f"Initialized EKF with first seed: {first['lat']:.5f}, {first['lon']:.5f}")

    for i in range(n):
        lbs = track["lbs"][i] if "lbs" in track else None

        res = pipe.process_imu(
            track["gyro"][i],
            track["accel"][i],
            track["mag"][i],
            prefilter="lpf",
            lbs_data=lbs
        )

        # Feed subsequent GPS fixes
        if gps_ptr < len(track["gps_times"]) and abs(track["t"][i] - track["gps_times"][gps_ptr]) < 0.01:
            pipe.process_gps(track["gps_lat"][gps_ptr], track["gps_lon"][gps_ptr])
            gps_ptr += 1

        state = res["state"]
        srt = res["srt204"]
        lbs_snap = res.get("lbs")  # from pipeline if used

        # Standard map matching on EKF output (for comparison)
        snap = simple_snap_to_road((state["lat"] or track["true_lat"][i],
                                    state["lon"] or track["true_lon"][i]),
                                   DEMO_ROADS)

        # Build SRT 204
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
            timestamp=int(track["t"][i] * 10),
        )
        srt204_list.append(srt204_obj)

        # Build SRT 205 (LBS data)
        if lbs:
            serving = lbs["serving"]
            srt205_obj = SrCustom205(
                serving_cell_id=serving["cell_id"],
                rssi_dbm=serving["rssi_dbm"],
                timing_advance=serving["ta"],
                bs_lat=serving["lat"],
                bs_lon=serving["lon"],
                raw_lbs_lat=lbs["raw_lbs_lat"],
                raw_lbs_lon=lbs["raw_lbs_lon"],
                lbs_quality=70,
                technology=3,
                timestamp=int(track["t"][i] * 10),
            )
            if lbs_snap:
                srt205_obj.raw_lbs_lat = lbs_snap.get("matched_lat", srt205_obj.raw_lbs_lat)
                srt205_obj.raw_lbs_lon = lbs_snap.get("matched_lon", srt205_obj.raw_lbs_lon)
            srt205_list.append(srt205_obj)

        if i % 80 == 0:
            print(f"t={track['t'][i]:5.2f}s  "
                  f"EKF lat/lon={state['lat']:.5f},{state['lon']:.5f}  "
                  f"head={state['heading']:.1f}°  conf={state.get('confidence',0):.2f}  "
                  f"snap→ {snap['road_name']} (d={snap['dist_m']}m)")
            if lbs_snap:
                print(f"          LBS snap → road {lbs_snap.get('road_id')} (conf={lbs_snap.get('confidence')})")

    print("\n--- Summary ---")
    print(f"Processed {len(srt204_list)} IMU steps")
    print(f"Produced {len([s for s in srt204_list if s.ekf_confidence > 0.6])} high-confidence SRT 204 records")
    print(f"Produced {len(srt205_list)} SRT 205 (LBS) records")

    # Show one example serialized SRT 204 (what would go into EGTS packet)
    example = srt204_list[len(srt204_list)//2]
    b = example.to_bytes()
    print(f"\nExample SRT 204 (binary len={len(b)}):")
    print("  ", example.to_dict())

    if srt205_list:
        ex205 = srt205_list[len(srt205_list)//2]
        b205 = ex205.to_bytes()
        print(f"\nExample SRT 205 LBS (binary len={len(b205)}):")
        print("  serving_cell:", ex205.serving_cell_id, "RSSI:", ex205.rssi_dbm, "TA:", ex205.timing_advance)

    # Demonstrate building a real EGTS packet with SRT 204 + SRT 205 using SERVICE codec (LBS + position)
    if srt204_list and srt205_list:
        print("\nBuilding sample EGTS packet with position (SRT204) + LBS (SRT205) using real SERVICE codec...")
        # Use first items for demo
        s204 = srt204_list[0]
        s205 = srt205_list[0]
        # Convert sandbox srt205 to real one for to_bytes (they are compatible)
        real_lbs = RealSrCustom205(
            serving_cell_id=s205.serving_cell_id,
            lac_tac=s205.lac_tac,
            mcc=s205.mcc,
            mnc=s205.mnc,
            rssi_dbm=s205.rssi_dbm,
            timing_advance=s205.timing_advance,
            bs_lat=s205.bs_lat,
            bs_lon=s205.bs_lon,
            raw_lbs_lat=s205.raw_lbs_lat,
            raw_lbs_lon=s205.raw_lbs_lon,
            neighbors=[type('obj', (object,), {'cell_id': getattr(n, 'cell_id', 0), 'rssi_dbm': getattr(n, 'rssi_dbm', 0)})() for n in getattr(s205, 'neighbors', [])],
            lbs_quality=s205.lbs_quality,
            technology=s205.technology,
            timestamp=s205.timestamp,
        )
        rd = RecordData(srt=204, srl=0, subrecord=s204)  # position (srl recomputed in to_bytes)
        rd_lbs = RecordData(srt=205, srl=0, subrecord=real_lbs)  # LBS
        sdr = ServiceDataRecord(record_data=[rd, rd_lbs])
        # Minimal header for demo packet
        hdr = Header(packet_id=1, packet_type=1, frame_data_length=0)  # lengths will be fixed in to_bytes
        pkt = EGTSPacket(header=hdr, body=[sdr])
        pkt_bytes = pkt.to_bytes()
        print(f"  Built packet len: {len(pkt_bytes)} bytes")
        print(f"  Hex start: {pkt_bytes.hex()[:60]}...")
        # Roundtrip parse with real codec
        parsed = EGTSPacket.from_bytes(pkt_bytes)
        print("  Parsed back OK, subrecords:", len(parsed.body[0].record_data) if parsed.body else 0)

    print("\nDemo finished. All ideas came from DOCS/discussions/ (08-18).")
    print("Next: integrate the clean classes into SERVICE/egts/filters/ + models.py (including SRT 205)")


if __name__ == "__main__":
    run_demo()
