# /decode-packet

Декодируй EGTS-пакет из hex-строки или файла и объясни каждое поле.

## Что делать

1. Если аргумент — hex-строка (содержит `0-9a-fA-F`, нет пробелов/путей):
   - Запусти: `python -c "from SERVICE.egts.codec import parse_packet; import json; p = parse_packet(bytes.fromhex('$ARGUMENTS')); print(json.dumps(p.to_dict(), indent=2, ensure_ascii=False))"`
   - Выведи результат как prettified JSON

2. Если аргумент — путь к файлу `.bin` или `.egts`:
   - Прочитай файл как байты и распарси через `parse_stream`

3. После JSON-вывода — краткий разбор по-русски:
   - Тип пакета (PT), сервис (SST/RST)
   - Каждый SRT с его именем из `SERVICE/egts/vocab.py::SRT_ITOS`
   - Для SRT 204 (IMU): heading, roll, pitch, ekf_confidence, vibration_rms
   - Для SRT 205 (LBS): serving_cell_id, rssi_dbm, timing_advance, raw_lbs_lat/lon
   - Для SRT 16 (POS_DATA): lat, lon, speed, heading, time
   - Ошибки CRC/HCS помечать красным (⚠️)

## Пример вызова
```
/decode-packet 010011000100100002005204a701...
```

## Зависимости
- `SERVICE/egts/codec.py` — parse_packet / parse_stream
- `SERVICE/egts/vocab.py` — SRT_ITOS, SRT_STOI, описания полей
- `SERVICE/egts/const.py` — все SRT_* константы

## Контекст проекта
EGTS (ГОСТ Р 54619-2011). Кастомные SRT: 200-203 (RTLS), 204 (IMU+EKF), 205 (LBS).
Эпоха EGTS = 2010-01-01 UTC. Координаты в 1e-7 градусах. Углы * 100 (int16).
