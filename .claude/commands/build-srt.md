# /build-srt

Сгенерируй и закодируй EGTS-пакет с заданным SRT-типом и полями.

## Что делать

Аргумент: `<SRT_TYPE> [field=value ...]`  
Пример: `204 heading=45.5 roll=1.2 pitch=-0.8 accel_x=0.12 ekf_confidence=0.91`

### SRT 204 — IMU / Inertial (discussion 09, 13-16)

Поля (все опциональны, используй дефолты если не указаны):
- `heading` (float, °, 0-360) — курс
- `roll`, `pitch` (float, °, ±180)
- `accel_x`, `accel_y`, `accel_z` (float, g)
- `gyro_x`, `gyro_y`, `gyro_z` (float, °/s)
- `vibration_rms` (float, g), `vibration_peak` (float, g)
- `dominant_freq_hz` (float)
- `ekf_confidence` (float, 0-1)
- `matched_lat`, `matched_lon` (float, °)

Сборка:
```python
from SERVICE.egts.models import SrCustom204
sr = SrCustom204(heading_deg=45.5, roll_deg=1.2, ...)
print(sr.to_bytes().hex().upper())
```

### SRT 205 — LBS (discussion 18)

Поля:
- `serving_cell_id`, `lac_tac`, `mcc`, `mnc`
- `rssi_dbm` (int, отрицательный), `timing_advance` (int, 0-63)
- `bs_lat`, `bs_lon` (float, °)
- `raw_lbs_lat`, `raw_lbs_lon` (float, °)
- `lbs_quality` (int, 0-100)

### SRT 16 — POS_DATA (стандартный)

Поля: `lat`, `lon`, `speed` (км/ч), `heading` (°), `time` (ISO 8601 или unix)

## Вывод

1. HEX подзаписи SRT (raw bytes)
2. Полный пакет EGTS (PT_APPDATA, SST=2, RST=2) как HEX  
3. Длина в байтах и краткая расшифровка полей

## Верификация

После генерации — обязательно сделай roundtrip:
```python
decoded = SrCustom204.from_bytes(encoded)
assert decoded.heading_deg == original.heading_deg  # и т.д.
```

## Зависимости
- `SERVICE/egts/models.py` — все SrCustom* классы
- `SERVICE/egts/vocab.py` — SRT_STOI (для lookup по имени)
- `SERVICE/egts/codec.py` — build_packet / ServiceDataRecord / RecordData
