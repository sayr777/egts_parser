"""
Extended Kalman Filter (EGTS_EKF) for GPS + IMU fusion (from 14-ekf-implementation.md)

Central component of the 3-layer architecture described in 13-sensor-fusion-architecture.md.
"""

import numpy as np
from dataclasses import dataclass


@dataclass
class EKFState:
    x: np.ndarray       # state vector
    P: np.ndarray       # covariance
    timestamp: float


class EGTS_EKF:
    """
    Extended Kalman Filter tuned for RTLS + IMU (transport / RNIС use-case).

    State: [lat, lon, vx, vy, heading, heading_bias]
    """

    def __init__(self, dt: float = 0.1):
        self.dt = float(dt)
        self.initialized = False

        self.x = np.zeros(6)
        self.P = np.eye(6) * 1000.0

        # Process noise (tuned per discussion 14 + vibration notes in 10)
        self.Q = np.diag([1e-6, 1e-6, 0.5, 0.5, 0.05, 0.001])

        # Measurement noise
        self.R_gps = np.diag([5e-5, 5e-5])      # ~5 m in WGS-84 degrees
        self.R_imu = np.diag([0.5, 0.5, 0.1])   # accel + heading

    def init(self, lat: float, lon: float, heading: float = 0.0):
        self.x = np.array([lat, lon, 0.0, 0.0, np.radians(heading), 0.0])
        self.P = np.diag([1e-6, 1e-6, 1.0, 1.0, 0.1, 0.01])
        self.initialized = True

    # ------------------------------------------------------------------
    # Predict (IMU dead-reckoning) — called at high rate (100 Hz)
    # ------------------------------------------------------------------
    def predict(self, accel_n: float = 0.0, accel_e: float = 0.0):
        """accel_n/e — North/East acceleration in m/s² after rotation by heading."""
        if not self.initialized:
            return

        dt = self.dt
        _, _, vx, vy, h, hb = self.x

        # Simple constant-velocity + heading model (non-linear because of heading)
        self.x[0] += vx * dt
        self.x[1] += vy * dt
        self.x[2] += accel_n * dt
        self.x[3] += accel_e * dt
        self.x[4] += hb * dt

        # Jacobian F
        F = np.eye(6)
        F[0, 2] = dt
        F[1, 3] = dt
        F[4, 5] = dt

        self.P = F @ self.P @ F.T + self.Q

    # ------------------------------------------------------------------
    # Updates
    # ------------------------------------------------------------------
    def update_gps(self, lat: float, lon: float):
        """GPS position correction (lower rate)."""
        if not self.initialized:
            self.init(lat, lon)
            return

        z = np.array([lat, lon])
        H = np.zeros((2, 6))
        H[0, 0] = 1.0
        H[1, 1] = 1.0

        y = z - H @ self.x
        S = H @ self.P @ H.T + self.R_gps
        K = self.P @ H.T @ np.linalg.inv(S)

        self.x = self.x + K @ y
        self.P = (np.eye(6) - K @ H) @ self.P

    def update_heading(self, heading_rad: float):
        """Heading correction from Madgwick (very important per discussions)."""
        if not self.initialized:
            return

        z = np.array([heading_rad])
        H = np.zeros((1, 6))
        H[0, 4] = 1.0

        y = z - H @ self.x
        # Normalize angle difference to [-pi, pi]
        y[0] = (y[0] + np.pi) % (2 * np.pi) - np.pi

        S = H @ self.P @ H.T + np.array([[self.R_imu[2, 2]]])
        K = self.P @ H.T @ np.linalg.inv(S)

        self.x = self.x + K @ y
        self.P = (np.eye(6) - K @ H) @ self.P

    # ------------------------------------------------------------------
    def get_state(self) -> dict:
        trace = float(np.trace(self.P))
        return {
            "lat": float(self.x[0]),
            "lon": float(self.x[1]),
            "speed_ms": float(np.hypot(self.x[2], self.x[3])),
            "heading": float(np.degrees(self.x[4]) % 360),
            "heading_bias_deg_s": float(np.degrees(self.x[5])),
            "confidence": float(1.0 / (1.0 + trace)),
            "cov_trace": trace,
        }


# ------------------------------------------------------------------
# Standalone smoke test (as shown in discussion 14)
# ------------------------------------------------------------------
if __name__ == "__main__":
    ekf = EGTS_EKF(dt=0.01)
    ekf.init(55.718, 37.439, heading=180.0)

    for i in range(20):
        # pretend small forward accel in body frame, rotated outside
        ekf.predict(accel_n=0.3, accel_e=0.0)
        if i % 5 == 0:
            ekf.update_gps(55.718 + i * 0.00001, 37.439 + i * 0.000005)
        ekf.update_heading(np.radians(180 + i * 0.1))

    st = ekf.get_state()
    print("EKF state after synthetic run:")
    for k, v in st.items():
        print(f"  {k}: {v:.6f}" if isinstance(v, float) else f"  {k}: {v}")
