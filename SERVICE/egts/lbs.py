"""
LBS (base stations) support for EGTS (discussion 18).
Simple Python LBS-aware map matching stub (for handler example).
In production use PostGIS version from sandbox/postgis_lbs.sql .
"""

from typing import Dict, Any, Optional

# Toy road segments (in real: from DB or PostGIS)
_DEMO_ROADS = [
    {"id": 101, "name": "ул. Примерная", "lat": 55.71813, "lon": 37.43960},
    {"id": 102, "name": "ул. Примерная", "lat": 55.71825, "lon": 37.43985},
]

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    import math
    R = 6371000.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2)
    return 2 * R * math.asin(math.sqrt(a))

def lbs_aware_snap(lbs_info: Dict[str, Any], roads: Optional[list] = None) -> Dict[str, Any]:
    """
    Simple LBS + road graph snap.
    lbs_info: dict with raw_lbs_lat, raw_lbs_lon, serving (with ta, rssi_dbm, lat, lon)
    Returns matched point on road + confidence.
    """
    if roads is None:
        roads = _DEMO_ROADS
    lat = lbs_info.get("raw_lbs_lat") or 0
    lon = lbs_info.get("raw_lbs_lon") or 0
    serving = lbs_info.get("serving", {}) or {}
    best = None
    best_score = -1
    for seg in roads:
        d = haversine(lat, lon, seg["lat"], seg["lon"])
        # Simple score: inverse distance + TA match if available
        score = 1 / (1 + d)
        if serving.get("ta"):
            ta_dist = serving["ta"] * 550
            bs_d = haversine(seg["lat"], seg["lon"], serving.get("lat", lat), serving.get("lon", lon))
            ta_match = 1 / (1 + abs(bs_d - ta_dist))
            score = 0.6 * score + 0.4 * ta_match
        if score > best_score:
            best_score = score
            best = seg
    if not best:
        return {"matched_lat": lat, "matched_lon": lon, "road_id": -1, "confidence": 0.0}
    conf = min(0.99, best_score * 10)
    return {
        "matched_lat": best["lat"],
        "matched_lon": best["lon"],
        "road_id": best["id"],
        "road_name": best.get("name", ""),
        "confidence": round(conf, 3),
        "lbs_likelihood": round(best_score, 4),
    }

# Example usage in handler:
# if lbs_records:
#     for rec in lbs_records:
#         matched = lbs_aware_snap(rec)
#         print("LBS snapped to road:", matched)
