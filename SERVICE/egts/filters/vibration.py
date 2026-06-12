"""
Vibration filtering and metrics for IMU data (from 10-vibration-filtering-algorithms.md)

Lightweight, no heavy deps beyond numpy/scipy.
Used as preprocessing before Madgwick (recommended in discussion 10 + 16).
"""

from __future__ import annotations
import numpy as np
from scipy.signal import butter, lfilter, medfilt


def butter_lowpass(cutoff: float, fs: float, order: int = 5):
    """Butterworth low-pass as shown in discussion 10."""
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    b, a = butter(order, normal_cutoff, btype="low", analog=False)
    return b, a


def butter_lowpass_filter(data: np.ndarray, cutoff: float = 10.0, fs: float = 100.0, order: int = 5) -> np.ndarray:
    """Alias expected by filters/__init__ and fusion code."""
    return lowpass_filter(data, cutoff, fs, order)


def lowpass_filter(data: np.ndarray, cutoff: float = 10.0, fs: float = 100.0, order: int = 5) -> np.ndarray:
    b, a = butter_lowpass(cutoff, fs, order)
    return lfilter(b, a, data)


def median_filter(data: np.ndarray, kernel_size: int = 5) -> np.ndarray:
    """Excellent for removing suspension impulse spikes (discussion 10)."""
    return medfilt(data, kernel_size=kernel_size)


def vibration_metrics(accel_xyz: np.ndarray, fs: float = 100.0) -> dict:
    """Alias for SRT 204 / fusion pipeline compatibility."""
    return compute_vibration_metrics(accel_xyz, fs)


def compute_vibration_metrics(accel_xyz: np.ndarray, fs: float = 100.0) -> dict:
    """
    Returns the fields proposed for SRT 204:
      vibration_rms, vibration_peak, dominant_frequency
    accel_xyz shape: (N, 3) or (3, N)
    """
    if accel_xyz.ndim == 1:
        accel_xyz = accel_xyz.reshape(-1, 1)
    if accel_xyz.shape[1] != 3:
        accel_xyz = accel_xyz.T

    # Overall magnitude
    mag = np.sqrt(np.sum(accel_xyz**2, axis=1))

    rms = float(np.sqrt(np.mean(mag**2)))
    peak = float(np.max(np.abs(mag)))

    # Very simple dominant freq via FFT (good enough for sandbox)
    if len(mag) > 8:
        fft_vals = np.fft.rfft(mag - np.mean(mag))
        freqs = np.fft.rfftfreq(len(mag), 1.0 / fs)
        idx = np.argmax(np.abs(fft_vals))
        dom_freq = float(freqs[idx])
    else:
        dom_freq = 0.0

    return {
        "vibration_rms": round(rms, 4),
        "vibration_peak": round(peak, 4),
        "dominant_freq_hz": round(dom_freq, 2),
    }


def filter_imu(accel: np.ndarray, gyro: np.ndarray, mag: np.ndarray,
               method: str = "lpf", fs: float = 100.0, cutoff: float = 12.0) -> dict:
    """
    Convenience wrapper.
    method: "none", "lpf", "median", "madgwick" (madgwick applied later)
    """
    out = {"method": method}
    if method == "lpf":
        out["accel"] = lowpass_filter(accel, cutoff=cutoff, fs=fs)
        out["gyro"] = lowpass_filter(gyro, cutoff=cutoff, fs=fs)
        out["mag"] = mag  # magnetometer usually not lowpassed the same way
    elif method == "median":
        out["accel"] = median_filter(accel)
        out["gyro"] = median_filter(gyro)
        out["mag"] = mag
    else:
        out["accel"] = accel
        out["gyro"] = gyro
        out["mag"] = mag

    vib = compute_vibration_metrics(out["accel"] if out["accel"].ndim > 1 else out["accel"][:, None], fs=fs)
    out.update(vib)
    return out


# Self-test
if __name__ == "__main__":
    np.random.seed(42)
    t = np.linspace(0, 2, 200)
    # Fake 10 Hz vibration + slow motion
    accel = np.stack([
        0.1 * np.sin(2 * np.pi * 10 * t) + 0.02 * np.random.randn(200),
        0.05 * np.sin(2 * np.pi * 10 * t + 1) + 0.02 * np.random.randn(200),
        9.8 + 0.08 * np.sin(2 * np.pi * 10 * t + 2)
    ], axis=1)

    metrics = compute_vibration_metrics(accel)
    print("Vibration metrics (raw):", metrics)

    filt = filter_imu(accel, np.zeros_like(accel), np.zeros_like(accel), method="lpf", fs=100.0, cutoff=8.0)
    print("After LPF rms:", filt["vibration_rms"])
