# 15. Алгоритмы Map Matching — обзор и выбор для EGTS RTLS

**Дата:** 2026-06-12  
**Контекст:** Сравнение алгоритмов для финального уровня Sensor Fusion (после EKF). Используется в проектах РНИС для транспорта по дорогам/выделенным полосам.

---

## Классификация алгоритмов

### 1. Геометрические (Point-to-Curve)

Проекция точки на ближайший сегмент дороги.

```
dist = min(ST_Distance(point, road_segment) for road_segment in candidates)
snapped = ST_ClosestPoint(nearest_segment, point)
```

**Плюсы:** простота, скорость O(log N) с R-tree индексом  
**Минусы:** нет учёта направления и последовательности → ошибки на параллельных дорогах  
**Применение:** первичная фильтрация кандидатов (top-5 по расстоянию)

---

### 2. Топологические (с учётом heading и скорости)

Добавляют вес на переход между сегментами через граф:

```python
score = w1 * dist_score + w2 * heading_diff + w3 * speed_consistency
```

**Плюсы:** учитывает связность дорог, быстрее HMM  
**Минусы:** накопление ошибки при длинных треках, проблемы на перекрёстках  
**Применение:** когда GPS плотный (>1 Гц) и дорожная сеть простая

---

### 3. HMM + Viterbi (Hidden Markov Model) — золотой стандарт

**Концепция:** каждая дорога-кандидат — скрытое состояние. GPS-точка — наблюдение.

```
Emission:    P(obs | state) = Gaussian(d, σ=5м)
Transition:  P(s_i+1 | s_i) = f(routing_dist / GPS_dist)
Viterbi:     argmax P(states | observations)
```

**Детально:**

```python
import math

def emission_prob(gps_point, road_segment, sigma=5.0):
    dist = haversine(gps_point, project(gps_point, road_segment))
    return (1 / (sigma * math.sqrt(2*math.pi))) * math.exp(-dist**2 / (2*sigma**2))

def transition_prob(seg_a, seg_b, gps_dist, beta=3.0):
    routing_dist = shortest_path_length(seg_a, seg_b)  # pgRouting
    dt = abs(routing_dist - gps_dist)
    return (1 / beta) * math.exp(-dt / beta)

# Viterbi dp: O(N * K²), N=GPS-точек, K=кандидатов на точку
def viterbi(gps_points, candidates, emit_fn, trans_fn):
    dp = [{} for _ in gps_points]
    backtrack = [{} for _ in gps_points]
    for seg in candidates[0]:
        dp[0][seg] = emit_fn(gps_points[0], seg)
    for i in range(1, len(gps_points)):
        for seg in candidates[i]:
            best = max(
                (dp[i-1][prev] * trans_fn(prev, seg, ...) * emit_fn(gps_points[i], seg), prev)
                for prev in candidates[i-1]
            )
            dp[i][seg], backtrack[i][seg] = best
    # Восстановление пути
    path = [max(dp[-1], key=dp[-1].get)]
    for i in range(len(gps_points)-1, 0, -1):
        path.append(backtrack[i][path[-1]])
    return list(reversed(path))
```

**Плюсы:** отлично работает с шумом, редкими точками (<1 Гц), параллельными дорогами  
**Минусы:** требует pgRouting или аналога для transition probability  
**Применение:** основной алгоритм для РНИС (транспорт, автобусы, грузовики)

---

### 4. Particle Filter (PF)

Монте-Карло аппроксимация: N частиц = N гипотез о положении ТС.

```python
# Псевдокод
particles = sample_from_prior(N=1000)
for gps_obs in track:
    weights = [likelihood(p, gps_obs) for p in particles]
    particles = resample(particles, weights)
    particles = [motion_model(p, imu_data) for p in particles]
estimate = weighted_mean(particles)
```

**Плюсы:** любые нелинейные модели, lane-level точность, отлично с IMU  
**Минусы:** высокая вычислительная стоимость (N=500–2000 частиц)  
**Применение:** высокая точность + IMU fusion (совместно с EKF/Madgwick)

---

## Сравнительная таблица

| Алгоритм | Точность | Скорость | Шум GPS | IMU fusion | Сложность |
|----------|----------|----------|---------|------------|-----------|
| Геометрический | низкая | очень высокая | плохо | нет | низкая |
| Топологический | средняя | высокая | средне | частично | средняя |
| **HMM + Viterbi** | **высокая** | **средняя** | **отлично** | **да** | **средняя** |
| Particle Filter | очень высокая | низкая | отлично | да | высокая |
| Deep Learning | высокая | средняя | отлично | да | очень высокая |

---

## Open-source библиотеки

| Библиотека | Язык | Алгоритм | Интеграция |
|------------|------|----------|------------|
| **pgMapMatch** | SQL/Python | HMM + pgRouting | PostGIS (рекомендуется) |
| **mappymatch** | Python | HMM + Valhalla/OSRM | REST API |
| **leuven-map-matching** | Python | HMM | OSM граф |
| **Valhalla** | C++ | HMM | REST, высокая нагрузка |
| **OSRM** | C++ | HMM | REST, высокая нагрузка |
| **gotrackit** | Python | улучшенный HMM | Shapefile/PostGIS |

**Рекомендация для РНИС:** pgMapMatch (PostGIS) — нет внешних зависимостей, интеграция с существующей БД.

---

## Рекомендуемая архитектура для EGTS RTLS

```
1. IMU (100 Hz)  ─→  Madgwick  ─→  heading
2. GPS (1–10 Hz) ─┐
   IMU heading  ──┴→  EKF  ─→  filtered (lat, lon, speed)
3. filtered track ─→  HMM Map Matching  ─→  road-snapped (lat, lon, road_id)
4. road-snapped   ─→  EGTS SRT 200/201  ─→  РНИС
```

**Частота Map Matching:** применяется к батчу из последних 5–20 точек (sliding window) для корректного расчёта transition probability.

---

## Интеграция с PostGIS (pgMapMatch)

```sql
-- Создание расширений
CREATE EXTENSION postgis;
CREATE EXTENSION pgrouting;

-- Таблица дорог (граф)
CREATE TABLE roads (
    id BIGSERIAL PRIMARY KEY,
    source INT,
    target INT,
    cost FLOAT,          -- длина сегмента
    reverse_cost FLOAT,
    geom GEOMETRY(LINESTRING, 4326)
);
CREATE INDEX roads_geom_idx ON roads USING GIST(geom);

-- Map Matching через pgMapMatch (HMM)
SELECT * FROM pgmapmatching(
    'SELECT id, source, target, cost, reverse_cost, geom FROM roads',
    ARRAY[
        ST_SetSRID(ST_MakePoint(56.123, 43.456), 4326),
        ST_SetSRID(ST_MakePoint(56.124, 43.457), 4326)
    ]::geometry[],
    sigma := 5.0,   -- GPS noise (м)
    beta  := 3.0    -- transition penalty
);
```

---

## Зависимости

- [13-sensor-fusion-architecture.md](./13-sensor-fusion-architecture.md) — место Map Matching в пайплайне
- [14-ekf-implementation.md](./14-ekf-implementation.md) — EKF как предшествующий шаг
- [11-postgis-map-matching.md](./11-postgis-map-matching.md) — PostGIS snap-запросы
- [08-road-graph-map-matching.md](./08-road-graph-map-matching.md) — теория и применение в РНИС
