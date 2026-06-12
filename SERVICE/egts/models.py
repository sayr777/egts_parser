"""
Модели данных EGTS — dataclasses с методами encode() / decode().

Каждый класс:
  • from_bytes(data) -> экземпляр  (decode)
  • to_bytes()       -> bytes       (encode)
  • to_dict()        -> dict        (JSON-сериализация)
  • from_dict(d)     -> экземпляр  (восстановление из dict для re-encode)
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from typing import Any, List

from .const import EPOCH, RESULT_CODES, SRT_NAMES, SVC_NAMES, SRT_CUSTOM_200, SRT_CUSTOM_201, SRT_CUSTOM_202, SRT_CUSTOM_203, SRT_CUSTOM_204

# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class EGTSError(Exception):
    pass


class _Base:
    def to_dict(self) -> dict:
        return asdict(self)  # type: ignore[call-arg]

    @classmethod
    def from_dict(cls, d: dict):
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})  # type: ignore

    def to_bytes(self) -> bytes:
        raise NotImplementedError

    @classmethod
    def from_bytes(cls, data: bytes):
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

@dataclass
class Header(_Base):
    protocol_version:   int = 1       # PRV
    security_key_id:    int = 0       # SKID
    prefix:             str = "00"    # PRF (2 bits)
    route:              str = "0"     # RTE (1 bit) — маршрутизация
    encryption_alg:     str = "00"    # ENA (2 bits)
    compression:        str = "0"     # CMP (1 bit)
    priority:           str = "00"    # PR  (2 bits)
    header_encoding:    int = 0       # HE
    frame_data_length:  int = 0       # FDL (auto)
    packet_id:          int = 0       # PID
    packet_type:        int = 1       # PT
    peer_address:       int = 0       # PRA (только при RTE=1)
    recipient_address:  int = 0       # RCA (только при RTE=1)
    time_to_live:       int = 0       # TTL (только при RTE=1)
    # computed
    header_length:      int = 0       # HL (auto)
    header_crc:         int = 0       # HCS (auto)

    @property
    def routed(self) -> bool:
        return self.route == "1"

    @property
    def _header_len(self) -> int:
        return 16 if self.routed else 11

    @classmethod
    def from_bytes(cls, data: bytes) -> tuple["Header", int]:
        """Returns (Header, bytes_consumed)."""
        if len(data) < 11:
            raise EGTSError(f"Header too short: {len(data)}")
        h = cls()
        h.protocol_version = data[0]
        h.security_key_id  = data[1]
        flags = data[2]
        bits  = f"{flags:08b}"
        h.prefix          = bits[0:2]
        h.route           = bits[2]
        h.encryption_alg  = bits[3:5]
        h.compression     = bits[5]
        h.priority        = bits[6:8]
        h.header_length   = data[3]
        h.header_encoding = data[4]
        h.frame_data_length = struct.unpack_from("<H", data, 5)[0]
        h.packet_id         = struct.unpack_from("<H", data, 7)[0]
        h.packet_type       = data[9]
        off = 10
        if h.routed:
            if len(data) < 16:
                raise EGTSError("Routed header too short")
            h.peer_address      = struct.unpack_from("<H", data, off)[0]; off += 2
            h.recipient_address = struct.unpack_from("<H", data, off)[0]; off += 2
            h.time_to_live      = data[off]; off += 1
        h.header_crc = data[off]
        return h, h.header_length

    def to_bytes(self, sfrd: bytes = b"") -> bytes:
        from .crc import crc8 as _crc8, crc16 as _crc16
        flags = int(self.prefix + self.route + self.encryption_alg + self.compression + self.priority, 2)
        hl = self._header_len
        self.frame_data_length = len(sfrd)
        buf = bytearray()
        buf += bytes([self.protocol_version, self.security_key_id, flags, hl, self.header_encoding])
        buf += struct.pack("<HHB", self.frame_data_length, self.packet_id, self.packet_type)
        if self.routed:
            buf += struct.pack("<HHB", self.peer_address, self.recipient_address, self.time_to_live)
        buf.append(_crc8(buf))
        buf += sfrd
        if sfrd:
            buf += struct.pack("<H", _crc16(sfrd))
        return bytes(buf)

    def to_dict(self) -> dict:
        return {
            "PRV":  self.protocol_version,
            "SKID": self.security_key_id,
            "PRF":  self.prefix,
            "RTE":  self.route,
            "ENA":  self.encryption_alg,
            "CMP":  self.compression,
            "PR":   self.priority,
            "HL":   self.header_length,
            "HE":   self.header_encoding,
            "FDL":  self.frame_data_length,
            "PID":  self.packet_id,
            "PT":   self.packet_type,
            "PRA":  self.peer_address,
            "RCA":  self.recipient_address,
            "TTL":  self.time_to_live,
            "HCS":  self.header_crc,
        }


# ---------------------------------------------------------------------------
# Subrecord base
# ---------------------------------------------------------------------------

class _Subrecord:
    SRT: int = -1

    def to_bytes(self) -> bytes:
        raise NotImplementedError

    @classmethod
    def from_bytes(cls, data: bytes) -> "_Subrecord":
        raise NotImplementedError

    def to_dict(self) -> dict:
        return asdict(self)  # type: ignore[call-arg]

    @classmethod
    def from_dict(cls, d: dict) -> "_Subrecord":
        fields = {f for f in cls.__dataclass_fields__}  # type: ignore
        return cls(**{k: v for k, v in d.items() if k in fields})


def _u24le(val: int) -> bytes:
    return struct.pack("<I", val & 0xFFFFFF)[:3]


def _read_u24le(data: bytes, off: int) -> int:
    return struct.unpack("<I", data[off:off+3] + b"\x00")[0]


# ---------------------------------------------------------------------------
# SRT 0 — EGTS_SR_RECORD_RESPONSE
# ---------------------------------------------------------------------------

@dataclass
class SrRecordResponse(_Subrecord):
    SRT: int = field(default=0, init=False, repr=False)
    confirmed_record_number: int = 0   # CRN
    record_status:           int = 0   # RST

    @classmethod
    def from_bytes(cls, data: bytes) -> "SrRecordResponse":
        if len(data) < 3:
            raise EGTSError("SrRecordResponse: too short")
        return cls(
            confirmed_record_number=struct.unpack_from("<H", data, 0)[0],
            record_status=data[2],
        )

    def to_bytes(self) -> bytes:
        return struct.pack("<HB", self.confirmed_record_number, self.record_status)

    def to_dict(self) -> dict:
        return {
            "CRN": self.confirmed_record_number,
            "RST": self.record_status,
            "RST_desc": RESULT_CODES.get(self.record_status, f"unknown({self.record_status})"),
        }


# ---------------------------------------------------------------------------
# SRT 1 — EGTS_SR_TERM_IDENTITY
# ---------------------------------------------------------------------------

@dataclass
class SrTermIdentity(_Subrecord):
    SRT: int = field(default=1, init=False, repr=False)
    terminal_id:  int = 0    # TID
    home_dispatcher_id: int | None = None  # HDID
    imei:  str | None = None
    imsi:  str | None = None
    lang:  str | None = None
    nid:   str | None = None
    buffer_size: int | None = None  # BS
    mobile_number: str | None = None  # MN

    @classmethod
    def from_bytes(cls, data: bytes) -> "SrTermIdentity":
        if len(data) < 5:
            raise EGTSError("SrTermIdentity: too short")
        tid  = struct.unpack_from("<I", data, 0)[0]
        flg  = data[4]
        bits = f"{flg:08b}"
        hdid_e, imei_e, imsi_e, lngc_e, nid_e, bs_e, mn_e = (
            bits[7], bits[6], bits[5], bits[4], bits[3], bits[2], bits[1]
        )
        off = 5
        obj = cls(terminal_id=tid)
        if hdid_e == "1" and off + 2 <= len(data):
            obj.home_dispatcher_id = struct.unpack_from("<H", data, off)[0]; off += 2
        if imei_e == "1" and off + 15 <= len(data):
            obj.imei = data[off:off+15].decode("ascii", errors="replace").rstrip("\x00"); off += 15
        if imsi_e == "1" and off + 16 <= len(data):
            obj.imsi = data[off:off+16].decode("ascii", errors="replace").rstrip("\x00"); off += 16
        if lngc_e == "1" and off + 3 <= len(data):
            obj.lang = data[off:off+3].decode("ascii", errors="replace").rstrip("\x00"); off += 3
        if nid_e  == "1" and off + 3 <= len(data):
            obj.nid  = data[off:off+3].hex().upper(); off += 3
        if bs_e   == "1" and off + 2 <= len(data):
            obj.buffer_size = struct.unpack_from("<H", data, off)[0]; off += 2
        if mn_e   == "1" and off + 15 <= len(data):
            obj.mobile_number = data[off:off+15].decode("ascii", errors="replace").rstrip("\x00")
        return obj

    def to_bytes(self) -> bytes:
        buf = bytearray(struct.pack("<I", self.terminal_id))
        hdid_e = int(self.home_dispatcher_id is not None)
        imei_e = int(self.imei is not None)
        imsi_e = int(self.imsi is not None)
        lngc_e = int(self.lang is not None)
        nid_e  = int(self.nid  is not None)
        bs_e   = int(self.buffer_size is not None)
        mn_e   = int(self.mobile_number is not None)
        flags  = int(f"0{mn_e}{bs_e}{nid_e}{lngc_e}{imsi_e}{imei_e}{hdid_e}", 2)
        buf.append(flags)
        if self.home_dispatcher_id is not None:
            buf += struct.pack("<H", self.home_dispatcher_id)
        if self.imei:
            buf += self.imei.encode("ascii", errors="replace").ljust(15, b"\x00")[:15]
        if self.imsi:
            buf += self.imsi.encode("ascii", errors="replace").ljust(16, b"\x00")[:16]
        if self.lang:
            buf += self.lang.encode("ascii", errors="replace").ljust(3, b"\x00")[:3]
        if self.nid:
            buf += bytes.fromhex(self.nid)[:3]
        if self.buffer_size is not None:
            buf += struct.pack("<H", self.buffer_size)
        if self.mobile_number:
            buf += self.mobile_number.encode("ascii", errors="replace").ljust(15, b"\x00")[:15]
        return bytes(buf)

    def to_dict(self) -> dict:
        return {k: v for k, v in {
            "TID": self.terminal_id,
            "HDID": self.home_dispatcher_id,
            "IMEI": self.imei,
            "IMSI": self.imsi,
            "LNGC": self.lang,
            "NID":  self.nid,
            "BS":   self.buffer_size,
            "MN":   self.mobile_number,
        }.items() if v is not None}


# ---------------------------------------------------------------------------
# SRT 7 — EGTS_SR_AUTH_INFO
# ---------------------------------------------------------------------------

@dataclass
class SrAuthInfo(_Subrecord):
    SRT: int = field(default=7, init=False, repr=False)
    user_name:     str = ""
    user_password: str = ""

    @classmethod
    def from_bytes(cls, data: bytes) -> "SrAuthInfo":
        obj = cls()
        if len(data) < 1:
            return obj
        unh_len = data[0]
        obj.user_name = data[1:1+unh_len].decode("utf-8", errors="replace")
        off = 1 + unh_len
        if off < len(data):
            pwd_len = data[off]
            obj.user_password = data[off+1:off+1+pwd_len].decode("utf-8", errors="replace")
        return obj

    def to_bytes(self) -> bytes:
        enc_u = self.user_name.encode("utf-8")
        enc_p = self.user_password.encode("utf-8")
        return bytes([len(enc_u)]) + enc_u + bytes([len(enc_p)]) + enc_p

    def to_dict(self) -> dict:
        return {"UNH": self.user_name, "SS": self.user_password}


# ---------------------------------------------------------------------------
# SRT 9 — EGTS_SR_RESULT_CODE
# ---------------------------------------------------------------------------

@dataclass
class SrResultCode(_Subrecord):
    SRT: int = field(default=9, init=False, repr=False)
    result_code: int = 0

    @classmethod
    def from_bytes(cls, data: bytes) -> "SrResultCode":
        return cls(result_code=data[0] if data else 0)

    def to_bytes(self) -> bytes:
        return bytes([self.result_code])

    def to_dict(self) -> dict:
        return {
            "RCD": self.result_code,
            "RCD_desc": RESULT_CODES.get(self.result_code, f"unknown({self.result_code})"),
        }


# ---------------------------------------------------------------------------
# SRT 5 — EGTS_SR_DISPATCHER_IDENTITY
# ---------------------------------------------------------------------------

@dataclass
class SrDispatcherIdentity(_Subrecord):
    SRT: int = field(default=5, init=False, repr=False)
    dispatcher_id:   int = 0
    dispatcher_type: int = 0
    description: str = ""

    @classmethod
    def from_bytes(cls, data: bytes) -> "SrDispatcherIdentity":
        if len(data) < 5:
            return cls()
        did = struct.unpack_from("<I", data, 0)[0]
        dt  = data[4]
        dscr = data[5:].decode("utf-8", errors="replace").rstrip("\x00") if len(data) > 5 else ""
        return cls(dispatcher_id=did, dispatcher_type=dt, description=dscr)

    def to_bytes(self) -> bytes:
        buf = struct.pack("<IB", self.dispatcher_id, self.dispatcher_type)
        if self.description:
            buf += self.description.encode("utf-8")
        return buf

    def to_dict(self) -> dict:
        return {"DID": self.dispatcher_id, "DT": self.dispatcher_type, "DSCR": self.description}


# ---------------------------------------------------------------------------
# SRT 16 — EGTS_SR_POS_DATA
# ---------------------------------------------------------------------------

@dataclass
class SrPosData(_Subrecord):
    SRT: int = field(default=16, init=False, repr=False)
    # Время навигации (datetime UTC)
    navigation_time: datetime = field(default_factory=lambda: EPOCH)
    # Координаты (градусы, со знаком)
    latitude:  float = 0.0
    longitude: float = 0.0
    # Флаги
    altitude_exists: bool = False   # ALTE
    speed_kmh:       float = 0.0   # SPD (0.1 км/ч дискретность)
    direction_deg:   int = 0        # DIR (0-359)
    odometer_km:     float = 0.0   # ODM (0.1 км дискретность)
    digital_inputs:  int = 0        # DIN
    source:          int = 0        # SRC
    altitude_m:      int = 0        # ALT (при altitude_exists)
    fix_3d:          bool = False   # FIX: False=2D True=3D
    valid:           bool = True    # VLD
    in_motion:       bool = False   # MV
    black_box:       bool = False   # BB
    cs_wgs84:        bool = True    # CS: True=WGS-84
    source_data:     int = 0        # SRCD

    @classmethod
    def from_bytes(cls, data: bytes) -> "SrPosData":
        if len(data) < 21:
            raise EGTSError(f"SrPosData: too short ({len(data)})")
        obj = cls()
        ntm_raw = struct.unpack_from("<I", data, 0)[0]
        obj.navigation_time = EPOCH + timedelta(seconds=ntm_raw)

        lat_raw = struct.unpack_from("<I", data, 4)[0]
        lon_raw = struct.unpack_from("<I", data, 8)[0]
        obj.latitude  = lat_raw * 90.0  / 0xFFFFFFFF
        obj.longitude = lon_raw * 180.0 / 0xFFFFFFFF

        flags = data[12]
        bits  = f"{flags:08b}"
        obj.altitude_exists = bits[0] == "1"
        lohs = bits[1] == "1"
        lahs = bits[2] == "1"
        obj.in_motion  = bits[3] == "1"
        obj.black_box  = bits[4] == "1"
        obj.cs_wgs84   = bits[5] == "0"
        obj.fix_3d     = bits[6] == "1"
        obj.valid      = bits[7] == "1"

        if lohs: obj.longitude = -obj.longitude
        if lahs: obj.latitude  = -obj.latitude

        spd_raw = struct.unpack_from("<H", data, 13)[0]
        dir_high   = (spd_raw >> 15) & 0x1
        alt_sign   = (spd_raw >> 14) & 0x1
        obj.speed_kmh   = (spd_raw & 0x3FFF) / 10.0
        obj.direction_deg = data[15] | (dir_high << 7)

        odm_raw = _read_u24le(data, 16)
        obj.odometer_km = odm_raw / 10.0

        obj.digital_inputs = data[19]
        obj.source         = data[20]

        off = 21
        if obj.altitude_exists and len(data) >= off + 3:
            alt_val = _read_u24le(data, off); off += 3
            obj.altitude_m = -int(alt_val) if alt_sign else int(alt_val)
        if len(data) >= off + 2:
            obj.source_data = struct.unpack_from("<h", data, off)[0]
        return obj

    def to_bytes(self) -> bytes:
        buf = bytearray()
        ntm = int((self.navigation_time - EPOCH).total_seconds())
        buf += struct.pack("<I", max(0, ntm))

        lat_abs = abs(self.latitude)
        lon_abs = abs(self.longitude)
        buf += struct.pack("<I", int(lat_abs / 90.0 * 0xFFFFFFFF))
        buf += struct.pack("<I", int(lon_abs / 180.0 * 0xFFFFFFFF))

        alte = int(self.altitude_exists)
        lohs = int(self.longitude < 0)
        lahs = int(self.latitude  < 0)
        mv   = int(self.in_motion)
        bb   = int(self.black_box)
        cs   = int(not self.cs_wgs84)
        fix  = int(self.fix_3d)
        vld  = int(self.valid)
        flags = int(f"{alte}{lohs}{lahs}{mv}{bb}{cs}{fix}{vld}", 2)
        buf.append(flags)

        spd_raw = int(self.speed_kmh * 10) & 0x3FFF
        dir_high = (self.direction_deg >> 7) & 0x1
        alt_sign = int(self.altitude_m < 0)
        spd_raw |= (dir_high << 15) | (alt_sign << 14)
        buf += struct.pack("<H", spd_raw)
        buf.append(self.direction_deg & 0x7F)

        odm = int(self.odometer_km * 10)
        buf += _u24le(odm)
        buf.append(self.digital_inputs & 0xFF)
        buf.append(self.source & 0xFF)

        if self.altitude_exists:
            buf += _u24le(abs(self.altitude_m))
        buf += struct.pack("<h", self.source_data)
        return bytes(buf)

    def to_dict(self) -> dict:
        return {
            "NTM": self.navigation_time.isoformat(),
            "LAT": round(self.latitude, 7),
            "LONG": round(self.longitude, 7),
            "ALTE": int(self.altitude_exists),
            "VLD": int(self.valid),
            "FIX": int(self.fix_3d),
            "MV": int(self.in_motion),
            "BB": int(self.black_box),
            "CS_WGS84": int(self.cs_wgs84),
            "SPD_kmh": self.speed_kmh,
            "DIR_deg": self.direction_deg,
            "ODM_km": self.odometer_km,
            "DIN": self.digital_inputs,
            "SRC": self.source,
            "ALT_m": self.altitude_m,
            "SRCD": self.source_data,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SrPosData":
        obj = cls()
        if "NTM" in d:
            obj.navigation_time = datetime.fromisoformat(d["NTM"])
        obj.latitude       = float(d.get("LAT", 0))
        obj.longitude      = float(d.get("LONG", 0))
        obj.altitude_exists = bool(int(d.get("ALTE", 0)))
        obj.valid          = bool(int(d.get("VLD", 1)))
        obj.fix_3d         = bool(int(d.get("FIX", 0)))
        obj.in_motion      = bool(int(d.get("MV", 0)))
        obj.black_box      = bool(int(d.get("BB", 0)))
        obj.cs_wgs84       = bool(int(d.get("CS_WGS84", 1)))
        obj.speed_kmh      = float(d.get("SPD_kmh", 0))
        obj.direction_deg  = int(d.get("DIR_deg", 0))
        obj.odometer_km    = float(d.get("ODM_km", 0))
        obj.digital_inputs = int(d.get("DIN", 0))
        obj.source         = int(d.get("SRC", 0))
        obj.altitude_m     = int(d.get("ALT_m", 0))
        obj.source_data    = int(d.get("SRCD", 0))
        return obj


# ---------------------------------------------------------------------------
# SRT 17 — EGTS_SR_EXT_POS_DATA
# ---------------------------------------------------------------------------

@dataclass
class SrExtPosData(_Subrecord):
    SRT: int = field(default=17, init=False, repr=False)
    vdop: float | None = None
    hdop: float | None = None
    pdop: float | None = None
    satellites: int | None = None
    nav_system: int | None = None  # NS bitmask

    @classmethod
    def from_bytes(cls, data: bytes) -> "SrExtPosData":
        if not data:
            return cls()
        obj = cls()
        flags = data[0]
        bits  = f"{flags:08b}"
        ns_e, sat_e, pdop_e, hdop_e, vdop_e = bits[3], bits[4], bits[5], bits[6], bits[7]
        off = 1
        if vdop_e == "1" and off + 2 <= len(data):
            obj.vdop = struct.unpack_from("<H", data, off)[0] * 0.1; off += 2
        if hdop_e == "1" and off + 2 <= len(data):
            obj.hdop = struct.unpack_from("<H", data, off)[0] * 0.1; off += 2
        if pdop_e == "1" and off + 2 <= len(data):
            obj.pdop = struct.unpack_from("<H", data, off)[0] * 0.1; off += 2
        if sat_e  == "1" and off     < len(data):
            obj.satellites = data[off]; off += 1
        if ns_e   == "1" and off + 2 <= len(data):
            obj.nav_system = struct.unpack_from("<H", data, off)[0]
        return obj

    def to_bytes(self) -> bytes:
        ns_e   = int(self.nav_system  is not None)
        sat_e  = int(self.satellites  is not None)
        pdop_e = int(self.pdop        is not None)
        hdop_e = int(self.hdop        is not None)
        vdop_e = int(self.vdop        is not None)
        flags  = int(f"000{ns_e}{sat_e}{pdop_e}{hdop_e}{vdop_e}", 2)
        buf = bytearray([flags])
        if self.vdop is not None: buf += struct.pack("<H", int(self.vdop * 10))
        if self.hdop is not None: buf += struct.pack("<H", int(self.hdop * 10))
        if self.pdop is not None: buf += struct.pack("<H", int(self.pdop * 10))
        if self.satellites is not None: buf.append(self.satellites)
        if self.nav_system is not None: buf += struct.pack("<H", self.nav_system)
        return bytes(buf)

    def to_dict(self) -> dict:
        return {k: v for k, v in {
            "VDOP": self.vdop, "HDOP": self.hdop, "PDOP": self.pdop,
            "SAT":  self.satellites, "NS":  self.nav_system,
        }.items() if v is not None}


# ---------------------------------------------------------------------------
# SRT 18 — EGTS_SR_AD_SENSORS_DATA
# ---------------------------------------------------------------------------

@dataclass
class SrAdSensorsData(_Subrecord):
    SRT: int = field(default=18, init=False, repr=False)
    # DIOEn — существование цифровых октетов (1..8)
    dioe: list[bool] = field(default_factory=lambda: [False]*8)
    # DOUT — цифровые выходы
    digital_outputs: int = 0
    # ASFEn — существование аналоговых каналов (1..8)
    asfe: list[bool] = field(default_factory=lambda: [False]*8)
    # ADIOn — доп. цифровые входы
    adio: list[int] = field(default_factory=lambda: [0]*8)
    # ANSn — аналоговые датчики (24-bit)
    ans: list[int] = field(default_factory=lambda: [0]*8)

    @classmethod
    def from_bytes(cls, data: bytes) -> "SrAdSensorsData":
        if len(data) < 3:
            raise EGTSError("SrAdSensorsData: too short")
        obj = cls()
        b0 = f"{data[0]:08b}"
        obj.dioe = [b0[7-i] == "1" for i in range(8)]
        obj.digital_outputs = data[1]
        b2 = f"{data[2]:08b}"
        obj.asfe = [b2[7-i] == "1" for i in range(8)]
        off = 3
        for i in range(8):
            if obj.dioe[i] and off < len(data):
                obj.adio[i] = data[off]; off += 1
        for i in range(8):
            if obj.asfe[i] and off + 3 <= len(data):
                obj.ans[i] = _read_u24le(data, off); off += 3
        return obj

    def to_bytes(self) -> bytes:
        dioe_bits = "".join("1" if self.dioe[7-i] else "0" for i in range(8))
        asfe_bits = "".join("1" if self.asfe[7-i] else "0" for i in range(8))
        buf = bytearray([int(dioe_bits, 2), self.digital_outputs, int(asfe_bits, 2)])
        for i in range(8):
            if self.dioe[i]: buf.append(self.adio[i] & 0xFF)
        for i in range(8):
            if self.asfe[i]: buf += _u24le(self.ans[i])
        return bytes(buf)

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"DOUT": self.digital_outputs}
        for i in range(8):
            n = i + 1
            if self.dioe[i]: d[f"ADIO{n}"] = self.adio[i]
            if self.asfe[i]: d[f"ANS{n}"]  = self.ans[i]
        return d


# ---------------------------------------------------------------------------
# SRT 19 — EGTS_SR_COUNTERS_DATA
# ---------------------------------------------------------------------------

@dataclass
class SrCountersData(_Subrecord):
    SRT: int = field(default=19, init=False, repr=False)
    # counters[i] = value or None if not present
    counters: list[int | None] = field(default_factory=lambda: [None]*8)

    @classmethod
    def from_bytes(cls, data: bytes) -> "SrCountersData":
        obj = cls()
        if not data:
            return obj
        flags = data[0]; off = 1
        for i in range(8):
            if flags & (1 << i) and off + 4 <= len(data):
                obj.counters[i] = struct.unpack_from("<I", data, off)[0]; off += 4
        return obj

    def to_bytes(self) -> bytes:
        flags = sum((1 << i) for i in range(8) if self.counters[i] is not None)
        buf = bytearray([flags])
        for i in range(8):
            if self.counters[i] is not None:
                buf += struct.pack("<I", self.counters[i])
        return bytes(buf)

    def to_dict(self) -> dict:
        return {f"CNT{i+1}": v for i, v in enumerate(self.counters) if v is not None}


# ---------------------------------------------------------------------------
# SRT 20/21 — EGTS_SR_STATE_DATA
# ---------------------------------------------------------------------------

@dataclass
class SrStateData(_Subrecord):
    SRT: int = field(default=21, init=False, repr=False)
    state:      int = 0    # ST: 0=active,1=sleep,2=no-motion-sleep,3=parked
    mpsv:       int = 0    # Main Power Source Voltage (×0.1 V)
    bbv:        int = 0    # Backup Battery Voltage (×0.1 V)
    ibv:        int = 0    # Internal Battery Voltage (×0.1 V)
    nms:        bool = False  # Navigation Module Sleep
    ibu:        bool = False  # Internal Battery Used
    bbu:        bool = False  # Backup Battery Used

    _STATE_DESC = {0: "active", 1: "sleep", 2: "sleep_nomotion", 3: "parked"}

    @classmethod
    def from_bytes(cls, data: bytes) -> "SrStateData":
        if len(data) < 5:
            raise EGTSError(f"SrStateData: too short ({len(data)})")
        obj = cls()
        obj.state, obj.mpsv, obj.bbv, obj.ibv = data[0], data[1], data[2], data[3]
        flags = f"{data[4]:08b}"
        obj.nms = flags[5] == "1"
        obj.ibu = flags[6] == "1"
        obj.bbu = flags[7] == "1"
        return obj

    def to_bytes(self) -> bytes:
        flags = int(f"00000{int(self.nms)}{int(self.ibu)}{int(self.bbu)}", 2)
        return bytes([self.state, self.mpsv, self.bbv, self.ibv, flags])

    def to_dict(self) -> dict:
        return {
            "ST":      self.state,
            "ST_desc": self._STATE_DESC.get(self.state, f"unknown({self.state})"),
            "MPSV_V":  round(self.mpsv * 0.1, 1),
            "BBV_V":   round(self.bbv  * 0.1, 1),
            "IBV_V":   round(self.ibv  * 0.1, 1),
            "NMS":     int(self.nms),
            "IBU":     int(self.ibu),
            "BBU":     int(self.bbu),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SrStateData":
        obj = cls()
        obj.state = int(d.get("ST", 0))
        obj.mpsv  = int(round(float(d.get("MPSV_V", 0)) * 10))
        obj.bbv   = int(round(float(d.get("BBV_V",  0)) * 10))
        obj.ibv   = int(round(float(d.get("IBV_V",  0)) * 10))
        obj.nms   = bool(int(d.get("NMS", 0)))
        obj.ibu   = bool(int(d.get("IBU", 0)))
        obj.bbu   = bool(int(d.get("BBU", 0)))
        return obj


# ---------------------------------------------------------------------------
# SRT 25 — EGTS_SR_ABS_CNTR_DATA
# ---------------------------------------------------------------------------

@dataclass
class SrAbsCntrData(_Subrecord):
    SRT: int = field(default=25, init=False, repr=False)
    channel_number: int = 0   # ACN
    counter_value:  int = 0   # ACV

    @classmethod
    def from_bytes(cls, data: bytes) -> "SrAbsCntrData":
        if len(data) < 2:
            raise EGTSError("SrAbsCntrData: too short")
        acn = data[0]
        acv_b = data[1:] + b"\x00" * (4 - len(data[1:]))
        return cls(channel_number=acn, counter_value=struct.unpack("<I", acv_b[:4])[0])

    def to_bytes(self) -> bytes:
        return bytes([self.channel_number]) + struct.pack("<I", self.counter_value)

    def to_dict(self) -> dict:
        return {"ACN": self.channel_number, "ACV": self.counter_value}


# ---------------------------------------------------------------------------
# SRT 27 — EGTS_SR_LIQUID_LEVEL_SENSOR
# ---------------------------------------------------------------------------

@dataclass
class SrLiquidLevelSensor(_Subrecord):
    SRT: int = field(default=27, init=False, repr=False)
    error_flag:  bool = False    # LLSEF
    value_unit:  str  = "00"    # LLSVU (2 bits: 00=litre,01=percent,10=mm)
    raw_data:    bool = False    # RDF
    sensor_num:  int  = 0       # LLSN (3 bits, 0-7)
    module_addr: int  = 0       # MADDR
    sensor_data: int  = 0       # LLSD (4 bytes)

    @classmethod
    def from_bytes(cls, data: bytes) -> "SrLiquidLevelSensor":
        if len(data) < 7:
            raise EGTSError(f"SrLiquidLevelSensor: too short ({len(data)})")
        obj = cls()
        flags = f"{data[0]:08b}"
        obj.error_flag  = flags[1] == "1"
        obj.value_unit  = flags[2:4]
        obj.raw_data    = flags[4] == "1"
        obj.sensor_num  = int(flags[5:], 2)
        obj.module_addr = struct.unpack_from("<H", data, 1)[0]
        obj.sensor_data = struct.unpack_from("<I", data, 3)[0]
        return obj

    def to_bytes(self) -> bytes:
        flags = int(f"0{int(self.error_flag)}{self.value_unit}{int(self.raw_data)}{self.sensor_num:03b}", 2)
        return bytes([flags]) + struct.pack("<HI", self.module_addr, self.sensor_data)

    def to_dict(self) -> dict:
        _units = {"00": "litre", "01": "percent", "10": "mm", "11": "raw"}
        return {
            "LLSEF":  int(self.error_flag),
            "LLSVU":  self.value_unit,
            "LLSVU_desc": _units.get(self.value_unit, "?"),
            "RDF":    int(self.raw_data),
            "LLSN":   self.sensor_num,
            "MADDR":  self.module_addr,
            "LLSD":   self.sensor_data,
        }


# ---------------------------------------------------------------------------
# SRT 28 — EGTS_SR_PASSENGERS_COUNTERS
# ---------------------------------------------------------------------------

@dataclass
class SrPassengersCounters(_Subrecord):
    SRT: int = field(default=28, init=False, repr=False)
    counter_in:  int = 0
    counter_out: int = 0

    @classmethod
    def from_bytes(cls, data: bytes) -> "SrPassengersCounters":
        cin  = struct.unpack_from("<H", data, 0)[0] if len(data) >= 2 else 0
        cout = struct.unpack_from("<H", data, 2)[0] if len(data) >= 4 else 0
        return cls(counter_in=cin, counter_out=cout)

    def to_bytes(self) -> bytes:
        return struct.pack("<HH", self.counter_in, self.counter_out)

    def to_dict(self) -> dict:
        return {"CNT_IN": self.counter_in, "CNT_OUT": self.counter_out}


# ---------------------------------------------------------------------------
# SRT 200-203 — RTLS vendor extensions
# ---------------------------------------------------------------------------

@dataclass
class SrCustom200(_Subrecord):
    """RTLS Extended Position: X/Y/Z (mm) + quality."""
    SRT: int = field(default=200, init=False, repr=False)
    x: int = 0
    y: int = 0
    z: int = 0
    quality: int = 0
    raw_hex: str = ""

    @classmethod
    def from_bytes(cls, data: bytes) -> "SrCustom200":
        obj = cls(raw_hex=data.hex().upper())
        if len(data) >= 8:
            obj.x, obj.y = struct.unpack_from("<ii", data, 0)
        if len(data) >= 12:
            obj.z = struct.unpack_from("<i", data, 8)[0]
        if len(data) >= 14:
            obj.quality = struct.unpack_from("<H", data, 12)[0]
        return obj

    def to_bytes(self) -> bytes:
        return struct.pack("<iiIH", self.x, self.y, abs(self.z), self.quality)

    def to_dict(self) -> dict:
        return {"X_mm": self.x, "Y_mm": self.y, "Z_mm": self.z, "quality": self.quality, "raw_hex": self.raw_hex}


@dataclass
class SrCustom201(_Subrecord):
    """RTLS Sensor Data: temperature, vibration, pressure."""
    SRT: int = field(default=201, init=False, repr=False)
    temperature_01c: int = 0   # ×0.1 °C
    vibration:       int = 0
    pressure_hpa:    int = 0
    sensor_flags:    int = 0
    raw_hex: str = ""

    @classmethod
    def from_bytes(cls, data: bytes) -> "SrCustom201":
        obj = cls(raw_hex=data.hex().upper())
        off = 0
        if len(data) >= off + 2: obj.temperature_01c = struct.unpack_from("<h", data, off)[0]; off += 2
        if len(data) >= off + 2: obj.vibration       = struct.unpack_from("<H", data, off)[0]; off += 2
        if len(data) >= off + 2: obj.pressure_hpa    = struct.unpack_from("<H", data, off)[0]; off += 2
        if len(data) > off:      obj.sensor_flags     = data[off]
        return obj

    def to_bytes(self) -> bytes:
        return struct.pack("<hHHB", self.temperature_01c, self.vibration, self.pressure_hpa, self.sensor_flags)

    def to_dict(self) -> dict:
        return {
            "temperature_01C": self.temperature_01c,
            "temperature_C": round(self.temperature_01c / 10.0, 1),
            "vibration": self.vibration,
            "pressure_hPa": self.pressure_hpa,
            "sensor_flags": f"{self.sensor_flags:#04x}",
            "raw_hex": self.raw_hex,
        }


@dataclass
class SrCustom202(_Subrecord):
    """RTLS Tag Identity: tag_id, zone_id, group_id, RSSI."""
    SRT: int = field(default=202, init=False, repr=False)
    tag_id:   int = 0
    zone_id:  int = 0
    group_id: int = 0
    rssi:     int = 0   # dBm, signed
    raw_hex: str = ""

    @classmethod
    def from_bytes(cls, data: bytes) -> "SrCustom202":
        obj = cls(raw_hex=data.hex().upper())
        if len(data) >= 4: obj.tag_id   = struct.unpack_from("<I", data, 0)[0]
        if len(data) >= 6: obj.zone_id  = struct.unpack_from("<H", data, 4)[0]
        if len(data) >= 8: obj.group_id = struct.unpack_from("<H", data, 6)[0]
        if len(data) >= 9: obj.rssi     = struct.unpack_from("<b", data, 8)[0]
        return obj

    def to_bytes(self) -> bytes:
        return struct.pack("<IHHb", self.tag_id, self.zone_id, self.group_id, self.rssi)

    def to_dict(self) -> dict:
        return {
            "tag_id": self.tag_id, "zone_id": self.zone_id,
            "group_id": self.group_id, "rssi_dBm": self.rssi,
            "raw_hex": self.raw_hex,
        }


@dataclass
class SrCustom203(_Subrecord):
    """RTLS Event Data: event type, zone, time, flags."""
    SRT: int = field(default=203, init=False, repr=False)
    event_type:  int = 0
    zone_id:     int = 0
    event_time:  datetime = field(default_factory=lambda: EPOCH)
    event_flags: int = 0
    raw_hex: str = ""

    _EVT = {0:"none",1:"zone_enter",2:"zone_exit",3:"alarm",4:"low_battery",5:"tamper"}

    @classmethod
    def from_bytes(cls, data: bytes) -> "SrCustom203":
        obj = cls(raw_hex=data.hex().upper())
        if len(data) >= 1: obj.event_type = data[0]
        if len(data) >= 5: obj.zone_id    = struct.unpack_from("<I", data, 1)[0]
        if len(data) >= 9:
            ts = struct.unpack_from("<I", data, 5)[0]
            obj.event_time = EPOCH + timedelta(seconds=ts)
        if len(data) >= 10: obj.event_flags = data[9]
        return obj

    def to_bytes(self) -> bytes:
        ts = int((self.event_time - EPOCH).total_seconds())
        return bytes([self.event_type]) + struct.pack("<II", self.zone_id, max(0, ts)) + bytes([self.event_flags])

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type,
            "event_desc": self._EVT.get(self.event_type, f"unknown({self.event_type})"),
            "zone_id": self.zone_id,
            "event_time": self.event_time.isoformat(),
            "event_flags": f"{self.event_flags:#04x}",
            "raw_hex": self.raw_hex,
        }


# ---------------------------------------------------------------------------
# SRT 204 — IMU / Inertial data + Sensor Fusion outputs
# (discussion 09-inertial-sensors-egts + 13-sensor-fusion-architecture + 14-16)
# ---------------------------------------------------------------------------
@dataclass
class SrCustom204(_Subrecord):
    """Proposed SRT 204 — IMU orientation, raw sensors, vibration metrics, EKF/map-match outputs."""
    SRT: int = field(default=204, init=False, repr=False)

    # Orientation (from Madgwick, discussion 16)
    heading_deg: float = 0.0
    roll_deg: float = 0.0
    pitch_deg: float = 0.0
    heading_accuracy_deg: float = 5.0

    # Raw IMU (body frame)
    accel_x: float = 0.0
    accel_y: float = 0.0
    accel_z: float = 0.0
    gyro_x: float = 0.0
    gyro_y: float = 0.0
    gyro_z: float = 0.0

    # Vibration metrics (discussion 10)
    vibration_rms: float = 0.0
    vibration_peak: float = 0.0
    dominant_freq_hz: float = 0.0
    filter_type: int = 0   # 0=none,1=lpf,2=madgwick,3=ekf,4=hybrid

    # EKF outputs (discussion 14)
    ekf_confidence: float = 0.0
    cov_trace: float = 0.0

    # Map matching outputs (discussion 08, 15)
    road_segment_id: int = 0
    matched_lat: float = 0.0
    matched_lon: float = 0.0
    snap_confidence: float = 0.0

    flags: int = 0
    timestamp: int = 0
    raw_hex: str = ""
    _raw_bytes: bytes = field(default=b"", repr=False)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("_raw_bytes", None)
        d["heading"] = round(self.heading_deg, 2)
        d["roll"] = round(self.roll_deg, 2)
        d["pitch"] = round(self.pitch_deg, 2)
        return d

    @classmethod
    def from_dict(cls, d: dict):
        known = {k for k in cls.__dataclass_fields__ if k not in ("SRT", "_raw_bytes")}
        filtered = {k: v for k, v in d.items() if k in known}
        return cls(**filtered)

    @classmethod
    def from_bytes(cls, data: bytes) -> "SrCustom204":
        obj = cls(_raw_bytes=data, raw_hex=data.hex().upper())
        if len(data) < 8:
            return obj
        off = 0
        if len(data) >= off + 8:
            h, r, p, ha = struct.unpack_from("<hhhh", data, off)
            obj.heading_deg = h / 100.0
            obj.roll_deg = r / 100.0
            obj.pitch_deg = p / 100.0
            obj.heading_accuracy_deg = ha / 100.0
            off += 8
        if len(data) >= off + 12:
            ax, ay, az, gx, gy, gz = struct.unpack_from("<hhhhhh", data, off)
            obj.accel_x = ax / 100.0; obj.accel_y = ay / 100.0; obj.accel_z = az / 100.0
            obj.gyro_x = gx / 100.0; obj.gyro_y = gy / 100.0; obj.gyro_z = gz / 100.0
            off += 12
        if len(data) >= off + 8:
            vrms, vpeak, dfreq, ftype, conf8 = struct.unpack_from("<HHHBB", data, off)
            obj.vibration_rms = vrms / 100.0
            obj.vibration_peak = vpeak / 100.0
            obj.dominant_freq_hz = dfreq / 10.0
            obj.filter_type = ftype
            obj.ekf_confidence = conf8 / 255.0
            off += 8
        if len(data) >= off + 4:
            obj.cov_trace = struct.unpack_from("<f", data, off)[0]; off += 4
        if len(data) >= off + 4:
            obj.road_segment_id = struct.unpack_from("<I", data, off)[0]; off += 4
        if len(data) >= off + 9:
            mlat, mlon = struct.unpack_from("<ii", data, off)
            obj.matched_lat = mlat / 1e7
            obj.matched_lon = mlon / 1e7
            obj.snap_confidence = data[off + 8] / 255.0
            off += 9
        if len(data) >= off + 5:
            obj.flags = data[off]
            obj.timestamp = struct.unpack_from("<I", data, off + 1)[0]
        return obj

    def to_bytes(self) -> bytes:
        def clamp(v, lo=-32767, hi=32767): return max(lo, min(hi, int(v)))
        out = struct.pack("<hhhh",
            clamp(self.heading_deg * 100), clamp(self.roll_deg * 100),
            clamp(self.pitch_deg * 100), clamp(self.heading_accuracy_deg * 100))
        out += struct.pack("<hhhhhh",
            clamp(self.accel_x * 100), clamp(self.accel_y * 100), clamp(self.accel_z * 100),
            clamp(self.gyro_x * 100), clamp(self.gyro_y * 100), clamp(self.gyro_z * 100))
        out += struct.pack("<HHHBB",
            int(self.vibration_rms * 100) & 0xFFFF,
            int(self.vibration_peak * 100) & 0xFFFF,
            int(self.dominant_freq_hz * 10) & 0xFFFF,
            self.filter_type & 0xFF,
            int(max(0, min(1, self.ekf_confidence)) * 255) & 0xFF)
        out += struct.pack("<f", float(self.cov_trace))
        out += struct.pack("<I", self.road_segment_id & 0xFFFFFFFF)
        out += struct.pack("<iiB",
            int(self.matched_lat * 1e7) & 0xFFFFFFFF,
            int(self.matched_lon * 1e7) & 0xFFFFFFFF,
            int(max(0, min(1, self.snap_confidence)) * 255) & 0xFF)
        out += struct.pack("<BI", self.flags & 0xFF, self.timestamp & 0xFFFFFFFF)
        self._raw_bytes = out
        self.raw_hex = out.hex().upper()
        return out


# ---------------------------------------------------------------------------
# SRT 205 — LBS (cellular base stations) data for road graph positioning
# (from discussion 18: using stations + road graph to find exact point on road)
# ---------------------------------------------------------------------------
@dataclass
class NeighborCell:
    cell_id: int = 0
    rssi_dbm: int = 0


@dataclass
class SrCustom205(_Subrecord):
    """LBS data: serving cell + TA + RSSI + neighbors for map-matching to road graph."""
    SRT: int = field(default=205, init=False, repr=False)

    serving_cell_id: int = 0
    lac_tac: int = 0
    mcc: int = 0
    mnc: int = 0
    rssi_dbm: int = 0
    timing_advance: int = 0
    bs_lat: float = 0.0
    bs_lon: float = 0.0
    neighbors: List[NeighborCell] = field(default_factory=list)
    raw_lbs_lat: float = 0.0
    raw_lbs_lon: float = 0.0
    lbs_quality: int = 0
    technology: int = 0
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
    def from_dict(cls, d: dict):
        known = {k for k in cls.__dataclass_fields__ if k not in ("SRT", "_raw_bytes")}
        filtered = {k: v for k, v in d.items() if k in known}
        if "neighbors" in filtered:
            filtered["neighbors"] = [NeighborCell(**n) if isinstance(n, dict) else n
                                     for n in filtered["neighbors"]]
        return cls(**filtered)

    @classmethod
    def from_bytes(cls, data: bytes) -> "SrCustom205":
        obj = cls(raw_hex=data.hex().upper())
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
        for _ in range(min(num_n, 8)):
            if off + 5 > len(data): break
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
        out += struct.pack("<bH", self.rssi_dbm, self.timing_advance)
        blat = int(self.bs_lat * 1e7)
        blon = int(self.bs_lon * 1e7)
        out += struct.pack("<ii", blat, blon)
        num_n = min(len(self.neighbors), 8)
        out += bytes([num_n])
        for n in self.neighbors[:num_n]:
            out += struct.pack("<Ib", n.cell_id, n.rssi_dbm)
        rlat = int(self.raw_lbs_lat * 1e7)
        rlon = int(self.raw_lbs_lon * 1e7)
        out += struct.pack("<ii", rlat, rlon)
        out += struct.pack("<BBBBI",
                           self.lbs_quality & 0xFF,
                           self.technology & 0xFF,
                           self.flags & 0xFF,
                           0,
                           self.timestamp & 0xFFFFFFFF)
        self._raw_bytes = out
        self.raw_hex = out.hex().upper()
        return out


# ---------------------------------------------------------------------------
# Raw / Unknown subrecord
# ---------------------------------------------------------------------------

@dataclass
class SrRaw(_Subrecord):
    SRT: int = field(default=-1, init=False, repr=False)
    srt_code: int = 0
    raw: bytes = b""

    @classmethod
    def from_bytes(cls, srt: int, data: bytes) -> "SrRaw":
        obj = cls()
        obj.srt_code = srt
        obj.raw = data
        return obj

    def to_bytes(self) -> bytes:
        return self.raw

    def to_dict(self) -> dict:
        return {"raw_hex": self.raw.hex().upper(), "note": "unimplemented decoder"}
