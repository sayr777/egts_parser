"""
SRT 204 — EGTS_SR_INERTIAL_DATA (proposed in 09-inertial-sensors-egts.md)

Clean, self-contained dataclass + encode/decode following the exact style
of the existing SrCustom200/201/202/203 in SERVICE/egts/models.py

This is the "vendor extension" record for IMU + heading + quality metrics.
"""

from __future__ import annotations
import struct
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from typing import Any

# Reuse the project's epoch if you want full compatibility.
# For sandbox we keep it local.
EPOCH = datetime(2010, 1, 1, tzinfo=timezone.utc)


@dataclass
class SrCustom204:
    """
    Proposed SRT 204 — Inertial / Orientation data for EGTS RTLS v2.

    Fields taken directly from discussion 09 + enriched with practical
    outputs from fusion (14, 16) and vibration (10).

    All units chosen for compactness when serialized into EGTS subrecord.
    """
    SRT: int = field(default=204, init=False, repr=False)

    # --- Core orientation (from Madgwick) ---
    heading_deg: float = 0.0          # 0-359.99 (yaw)
    roll_deg: float = 0.0
    pitch_deg: float = 0.0
    heading_accuracy_deg: float = 5.0

    # --- Raw / filtered IMU (body frame) ---
    accel_x: float = 0.0              # m/s² or g (document in flags)
    accel_y: float = 0.0
    accel_z: float = 0.0
    gyro_x: float = 0.0               # rad/s
    gyro_y: float = 0.0
    gyro_z: float = 0.0

    # --- Optional magnetometer (for diagnostics / calibration) ---
    mag_x: float = 0.0                # µT or normalized
    mag_y: float = 0.0
    mag_z: float = 0.0

    # --- Vibration & quality (from 10-vibration-filtering-algorithms.md) ---
    vibration_rms: float = 0.0        # overall or per-axis aggregate
    vibration_peak: float = 0.0
    dominant_freq_hz: float = 0.0
    filter_type: int = 0              # 0=none, 1=lpf, 2=madgwick, 3=ekf, 4=hybrid

    # --- Fusion outputs (from 13/14) ---
    ekf_confidence: float = 0.0       # 0..1 (or use 1/(1+cov_trace))
    cov_trace: float = 0.0
    road_segment_id: int = 0          # after map matching (08/15)
    matched_lat: float = 0.0
    matched_lon: float = 0.0
    snap_confidence: float = 0.0      # 0..1

    # --- Misc ---
    flags: int = 0                    # bitfield: calibrated, mag_disturbance, using_gps, etc.
    timestamp: int = 0                # seconds since EGTS EPOCH (or ms)
    raw_hex: str = ""

    # --- Internal for roundtrip ---
    _raw_bytes: bytes = field(default=b"", repr=False)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("_raw_bytes", None)
        # Add human-friendly derived values
        d["heading"] = round(self.heading_deg, 2)
        d["roll"] = round(self.roll_deg, 2)
        d["pitch"] = round(self.pitch_deg, 2)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "SrCustom204":
        known = {k for k in cls.__dataclass_fields__ if k not in ("SRT", "_raw_bytes")}
        filtered = {k: v for k, v in d.items() if k in known}
        return cls(**filtered)

    # ------------------------------------------------------------------
    # Binary (for future integration into codec.py / models.py)
    # Compact layout (example — tune as needed for real SRT 204 spec)
    # ------------------------------------------------------------------
    # Layout idea (variable, we use a generous fixed for sandbox):
    # heading(2), roll(2), pitch(2), h_acc(2)   [all *100 → int16]
    # accel[3](3*2), gyro[3](3*2)               int16 scaled
    # vib_rms(2), vib_peak(2), dom_freq(2), filter(1), conf(1), cov(4)
    # road_id(4), matched_lat/lon (scaled), snap_conf(1), flags(1), ts(4)
    # Total ~ 2+2+2+2 +6+6 +2+2+2+1+1+4 +4 +8 +1+1+4 ≈ 50 bytes (fits nicely)

    @classmethod
    def from_bytes(cls, data: bytes) -> "SrCustom204":
        obj = cls(_raw_bytes=data, raw_hex=data.hex().upper())
        if len(data) < 8:
            return obj

        off = 0
        # Orientation * 0.01 deg
        if len(data) >= off + 8:
            h, r, p, ha = struct.unpack_from("<hhhh", data, off)
            obj.heading_deg = h / 100.0
            obj.roll_deg = r / 100.0
            obj.pitch_deg = p / 100.0
            obj.heading_accuracy_deg = ha / 100.0
            off += 8

        # Accel & Gyro (scaled by 100 for m/s2 / 0.01 rad/s example)
        if len(data) >= off + 12:
            ax, ay, az, gx, gy, gz = struct.unpack_from("<hhhhhh", data, off)
            obj.accel_x = ax / 100.0
            obj.accel_y = ay / 100.0
            obj.accel_z = az / 100.0
            obj.gyro_x = gx / 100.0
            obj.gyro_y = gy / 100.0
            obj.gyro_z = gz / 100.0
            off += 12

        if len(data) >= off + 8:
            vrms, vpeak, dfreq, ftype, conf8 = struct.unpack_from("<HHHB B", data, off)
            obj.vibration_rms = vrms / 100.0
            obj.vibration_peak = vpeak / 100.0
            obj.dominant_freq_hz = dfreq / 10.0
            obj.filter_type = ftype
            obj.ekf_confidence = conf8 / 255.0
            off += 8

        if len(data) >= off + 4:
            obj.cov_trace = struct.unpack_from("<f", data, off)[0]
            off += 4

        if len(data) >= off + 4:
            obj.road_segment_id = struct.unpack_from("<I", data, off)[0]
            off += 4

        if len(data) >= off + 9:
            mlat, mlon = struct.unpack_from("<ii", data, off)  # scaled 1e7 like many GNSS
            obj.matched_lat = mlat / 1e7
            obj.matched_lon = mlon / 1e7
            obj.snap_confidence = data[off+8] / 255.0
            off += 9

        if len(data) >= off + 6:
            obj.flags = data[off]
            obj.timestamp = struct.unpack_from("<I", data, off+1)[0]
            # mag etc can be added in future layout

        return obj

    def to_bytes(self) -> bytes:
        # Build compact representation (see from_bytes for layout)
        h = max(-32767, min(32767, int(self.heading_deg * 100)))
        r = max(-32767, min(32767, int(self.roll_deg * 100)))
        p = max(-32767, min(32767, int(self.pitch_deg * 100)))
        ha = max(-32767, min(32767, int(self.heading_accuracy_deg * 100)))

        ax = max(-32767, min(32767, int(self.accel_x * 100)))
        ay = max(-32767, min(32767, int(self.accel_y * 100)))
        az = max(-32767, min(32767, int(self.accel_z * 100)))
        gx = max(-32767, min(32767, int(self.gyro_x * 100)))
        gy = max(-32767, min(32767, int(self.gyro_y * 100)))
        gz = max(-32767, min(32767, int(self.gyro_z * 100)))

        vrms = int(self.vibration_rms * 100) & 0xFFFF
        vpk = int(self.vibration_peak * 100) & 0xFFFF
        df = int(self.dominant_freq_hz * 10) & 0xFFFF
        ftype = self.filter_type & 0xFF
        conf8 = int(max(0, min(1, self.ekf_confidence)) * 255) & 0xFF

        cov = struct.pack("<f", float(self.cov_trace))

        road = struct.pack("<I", self.road_segment_id & 0xFFFFFFFF)

        mlat = int(self.matched_lat * 1e7) & 0xFFFFFFFF
        mlon = int(self.matched_lon * 1e7) & 0xFFFFFFFF
        snapc = int(max(0, min(1, self.snap_confidence)) * 255) & 0xFF

        flags = self.flags & 0xFF
        ts = self.timestamp & 0xFFFFFFFF

        # Orientation block
        out = struct.pack("<hhhh", h, r, p, ha)  # signed short, values clamped above
        # IMU
        out += struct.pack("<hhhhhh", ax, ay, az, gx, gy, gz)
        # Vib + filter + conf
        out += struct.pack("<HHHB B", vrms, vpk, df, ftype, conf8)
        out += cov
        out += road
        out += struct.pack("<iiB", mlat, mlon, snapc)
        out += struct.pack("<BI", flags, ts)

        self._raw_bytes = out
        self.raw_hex = out.hex().upper()
        return out


# ------------------------------------------------------------------
# Quick self-test (run this file directly)
# ------------------------------------------------------------------
if __name__ == "__main__":
    s = SrCustom204(
        heading_deg=87.34,
        roll_deg=-1.2,
        pitch_deg=0.8,
        accel_x=0.12, accel_y=-0.03, accel_z=9.81,
        gyro_z=0.01,
        vibration_rms=0.45,
        ekf_confidence=0.92,
        matched_lat=55.7182, matched_lon=37.4397,
        snap_confidence=0.87,
        filter_type=3,
        timestamp=123456789
    )
    b = s.to_bytes()
    print("SRT204 bytes len:", len(b))
    print("hex:", s.raw_hex[:60], "...")

    s2 = SrCustom204.from_bytes(b)
    print("Roundtrip heading:", s2.heading_deg)
    print("Roundtrip matched_lat:", s2.matched_lat)
    print("Roundtrip confidence:", s2.ekf_confidence)
    print("Dict sample:", {k: s2.to_dict()[k] for k in ["heading", "ekf_confidence", "road_segment_id"]})
