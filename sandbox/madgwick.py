"""
Madgwick AHRS Filter — full implementation (from 16-madgwick-filter-implementation.md)

Clean extraction of the class proposed for EGTS RTLS.
Reference: Madgwick et al. (2010) — IMU and MARG orientation filter.

Fits exactly as Level 1 in the 3-layer architecture of discussion 13.
"""

import numpy as np
from math import sqrt
from typing import Tuple


class MadgwickFilter:
    """
    Madgwick AHRS filter for orientation (roll, pitch, yaw/heading).

    Usage in pipeline (per 13 + 14 + 16):
        mad = MadgwickFilter(beta=0.033, sample_period=0.01)
        q = mad.update(gyro, accel, mag)          # or update_imu only
        heading = mad.get_heading()
        roll, pitch, yaw = mad.get_euler()
    """

    def __init__(self, beta: float = 0.033, sample_period: float = 0.01):
        self.beta = float(beta)                     # 0.01–0.1 recommended for RNIС
        self.sample_period = float(sample_period)
        self.q = np.array([1.0, 0.0, 0.0, 0.0])     # [w, x, y, z]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def update(self, gyro: np.ndarray, accel: np.ndarray, mag: np.ndarray) -> np.ndarray:
        """MARG update (mag + accel + rate gyro). Returns current quaternion."""
        return self._marg_update(gyro, accel, mag)

    def update_imu(self, gyro: np.ndarray, accel: np.ndarray) -> np.ndarray:
        """IMU-only (no magnetometer — useful indoors)."""
        return self._imu_update(gyro, accel)

    def get_euler(self) -> Tuple[float, float, float]:
        """Returns (roll, pitch, yaw) in degrees."""
        w, x, y, z = self.q
        roll = np.degrees(np.arctan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y)))
        pitch = np.degrees(np.arcsin(2 * (w * y - z * x)))
        yaw = np.degrees(np.arctan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z)))
        return float(roll), float(pitch), float(yaw % 360)

    def get_heading(self) -> float:
        """Heading / yaw in [0, 360) degrees."""
        _, _, yaw = self.get_euler()
        return yaw % 360

    def get_heading_rad(self) -> float:
        return np.radians(self.get_heading())

    def reset(self):
        self.q = np.array([1.0, 0.0, 0.0, 0.0])

    # ------------------------------------------------------------------
    # Internal (exact logic from discussion 16)
    # ------------------------------------------------------------------
    def _marg_update(self, gyro: np.ndarray, accel: np.ndarray, mag: np.ndarray) -> np.ndarray:
        q = self.q
        gx, gy, gz = gyro
        ax, ay, az = accel
        mx, my, mz = mag

        # Normalize accel
        norm = sqrt(ax*ax + ay*ay + az*az)
        if norm == 0:
            return q
        ax, ay, az = ax / norm, ay / norm, az / norm

        # Normalize mag (fallback to IMU-only if mag is zero)
        norm = sqrt(mx*mx + my*my + mz*mz)
        if norm == 0:
            return self._imu_update(gyro, accel)
        mx, my, mz = mx / norm, my / norm, mz / norm

        # Auxiliary variables
        q0, q1, q2, q3 = q
        _2q0 = 2 * q0
        _2q1 = 2 * q1
        _2q2 = 2 * q2
        _2q3 = 2 * q3
        _4q0 = 4 * q0
        _4q1 = 4 * q1
        _4q2 = 4 * q2
        _8q1 = 8 * q1
        _8q2 = 8 * q2
        q0q0 = q0 * q0
        q1q1 = q1 * q1
        q2q2 = q2 * q2
        q3q3 = q3 * q3

        # Reference direction of Earth's magnetic field (simplified)
        hx = mx * (_2q0 * q3 + _2q1 * q2 - 1) - my * (_2q0 * q2 - _2q1 * q3) + \
             mz * (q1q1 - q2q2 - q3q3 + q0q0) * 2
        hy = mx * (1 - _2q1 * q1 - _2q2 * q2) + my * (_2q1 * q2 + _2q0 * q3) + \
             mz * (_2q2 * q3 - _2q0 * q1)
        _2bx = sqrt(hx * hx + hy * hy)
        _2bz = -(_2q0 * my - _2q3 * mx) + mz

        # Gradient of objective function (error)
        s0 = (-_2q2 * (2 * (q1q1 + q3q3) - 1 - az) +
              _2q1 * (2 * (q1 * q2 - q0 * q3) - ay))
        s1 = (_2q3 * (2 * (q1q1 + q3q3) - 1 - az) +
              _2q0 * (2 * (q1 * q2 - q0 * q3) - ay) -
              4 * q1 * (1 - 2 * (q1q1 + q2q2) - ax))
        s2 = (-_2q0 * (2 * (q1q1 + q3q3) - 1 - az) +
              _2q3 * (2 * (q1 * q2 - q0 * q3) - ay) -
              4 * q2 * (1 - 2 * (q1q1 + q2q2) - ax))
        s3 = (_2q1 * (2 * (q1q1 + q3q3) - 1 - az) +
              _2q2 * (2 * (q1 * q2 - q0 * q3) - ay))

        norm = sqrt(s0*s0 + s1*s1 + s2*s2 + s3*s3)
        if norm > 0:
            s0, s1, s2, s3 = s0 / norm, s1 / norm, s2 / norm, s3 / norm

        # Rate of change of quaternion
        qDot = np.array([
            0.5 * (-q1 * gx - q2 * gy - q3 * gz) - self.beta * s0,
            0.5 * (q0 * gx + q2 * gz - q3 * gy) - self.beta * s1,
            0.5 * (q0 * gy - q1 * gz + q3 * gx) - self.beta * s2,
            0.5 * (q0 * gz + q1 * gy - q2 * gx) - self.beta * s3,
        ])

        self.q = q + qDot * self.sample_period
        self.q /= np.linalg.norm(self.q)
        return self.q

    def _imu_update(self, gyro: np.ndarray, accel: np.ndarray) -> np.ndarray:
        q = self.q
        gx, gy, gz = gyro
        ax, ay, az = accel

        norm = sqrt(ax*ax + ay*ay + az*az)
        if norm == 0:
            return q
        ax, ay, az = ax / norm, ay / norm, az / norm

        q0, q1, q2, q3 = q
        s0 = 4 * q0 * q2 * q2 + 2 * q2 * ax + 4 * q0 * q1 * q1 - 2 * q1 * ay
        s1 = 4 * q1 * q3 * q3 - 2 * q3 * ax + 4 * q0 * q0 * q1 - 2 * q0 * ay - 4 * q1 + \
             8 * q1 * q1 * q1 + 8 * q1 * q2 * q2 - 4 * q1 * az
        s2 = 4 * q0 * q0 * q2 + 2 * q0 * ax + 4 * q2 * q3 * q3 - 2 * q3 * ay - 4 * q2 + \
             8 * q2 * q1 * q1 + 8 * q2 * q2 * q2 - 4 * q2 * az
        s3 = 4 * q1 * q1 * q3 - 2 * q1 * ax + 4 * q2 * q2 * q3 - 2 * q2 * ay

        norm = sqrt(s0 * s0 + s1 * s1 + s2 * s2 + s3 * s3)
        if norm > 0:
            s0, s1, s2, s3 = s0 / norm, s1 / norm, s2 / norm, s3 / norm

        qDot = np.array([
            0.5 * (-q1 * gx - q2 * gy - q3 * gz) - self.beta * s0,
            0.5 * (q0 * gx + q2 * gz - q3 * gy) - self.beta * s1,
            0.5 * (q0 * gy - q1 * gz + q3 * gx) - self.beta * s2,
            0.5 * (q0 * gz + q1 * gy - q2 * gx) - self.beta * s3,
        ])

        self.q = q + qDot * self.sample_period
        self.q /= np.linalg.norm(self.q)
        return self.q


# ------------------------------------------------------------------
# Quick demo (matches usage pattern in 14-ekf + 16)
# ------------------------------------------------------------------
if __name__ == "__main__":
    mad = MadgwickFilter(beta=0.033, sample_period=0.01)

    # Synthetic stationary + small rotation
    for i in range(50):
        # Almost still + tiny gyro
        gyro = np.array([0.0, 0.0, 0.002])
        accel = np.array([0.01, 0.02, 9.81])
        mag = np.array([20.0, 5.0, -40.0])   # fake local field
        mad.update(gyro, accel, mag)

    roll, pitch, yaw = mad.get_euler()
    print(f"Madgwick demo → roll={roll:.2f}° pitch={pitch:.2f}° heading={yaw:.2f}°")
    print("Heading (rad):", mad.get_heading_rad())
