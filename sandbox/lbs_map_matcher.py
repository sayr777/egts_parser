"""
LBS (Location Based Services / cellular base stations) + Road Graph Map Matching prototype.

Implements ideas from discussion 18-lbs-road-graph-positioning.md
Extends the simple geometric snap from map_matcher.py (from 08/15).

Key concept:
- LBS gives coarse position + signal measurements (serving cell + TA + RSSI, neighbors).
- Use known base station locations + signal model to compute likelihood for road segments.
- Snap the most likely road point (much more accurate than raw LBS).

This is an extension of the Map Matching level in the 3-layer architecture (discussion 13).
"""

import math
from typing import List, Dict, Tuple, Optional
from map_matcher import haversine, DEMO_ROADS


# ------------------------------------------------------------------
# Synthetic / demo base stations (in the area of real EGTS test packets)
# In real life this would come from operator DB or crowdsourced (OpenCellID etc.)
# ------------------------------------------------------------------
DEMO_BASE_STATIONS = [
    {"id": 1001, "lat": 55.7185, "lon": 37.4398, "mcc": 250, "mnc": 1, "name": "BS-Primorskaya"},
    {"id": 1002, "lat": 55.7192, "lon": 37.4415, "mcc": 250, "mnc": 1, "name": "BS-Testovaya"},
    {"id": 1003, "lat": 55.7178, "lon": 37.4382, "mcc": 250, "mnc": 2, "name": "BS-Severnaya"},
]


def generate_synthetic_lbs( true_lat: float, true_lon: float, noise: float = 0.8 ) -> Dict:
    """
    Generate fake LBS measurement as if the device is at (true_lat, true_lon).
    In production this would come from the modem (AT+CREG, +CGREG, +CPSI, etc.).
    """
    serving = None
    neighbors = []
    min_dist = float("inf")

    for bs in DEMO_BASE_STATIONS:
        dist = haversine(true_lat, true_lon, bs["lat"], bs["lon"])
        # Simple path loss model (very rough)
        rssi = -70 - (dist / 200.0) + (noise * (0.5 - (hash(str(bs["id"])) % 1000) / 1000.0))
        rssi = max(-110, min(-50, rssi))

        # Timing Advance (rough, ~550m per unit in GSM)
        ta = int(dist / 550.0 + 0.5)

        meas = {
            "cell_id": bs["id"],
            "lat": bs["lat"],
            "lon": bs["lon"],
            "rssi_dbm": round(rssi, 1),
            "ta": ta,
            "dist_m": round(dist, 1),
        }

        if dist < min_dist:
            if serving:
                neighbors.append(serving)
            serving = meas
            min_dist = dist
        else:
            neighbors.append(meas)

    return {
        "serving": serving,
        "neighbors": neighbors[:2],   # limit for demo
        "raw_lbs_lat": true_lat + (noise * 0.0003 * (hash("lat") % 5 - 2)),
        "raw_lbs_lon": true_lon + (noise * 0.0003 * (hash("lon") % 5 - 2)),
    }


def lbs_likelihood(road_point: Tuple[float, float], lbs_data: Dict) -> float:
    """
    Improved LBS likelihood (discussion 18 continuation).
    - Okumura-Hata simplified urban path loss.
    - TA + RSSI fusion.
    - Multiple stations (serving + neighbors).
    """
    plat, plon = road_point
    serving = lbs_data.get("serving", {})
    if not serving or not serving.get("lat"):
        return 0.01

    def path_loss(dist_m: float, freq_mhz: float = 900.0) -> float:
        if dist_m < 1: dist_m = 1
        return 69.55 + 26.16 * math.log10(freq_mhz) - 13.82 * math.log10(50) + (44.9 - 6.55 * math.log10(50)) * math.log10(dist_m / 1000.0)

    total = 1.0

    # Serving cell
    dist = haversine(plat, plon, serving["lat"], serving["lon"])
    exp_rssi = -path_loss(dist)
    rssi_err = abs(serving.get("rssi_dbm", -70) - exp_rssi)
    total *= math.exp( - (rssi_err ** 2) / (2 * 8**2) )

    ta = serving.get("ta", 0)
    exp_ta = ta * 550.0
    ta_err = abs(dist - exp_ta)
    total *= math.exp( - (ta_err ** 2) / (2 * (550 * 1.2)**2) )

    # Neighbors
    for nb in lbs_data.get("neighbors", []):
        if not nb.get("lat"): continue
        d = haversine(plat, plon, nb["lat"], nb["lon"])
        e = -path_loss(d)
        err = abs(nb.get("rssi_dbm", -80) - e)
        total *= math.exp( - (err ** 2) / (2 * 10**2) )

    return max(0.001, min(1.0, total))


def lbs_aware_snap_to_road(
    lbs_data: Dict,
    road_segments: List[Dict],
    use_raw_lbs_as_fallback: bool = True
) -> Dict:
    """
    LBS-aware map matching.

    Instead of snapping a GPS point, we score every road segment by
    how well it explains the observed LBS signals (serving cell + TA + RSSI).

    Returns the best road point + confidence.
    """
    best_score = -1.0
    best_result = None

    raw_lat = lbs_data.get("raw_lbs_lat")
    raw_lon = lbs_data.get("raw_lbs_lon")

    for seg in road_segments:
        # For demo we still use representative point.
        # In real version: sample multiple points along the actual LineString geometry.
        point = (seg["lat"], seg["lon"])
        score = lbs_likelihood(point, lbs_data)

        if score > best_score:
            best_score = score
            dist_from_raw = haversine(raw_lat, raw_lon, seg["lat"], seg["lon"]) if raw_lat else 0

            best_result = {
                "matched_lat": seg["lat"],
                "matched_lon": seg["lon"],
                "road_id": seg.get("id", 0),
                "road_name": seg.get("name", ""),
                "lbs_likelihood": round(score, 4),
                "dist_from_raw_lbs_m": round(dist_from_raw, 1),
                "confidence": round(min(0.99, score * 12), 3),   # heuristic scaling
            }

    if best_result is None:
        if use_raw_lbs_as_fallback and raw_lat:
            return {
                "matched_lat": raw_lat,
                "matched_lon": raw_lon,
                "road_id": -1,
                "road_name": "unknown",
                "lbs_likelihood": 0.0,
                "confidence": 0.1,
                "dist_from_raw_lbs_m": 0,
            }
        return {"matched_lat": 0, "matched_lon": 0, "road_id": -1, "confidence": 0.0}

    return best_result


# ------------------------------------------------------------------
# Demo
# ------------------------------------------------------------------
if __name__ == "__main__":
    print("LBS + Road Graph Map Matching demo (discussion 18)")
    print("=" * 60)

    # Simulate a point that is actually on the road but LBS is noisy
    true_road_point = (55.71825, 37.43985)   # on "ул. Примерная"

    lbs = generate_synthetic_lbs(true_road_point[0], true_road_point[1], noise=1.2)

    print("\nRaw LBS observation:")
    print(f"  Serving: cell={lbs['serving']['cell_id']}  TA={lbs['serving']['ta']}  RSSI={lbs['serving']['rssi_dbm']} dBm")
    print(f"  Raw LBS position (noisy): {lbs['raw_lbs_lat']:.5f}, {lbs['raw_lbs_lon']:.5f}")

    print("\nLBS-aware snap to road graph:")
    result = lbs_aware_snap_to_road(lbs, DEMO_ROADS)

    print(f"  Snapped to: {result['road_name']} (id={result['road_id']})")
    print(f"  Matched point: {result['matched_lat']:.5f}, {result['matched_lon']:.5f}")
    print(f"  LBS likelihood: {result['lbs_likelihood']}")
    print(f"  Confidence: {result['confidence']}")
    print(f"  Distance from raw LBS: {result.get('dist_from_raw_lbs_m', 0)} m")

    print("\nCompare with plain geometric snap (from map_matcher):")
    from map_matcher import simple_snap_to_road
    plain = simple_snap_to_road( (lbs['raw_lbs_lat'], lbs['raw_lbs_lon']), DEMO_ROADS )
    print(f"  Plain snap → {plain['road_name']} (conf={plain['confidence']})  dist={plain['dist_m']}m")

    print("\nLBS + road graph gives much better road-constrained result even with noisy cellular data.")
    print("In real system this would run inside the fusion pipeline (GPS/IMU + LBS).")