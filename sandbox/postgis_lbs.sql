-- LBS-aware Map Matching extension (discussion 18)
-- Extends egts_map_match from discussions 11/15 with LBS (TA + RSSI from base stations)
-- Assumes tables:
--   roads (id, geom, name, ...)
--   base_stations (id, lat, lon, mcc, mnc, technology)

CREATE OR REPLACE FUNCTION egts_lbs_map_match(
    p_lat double precision,
    p_lon double precision,
    p_lbs_json jsonb,           -- { "serving": {cell_id, ta, rssi_dbm, lat, lon}, "neighbors": [...] }
    p_heading double precision DEFAULT NULL
) RETURNS TABLE (
    matched_lat double precision,
    matched_lon double precision,
    edge_id bigint,
    road_name text,
    lane int,
    confidence double precision,
    lbs_likelihood double precision,
    distance_to_road double precision
) AS $$
DECLARE
    serving RECORD;
    cand RECORD;
    dist_to_bs double precision;
    expected_dist double precision;
    ta_likelihood double precision;
    rssi_likelihood double precision;
    total_likelihood double precision;
    best_likelihood double precision := 0;
    best_edge RECORD;
    sigma_ta CONSTANT double precision := 550;  -- meters per TA unit (GSM)
BEGIN
    -- Extract serving cell
    serving := jsonb_populate_record(NULL::record, (p_lbs_json->'serving')::jsonb);

    -- Find candidate edges near raw position
    FOR cand IN
        SELECT r.id, r.name,
               ST_ClosestPoint(r.geom, ST_SetSRID(ST_MakePoint(p_lon, p_lat), 4326)) AS closest_pt,
               ST_Distance(r.geom, ST_SetSRID(ST_MakePoint(p_lon, p_lat), 4326)) AS dist
        FROM roads r
        WHERE ST_DWithin(r.geom, ST_SetSRID(ST_MakePoint(p_lon, p_lat), 4326), 1000)  -- 1km search
        ORDER BY dist
        LIMIT 20
    LOOP
        -- Compute likelihood based on serving BS
        IF serving.lat IS NOT NULL AND serving.lon IS NOT NULL THEN
            dist_to_bs := ST_Distance(
                ST_SetSRID(ST_MakePoint(serving.lon, serving.lat), 4326),
                cand.closest_pt
            );

            expected_dist := COALESCE(serving.ta, 0) * sigma_ta;
            ta_likelihood := exp( - power(dist_to_bs - expected_dist, 2) / (2 * power(sigma_ta * 1.5, 2)) );

            -- Simple RSSI path loss (free space approx)
            rssi_likelihood := exp( - power(serving.rssi_dbm + 70 + (dist_to_bs / 200.0), 2) / (2 * 8*8) );

            total_likelihood := ta_likelihood * rssi_likelihood;
        ELSE
            total_likelihood := 0.1;  -- fallback
        END IF;

        IF total_likelihood > best_likelihood THEN
            best_likelihood := total_likelihood;
            best_edge := cand;
        END IF;
    END LOOP;

    IF best_edge IS NOT NULL THEN
        RETURN QUERY SELECT
            ST_Y(best_edge.closest_pt),
            ST_X(best_edge.closest_pt),
            best_edge.id,
            best_edge.name,
            1,
            GREATEST(0, 1 - best_edge.dist / 50.0),
            best_likelihood,
            best_edge.dist;
    ELSE
        -- fallback to simple snap
        RETURN QUERY SELECT * FROM egts_map_match(p_lat, p_lon, p_heading);
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Example usage:
-- SELECT * FROM egts_lbs_map_match(55.718, 37.44, '{"serving": {"ta": 2, "rssi_dbm": -75, "lat": 55.7185, "lon": 37.4398}}');