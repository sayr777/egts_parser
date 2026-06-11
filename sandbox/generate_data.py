"""
Synthetic track + IMU generator (supports demos for 13/14/15/16/10).

Can seed from real decoded EGTS points (SERVICE/egts_20260607.json).
"""

import json
import numpy as np
from pathlib import Path
from typing import List, Dict


def load_real_gps_seeds(json_path: str = "../SERVICE/egts_20260607.json", max_points: int = 8) -> List[Dict]:
    """Extract a few SRT 16 positions from the real log."""
    p = Path(json_path)
    if not p.exists():
        # fallback to the one inside the repo layout
        p = Path(__file__).parent.parent / "SERVICE" / "egts_20260607.json"
    if not p.exists():
        return []

    data = json.loads(p.read_text(encoding="utf-8"))
    seeds = []
    for pkt in data.get("packets", []):
        for sdr in pkt.get("SFRD", []):
            for rd in sdr.get("RD", []):
                if rd.get("SRT") == 16:
                    s = rd["SRD"]
                    seeds.append({
                        "ts": s.get("NTM"),
                        "lat": s["LAT"],
                        "lon": s["LONG"],
                        "speed_kmh": s.get("SPD_kmh", 0),
                        "dir": s.get("DIR_deg", 0),
                    })
                    if len(seeds) >= max_points:
                        return seeds
    return seeds


def generate_synthetic_track(seed_points: List[Dict], imu_hz: int = 100, duration_s: float = 8.0) -> Dict:
    """
    Creates a smooth trajectory + realistic IMU (with vibration) + occasional GPS.
    Returns dict with arrays ready for fusion_pipeline.
    """
    n_imu = int(duration_s * imu_hz)
    t = np.linspace(0, duration_s, n_imu)

    # Interpolate a simple path from seeds (or make a gentle curve if no seeds)
    if len(seed_points) >= 2:
        lats = np.interp(t, np.linspace(0, duration_s, len(seed_points)),
                         [p["lat"] for p in seed_points[:len(t)]])
        lons = np.interp(t, np.linspace(0, duration_s, len(seed_points)),
                         [p["lon"] for p in seed_points[:len(t)]])
    else:
        base_lat, base_lon = 55.71813, 37.43960
        lats = base_lat + np.cumsum(np.sin(t * 0.6) * 0.000012)
        lons = base_lon + np.cumsum(np.cos(t * 0.3) * 0.000015)

    # Heading from delta
    dlat = np.diff(lats, prepend=lats[0])
    dlon = np.diff(lons, prepend=lons[0])
    headings = (np.degrees(np.arctan2(dlon, dlat)) + 360) % 360

    # Synthetic IMU (body frame) + vibration
    np.random.seed(123)
    vib = 0.6 * np.sin(2 * np.pi * 11 * t) + 0.15 * np.random.randn(n_imu)   # ~11 Hz suspension
    accel_x = 0.12 * np.sin(t * 0.9) + vib * 0.4
    accel_y = 0.08 * np.cos(t * 1.1) + vib * 0.25
    accel_z = 9.79 + vib * 0.15
    gyro_z = np.radians(np.diff(headings, prepend=headings[0]) * imu_hz * 0.6)

    accel = np.stack([accel_x, accel_y, accel_z], axis=1)
    gyro = np.stack([np.zeros(n_imu), np.zeros(n_imu), gyro_z], axis=1)
    mag = np.tile([20.0, 3.5, -41.0], (n_imu, 1)) + np.random.randn(n_imu, 3) * 0.8

    # Sparse GPS observations (every ~1s)
    gps_idx = np.arange(0, n_imu, imu_hz)
    gps_lats = lats[gps_idx] + np.random.randn(len(gps_idx)) * 0.000008
    gps_lons = lons[gps_idx] + np.random.randn(len(gps_idx)) * 0.000006

    return {
        "t": t,
        "true_lat": lats,
        "true_lon": lons,
        "true_heading": headings,
        "accel": accel,
        "gyro": gyro,
        "mag": mag,
        "gps_times": t[gps_idx],
        "gps_lat": gps_lats,
        "gps_lon": gps_lons,
        "imu_hz": imu_hz,
    }


if __name__ == "__main__":
    seeds = load_real_gps_seeds()
    print(f"Loaded {len(seeds)} real GPS seeds from project log")
    track = generate_synthetic_track(seeds or [], duration_s=5.0)
    print("Synthetic track generated:")
    print("  points:", len(track["t"]))
    print("  GPS fixes:", len(track["gps_lat"]))
    print("  sample true heading range:", track["true_heading"].min(), "→", track["true_heading"].max())
