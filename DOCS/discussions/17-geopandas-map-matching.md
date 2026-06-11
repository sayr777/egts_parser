# 17. GeoPandas — анализ и Map Matching для EGTS RTLS

**Дата:** 2026-06-12  
**Контекст:** GeoPandas как инструмент для разработки, тестирования и прототипирования алгоритмов map-matching в проектах РНИС до переноса в production (PostGIS).

---

## Что такое GeoPandas

GeoPandas расширяет pandas для работы с геопространственными данными:

- `GeoDataFrame` = DataFrame + колонка `geometry` (Shapely-объекты)
- Под капотом: **Shapely** (геометрия), **pyproj** (проекции), **Fiona** (I/O), **matplotlib** (визуализация)
- Читает/пишет: Shapefile, GeoJSON, GeoParquet, PostGIS (SQLAlchemy), CSV с координатами

```bash
pip install geopandas osmnx shapely pyproj
```

---

## Сравнение с PostGIS

| Задача | GeoPandas | PostGIS | Рекомендация |
|--------|-----------|---------|--------------|
| Прототипирование алгоритмов | Отлично | Медленнее | GeoPandas |
| Большие датасеты (>1М точек) | In-memory (медленнее) | GIST-индексы (быстро) | PostGIS |
| Map Matching на графе | + OSMnx / leuven | + pgRouting | Комбинация |
| Визуализация треков | Легко (.plot()) | Сторонний инструмент | GeoPandas |
| Production ingestion | Не основной | Основной | PostGIS |

**Вывод:** GeoPandas идеален для разработки и офлайн-валидации; PostGIS — для production РНИС.

---

## Загрузка GPS-треков из EGTS

```python
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, LineString

# GPS-точки из EGTS-пакетов (после декодирования)
egts_data = [
    {"ts": 1720000000, "lat": 55.7558, "lon": 37.6176, "speed": 12.5},
    {"ts": 1720000010, "lat": 55.7562, "lon": 37.6185, "speed": 13.1},
    {"ts": 1720000020, "lat": 55.7568, "lon": 37.6194, "speed": 11.8},
]

df = pd.DataFrame(egts_data)
gdf = gpd.GeoDataFrame(
    df,
    geometry=[Point(row.lon, row.lat) for row in df.itertuples()],
    crs="EPSG:4326"
)

# Перевод в метровую систему (UTM зона 37N для Москвы)
gdf_utm = gdf.to_crs(epsg=32637)

print(gdf_utm[["ts", "speed", "geometry"]])
```

---

## Map Matching с GeoPandas + OSMnx

### Загрузка дорожного графа OSM

```python
import osmnx as ox
import geopandas as gpd
from shapely.geometry import Point

# Загрузка графа дорог для района
G = ox.graph_from_place("Пермь, Россия", network_type="drive")

# Конвертация рёбер в GeoDataFrame
edges = ox.graph_to_gdfs(G, nodes=False)
edges_utm = edges.to_crs(epsg=32663)   # UTM для Перми
```

### Простой snap (геометрический)

```python
def snap_to_road(point_gdf: gpd.GeoDataFrame,
                 roads_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Проекция точек на ближайший сегмент дороги."""
    result = []
    for _, row in point_gdf.iterrows():
        # Ближайший сегмент
        nearest_idx = roads_gdf.distance(row.geometry).idxmin()
        nearest_road = roads_gdf.loc[nearest_idx]

        # Проекция на сегмент
        snapped = nearest_road.geometry.interpolate(
            nearest_road.geometry.project(row.geometry)
        )
        dist = row.geometry.distance(snapped)

        result.append({
            **row.to_dict(),
            "snapped_geometry": snapped,
            "road_id": nearest_idx,
            "road_name": nearest_road.get("name", ""),
            "snap_dist_m": dist,
            "confidence": float(max(0, 1 - dist / 50))  # 0–1, 50м = 0
        })

    snapped_gdf = gpd.GeoDataFrame(result, geometry="snapped_geometry", crs=point_gdf.crs)
    return snapped_gdf
```

---

## HMM Map Matching с leuven-map-matching

```bash
pip install leuven-map-matching
```

```python
from leuvenmapmatching.matcher.distance import DistanceMatcher
from leuvenmapmatching.map.inmem import InMemMap

# Создание графа из OSM edges
map_con = InMemMap("osm", use_rtree=True, index_edges=True)

for idx, row in edges.iterrows():
    coords = list(row.geometry.coords)
    map_con.add_edge(idx[0], idx[1], coords)

map_con.finalize()

# HMM matching
path = [(row.lat, row.lon) for row in gdf.itertuples()]
matcher = DistanceMatcher(map_con, max_dist=50, obs_noise=4.07, min_prob_norm=0.001)
matcher.match(path)

# Результаты
matched_nodes = matcher.path_pred_onlynodes
print(f"Matched {len(matched_nodes)} nodes")
```

---

## Интеграция с EKF (из [14-ekf-implementation.md](./14-ekf-implementation.md))

```python
from egts.filters.ekf import EGTS_EKF
import geopandas as gpd

ekf = EGTS_EKF(dt=0.1)

# Обработка трека с EKF → map matching
results = []
for i, row in gdf.iterrows():
    ekf.update_gps(row.lat, row.lon)
    state = ekf.get_state()

    results.append({
        "raw_lat": row.lat,
        "raw_lon": row.lon,
        "ekf_lat": state["lat"],
        "ekf_lon": state["lon"],
        "confidence": state["confidence"],
    })

ekf_gdf = gpd.GeoDataFrame(
    results,
    geometry=[Point(r["ekf_lon"], r["ekf_lat"]) for r in results],
    crs="EPSG:4326"
)

# Snap EKF-треков (намного точнее сырых GPS)
snapped = snap_to_road(ekf_gdf.to_crs(epsg=32637), edges_utm)
```

---

## Анализ качества

```python
import matplotlib.pyplot as plt

fig, axes = plt.subplots(1, 2, figsize=(14, 6))

# Сырой GPS трек
gdf.plot(ax=axes[0], color="red", markersize=5, label="GPS raw")
edges.plot(ax=axes[0], color="gray", linewidth=0.5)
axes[0].set_title("Сырые GPS точки")

# Map-matched трек
snapped.plot(ax=axes[1], color="blue", markersize=5, label="Snapped")
edges.plot(ax=axes[1], color="gray", linewidth=0.5)
axes[1].set_title("После Map Matching")

# Статистика отклонения
print(f"Среднее отклонение: {snapped['snap_dist_m'].mean():.2f} м")
print(f"Макс. отклонение: {snapped['snap_dist_m'].max():.2f} м")
print(f"% точек с dist < 10 м: {(snapped['snap_dist_m'] < 10).mean()*100:.1f}%")
```

---

## Рекомендованный пайплайн для РНИС

```
EGTS decode
    │
    ▼
DataFrame (pandas)
    │
    ▼
GeoDataFrame (GeoPandas) ─── разработка/анализ/визуализация
    │
    ▼
EKF filter ([14](./14-ekf-implementation.md))
    │
    ▼
leuven / HMM map matching
    │
    ▼
Результат → PostGIS (production)
    │
    ▼
EGTS encode → РНИС
```

---

## Зависимости

- [08-road-graph-map-matching.md](./08-road-graph-map-matching.md) — теория Map Matching
- [11-postgis-map-matching.md](./11-postgis-map-matching.md) — production PostGIS
- [14-ekf-implementation.md](./14-ekf-implementation.md) — EKF перед map matching
- [15-map-matching-algorithms.md](./15-map-matching-algorithms.md) — сравнение алгоритмов
