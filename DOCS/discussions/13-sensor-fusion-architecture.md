# 13. Sensor Fusion Architecture для EGTS / RTLS

**Дата:** 2026-06-12  
**Контекст:** Многоуровневая архитектура объединения сенсоров для точного определения позиции и ориентации ТС в проектах РНИС (Indoor/Outdoor, EGTS + IMU).

---

## Архитектура: три уровня слияния

```
IMU (акселерометр + гироскоп + магнетометр)
        │
        ▼
┌─────────────────┐
│   Madgwick      │  → heading (азимут, roll, pitch)  ~100–200 Hz
│   Filter        │    быстро, малая задержка
└────────┬────────┘
         │  quaternion / Euler angles
         ▼
┌─────────────────┐
│   EKF           │  → позиция (lat, lon, alt)         ~10–50 Hz
│   (Extended     │     velocity (v_x, v_y, v_z)
│   Kalman Filter)│     ковариация ошибки
└────────┬────────┘
         │  сглаженная траектория
         ▼
┌─────────────────┐
│  Map Matching   │  → финальная коррекция на граф     ~1–10 Hz
│  (PostGIS /     │    дорог (snap to road)
│   pgRouting)    │    устранение GPS-дрейфа
└─────────────────┘
         │
         ▼
  EGTS-пакет (SRT 200–203) → РНИС
```

---

## Уровень 1: Madgwick Filter — быстрый heading

**Назначение:** определение ориентации тела (roll, pitch, yaw/heading) из сырых данных IMU.

**Входные данные:**
- Акселерометр: `[ax, ay, az]` (м/с²)
- Гироскоп: `[gx, gy, gz]` (рад/с)
- Магнетометр: `[mx, my, mz]` (мкТл)

**Выход:** кватернион `q = [w, x, y, z]` → Euler: roll, pitch, **yaw (heading)**

**Почему Madgwick, а не Mahony:**
| Критерий | Madgwick | Mahony |
|----------|----------|--------|
| Точность heading | выше | ниже |
| Вычислительная нагрузка | средняя | низкая |
| Drift при движении | минимальный | умеренный |
| Подходит для Flutter/embedded | да | да |

**Параметр β (бета):** коэффициент коррекции по акселерометру/магнетометру.
- `β = 0.01–0.05` — плавно, доверяем гироскопу
- `β = 0.1–0.5` — быстрая сходимость, больше шума

**Пример (Python, упрощённо):**
```python
import ahrs
madgwick = ahrs.filters.Madgwick(frequency=100.0, beta=0.033)

# В цикле:
q = madgwick.updateMARG(q, gyroscope=gyro, accelerometer=accel, magnetometer=mag)
roll, pitch, yaw = ahrs.common.orientation.q2euler(q)
```

---

## Уровень 2: EKF — позиция и скорость

**Назначение:** объединение GPS (GNSS) + IMU-dead-reckoning для оценки позиции и скорости с ковариацией ошибки.

**Вектор состояния:**
```
x = [lat, lon, alt, v_n, v_e, v_d, bias_ax, bias_ay, bias_az]
```

**Модель предсказания (IMU dead-reckoning):**
```
x_pred = f(x, u)   где u = [accel, gyro] с учётом heading из Madgwick
P_pred = F · P · Fᵀ + Q
```

**Шаг обновления (GPS):**
```
K = P_pred · Hᵀ · (H · P_pred · Hᵀ + R)⁻¹
x = x_pred + K · (z_gps - H · x_pred)
P = (I - K · H) · P_pred
```

**Матрицы шума:**
- `Q` — шум процесса (IMU drift, вибрации — см. [10-vibration-filtering-algorithms.md](./10-vibration-filtering-algorithms.md))
- `R` — шум измерений GPS (σ² = 5–15 м в городе)

**Частота обновлений:**
| Источник | Частота | Роль |
|----------|---------|------|
| IMU (predict) | 100 Hz | dead-reckoning между GPS |
| GPS (update) | 1–10 Hz | коррекция позиции |
| Madgwick heading | 100 Hz | ориентация в predict шаге |

**Пример (Python):**
```python
from filterpy.kalman import ExtendedKalmanFilter
import numpy as np

ekf = ExtendedKalmanFilter(dim_x=9, dim_z=3)
ekf.x = np.array([lat0, lon0, alt0, 0, 0, 0, 0, 0, 0])
ekf.R *= 10.0   # GPS uncertainty ~10м
ekf.Q = np.eye(9) * 0.001

# predict — каждые 10 мс (IMU)
ekf.predict_update(z=gps_measurement, HJacobian=H_gps, Hx=h_gps)
```

---

## Уровень 3: Map Matching — финальная коррекция на граф дорог

**Назначение:** проекция сглаженной EKF-траектории на граф дорог. Устраняет:
- GPS-дрейф в городской застройке
- Ошибки dead-reckoning при поворотах
- Выезды "на тротуар" в данных РНИС

**Алгоритм (HMM Map Matching):**
```
1. Candidates: ближайшие N сегментов к каждой точке (PostGIS: ST_DWithin)
2. Emission prob: P(наблюдение | сегмент) = Gaussian(dist_to_road, σ=5м)
3. Transition prob: P(сег_i+1 | сег_i) = f(routing_distance)
4. Viterbi: оптимальная последовательность сегментов
5. Snap: проекция точек на выбранные сегменты (ST_ClosestPoint)
```

**PostGIS-запрос (snap):**
```sql
SELECT
  p.id,
  ST_AsText(ST_ClosestPoint(r.geom, p.geom)) AS snapped_point,
  r.road_id,
  r.road_name
FROM gps_track p
CROSS JOIN LATERAL (
  SELECT geom, road_id, road_name
  FROM roads
  ORDER BY geom <-> p.geom
  LIMIT 1
) r;
```

Подробнее: [08-road-graph-map-matching.md](./08-road-graph-map-matching.md), [11-postgis-map-matching.md](./11-postgis-map-matching.md)

---

## Интеграция с EGTS (SRT-пакеты)

```
Madgwick → heading → SRT 202 (ориентация: roll, pitch, yaw)
EKF      → pos/vel → SRT 200 (координаты) + SRT 201 (скорость)
Map Match → snap   → коррекция lat/lon перед отправкой в РНИС
```

**Цикл отправки EGTS:**
```python
# heading из Madgwick
q = madgwick.updateMARG(q, gyro, accel, mag)
roll, pitch, yaw = q2euler(q)

# позиция из EKF
ekf.predict(imu_dt, accel, yaw)
if gps_available:
    ekf.update(gps_lat, gps_lon)

# map matching (если ТС на дороге)
snapped = map_match(ekf.x[0], ekf.x[1])

# формирование EGTS-пакета
srt200 = build_srt200(lat=snapped.lat, lon=snapped.lon, alt=ekf.x[2])
srt201 = build_srt201(speed=ekf.speed, heading=yaw)
srt202 = build_srt202(roll=roll, pitch=pitch, yaw=yaw)
send_egts([srt200, srt201, srt202])
```

---

## Сравнение вариантов архитектуры

| Вариант | Heading | Позиция | Map Match | Сложность |
|---------|---------|---------|-----------|-----------|
| GPS only | GPS bearing | GPS | нет | низкая |
| GPS + Madgwick | IMU | GPS | нет | средняя |
| **GPS + Madgwick + EKF** | **IMU** | **фьюжн** | **нет** | **высокая** |
| **GPS + Madgwick + EKF + MM** | **IMU** | **фьюжн** | **да** | **оптимальная** |

---

## Зависимости и связанные обсуждения

- [09-inertial-sensors-egts.md](./09-inertial-sensors-egts.md) — описание сенсоров и SRT-структур
- [10-vibration-filtering-algorithms.md](./10-vibration-filtering-algorithms.md) — предобработка IMU (LPF перед Madgwick)
- [08-road-graph-map-matching.md](./08-road-graph-map-matching.md) — теория Map Matching
- [11-postgis-map-matching.md](./11-postgis-map-matching.md) — реализация на PostGIS
- [12-flutter-imu-integration.md](./12-flutter-imu-integration.md) — сбор IMU в мобильном приложении
