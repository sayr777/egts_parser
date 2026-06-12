"""
EGTS vocabulary — all lookup tables in one place.

Inspired by Andrej Karpathy's character-level language model style:
    stoi = string → index  (name  → code)
    itos = index → string  (code  → name)

Usage:
    from egts.vocab import SRT_ITOS, SRT_STOI, SRT_DESC
    from egts.vocab import decode_srt, decode_pt, decode_result

    name = SRT_ITOS[204]          # "EGTS_SR_CUSTOM_SRT204"
    code = SRT_STOI["POS_DATA"]   # 16
    desc = SRT_DESC[204]          # "IMU + EKF + Map Match (RTLS v2, discussions 09/13-16)"
"""

# ---------------------------------------------------------------------------
# SRT  (SubRecord Type)
# ---------------------------------------------------------------------------

# itos: index → full string name   (canonical, matches GOST R 54619)
SRT_ITOS: dict[int, str] = {
    0:   "EGTS_SR_RECORD_RESPONSE",
    1:   "EGTS_SR_TERM_IDENTITY",
    2:   "EGTS_SR_MODULE_DATA",
    5:   "EGTS_SR_DISPATCHER_IDENTITY",
    7:   "EGTS_SR_AUTH_INFO",
    9:   "EGTS_SR_RESULT_CODE",
    15:  "EGTS_SR_EGTS_PLUS_DATA",
    16:  "EGTS_SR_POS_DATA",
    17:  "EGTS_SR_EXT_POS_DATA",
    18:  "EGTS_SR_AD_SENSORS_DATA",
    19:  "EGTS_SR_COUNTERS_DATA",
    20:  "EGTS_SR_STATE_DATA",            # also ACCEL at len!=5
    21:  "EGTS_SR_STATE_DATA",
    22:  "EGTS_SR_LOOPIN_DATA",
    23:  "EGTS_SR_ABS_DIG_SENS_DATA",
    24:  "EGTS_SR_ABS_AN_SENS_DATA",
    25:  "EGTS_SR_ABS_CNTR_DATA",
    26:  "EGTS_SR_ABS_LOOPIN_DATA",
    27:  "EGTS_SR_LIQUID_LEVEL_SENSOR",
    28:  "EGTS_SR_PASSENGERS_COUNTERS",
    # RTLS v2 extensions (custom, non-GOST)
    200: "EGTS_SR_CUSTOM_SRT200",
    201: "EGTS_SR_CUSTOM_SRT201",
    202: "EGTS_SR_CUSTOM_SRT202",
    203: "EGTS_SR_CUSTOM_SRT203",
    204: "EGTS_SR_CUSTOM_SRT204",
    205: "EGTS_SR_CUSTOM_SRT205",
}

# stoi: short alias → code   (for human input, case-insensitive keys)
SRT_STOI: dict[str, int] = {
    "RECORD_RESPONSE":     0,
    "TERM_IDENTITY":       1,
    "MODULE_DATA":         2,
    "DISPATCHER_IDENTITY": 5,
    "AUTH_INFO":           7,
    "RESULT_CODE":         9,
    "EGTS_PLUS_DATA":      15,
    "POS_DATA":            16,
    "EXT_POS_DATA":        17,
    "AD_SENSORS_DATA":     18,
    "COUNTERS_DATA":       19,
    "STATE_DATA":          20,
    "LOOPIN_DATA":         22,
    "ABS_DIG_SENS_DATA":   23,
    "ABS_AN_SENS_DATA":    24,
    "ABS_CNTR_DATA":       25,
    "ABS_LOOPIN_DATA":     26,
    "LIQUID_LEVEL_SENSOR": 27,
    "PASSENGERS_COUNTERS": 28,
    "SRT200":              200,
    "SRT201":              201,
    "SRT202":              202,
    "SRT203":              203,
    "SRT204":              204,  # IMU
    "SRT205":              205,  # LBS
    "IMU":                 204,
    "INERTIAL":            204,
    "LBS":                 205,
}

# Human-readable description of each SRT
SRT_DESC: dict[int, str] = {
    0:   "Ответ на запись (ACK)",
    1:   "Идентификация терминала (IMEI, IMSI, VIN и т.д.)",
    2:   "Данные модуля (версия ПО/ФФ)",
    5:   "Идентификация диспетчера",
    7:   "Аутентификационная информация",
    9:   "Код результата операции",
    15:  "EGTS+ данные (расширенный формат)",
    16:  "Позиционные данные (lat/lon/speed/heading/time) — основной SRT",
    17:  "Расширенные позиционные данные (HDOP, VDOP, высота)",
    18:  "Данные аналоговых и дискретных датчиков",
    19:  "Данные счётчиков",
    20:  "Состояние терминала / Данные акселерометра",
    21:  "Состояние терминала (5 байт)",
    22:  "Данные шлейфа",
    23:  "Абс. данные дискр. датчиков",
    24:  "Абс. данные аналог. датчиков",
    25:  "Абсолютные данные счётчиков",
    26:  "Абс. данные шлейфа",
    27:  "Данные датчика уровня жидкости",
    28:  "Данные счётчика пассажиров",
    # RTLS v2
    200: "RTLS: координаты метки (x, y, z, tag_id)",
    201: "RTLS: данные якорей (anchor_id, rssi)",
    202: "RTLS: ориентация метки (heading, roll, pitch от IMU)",
    203: "RTLS: зона/регион (zone_id, flags)",
    204: "IMU + EKF + Map Match (RTLS v2, discussions 09/13-16)\n"
         "  → heading, roll, pitch, accel/gyro xyz, vibration_rms/peak,\n"
         "  → ekf_confidence, cov_trace, road_segment_id, matched_lat/lon",
    205: "LBS: данные базовых станций для road-graph позиционирования (discussion 18)\n"
         "  → serving_cell_id, LAC/TAC, MCC/MNC, RSSI, Timing Advance,\n"
         "  → bs_lat/lon, neighbors[6], raw_lbs_lat/lon, lbs_quality",
}

# SRT wire sizes (bytes, fixed-length SRTs only; variable → None)
SRT_SIZE: dict[int, int | None] = {
    0:   3,
    9:   1,
    16:  21,
    17:  8,
    20:  None,   # 4 or 5 depending on subtype
    21:  5,
    25:  6,
    204: 50,     # fixed: see SrCustom204.to_bytes()
    205: None,   # variable (depends on neighbors count)
}

# ---------------------------------------------------------------------------
# PT  (Packet Type)
# ---------------------------------------------------------------------------

PT_ITOS: dict[int, str] = {
    0: "EGTS_PT_RESPONSE",
    1: "EGTS_PT_APPDATA",
    3: "EGTS_PT_SIGNED_APPDATA",
}

PT_STOI: dict[str, int] = {v.replace("EGTS_PT_", ""): k for k, v in PT_ITOS.items()}

PT_DESC: dict[int, str] = {
    0: "Ответ сервера/клиента на пакет данных",
    1: "Пакет прикладных данных (основной тип отправки)",
    3: "Пакет данных с подписью (ГОСТ Р 34.11)",
}

# ---------------------------------------------------------------------------
# SVC  (Service Type)
# ---------------------------------------------------------------------------

SVC_ITOS: dict[int, str] = {
    1: "EGTS_AUTH_SERVICE",
    2: "EGTS_TELEDATA_SERVICE",
    4: "EGTS_COMMANDS_SERVICE",
    9: "EGTS_FIRMWARE_SERVICE",
    10: "EGTS_ECALL_SERVICE",
}

SVC_STOI: dict[str, int] = {v.replace("EGTS_", "").replace("_SERVICE", ""): k for k, v in SVC_ITOS.items()}

SVC_DESC: dict[int, str] = {
    1:  "Аутентификация терминала (IMEI, ключи, результат)",
    2:  "Телематические данные (позиция, датчики, IMU, LBS)",
    4:  "Команды управления терминалом",
    9:  "Прошивка OTA",
    10: "eCall / экстренный вызов",
}

# ---------------------------------------------------------------------------
# Result codes
# ---------------------------------------------------------------------------

RC_ITOS: dict[int, str] = {
    0:   "EGTS_PC_OK",
    1:   "EGTS_PC_IN_PROGRESS",
    128: "EGTS_PC_UNS_PROTOCOL",
    129: "EGTS_PC_DECRYPT_ERROR",
    130: "EGTS_PC_INC_DATAFORM",
    131: "EGTS_PC_INC_HEADERFORM",
    132: "EGTS_PC_UNS_TYPE",
    133: "EGTS_PC_NOTEN_PARAMS",
    134: "EGTS_PC_DBL_PROC",
    135: "EGTS_PC_PROC_DENIED",
    136: "EGTS_PC_INC_HEADERCRC",
    137: "EGTS_PC_INC_DATACRC",
    138: "EGTS_PC_INVDATALEN",
    139: "EGTS_PC_ROUTE_NFOUND",
    140: "EGTS_PC_ROUTE_CLOSED",
    141: "EGTS_PC_ROUTE_DENIED",
    142: "EGTS_PC_INVADDR",
    143: "EGTS_PC_TTLEXPIRED",
    144: "EGTS_PC_NO_ACK",
    145: "EGTS_PC_OBJ_NFOUND",
    146: "EGTS_PC_EVNT_NFOUND",
    147: "EGTS_PC_SRVC_NFOUND",
    148: "EGTS_PC_SRVC_DENIED",
    149: "EGTS_PC_SRVC_UNKN",
    150: "EGTS_PC_AUTH_DENIED",
    151: "EGTS_PC_ALREADY_EXISTS",
    152: "EGTS_PC_ID_NFOUND",
    153: "EGTS_PC_INC_DATETIME",
    154: "EGTS_PC_IO_ERROR",
    155: "EGTS_PC_NO_RES_AVAIL",
    156: "EGTS_PC_MODULE_FAULT",
    157: "EGTS_PC_MODULE_PWR_FLT",
    158: "EGTS_PC_MODULE_PROC_FLT",
    159: "EGTS_PC_MODULE_SW_FLT",
    160: "EGTS_PC_MODULE_FW_FLT",
    161: "EGTS_PC_MODULE_IO_FLT",
    162: "EGTS_PC_MODULE_MEM_FLT",
    163: "EGTS_PC_TEST_FAILED",
}

RC_STOI: dict[str, int] = {v: k for k, v in RC_ITOS.items()}

RC_DESC: dict[int, str] = {
    0:   "Успех",
    1:   "В процессе выполнения",
    128: "Неподдерживаемый протокол",
    129: "Ошибка дешифрования",
    130: "Некорректный формат данных",
    131: "Некорректный формат заголовка",
    132: "Неподдерживаемый тип",
    133: "Недостаточно параметров",
    134: "Двойная обработка",
    135: "Обработка запрещена",
    136: "Ошибка CRC заголовка",
    137: "Ошибка CRC данных",
    138: "Неверная длина данных",
    139: "Маршрут не найден",
    140: "Маршрут закрыт",
    141: "Маршрутизация запрещена",
    142: "Неверный адрес",
    143: "TTL истёк",
    144: "Нет подтверждения",
    145: "Объект не найден",
    146: "Событие не найдено",
    147: "Сервис не найден",
    148: "Сервис запрещён",
    149: "Неизвестный сервис",
    150: "Аутентификация запрещена",
    151: "Уже существует",
    152: "ID не найден",
    153: "Некорректная дата/время",
    154: "Ошибка ввода/вывода",
    155: "Нет доступных ресурсов",
    156: "Неисправность модуля",
    157: "Неисправность питания модуля",
    158: "Неисправность процессора модуля",
    159: "Неисправность ПО модуля",
    160: "Неисправность прошивки модуля",
    161: "Неисправность I/O модуля",
    162: "Неисправность памяти модуля",
    163: "Самодиагностика не прошла",
}

# ---------------------------------------------------------------------------
# Convenience decoders
# ---------------------------------------------------------------------------

def decode_srt(code: int) -> tuple[str, str]:
    """Return (name, description) for SRT code."""
    return SRT_ITOS.get(code, f"SRT_{code}_UNKNOWN"), SRT_DESC.get(code, "—")


def decode_pt(code: int) -> tuple[str, str]:
    return PT_ITOS.get(code, f"PT_{code}_UNKNOWN"), PT_DESC.get(code, "—")


def decode_svc(code: int) -> tuple[str, str]:
    return SVC_ITOS.get(code, f"SVC_{code}_UNKNOWN"), SVC_DESC.get(code, "—")


def decode_result(code: int) -> tuple[str, str]:
    return RC_ITOS.get(code, f"RC_{code}_UNKNOWN"), RC_DESC.get(code, "—")


def srt_from_name(name: str) -> int:
    """Lookup SRT code by short alias (case-insensitive). Raises KeyError if unknown."""
    return SRT_STOI[name.upper().replace("EGTS_SR_CUSTOM_", "").replace("EGTS_SR_", "")]


# ---------------------------------------------------------------------------
# Self-check  (python -m SERVICE.egts.vocab)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== EGTS Vocabulary ===\n")
    print(f"{'CODE':>5}  {'NAME':<40}  {'SIZE':>5}  DESCRIPTION")
    print("-" * 90)
    for code in sorted(SRT_ITOS):
        name = SRT_ITOS[code]
        size = SRT_SIZE.get(code)
        size_s = str(size) if size else "var"
        desc = SRT_DESC.get(code, "—").split("\n")[0]
        print(f"{code:>5}  {name:<40}  {size_s:>5}  {desc}")
    print()
    print(f"PT  codes : {list(PT_ITOS)}")
    print(f"SVC codes : {list(SVC_ITOS)}")
    print(f"RC  codes : {len(RC_ITOS)} entries (0..163)")
