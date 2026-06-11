"""
SRT 205 — EGTS_SR_LBS_DATA (proposed based on discussion 18-lbs-road-graph-positioning.md)

Clean dataclass + encode/decode following the style of SrCustom200–204.

Purpose: Carry cellular base station data (Cell ID, LAC/TAC, RSSI, Timing Advance, neighbors)
so that the server-side fusion / map-matching layer can use it for precise road snapping
when GNSS is weak or unavailable.

This complements SRT 200 (RTLS position) and SRT 204 (inertial data).
"""

from __future__ import annotations
import struct
from dataclasses import dataclass, field, asdict
from typing import List, Dict


@dataclass
class NeighborCell:
    cell_id: int = 0
    rssi_dbm: int = 0   # negative dBm, e.g. -85


@dataclass
class SrCustom205:
    """
    LBS (cellular) data for EGTS RTLS v2.

    Fields chosen for compactness and usefulness in LBS-aware map matching.
    """
    SRT: int = field(default=205, init=False, repr=False)

    # Serving cell
    serving_cell_id: int = 0
    lac_tac: int = 0
    mcc: int = 0
    mnc: int = 0
    rssi_dbm: int = 0          # e.g. -85
    timing_advance: int = 0    # raw TA value (units depend on technology)
    bs_lat: float = 0.0        # known location of serving BS (if available in terminal)
    bs_lon: float = 0.0

    # Neighbors (up to 4 for demo; real implementations may vary)
    neighbors: List[NeighborCell] = field(default_factory=list)

    # Optional raw LBS position computed on device (if the modem does it)
    raw_lbs_lat: float = 0.0
    raw_lbs_lon: float = 0.0

    # Quality / metadata
    lbs_quality: int = 0       # 0-100 or vendor specific
    technology: int = 0        # 0=unknown, 1=GSM, 2=UMTS, 3=LTE, 4=5G
    flags: int = 0
    timestamp: int = 0

    raw_hex: str = ""
    _raw_bytes: bytes = field(default=b"", repr=False)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("_raw_bytes", None)
        d["neighbors"] = [asdict(n) for n in self.neighbors]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "SrCustom205":
        known = {k for k in cls.__dataclass_fields__ if k not in ("SRT", "_raw_bytes")}
        filtered = {k: v for k, v in d.items() if k in known}
        if "neighbors" in filtered:
            filtered["neighbors"] = [NeighborCell(**n) if isinstance(n, dict) else n
                                     for n in filtered["neighbors"]]
        return cls(**filtered)

    # ------------------------------------------------------------------
    # Binary layout (compact, variable-length neighbors)
    # Layout idea (for sandbox):
    # serving_cell_id(4) lac_tac(2) mcc(2) mnc(2)
    # rssi(1) ta(2) bs_lat(4) bs_lon(4)   [floats * 1e7 as int32]
    # num_neighbors(1)
    # [for each: cell_id(4) rssi(1)]
    # raw_lbs_lat/lon (4+4)
    # quality(1) tech(1) flags(1) ts(4)
    # Total base ~ 40 bytes + 5*num_neighbors
    # ------------------------------------------------------------------

    @classmethod
    def from_bytes(cls, data: bytes) -> "SrCustom205":
        obj = cls(raw_hex=data.hex().upper(), _raw_bytes=data)
        if len(data) < 30:
            return obj

        off = 0
        obj.serving_cell_id = struct.unpack_from("<I", data, off)[0]; off += 4
        obj.lac_tac = struct.unpack_from("<H", data, off)[0]; off += 2
        obj.mcc = struct.unpack_from("<H", data, off)[0]; off += 2
        obj.mnc = struct.unpack_from("<H", data, off)[0]; off += 2

        obj.rssi_dbm = struct.unpack_from("<b", data, off)[0]; off += 1
        obj.timing_advance = struct.unpack_from("<H", data, off)[0]; off += 2

        blat, blon = struct.unpack_from("<ii", data, off); off += 8
        obj.bs_lat = blat / 1e7
        obj.bs_lon = blon / 1e7

        num_n = data[off]; off += 1
        for _ in range(min(num_n, 8)):  # safety
            if off + 5 > len(data):
                break
            cid = struct.unpack_from("<I", data, off)[0]; off += 4
            r = struct.unpack_from("<b", data, off)[0]; off += 1
            obj.neighbors.append(NeighborCell(cid, r))

        if off + 8 <= len(data):
            rlat, rlon = struct.unpack_from("<ii", data, off); off += 8
            obj.raw_lbs_lat = rlat / 1e7
            obj.raw_lbs_lon = rlon / 1e7

        if off + 7 <= len(data):
            obj.lbs_quality = data[off]; off += 1
            obj.technology = data[off]; off += 1
            obj.flags = data[off]; off += 1
            obj.timestamp = struct.unpack_from("<I", data, off)[0]

        return obj

    def to_bytes(self) -> bytes:
        out = struct.pack("<IHHH", self.serving_cell_id, self.lac_tac, self.mcc, self.mnc)
        out += struct.pack("<bH", int(self.rssi_dbm), int(self.timing_advance))
        blat = int(self.bs_lat * 1e7)
        blon = int(self.bs_lon * 1e7)
        out += struct.pack("<ii", blat, blon)

        num_n = min(len(self.neighbors), 8)
        out += bytes([num_n])
        for n in self.neighbors[:num_n]:
            out += struct.pack("<I b", n.cell_id, n.rssi_dbm)

        rlat = int(self.raw_lbs_lat * 1e7)
        rlon = int(self.raw_lbs_lon * 1e7)
        out += struct.pack("<ii", rlat, rlon)

        out += struct.pack("<BBBBI",
                           self.lbs_quality & 0xFF,
                           self.technology & 0xFF,
                           self.flags & 0xFF,
                           0,  # reserved
                           self.timestamp & 0xFFFFFFFF)

        self._raw_bytes = out
        self.raw_hex = out.hex().upper()
        return out


# ------------------------------------------------------------------
# Quick self-test
# ------------------------------------------------------------------
if __name__ == "__main__":
    n1 = NeighborCell(2001, -92)
    n2 = NeighborCell(2002, -105)

    s = SrCustom205(
        serving_cell_id=1001,
        lac_tac=12345,
        mcc=250, mnc=1,
        rssi_dbm=-78,
        timing_advance=3,
        bs_lat=55.7185, bs_lon=37.4398,
        neighbors=[n1, n2],
        raw_lbs_lat=55.7183, raw_lbs_lon=37.4399,
        lbs_quality=65,
        technology=3,  # LTE
        timestamp=123456
    )

    b = s.to_bytes()
    print("SRT205 bytes len:", len(b))
    print("hex head:", s.raw_hex[:80])

    s2 = SrCustom205.from_bytes(b)
    print("Roundtrip serving_cell:", s2.serving_cell_id)
    print("Roundtrip rssi:", s2.rssi_dbm)
    print("Roundtrip neighbors:", len(s2.neighbors))
    print("Roundtrip raw_lbs:", s2.raw_lbs_lat, s2.raw_lbs_lon)
    print("Dict sample keys:", list(s2.to_dict().keys())[:8])