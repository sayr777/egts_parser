"""
Yandex Cloud Function — EGTS Parser (Python 3.11+)

handler(event, context) — точка входа Cloud Function.

CLI:
  python handler.py <hex_string>
  python handler.py --file packets.csv [--out report.json]
  python handler.py --listen 6000
  python handler.py --encode packet.json   # JSON → binary hex
"""

import base64
import binascii
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Добавляем SERVICE/ в путь
sys.path.insert(0, str(Path(__file__).parent))

from egts.codec import parse_stream, build_packet, EGTSPacket
from egts.log   import setup_file_logger, log_packet, log_summary

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

_LOG_DIR  = os.environ.get("EGTS_LOG_DIR", ".")
_DATE     = datetime.now(timezone.utc).strftime("%Y%m%d")
_LOG_FILE = os.path.join(_LOG_DIR, f"egts_{_DATE}.log")
_JSON_LOG = os.path.join(_LOG_DIR, f"egts_{_DATE}.json")

_file_logger = setup_file_logger(_LOG_FILE)

logging.basicConfig(level=logging.WARNING, format="%(message)s")


# ---------------------------------------------------------------------------
# JSON log helpers
# ---------------------------------------------------------------------------

def _load_json_log() -> list[dict]:
    if os.path.exists(_JSON_LOG):
        try:
            with open(_JSON_LOG, encoding="utf-8") as f:
                return json.load(f).get("packets", [])
        except Exception:
            pass
    return []


def _save_json_log(packets: list[dict]) -> None:
    try:
        with open(_JSON_LOG, "w", encoding="utf-8") as f:
            json.dump(
                {"generated_at": datetime.now(timezone.utc).isoformat(), "packets": packets},
                f, ensure_ascii=False, indent=2, default=str,
            )
    except Exception as e:
        logging.warning("Cannot write JSON log: %s", e)


def _append_packets(pkts: list[EGTSPacket]) -> None:
    existing = _load_json_log()
    existing.extend(p.to_dict() for p in pkts)
    _save_json_log(existing)


# ---------------------------------------------------------------------------
# Yandex Cloud Function handler
# ---------------------------------------------------------------------------

def handler(event: dict, context=None) -> dict:
    """
    Принимает:
      event["body"]            — hex-строка или base64
      event["isBase64Encoded"] — bool (опционально)
      event["encode"]          — dict (опционально) — пакет для кодирования из JSON

    Возвращает:
      {"statusCode": 200, "body": <JSON>, "headers": {...}}
    """
    # Режим encode: принимаем dict пакета и возвращаем hex
    if "encode" in event:
        try:
            result = _encode_from_dict(event["encode"])
            return _resp(200, result)
        except Exception as e:
            return _resp(400, {"error": str(e)})

    # Режим decode
    body   = event.get("body", "")
    is_b64 = event.get("isBase64Encoded", False)

    try:
        raw = base64.b64decode(body) if is_b64 else bytes.fromhex(body.replace(" ", "").replace("\n", ""))
    except (ValueError, binascii.Error) as e:
        return _resp(400, {"error": f"Cannot decode body: {e}"})

    pkts = parse_stream(raw) if raw else []
    for idx, p in enumerate(pkts):
        log_packet(p, idx, _file_logger)
    log_summary(pkts, _file_logger)
    _append_packets(pkts)

    # LBS processing example (SRT 205 - discussion 18)
    lbs_records = []
    for p in pkts:
        for sdr in getattr(p, 'body', []) or []:
            if hasattr(sdr, 'record_data'):
                for rd in sdr.record_data:
                    if getattr(rd, 'srt', None) == 205 and hasattr(rd, 'subrecord'):
                        lbs = rd.subrecord
                        lbs_info = {
                            "serving_cell_id": getattr(lbs, 'serving_cell_id', None),
                            "rssi_dbm": getattr(lbs, 'rssi_dbm', None),
                            "timing_advance": getattr(lbs, 'timing_advance', None),
                            "raw_lbs_lat": getattr(lbs, 'raw_lbs_lat', None),
                            "raw_lbs_lon": getattr(lbs, 'raw_lbs_lon', None),
                            "neighbors_count": len(getattr(lbs, 'neighbors', []) or []),
                        }
                        lbs_records.append(lbs_info)
                        logging.info("LBS record (for road graph matching): %s", lbs_info)  # forward example
                        # Simple Python LBS snap (for demo; use PostGIS in prod - see sandbox/postgis_lbs.sql)
                        try:
                            from .lbs import lbs_aware_snap
                            matched = lbs_aware_snap(lbs_info)
                            logging.info("LBS snapped to road: %s", matched)
                            lbs_info["matched"] = matched
                        except Exception as e:
                            logging.warning("LBS snap failed: %s", e)

    return _resp(200, {
        "ts":      datetime.now(timezone.utc).isoformat(),
        "count":   len(pkts),
        "packets": [p.to_dict() for p in pkts],
        "lbs_records": lbs_records,  # LBS forwarding for map matching
    })


def _resp(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "body": json.dumps(body, ensure_ascii=False, indent=2, default=str),
        "headers": {"Content-Type": "application/json; charset=utf-8"},
    }


# ---------------------------------------------------------------------------
# Encode from JSON dict (re-encode a previously parsed packet)
# ---------------------------------------------------------------------------

def _encode_from_dict(d: dict) -> dict:
    """
    Принимает JSON-представление пакета (результат parse).
    Пересчитывает все CRC и длины, возвращает hex.
    """
    from egts.codec import EGTSPacket, PtResponse, ServiceDataRecord, RecordData
    from egts.models import Header
    from egts.const  import PT_APPDATA, PT_RESPONSE

    pkt   = EGTSPacket(header=Header())
    h_src = d.get("HEADER", {})
    hdr   = pkt.header
    hdr.protocol_version   = int(h_src.get("PRV", 1))
    hdr.security_key_id    = int(h_src.get("SKID", 0))
    hdr.prefix             = str(h_src.get("PRF", "00"))
    hdr.route              = str(h_src.get("RTE", "0"))
    hdr.encryption_alg     = str(h_src.get("ENA", "00"))
    hdr.compression        = str(h_src.get("CMP", "0"))
    hdr.priority           = str(h_src.get("PR", "00"))
    hdr.header_encoding    = int(h_src.get("HE", 0))
    hdr.packet_id          = int(h_src.get("PID", 0))
    hdr.packet_type        = int(h_src.get("PT", PT_APPDATA))

    sfrd_src = d.get("SFRD")
    if hdr.packet_type == PT_APPDATA and isinstance(sfrd_src, list):
        pkt.body = [_sdr_from_dict(s) for s in sfrd_src]
    elif hdr.packet_type == PT_RESPONSE and isinstance(sfrd_src, dict):
        pkt.body = PtResponse(
            response_packet_id=sfrd_src.get("RPID", 0),
            processing_result=sfrd_src.get("PR", 0),
        )

    raw = build_packet(pkt)
    return {"hex": raw.hex().upper(), "bytes": len(raw)}


def _sdr_from_dict(d: dict):
    from egts.codec import ServiceDataRecord, RecordData
    from egts.models import (
        SrPosData, SrStateData, SrLiquidLevelSensor,
        SrAdSensorsData, SrAbsCntrData, SrTermIdentity,
        SrRecordResponse, SrResultCode, SrAuthInfo,
        SrExtPosData, SrCountersData, SrPassengersCounters,
        SrCustom200, SrCustom201, SrCustom202, SrCustom203, SrCustom205, SrRaw,
    )
    from egts.const import (
        SRT_POS_DATA, SRT_STATE_DATA, SRT_STATE_OR_ACCEL,
        SRT_LIQUID_LEVEL_SENSOR, SRT_AD_SENSORS_DATA, SRT_ABS_CNTR_DATA,
        SRT_TERM_IDENTITY, SRT_RECORD_RESPONSE, SRT_RESULT_CODE,
        SRT_AUTH_INFO, SRT_EXT_POS_DATA, SRT_COUNTERS_DATA,
        SRT_PASSENGERS_COUNTERS, SRT_CUSTOM_200, SRT_CUSTOM_201,
        SRT_CUSTOM_202, SRT_CUSTOM_203, SRT_CUSTOM_205,
    )

    sdr = ServiceDataRecord(
        record_number=d.get("RN", 0),
        ssod=str(d.get("SSOD", "0")), rsod=str(d.get("RSOD", "0")),
        grp=str(d.get("GRP", "0")),   rpp=str(d.get("RPP", "00")),
        tmfe=str(d.get("TMFE", "0")), evfe=str(d.get("EVFE", "0")),
        obfe=str(d.get("OBFE", "0")),
        source_service_type=d.get("SST", 2),
        recipient_service_type=d.get("RST_svc", 2),
    )

    _MODEL_MAP = {
        SRT_POS_DATA:            SrPosData,
        SRT_STATE_DATA:          SrStateData,
        SRT_STATE_OR_ACCEL:      SrStateData,
        SRT_LIQUID_LEVEL_SENSOR: SrLiquidLevelSensor,
        SRT_AD_SENSORS_DATA:     SrAdSensorsData,
        SRT_ABS_CNTR_DATA:       SrAbsCntrData,
        SRT_TERM_IDENTITY:       SrTermIdentity,
        SRT_RECORD_RESPONSE:     SrRecordResponse,
        SRT_RESULT_CODE:         SrResultCode,
        SRT_AUTH_INFO:           SrAuthInfo,
        SRT_EXT_POS_DATA:        SrExtPosData,
        SRT_COUNTERS_DATA:       SrCountersData,
        SRT_PASSENGERS_COUNTERS: SrPassengersCounters,
        SRT_CUSTOM_200:          SrCustom200,
        SRT_CUSTOM_201:          SrCustom201,
        SRT_CUSTOM_202:          SrCustom202,
        SRT_CUSTOM_203:          SrCustom203,
        SRT_CUSTOM_205:          SrCustom205,  # LBS (base stations) for road graph positioning (discussion 18)
    }

    for rd_dict in d.get("RD", []):
        srt   = rd_dict.get("SRT", 0)
        srd_d = rd_dict.get("SRD", {})
        Model = _MODEL_MAP.get(srt)
        if Model and hasattr(Model, "from_dict"):
            subrecord = Model.from_dict(srd_d)
        elif Model and hasattr(Model, "from_bytes") and "raw_hex" in srd_d:
            subrecord = Model.from_bytes(bytes.fromhex(srd_d["raw_hex"]))
        else:
            subrecord = SrRaw.from_bytes(srt, bytes.fromhex(srd_d.get("raw_hex", "")))
        raw_b = subrecord.to_bytes()
        sdr.record_data.append(RecordData(srt=srt, srl=len(raw_b), subrecord=subrecord))

    return sdr


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli_decode_hex(hex_str: str) -> None:
    raw  = bytes.fromhex(hex_str.replace(" ", "").replace("\n", ""))
    pkts = parse_stream(raw)
    for i, p in enumerate(pkts):
        log_packet(p, i, _file_logger)
    log_summary(pkts, _file_logger)
    _append_packets(pkts)
    print(f"\nJSON log : {_JSON_LOG}")
    print(f"Text log : {_LOG_FILE}")


def _cli_decode_file(path: str, out_json: str | None = None) -> None:
    all_pkts: list[EGTSPacket] = []
    with open(path, encoding="utf-8") as f:
        for line_no, line in enumerate(f):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            hex_str = line.split(",")[0].strip()
            try:
                pkts = parse_stream(bytes.fromhex(hex_str))
                for i, p in enumerate(pkts):
                    log_packet(p, len(all_pkts) + i, _file_logger)
                all_pkts.extend(pkts)
            except Exception as e:
                print(f"  Line {line_no+1}: {e}")
    log_summary(all_pkts, _file_logger)
    _append_packets(all_pkts)
    if out_json:
        _save_json_log([p.to_dict() for p in all_pkts])
        print(f"JSON: {out_json}")
    print(f"\nJSON log : {_JSON_LOG}")
    print(f"Text log : {_LOG_FILE}")


def _cli_encode(json_path: str) -> None:
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    packets = data.get("packets", [data]) if "packets" in data else [data]
    for i, pkt_dict in enumerate(packets):
        result = _encode_from_dict(pkt_dict)
        print(f"PKT #{i}: {result['hex']}  ({result['bytes']} bytes)")


def _cli_listen(port: int) -> None:
    import socket
    print(f"Listening TCP :{port}  (Ctrl+C to stop)")
    counter = 0
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("0.0.0.0", port))
        srv.listen(5)
        try:
            while True:
                conn, addr = srv.accept()
                print(f"Connected: {addr}")
                with conn:
                    data = b""
                    while chunk := conn.recv(4096):
                        data += chunk
                if data:
                    pkts = parse_stream(data)
                    for p in pkts:
                        log_packet(p, counter, _file_logger)
                        counter += 1
                    _append_packets(pkts)
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(0)

    if args[0] == "--file":
        out = None
        if "--out" in args:
            out = args[args.index("--out") + 1]
        _cli_decode_file(args[1], out)
    elif args[0] == "--encode":
        _cli_encode(args[1])
    elif args[0] == "--listen":
        _cli_listen(int(args[1]) if len(args) > 1 else 6000)
    else:
        _cli_decode_hex(args[0])
