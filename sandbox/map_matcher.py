"""
Map Matching prototypes (from 08, 11, 15, 17).

- Simple geometric nearest-segment snap (pure Python, no deps)
- Stubs + comments for HMM (Viterbi), PostGIS, GeoPandas+leuven (from the discussions)

This is Level 3 of the architecture in discussion 13.
"""

import math
from typing import List, Dict, Tuple


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance in meters."""
    R = 6371000.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2)
    return 2 * R * math.asin(math.sqrt(a))


def simple_snap_to_road(point: Tuple[float, float],
                        road_segments: List[Dict]) -> Dict:
    """
    Very basic geometric snap (Point-to-Curve).
    road_segments: list of dicts with 'id', 'name', 'lat', 'lon' (or better: list of points for the segment).

    For real use replace with PostGIS ST_ClosestPoint + GIST index (see 11-postgis-map-matching.md).
    """
    plat, plon = point
    best = None
    best_dist = float("inf")

    for seg in road_segments:
        # For demo we treat each "road" as a single representative point.
        # In real version you would iterate over line segments.
        d = haversine(plat, plon, seg["lat"], seg["lon"])
        if d < best_dist:
            best_dist = d
            best = seg

    if not best:
        return {"matched_lat": plat, "matched_lon": plon, "road_id": -1, "confidence": 0.0, "dist_m": 999}

    conf = max(0.0, 1.0 - best_dist / 50.0)   # 50 m = zero confidence (per discussions)
    return {
        "matched_lat": best["lat"],
        "matched_lon": best["lon"],
        "road_id": best.get("id", 0),
        "road_name": best.get("name", ""),
        "confidence": round(conf, 3),
        "dist_m": round(best_dist, 1),
    }


# ------------------------------------------------------------------
# PostGIS example (exact snippet from 11-postgis-map-matching.md)
# ------------------------------------------------------------------
POSTGIS_EXAMPLE_SQL = """
-- Production-grade snap (discussion 11 + 15)
CREATE OR REPLACE FUNCTION egts_map_match(
    p_lat double precision, p_lon double precision, p_heading double precision DEFAULT NULL
) RETURNS TABLE (
    matched_lat double precision, matched_lon double precision,
    edge_id bigint, road_name text, lane int,
    confidence double precision, distance_to_road double precision
) AS $$
...
$$ LANGUAGE plpgsql;
"""

# ------------------------------------------------------------------
# GeoPandas + OSMnx + HMM stub (from 17 + 15)
# ------------------------------------------------------------------
GEOPANDAS_STUB = """
# Prototyping only (discussion 17)
# pip install geopandas osmnx leuven-map-matching shapely

import geopandas as gpd
import osmnx as ox
from leuvenmapmatching.matcher.distance import DistanceMatcher
from leuvenmapmatching.map.inmem import InMemMap

# G = ox.graph_from_place("Пермь, Россия", network_type="drive")
# edges = ox.graph_to_gdfs(G, nodes=False)
# ... build InMemMap, DistanceMatcher, matcher.match(path)
"""

# ------------------------------------------------------------------
# Demo road "graph" (toy data around the real packet locations)
# ------------------------------------------------------------------
DEMO_ROADS = [
    {"id": 101, "name": "ул. Примерная", "lat": 55.71813, "lon": 37.43960},
    {"id": 102, "name": "ул. Примерная", "lat": 55.71825, "lon": 37.43985},
    {"id": 103, "name": "ул. Тестовая",   "lat": 55.71840, "lon": 37.44010},
    {"id": 104, "name": "ул. Тестовая",   "lat": 55.71870, "lon": 37.44055},
]


if __name__ == "__main__":
    raw_points = [
        (55.7181341, 37.4396038),
        (55.71820, 37.43972),
        (55.71855, 37.44030),   # slightly off
    ]

    print("Simple geometric map matching demo (08/15):")
    for p in raw_points:
        res = simple_snap_to_road(p, DEMO_ROADS)
        print(f"  raw {p}  → snapped road={res['road_name']} (id={res['road_id']}) "
              f"conf={res['confidence']} dist={res['dist_m']}m")
