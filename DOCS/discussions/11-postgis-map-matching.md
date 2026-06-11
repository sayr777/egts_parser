# 11. PostGIS Map Matching Example для EGTS RTLS

**Дата:** 2026-06-11

## Обзор
Привязка сырых GPS/IMU координат к графу дорог с помощью PostGIS + pgRouting для проектов РНИС.

## Почему важно
- Транспорт едет только по дорогам / выделенным полосам.
- Улучшение точности позиционирования.
- Снижение ошибок в аналитике (скорость, нарушения ПДД, маршруты).

## Реализация в PostGIS

```sql
-- Пример функции map_match
CREATE OR REPLACE FUNCTION egts_map_match(
    p_lat double precision,
    p_lon double precision,
    p_heading double precision DEFAULT NULL
) RETURNS TABLE (
    matched_lat double precision,
    matched_lon double precision,
    edge_id bigint,
    road_name text,
    lane int,
    confidence double precision,
    distance_to_road double precision
) AS $$
DECLARE
    closest_edge record;
BEGIN
    -- Найти ближайший сегмент дороги
    SELECT 
        id, 
        ST_ClosestPoint(geom, ST_SetSRID(ST_MakePoint(p_lon, p_lat), 4326)) as closest_pt,
        ST_Distance(geom, ST_SetSRID(ST_MakePoint(p_lon, p_lat), 4326)) as dist
    INTO closest_edge
    FROM roads 
    ORDER BY dist LIMIT 1;

    -- Возврат результата
    RETURN QUERY SELECT 
        ST_Y(closest_edge.closest_pt),
        ST_X(closest_edge.closest_pt),
        closest_edge.id,
        closest_edge.name,
        1, -- lane calculation logic
        GREATEST(0, 1 - closest_edge.dist / 50.0),
        closest_edge.dist;
END;
$$ LANGUAGE plpgsql;
```

## Интеграция в Python (handler.py)

```python
import psycopg2
from egts.filters.kalman import EGTSKalmanFilter

def process_with_map_matching(packet):
    # ... Kalman filtering first
    for srt in packet.srts:
        if isinstance(srt, EGTS_SR_INERTIAL_DATA):
            result = map_match_to_postgis(srt.lat, srt.lon, srt.heading)
            srt.matched_lat = result.matched_lat
            srt.road_segment_id = result.edge_id
            # etc.
```

## Рекомендации
- Использовать OSM данные + osm2pgsql + pgRouting.
- Добавить индексы и materialized views для производительности.
- Интегрировать в ClickHouse для аналитики.

## Для ТЗ RTLS v2
Добавить раздел "Map Matching на стороне сервера с PostGIS".
