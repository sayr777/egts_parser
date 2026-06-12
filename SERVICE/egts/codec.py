"""
Top-level encode / decode для EGTS пакетов.

  parse_packet(raw: bytes)  -> EGTSPacket
  parse_stream(raw: bytes)  -> list[EGTSPacket]
  build_packet(pkt: EGTSPacket) -> bytes
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from .const import (
    PT_APPDATA, PT_RESPONSE, EPOCH,
    SRT_RECORD_RESPONSE, SRT_TERM_IDENTITY, SRT_MODULE_DATA,
    SRT_DISPATCHER_IDENTITY, SRT_AUTH_INFO, SRT_RESULT_CODE,
    SRT_EGTS_PLUS_DATA, SRT_POS_DATA, SRT_EXT_POS_DATA,
    SRT_AD_SENSORS_DATA, SRT_COUNTERS_DATA, SRT_STATE_OR_ACCEL,
    SRT_STATE_DATA, SRT_ABS_CNTR_DATA, SRT_LIQUID_LEVEL_SENSOR,
    SRT_PASSENGERS_COUNTERS, SRT_CUSTOM_200, SRT_CUSTOM_201,
    SRT_CUSTOM_202, SRT_CUSTOM_203, SRT_CUSTOM_204, SRT_CUSTOM_205, SRT_NAMES, PT_NAMES, SVC_NAMES,
    RESULT_CODES,
)
from .crc import crc8, crc16
from .models import (
    Header, EGTSError,
    SrRecordResponse, SrTermIdentity, SrAuthInfo, SrResultCode,
    SrDispatcherIdentity, SrPosData, SrExtPosData, SrAdSensorsData,
    SrCountersData, SrStateData, SrAbsCntrData, SrLiquidLevelSensor,
    SrPassengersCounters, SrCustom200, SrCustom201, SrCustom202, SrCustom203, SrCustom204, SrCustom205,
    SrRaw, _Subrecord,
)


# ---------------------------------------------------------------------------
# Диспетчер декодеров SRT
# ---------------------------------------------------------------------------

def _decode_subrecord(srt: int, data: bytes) -> _Subrecord:
    try:
        if srt == SRT_RECORD_RESPONSE:     return SrRecordResponse.from_bytes(data)
        if srt == SRT_TERM_IDENTITY:       return SrTermIdentity.from_bytes(data)
        if srt == SRT_AUTH_INFO:           return SrAuthInfo.from_bytes(data)
        if srt == SRT_RESULT_CODE:         return SrResultCode.from_bytes(data)
        if srt == SRT_DISPATCHER_IDENTITY: return SrDispatcherIdentity.from_bytes(data)
        if srt == SRT_POS_DATA:            return SrPosData.from_bytes(data)
        if srt == SRT_EXT_POS_DATA:        return SrExtPosData.from_bytes(data)
        if srt == SRT_AD_SENSORS_DATA:     return SrAdSensorsData.from_bytes(data)
        if srt == SRT_COUNTERS_DATA:       return SrCountersData.from_bytes(data)
        if srt in (SRT_STATE_OR_ACCEL, SRT_STATE_DATA):
            return SrStateData.from_bytes(data) if len(data) == 5 else SrRaw.from_bytes(srt, data)
        if srt == SRT_ABS_CNTR_DATA:       return SrAbsCntrData.from_bytes(data)
        if srt == SRT_LIQUID_LEVEL_SENSOR: return SrLiquidLevelSensor.from_bytes(data)
        if srt == SRT_PASSENGERS_COUNTERS: return SrPassengersCounters.from_bytes(data)
        if srt == SRT_CUSTOM_200:          return SrCustom200.from_bytes(data)
        if srt == SRT_CUSTOM_201:          return SrCustom201.from_bytes(data)
        if srt == SRT_CUSTOM_202:          return SrCustom202.from_bytes(data)
        if srt == SRT_CUSTOM_203:          return SrCustom203.from_bytes(data)
        if srt == SRT_CUSTOM_204:          return SrCustom204.from_bytes(data)  # IMU + fusion (09/13-16)
        if srt == SRT_CUSTOM_205:          return SrCustom205.from_bytes(data)  # LBS for road graph (18)
    except EGTSError as e:
        raw = SrRaw.from_bytes(srt, data)
        raw.to_dict()  # noop — store error info
        return raw
    return SrRaw.from_bytes(srt, data)


# ---------------------------------------------------------------------------
# RecordData  (одна подзапись внутри SDR)
# ---------------------------------------------------------------------------

@dataclass
class RecordData:
    srt:      int         # SubrecordType
    srl:      int         # SubrecordLength
    subrecord: _Subrecord

    def to_dict(self) -> dict:
        return {
            "SRT":      self.srt,
            "SRT_name": SRT_NAMES.get(self.srt, f"SRT_{self.srt}"),
            "SRL":      self.srl,
            "SRD":      self.subrecord.to_dict(),
        }

    def to_bytes(self) -> bytes:
        srd = self.subrecord.to_bytes()
        return bytes([self.srt]) + struct.pack("<H", len(srd)) + srd


def _parse_record_data_set(buf: bytes) -> list[RecordData]:
    records: list[RecordData] = []
    off = 0
    while off + 3 <= len(buf):
        srt = buf[off]
        srl = struct.unpack_from("<H", buf, off + 1)[0]
        off += 3
        srd_bytes = buf[off:off + srl]
        off += srl
        records.append(RecordData(srt=srt, srl=srl, subrecord=_decode_subrecord(srt, srd_bytes)))
    return records


# ---------------------------------------------------------------------------
# ServiceDataRecord
# ---------------------------------------------------------------------------

@dataclass
class ServiceDataRecord:
    record_length:    int = 0
    record_number:    int = 0
    # flags
    ssod: str = "0"   # SourceServiceOnDevice
    rsod: str = "0"   # RecipientServiceOnDevice
    grp:  str = "0"   # Group
    rpp:  str = "00"  # RecordProcessingPriority
    tmfe: str = "0"   # TimeFieldExists
    evfe: str = "0"   # EventIDFieldExists
    obfe: str = "0"   # ObjectIDFieldExists
    # optional fields
    object_id:  int | None = None
    event_id:   int | None = None
    record_time: datetime | None = None
    # service types
    source_service_type:    int = 2
    recipient_service_type: int = 2
    # subrecords
    record_data: list[RecordData] = field(default_factory=list)

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "RL":  self.record_length,
            "RN":  self.record_number,
            "SSOD": self.ssod, "RSOD": self.rsod, "GRP": self.grp,
            "RPP":  self.rpp, "TMFE": self.tmfe, "EVFE": self.evfe, "OBFE": self.obfe,
            "SST":      self.source_service_type,
            "SST_name": SVC_NAMES.get(self.source_service_type, f"SVC_{self.source_service_type}"),
            "RST_svc":  self.recipient_service_type,
            "RST_name": SVC_NAMES.get(self.recipient_service_type, f"SVC_{self.recipient_service_type}"),
            "RD": [rd.to_dict() for rd in self.record_data],
        }
        if self.object_id    is not None: d["OID"]  = self.object_id
        if self.event_id     is not None: d["EVID"] = self.event_id
        if self.record_time  is not None: d["TM"]   = self.record_time.isoformat()
        return d

    def to_bytes(self) -> bytes:
        rds_bytes = b"".join(rd.to_bytes() for rd in self.record_data)
        flags = int(self.ssod + self.rsod + self.grp + self.rpp + self.tmfe + self.evfe + self.obfe, 2)
        buf = bytearray()
        buf += struct.pack("<HHB", len(rds_bytes), self.record_number, flags)
        if self.obfe == "1" and self.object_id is not None:
            buf += struct.pack("<I", self.object_id)
        if self.evfe == "1" and self.event_id is not None:
            buf += struct.pack("<I", self.event_id)
        if self.tmfe == "1" and self.record_time is not None:
            ts = int((self.record_time - EPOCH).total_seconds())
            buf += struct.pack("<I", max(0, ts))
        buf.append(self.source_service_type)
        buf.append(self.recipient_service_type)
        buf += rds_bytes
        return bytes(buf)


def _parse_service_data_set(sfrd: bytes) -> list[ServiceDataRecord]:
    records: list[ServiceDataRecord] = []
    off = 0
    while off + 7 <= len(sfrd):
        rl  = struct.unpack_from("<H", sfrd, off)[0]
        rn  = struct.unpack_from("<H", sfrd, off + 2)[0]
        flg = sfrd[off + 4]
        bits = f"{flg:08b}"
        ssod, rsod, grp, rpp, tmfe, evfe, obfe = (
            bits[0], bits[1], bits[2], bits[3:5], bits[5], bits[6], bits[7]
        )
        off += 5
        sdr = ServiceDataRecord(
            record_length=rl, record_number=rn,
            ssod=ssod, rsod=rsod, grp=grp, rpp=rpp,
            tmfe=tmfe, evfe=evfe, obfe=obfe,
        )
        if obfe == "1" and off + 4 <= len(sfrd):
            sdr.object_id = struct.unpack_from("<I", sfrd, off)[0]; off += 4
        if evfe == "1" and off + 4 <= len(sfrd):
            sdr.event_id = struct.unpack_from("<I", sfrd, off)[0]; off += 4
        if tmfe == "1" and off + 4 <= len(sfrd):
            ts = struct.unpack_from("<I", sfrd, off)[0]
            sdr.record_time = EPOCH + timedelta(seconds=ts); off += 4
        sdr.source_service_type    = sfrd[off];     off += 1
        sdr.recipient_service_type = sfrd[off];     off += 1
        rds_bytes = sfrd[off:off + rl]
        off += rl
        sdr.record_data = _parse_record_data_set(rds_bytes)
        records.append(sdr)
    return records


# ---------------------------------------------------------------------------
# PT_RESPONSE body
# ---------------------------------------------------------------------------

@dataclass
class PtResponse:
    response_packet_id: int = 0
    processing_result:  int = 0
    service_data: list[ServiceDataRecord] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "RPID": self.response_packet_id,
            "PR":   self.processing_result,
            "PR_desc": RESULT_CODES.get(self.processing_result, f"unknown({self.processing_result})"),
            "SDR":  [sdr.to_dict() for sdr in self.service_data],
        }

    def to_bytes(self) -> bytes:
        buf = struct.pack("<HB", self.response_packet_id, self.processing_result)
        for sdr in self.service_data:
            buf += sdr.to_bytes()
        return buf


# ---------------------------------------------------------------------------
# EGTSPacket — полный пакет
# ---------------------------------------------------------------------------

@dataclass
class EGTSPacket:
    header:      Header
    body:        list[ServiceDataRecord] | PtResponse | None = None
    # validation results
    hcs_valid:   bool = True
    crc16_valid: bool = True
    crc16_value: int  = 0
    parse_errors: list[str] = field(default_factory=list)
    hex_raw:      str = ""
    total_bytes:  int = 0

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "hex_raw":      self.hex_raw,
            "total_bytes":  self.total_bytes,
            "parse_errors": self.parse_errors,
            "HEADER": self.header.to_dict() | {
                "HCS_valid":   self.hcs_valid,
            },
            "SFRD_CRC16":       self.crc16_value,
            "SFRD_CRC16_valid": self.crc16_valid,
        }
        if isinstance(self.body, list):
            d["SFRD"] = [sdr.to_dict() for sdr in self.body]
        elif isinstance(self.body, PtResponse):
            d["SFRD"] = self.body.to_dict()
        else:
            d["SFRD"] = None
        return d

    def to_bytes(self) -> bytes:
        """Re-encode the packet from current attribute state (recalculates all CRCs/lengths)."""
        if isinstance(self.body, list):
            sfrd = b"".join(sdr.to_bytes() for sdr in self.body)
        elif isinstance(self.body, PtResponse):
            sfrd = self.body.to_bytes()
        else:
            sfrd = b""
        return self.header.to_bytes(sfrd)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_packet(raw: bytes) -> EGTSPacket:
    """Разбирает один бинарный EGTS-пакет."""
    pkt = EGTSPacket(header=Header(), hex_raw=raw.hex().upper(), total_bytes=len(raw))

    if len(raw) < 11:
        pkt.parse_errors.append(f"Пакет слишком короткий: {len(raw)} байт")
        return pkt

    try:
        pkt.header, _ = Header.from_bytes(raw)
    except EGTSError as e:
        pkt.parse_errors.append(str(e))
        return pkt

    hl  = pkt.header.header_length
    fdl = pkt.header.frame_data_length

    # HCS validation
    pkt.hcs_valid = (raw[hl - 1] == crc8(raw[:hl - 1]))
    if not pkt.hcs_valid:
        calc = crc8(raw[:hl - 1])
        pkt.parse_errors.append(f"HCS mismatch: got {raw[hl-1]:#04x}, calc {calc:#04x}")

    if len(raw) < hl + fdl + 2:
        pkt.parse_errors.append(f"Пакет обрезан: need {hl+fdl+2} байт, have {len(raw)}")
        return pkt

    sfrd = raw[hl:hl + fdl]
    sfrcs = struct.unpack_from("<H", raw, hl + fdl)[0]
    pkt.crc16_value = sfrcs
    pkt.crc16_valid = (sfrcs == crc16(sfrd))
    if not pkt.crc16_valid:
        calc = crc16(sfrd)
        pkt.parse_errors.append(f"SFRCS mismatch: got {sfrcs:#06x}, calc {calc:#06x}")

    if fdl == 0:
        return pkt

    pt = pkt.header.packet_type
    try:
        if pt == PT_APPDATA:
            pkt.body = _parse_service_data_set(sfrd)
        elif pt == PT_RESPONSE:
            if len(sfrd) >= 3:
                rpid = struct.unpack_from("<H", sfrd, 0)[0]
                pr   = sfrd[2]
                sdr_list = _parse_service_data_set(sfrd[3:]) if len(sfrd) > 3 else []
                pkt.body = PtResponse(response_packet_id=rpid, processing_result=pr, service_data=sdr_list)
        else:
            pkt.parse_errors.append(f"Неизвестный PT={pt}")
    except Exception as e:
        pkt.parse_errors.append(f"Ошибка парсинга тела: {e}")

    return pkt


def parse_stream(raw: bytes) -> list[EGTSPacket]:
    """Разбирает поток байт, содержащий один или несколько пакетов."""
    packets: list[EGTSPacket] = []
    off = 0
    while off < len(raw):
        # Sync: ищем PRV=0x01
        if raw[off] != 0x01:
            off += 1
            continue
        if off + 10 > len(raw):
            break
        hl  = raw[off + 3]
        fdl = struct.unpack_from("<H", raw, off + 5)[0]
        pkt_len = hl + fdl + 2
        if off + pkt_len > len(raw):
            break
        pkt_bytes = raw[off:off + pkt_len]
        packets.append(parse_packet(pkt_bytes))
        off += pkt_len
    return packets


def build_packet(pkt: EGTSPacket) -> bytes:
    """Кодирует пакет в байты (полный re-encode с пересчётом CRC и длин)."""
    return pkt.to_bytes()
