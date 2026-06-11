# 16. Madgwick Filter — реализация для EGTS RTLS

**Дата:** 2026-06-12  
**Контекст:** Реализация Madgwick Filter как первого уровня Sensor Fusion (heading/orientation) для SRT 202/204 в проектах РНИС.

---

## Назначение

Madgwick Filter оценивает ориентацию тела (roll, pitch, yaw/heading) из IMU через градиентный спуск в пространстве кватернионов. Работает на 100–200 Гц, малая задержка, подходит для embedded и Flutter.

**В пайплайне:** IMU → **Madgwick** → heading → EKF ([14](./14-ekf-implementation.md)) → Map Matching ([15](./15-map-matching-algorithms.md))

---

## Реализация (`SERVICE/egts/filters/madgwick.py`)

```python
import numpy as np
from math import sqrt

class MadgwickFilter:
    """
    Madgwick AHRS filter для оценки ориентации.
    Ref: Madgwick et al. (2010) — IMU and MARG orientation filter.
    """

    def __init__(self, beta: float = 0.033, sample_period: float = 0.01):
        self.beta = beta                  # коэффициент коррекции (0.01–0.1)
        self.sample_period = sample_period  # 1/частота_дискретизации
        self.q = np.array([1.0, 0.0, 0.0, 0.0])  # кватернион [w, x, y, z]

    # ------------------------------------------------------------------
    # MARG update (Mag + Accel + Rate Gyro) — полный режим
    # ------------------------------------------------------------------
    def update(self,
               gyro:  np.ndarray,   # [gx, gy, gz] рад/с
               accel: np.ndarray,   # [ax, ay, az] любые единицы (нормируется)
               mag:   np.ndarray    # [mx, my, mz] любые единицы (нормируется)
               ) -> np.ndarray:
        """Один шаг фильтра. Возвращает кватернион."""
        q = self.q
        gx, gy, gz = gyro
        ax, ay, az = accel
        mx, my, mz = mag

        # Нормализация
        norm = sqrt(ax*ax + ay*ay + az*az)
        if norm == 0:
            return q
        ax, ay, az = ax/norm, ay/norm, az/norm

        norm = sqrt(mx*mx + my*my + mz*mz)
        if norm == 0:
            return self._imu_update(gyro, accel)
        mx, my, mz = mx/norm, my/norm, mz/norm

        # Вспомогательные переменные (сокращение вычислений)
        q0, q1, q2, q3 = q
        _2q0 = 2*q0; _2q1 = 2*q1; _2q2 = 2*q2; _2q3 = 2*q3
        _4q0 = 4*q0; _4q1 = 4*q1; _4q2 = 4*q2
        _8q1 = 8*q1; _8q2 = 8*q2
        q0q0 = q0*q0; q1q1 = q1*q1; q2q2 = q2*q2; q3q3 = q3*q3

        # Опорное поле Земли в теле координат
        hx = mx*(_2q0*q3 + _2q1*q2 - 1) - my*(_2q0*q2 - _2q1*q3) + \
             mz*(q1q1 - q2q2 - q3q3 + q0q0) * 2  # упрощено
        hy = mx*(1 - _2q1*q1 - _2q2*q2) + my*(_2q1*q2 + _2q0*q3) + \
             mz*(_2q2*q3 - _2q0*q1)
        _2bx = sqrt(hx*hx + hy*hy)
        _2bz = -(_2q0*my - _2q3*mx) + mz  # упрощённо

        # Функция ошибки (gradient of objective function)
        s0 = (-_2q2*(2*(q1q1 + q3q3) - 1 - az) +
               _2q1*(2*(q1*q2 - q0*q3) - ay))
        s1 = (_2q3*(2*(q1q1 + q3q3) - 1 - az) +
               _2q0*(2*(q1*q2 - q0*q3) - ay) -
               4*q1*(1 - 2*(q1q1 + q2q2) - ax))
        s2 = (-_2q0*(2*(q1q1 + q3q3) - 1 - az) +
               _2q3*(2*(q1*q2 - q0*q3) - ay) -
               4*q2*(1 - 2*(q1q1 + q2q2) - ax))
        s3 = (_2q1*(2*(q1q1 + q3q3) - 1 - az) +
               _2q2*(2*(q1*q2 - q0*q3) - ay))

        norm = sqrt(s0*s0 + s1*s1 + s2*s2 + s3*s3)
        if norm > 0:
            s0, s1, s2, s3 = s0/norm, s1/norm, s2/norm, s3/norm

        # Производная кватерниона
        qDot = np.array([
            0.5*(-q1*gx - q2*gy - q3*gz) - self.beta*s0,
            0.5*( q0*gx + q2*gz - q3*gy) - self.beta*s1,
            0.5*( q0*gy - q1*gz + q3*gx) - self.beta*s2,
            0.5*( q0*gz + q1*gy - q2*gx) - self.beta*s3,
        ])

        # Интегрирование
        self.q = q + qDot * self.sample_period
        self.q /= np.linalg.norm(self.q)
        return self.q

    # ------------------------------------------------------------------
    # IMU-only update (без магнетометра — в помещении)
    # ------------------------------------------------------------------
    def _imu_update(self, gyro: np.ndarray, accel: np.ndarray) -> np.ndarray:
        q = self.q
        gx, gy, gz = gyro
        ax, ay, az = accel
        norm = sqrt(ax*ax + ay*ay + az*az)
        if norm == 0:
            return q
        ax, ay, az = ax/norm, ay/norm, az/norm

        q0, q1, q2, q3 = q
        s0 = 4*q0*q2*q2 + 2*q2*ax + 4*q0*q1*q1 - 2*q1*ay
        s1 = 4*q1*q3*q3 - 2*q3*ax + 4*q0*q0*q1 - 2*q0*ay - 4*q1 + 8*q1*q1*q1 + 8*q1*q2*q2 - 4*q1*az
        s2 = 4*q0*q0*q2 + 2*q0*ax + 4*q2*q3*q3 - 2*q3*ay - 4*q2 + 8*q2*q1*q1 + 8*q2*q2*q2 - 4*q2*az
        s3 = 4*q1*q1*q3 - 2*q1*ax + 4*q2*q2*q3 - 2*q2*ay
        norm = sqrt(s0*s0 + s1*s1 + s2*s2 + s3*s3)
        if norm > 0:
            s0, s1, s2, s3 = s0/norm, s1/norm, s2/norm, s3/norm

        qDot = np.array([
            0.5*(-q1*gx - q2*gy - q3*gz) - self.beta*s0,
            0.5*( q0*gx + q2*gz - q3*gy) - self.beta*s1,
            0.5*( q0*gy - q1*gz + q3*gx) - self.beta*s2,
            0.5*( q0*gz + q1*gy - q2*gx) - self.beta*s3,
        ])
        self.q = q + qDot * self.sample_period
        self.q /= np.linalg.norm(self.q)
        return self.q

    # ------------------------------------------------------------------
    # Извлечение углов Эйлера
    # ------------------------------------------------------------------
    def get_euler(self) -> tuple[float, float, float]:
        """Возвращает (roll, pitch, yaw) в градусах."""
        w, x, y, z = self.q
        roll  = np.degrees(np.arctan2(2*(w*x + y*z), 1 - 2*(x*x + y*y)))
        pitch = np.degrees(np.arcsin( 2*(w*y - z*x)))
        yaw   = np.degrees(np.arctan2(2*(w*z + x*y), 1 - 2*(y*y + z*z)))
        return roll, pitch, yaw

    def get_heading(self) -> float:
        """Heading (yaw) в градусах [0, 360)."""
        _, _, yaw = self.get_euler()
        return yaw % 360

    def get_heading_rad(self) -> float:
        return np.radians(self.get_heading())

    def reset(self):
        self.q = np.array([1.0, 0.0, 0.0, 0.0])
```

---

## Параметр β — выбор значения

| β | Поведение | Применение |
|---|-----------|------------|
| 0.01–0.033 | плавно, доверяем гироскопу | стационарные/медленные ТС |
| 0.033–0.1 | баланс | **рекомендуется для РНИС** |
| 0.1–0.5 | быстрая сходимость, шум выше | первичная инициализация |

**Автоматическая адаптация β:**
```python
# Снижаем β при обнаружении вибрации (высокая дисперсия акселя)
accel_var = np.var(accel_buffer[-10:])
beta = 0.033 if accel_var < 0.5 else 0.01
```

---

## Dart-реализация для Flutter ([12-flutter-imu-integration.md](./12-flutter-imu-integration.md))

```dart
class MadgwickFilter {
  double beta;
  double samplePeriod;
  List<double> q = [1.0, 0.0, 0.0, 0.0]; // w, x, y, z

  MadgwickFilter({this.beta = 0.033, this.samplePeriod = 0.01});

  void update(List<double> gyro, List<double> accel, List<double> mag) {
    // ... аналогичная реализация через dart:math
    // полный код: SERVICE/flutter_app/lib/sensors/madgwick.dart
  }

  double get heading {
    final w = q[0], x = q[1], y = q[2], z = q[3];
    final yaw = math.atan2(2*(w*z + x*y), 1 - 2*(y*y + z*z));
    return (yaw * 180 / math.pi + 360) % 360;
  }
}
```

---

## Использование с EKF

```python
from egts.filters.madgwick import MadgwickFilter
from egts.filters.ekf import EGTS_EKF

madgwick = MadgwickFilter(beta=0.033, sample_period=0.01)
ekf = EGTS_EKF(dt=0.01)

# IMU цикл — 100 Hz
def on_imu(gyro, accel, mag):
    madgwick.update(gyro, accel, mag)
    heading_rad = madgwick.get_heading_rad()
    roll, pitch, yaw = madgwick.get_euler()

    # Поворот акселерометра в географическую систему
    accel_n = accel[0] * np.cos(heading_rad) - accel[1] * np.sin(heading_rad)
    accel_e = accel[0] * np.sin(heading_rad) + accel[1] * np.cos(heading_rad)

    ekf.predict(accel_n, accel_e)
    ekf.update_heading(heading_rad)

    return madgwick.q, roll, pitch, yaw
```

---

## Интеграция с EGTS SRT 202

```python
def build_srt202(roll: float, pitch: float, yaw: float) -> bytes:
    """SRT 202 — ориентация ТС (расширение EGTS RTLS)."""
    return struct.pack('<hhh',
        int(roll  * 100) & 0xFFFF,   # 0.01° resolution
        int(pitch * 100) & 0xFFFF,
        int(yaw   * 100) & 0xFFFF,
    )
```

---

## Зависимости

- [13-sensor-fusion-architecture.md](./13-sensor-fusion-architecture.md) — место в пайплайне
- [14-ekf-implementation.md](./14-ekf-implementation.md) — потребитель heading из Madgwick
- [10-vibration-filtering-algorithms.md](./10-vibration-filtering-algorithms.md) — LPF перед Madgwick
- [09-inertial-sensors-egts.md](./09-inertial-sensors-egts.md) — описание сенсоров и их параметры
- [12-flutter-imu-integration.md](./12-flutter-imu-integration.md) — мобильная реализация
