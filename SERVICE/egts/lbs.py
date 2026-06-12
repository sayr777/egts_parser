"""
LBS (base stations) support for EGTS (discussion 18).
LBS-aware snap using TA + RSSI + simplified Okumura-Hata path loss + multi-station.
For production replace the toy roads with PostGIS graph query (see sandbox/postgis_lbs.sql).
"""

from typing import Dict, Any, Optional, List
import math

# Toy road segments (demo). In real: query road graph (PostGIS + pgr or GeoPandas).
_DEMO_ROADS = [
    {"id": 101, "name": "ул. Примерная", "lat": 55.71813, "lon": 37.43960},
    {"id": 102, "name": "ул. Примерная", "lat": 55.71825, "lon": 37.43985},
]

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2)
    return 2 * R * math.asin(math.sqrt(a))

def _path_loss(dist_m: float, freq_mhz: float = 900.0) -> float:
    """Simplified Okumura-Hata urban model (dB)."""
    if dist_m < 1:
        dist_m = 1.0
    d_km = dist_m / 1000.0
    return 69.55 + 26.16 * math.log10(freq_mhz) - 13.82 * math.log10(50) + (44.9 - 6.55 * math.log10(50)) * math.log10(d_km)

def lbs_likelihood(road_point: tuple, lbs_info: Dict[str, Any]) -> float:
    """Emission score for a road point given LBS observation (serving + neighbors)."""
    plat, plon = road_point
    serving = lbs_info.get("serving") or lbs_info.get("raw") or {}
    if not serving or not serving.get("lat"):
        # fallback to raw LBS distance only
        raw_lat = lbs_info.get("raw_lbs_lat") or 0
        raw_lon = lbs_info.get("raw_lbs_lon") or 0
        return max(0.001, 1.0 / (1 + haversine(plat, plon, raw_lat, raw_lon)))

    total = 1.0

    # Serving
    dist = haversine(plat, plon, serving["lat"], serving["lon"])
    exp_rssi = -_path_loss(dist)
    rssi_err = abs((serving.get("rssi_dbm") or serving.get("rssi") or -70) - exp_rssi)
    total *= math.exp( - (rssi_err ** 2) / (2 * 8**2) )

    ta = serving.get("ta") or 0
    exp_ta = ta * 550.0
    ta_err = abs(dist - exp_ta)
    total *= math.exp( - (ta_err ** 2) / (2 * (550 * 1.2)**2) )

    # Neighbors (multi-station)
    for nb in (lbs_info.get("neighbors") or []):
        if not nb.get("lat"):
            continue
        d = haversine(plat, plon, nb["lat"], nb["lon"])
        e = -_path_loss(d)
        err = abs((nb.get("rssi_dbm") or nb.get("rssi") or -80) - e)
        total *= math.exp( - (err ** 2) / (2 * 10**2) )

    return max(0.001, min(1.0, total))

def lbs_aware_snap(lbs_info: Dict[str, Any], roads: Optional[List[Dict]] = None) -> Dict[str, Any]:
    """
    LBS-aware map matching (discussion 18).
    Scores road segments by how well they explain observed TA/RSSI from serving + neighbor cells.
    Returns snapped point + confidence + likelihood (ready for EKF or PostGIS).
    """
    if roads is None:
        roads = _DEMO_ROADS

    raw_lat = lbs_info.get("raw_lbs_lat") or 0.0
    raw_lon = lbs_info.get("raw_lbs_lon") or 0.0

    best_score = -1.0
    best = None
    for seg in roads:
        pt = (seg["lat"], seg["lon"])
        sc = lbs_likelihood(pt, lbs_info)
        if sc > best_score:
            best_score = sc
            best = seg

    if not best:
        return {
            "matched_lat": raw_lat, "matched_lon": raw_lon,
            "road_id": -1, "confidence": 0.1, "lbs_likelihood": 0.0
        }

    conf = min(0.99, best_score * 12)
    dist = haversine(raw_lat, raw_lon, best["lat"], best["lon"])
    return {
        "matched_lat": best["lat"],
        "matched_lon": best["lon"],
        "road_id": best.get("id", 0),
        "road_name": best.get("name", ""),
        "confidence": round(conf, 3),
        "lbs_likelihood": round(best_score, 4),
        "dist_from_raw_lbs_m": round(dist, 1),
    }

# Example in handler (SRT 205 path):
#   matched = lbs_aware_snap(lbs_info)
#   # then forward matched to map-matching service or store road_id + confidence in DB
