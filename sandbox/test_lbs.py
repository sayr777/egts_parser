"""
Tests / edge-cases for LBS + road graph (discussion 18).
Run: python test_lbs.py
"""

from lbs_map_matcher import (
    generate_synthetic_lbs, lbs_likelihood, lbs_aware_snap_to_road, DEMO_ROADS, DEMO_BASE_STATIONS
)

def test_basic_snap():
    true_p = (55.71825, 37.43985)  # on road 102
    lbs = generate_synthetic_lbs(true_p[0], true_p[1], noise=0.5)
    res = lbs_aware_snap_to_road(lbs, DEMO_ROADS)
    assert res.get("road_id") in [101, 102], "Should snap to a reasonable road segment"
    print("basic_snap: OK", res["road_name"], "road_id=", res.get("road_id"))

def test_weak_gnss_fallback():
    # Noisy LBS far from road
    lbs = {
        "serving": {"cell_id": 1001, "lat": 55.72, "lon": 37.44, "ta": 10, "rssi_dbm": -90},
        "neighbors": [],
        "raw_lbs_lat": 55.72,
        "raw_lbs_lon": 37.44,
    }
    res = lbs_aware_snap_to_road(lbs, DEMO_ROADS)
    assert res["confidence"] < 0.5 or res["road_id"] in [101,102], "Should still find reasonable road"
    print("weak_gnss: OK", res["confidence"])

def test_multi_station():
    # Use real BS locations
    lbs = generate_synthetic_lbs(55.71825, 37.43985, noise=0.8)
    score = lbs_likelihood((55.71825, 37.43985), lbs)
    assert score > 0.001
    print("multi_station_likelihood: OK", score)

if __name__ == "__main__":
    test_basic_snap()
    test_weak_gnss_fallback()
    test_multi_station()
    print("All LBS edge-case tests passed.")