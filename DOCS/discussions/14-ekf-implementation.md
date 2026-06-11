# 14. Реализация Extended Kalman Filter (EKF) для EGTS RTLS

**Дата:** 2026-06-12  
**Контекст:** EKF для fusion GPS + IMU в транспортных проектах РНИС. Является центральным блоком архитектуры из [13-sensor-fusion-architecture.md](./13-sensor-fusion-architecture.md).

---

## Назначение

Extended Kalman Filter используется для точной оценки состояния при нелинейных моделях движения (повороты, ускорения, вибрации). Критично для GPS + IMU fusion в условиях городской застройки, туннелей и слабого GNSS-сигнала.

**Преимущества EKF перед простым Kalman:**
- Работает с нелинейными моделями через матрицы Якоби
- Лучшая точность heading и позиции при манёврах
- Явный учёт drift-bias гироскопа и акселерометра
- Ковариация ошибки → метрика уверенности (confidence)

---

## Вектор состояния

```
x = [lat, lon, vx, vy, heading, heading_bias]
     [0]   [1]  [2] [3]  [4]       [5]
```

| Компонент | Единица | Описание |
|-----------|---------|----------|
| `lat`, `lon` | градусы | Позиция (WGS-84) |
| `vx`, `vy` | м/с | Скорость по осям |
| `heading` | рад | Азимут из Madgwick |
| `heading_bias` | рад/с | Drift гироскопа |

---

## Реализация (`SERVICE/egts/filters/ekf.py`)

```python
import numpy as np
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class EKFState:
    x: np.ndarray       # вектор состояния [6]
    P: np.ndarray       # ковариационная матрица [6x6]
    timestamp: float

class EGTS_EKF:
    """Extended Kalman Filter для RTLS + IMU (GPS fusion)."""

    def __init__(self, dt: float = 0.1):
        self.dt = dt
        self.initialized = False

        self.x = np.zeros(6)
        self.P = np.eye(6) * 1000.0  # начальная неопределённость

        # Шум процесса: [lat, lon, vx, vy, heading, heading_bias]
        self.Q = np.diag([1e-6, 1e-6, 0.5, 0.5, 0.05, 0.001])

        # Шум измерений
        self.R_gps = np.diag([5e-5, 5e-5])   # ~5 м в градусах WGS-84
        self.R_imu = np.diag([0.5, 0.5, 0.1])  # accel x/y, heading

    def init(self, lat: float, lon: float, heading: float = 0.0):
        """Инициализация по первому GPS-фиксу."""
        self.x = np.array([lat, lon, 0.0, 0.0, np.radians(heading), 0.0])
        self.P = np.diag([1e-6, 1e-6, 1.0, 1.0, 0.1, 0.01])
        self.initialized = True

    # ------------------------------------------------------------------
    # Шаг предсказания (IMU dead-reckoning)
    # ------------------------------------------------------------------
    def predict(self, accel_n: float = 0.0, accel_e: float = 0.0):
        """
        Предсказание следующего состояния по модели постоянной скорости.
        accel_n, accel_e — ускорения в географической системе (м/с²),
        полученные после поворота через heading из Madgwick.
        """
        if not self.initialized:
            return

        dt = self.dt
        _, _, vx, vy, h, hb = self.x

        # Нелинейная модель f(x)
        self.x[0] += vx * dt                  # lat
        self.x[1] += vy * dt                  # lon
        self.x[2] += accel_n * dt             # vx
        self.x[3] += accel_e * dt             # vy
        self.x[4] += hb * dt                  # heading drift
        # self.x[5] = hb (константа между обновлениями)

        # Якобиан F = df/dx
        F = np.eye(6)
        F[0, 2] = dt          # d(lat)/d(vx)
        F[1, 3] = dt          # d(lon)/d(vy)
        F[4, 5] = dt          # d(heading)/d(heading_bias)

        self.P = F @ self.P @ F.T + self.Q

    # ------------------------------------------------------------------
    # Шаг обновления по GPS
    # ------------------------------------------------------------------
    def update_gps(self, lat: float, lon: float):
        """Коррекция по GPS/GNSS измерению."""
        if not self.initialized:
            self.init(lat, lon)
            return

        z = np.array([lat, lon])
        H = np.zeros((2, 6))
        H[0, 0] = 1.0   # lat
        H[1, 1] = 1.0   # lon

        y = z - H @ self.x          # инновация
        S = H @ self.P @ H.T + self.R_gps
        K = self.P @ H.T @ np.linalg.inv(S)

        self.x = self.x + K @ y
        self.P = (np.eye(6) - K @ H) @ self.P

    # ------------------------------------------------------------------
    # Шаг обновления по heading из Madgwick
    # ------------------------------------------------------------------
    def update_heading(self, heading_rad: float):
        """Коррекция heading по Madgwick (рад)."""
        if not self.initialized:
            return

        z = np.array([heading_rad])
        H = np.zeros((1, 6))
        H[0, 4] = 1.0

        y = z - H @ self.x
        # Нормализация разницы углов в [-π, π]
        y[0] = (y[0] + np.pi) % (2 * np.pi) - np.pi

        S = H @ self.P @ H.T + np.array([[self.R_imu[2, 2]]])
        K = self.P @ H.T @ np.linalg.inv(S)

        self.x = self.x + K @ y
        self.P = (np.eye(6) - K @ H) @ self.P

    # ------------------------------------------------------------------
    # Результат
    # ------------------------------------------------------------------
    def get_state(self) -> dict:
        trace = float(np.trace(self.P))
        return {
            "lat":        float(self.x[0]),
            "lon":        float(self.x[1]),
            "speed_ms":   float(np.hypot(self.x[2], self.x[3])),
            "heading":    float(np.degrees(self.x[4]) % 360),
            "confidence": float(1.0 / (1.0 + trace)),
            "cov_trace":  trace,
        }
```

---

## Матрицы шума — рекомендации

| Матрица | Компонент | Значение | Источник неточности |
|---------|-----------|----------|---------------------|
| Q | lat/lon | 1e-6 | численный drift |
| Q | vx/vy | 0.5 | вибрации (см. [10](./10-vibration-filtering-algorithms.md)) |
| Q | heading | 0.05 | магнитные помехи |
| Q | heading_bias | 0.001 | температурный drift гироскопа |
| R_gps | lat/lon | 5e-5 | ~5 м в городе |
| R_imu | heading | 0.1 рад | Madgwick uncertainty |

**Тюнинг:** при высоком `cov_trace` (>50) — GPS-фикс плохой, доверяем IMU. При `cov_trace < 1` — фильтр сошёлся.

---

## Интеграция в пайплайн (из [13-sensor-fusion-architecture.md](./13-sensor-fusion-architecture.md))

```python
from egts.filters.ekf import EGTS_EKF
from egts.filters.madgwick import MadgwickFilter

ekf = EGTS_EKF(dt=0.01)   # 100 Hz IMU
madgwick = MadgwickFilter(beta=0.033, sample_period=0.01)

# Цикл 100 Hz — IMU
q = madgwick.update(gyro, accel, mag)
heading_rad = madgwick.get_heading_rad()
accel_n, accel_e = rotate_to_geo(accel, heading_rad)

ekf.predict(accel_n, accel_e)
ekf.update_heading(heading_rad)

# Цикл 1–10 Hz — GPS
if gps_fix:
    ekf.update_gps(gps_lat, gps_lon)

state = ekf.get_state()
```

---

## Интеграция с EGTS SRT 204 (расширение)

Дополнительные поля пакета SRT 204:

| Поле | Тип | Описание |
|------|-----|----------|
| `filtered_lat` | float64 | EKF-скорректированная широта |
| `filtered_lon` | float64 | EKF-скорректированная долгота |
| `filtered_heading` | uint16 | Heading в 0.01° |
| `ekf_confidence` | uint8 | 0–255 (confidence × 255) |
| `cov_trace` | float32 | Trace ковариационной матрицы |

---

## Зависимости

- [13-sensor-fusion-architecture.md](./13-sensor-fusion-architecture.md) — общая архитектура пайплайна
- [15-map-matching-algorithms.md](./15-map-matching-algorithms.md) — Map Matching после EKF
- [16-madgwick-sensor-fusion.md](./16-madgwick-sensor-fusion.md) — Madgwick как источник heading
- [10-vibration-filtering-algorithms.md](./10-vibration-filtering-algorithms.md) — предобработка IMU
