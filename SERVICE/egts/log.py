"""Терминальный лог + файловый лог для EGTS-парсера."""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .codec import EGTSPacket

_USE_COLOR = os.environ.get("FORCE_COLOR") or (
    hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
)

C = {
    "reset":   "\033[0m",
    "bold":    "\033[1m",
    "header":  "\033[1;36m",
    "ok":      "\033[1;32m",
    "warn":    "\033[1;33m",
    "error":   "\033[1;31m",
    "key":     "\033[0;33m",
    "val":     "\033[0;97m",
    "section": "\033[1;35m",
    "dim":     "\033[2;37m",
    "custom":  "\033[1;34m",
} if _USE_COLOR else {k: "" for k in ["reset","bold","header","ok","warn","error","key","val","section","dim","custom"]}


def _c(color: str, text: str) -> str:
    return C.get(color, "") + text + C.get("reset", "")


def _safe_print(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode())


def setup_file_logger(log_path: str) -> logging.Logger:
    logger = logging.getLogger("egts_file")
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s  %(message)s"))
        logger.addHandler(fh)
    return logger


def _out(colored: str, plain: str, logger: logging.Logger | None) -> None:
    _safe_print(colored)
    if logger:
        logger.info(plain)


def _kv(key: str, val, depth: int, logger: logging.Logger | None) -> None:
    pad = "  " * depth
    colored = f"{pad}{_c('key', key)}: {_c('val', str(val))}"
    plain   = f"{pad}{key}: {val}"
    _out(colored, plain, logger)


def log_packet(pkt: "EGTSPacket", idx: int = 0, logger: logging.Logger | None = None) -> None:
    sep72 = "=" * 72
    now   = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    ok    = not pkt.parse_errors and pkt.hcs_valid and pkt.crc16_valid

    _out(_c("header", sep72), sep72, logger)
    title = f"  PKT #{idx:04d}  |  {now}  |  {pkt.total_bytes} bytes  |  {'OK' if ok else 'ERR'}"
    _out(_c("header" if ok else "error", title), title, logger)
    _out(_c("header", sep72), sep72, logger)

    # HEX raw (dim, max 128 chars)
    hex_preview = pkt.hex_raw[:128] + ("..." if len(pkt.hex_raw) > 128 else "")
    _out(_c("dim", f"  HEX: {hex_preview}"), f"  HEX: {hex_preview}", logger)

    for err in pkt.parse_errors:
        _out(f"  {_c('error', 'ERR')} {err}", f"  ERR {err}", logger)

    # ── HEADER ──
    h = pkt.header
    hcs_mark = _c("ok", "OK") if pkt.hcs_valid else _c("error", "FAIL")
    crc_mark  = _c("ok", "OK") if pkt.crc16_valid else _c("error", "FAIL")
    _out("", "", logger)
    _out(_c("bold", "  HEADER"), "  HEADER", logger)

    from .const import PT_NAMES
    pt_name = PT_NAMES.get(h.packet_type, f"PT_{h.packet_type}")
    fields = [
        ("PRV", h.protocol_version), ("SKID", h.security_key_id),
        ("PRF", h.prefix), ("RTE", h.route), ("ENA", h.encryption_alg),
        ("CMP", h.compression), ("PR", h.priority),
        ("HL", h.header_length), ("HE", h.header_encoding),
        ("FDL", h.frame_data_length), ("PID", h.packet_id),
        ("PT", f"{h.packet_type} ({pt_name})"),
    ]
    if h.routed:
        fields += [("PRA", h.peer_address), ("RCA", h.recipient_address), ("TTL", h.time_to_live)]
    fields += [
        ("HCS", f"{h.header_crc:#04x}  [{hcs_mark}]"),
        ("SFRD_CRC16", f"{pkt.crc16_value:#06x}  [{crc_mark}]"),
    ]
    for k, v in fields:
        _kv(k, v, 2, logger)

    # ── SFRD ──
    body = pkt.body
    _out("", "", logger)
    if body is None:
        _out(_c("dim", "  SFRD: (empty, FDL=0)"), "  SFRD: (empty, FDL=0)", logger)
        return

    from .codec import PtResponse, ServiceDataRecord
    if isinstance(body, PtResponse):
        _out(_c("section", "  SFRD [PT_RESPONSE]"), "  SFRD [PT_RESPONSE]", logger)
        _kv("RPID", body.response_packet_id, 2, logger)
        from .const import RESULT_CODES
        _kv("PR", f"{body.processing_result} ({RESULT_CODES.get(body.processing_result,'?')})", 2, logger)
        _log_sdr_list(body.service_data, logger)
    elif isinstance(body, list):
        _out(_c("section", f"  SFRD [PT_APPDATA]  ({len(body)} SDR)"), f"  SFRD [PT_APPDATA] ({len(body)} SDR)", logger)
        _log_sdr_list(body, logger)

    _out(_c("dim", "─" * 72), "─" * 72, logger)
    _out("", "", logger)


def _log_sdr_list(sdrs: list, logger: logging.Logger | None) -> None:
    from .const import SVC_NAMES
    for si, sdr in enumerate(sdrs):
        sst = SVC_NAMES.get(sdr.source_service_type, f"SVC_{sdr.source_service_type}")
        rst = SVC_NAMES.get(sdr.recipient_service_type, f"SVC_{sdr.recipient_service_type}")
        title = f"  SDR #{si}  RN={sdr.record_number}  SST={sst}  RST={rst}"
        _out(_c("warn", title), title, logger)
        if sdr.record_time:
            _kv("TM", sdr.record_time.isoformat(), 3, logger)
        if sdr.object_id is not None:
            _kv("OID", sdr.object_id, 3, logger)
        _log_rd_list(sdr.record_data, logger)


def _log_rd_list(rds: list, logger: logging.Logger | None) -> None:
    from .const import SRT_NAMES
    for ri, rd in enumerate(rds):
        srt_name = SRT_NAMES.get(rd.srt, f"SRT_{rd.srt}")
        color = "custom" if rd.srt >= 200 else "section"
        title = f"    [{ri:02d}] {srt_name}  SRT={rd.srt}  SRL={rd.srl}"
        _out(_c(color, title), title, logger)
        d = rd.subrecord.to_dict()
        for k, v in d.items():
            _kv(k, v, 5, logger)


def log_summary(packets: list, logger: logging.Logger | None = None) -> None:
    total  = len(packets)
    errors = sum(1 for p in packets if p.parse_errors or not p.hcs_valid or not p.crc16_valid)
    ok     = total - errors
    sep    = "=" * 72
    line   = f"  TOTAL: {total} packets | {ok} OK | {errors} errors"
    _out(_c("header", sep), sep, logger)
    _out(_c("ok" if not errors else "warn", line), line, logger)
    _out(_c("header", sep), sep, logger)
