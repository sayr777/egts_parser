# EGTS Parser — Документация

## Нормативная база

| Документ | Описание | Файл в репозитории |
|----------|----------|-------------------|
| ГОСТ Р 54619-2011 | Глобальная навигационная спутниковая система. Структура обмена навигационными данными в системах мониторинга транспортных средств | `egts-protocol/docs/gost54619-2011.pdf` |
| ГОСТ Р 33472-2015 | Навигационная деятельность. Прикладное программное обеспечение. Обмен данными между диспетчерскими центрами | `egts-protocol/docs/gost33472-2015.pdf` |
| Приказ МинТранс №285 | О порядке передачи телематических данных в систему ЭРА-ГЛОНАСС | `egts-protocol/docs/mitransNo285.pdf` |
| ТЗ EGTS RTLS v2 | Техническое задание на систему RTLS (Indoor-позиционирование) | `DOCS/TZ_EGTS_RTLS_v2.docx` |

---

## Структура репозитория

```
egts_parser/
├── DOCS/                            ← эта папка
│   ├── README.md                    ← общая документация (этот файл)
│   ├── SERVICE.md                   ← документация сервиса (Cloud Function)
│   ├── make_landing.py              ← генератор PDF лендинга
│   ├── egts_tracker_landing.pdf     ← лендинг-страница проекта
│   └── TZ_EGTS_RTLS_v2.docx        ← ТЗ на RTLS-систему
│
├── SERVICE/                         ← Yandex Cloud Function + CLI-парсер
│   ├── handler.py                   ← точка входа (handler + CLI-режим)
│   ├── requirements.txt             ← пустой (только stdlib)
│   └── egts/
│       ├── __init__.py
│       ├── crc.py                   ← CRC-8 / CRC-16 (lookup tables)
│       ├── const.py                 ← константы: SRT, PT, коды результата
│       ├── models.py                ← dataclasses для всех SRT-типов
│       ├── codec.py                 ← parse_packet() / build_packet()
│       └── log.py                   ← ANSI-лог + JSON-лог файл
│
├── PARSER/                          ← Двунаправленный Excel-парсер
│   └── egts_excel_parser.py         ← decode CSV/hex → xlsx  +  encode xlsx → binary
│
├── MOBILE_APP/                      ← Flutter Android-приложение
│   ├── egts_tracker.apk             ← собранный APK (android-arm64 release, ~18 MB)
│   ├── pubspec.yaml
│   ├── android/
│   └── lib/
│       ├── main.dart
│       ├── models/models.dart       ← NfcEntry, BeaconEntry, WifiEntry, GpsData, ...
│       ├── core/
│       │   ├── tracker_provider.dart  ← ChangeNotifier: GPS + BLE + WiFi + NFC
│       │   ├── prefs/app_prefs.dart   ← SharedPreferences (whitelist, config)
│       │   └── egts/
│       │       ├── egts_crc.dart      ← CRC-8 / CRC-16
│       │       ├── egts_builder.dart  ← формирование пакетов EGTS
│       │       └── egts_client.dart   ← HTTP POST на Cloud Function
│       ├── screens/
│       │   ├── monitoring/           ← вкладки: События / NFC / iBeacon / WiFi
│       │   └── settings/             ← сервер + белые списки
│       └── widgets/
│           └── egts_packet_view.dart ← раскрываемая карточка пакета
│
└── egts-protocol/                   ← Go-реализация (оригинал, read-only)
    ├── libs/egts/                   ← библиотека протокола на Go
    ├── cli/receiver/                ← TCP-сервер
    └── docs/                        ← PDF стандартов
```

---

## Протокол EGTS — краткое описание

### Формат пакета

```
┌──────────────────────────────────────────────────────┐
│ HEADER (11 байт, или 16 при RTE=1)                   │
│  PRV(1) SKID(1) FLAGS(1) HL(1) HE(1) FDL(2)         │
│  PID(2) PT(1) [PRA(2) RCA(2) TTL(1)] HCS(1)         │
├──────────────────────────────────────────────────────┤
│ SFRD — тело пакета (FDL байт)                        │
│  Для PT=1 (PT_APPDATA): набор SDR                    │
│  Для PT=0 (PT_RESPONSE): RPID(2) PR(1) [SDR...]     │
├──────────────────────────────────────────────────────┤
│ SFRCS — CRC-16 тела (2 байта)                        │
└──────────────────────────────────────────────────────┘
```

### Типы пакетов (PT)

| Код | Название | Описание |
|-----|----------|----------|
| 0 | EGTS_PT_RESPONSE | Подтверждение ранее принятого пакета |
| 1 | EGTS_PT_APPDATA | Пакет с данными от терминала |

### Service Data Record (SDR)

```
RL(2) RN(2) FLAGS(1) [OID(4)] [EVID(4)] [TM(4)] SST(1) RST(1) RD(RL байт)
```

### Типы сервисов (SST/RST)

| Код | Название | Описание |
|-----|----------|----------|
| 1 | EGTS_AUTH_SERVICE | Авторизация терминала |
| 2 | EGTS_TELEDATA_SERVICE | Телематические данные (навигация, датчики) |

---

## Поддерживаемые типы подзаписей (SRT)

### Стандартные (ГОСТ Р 54619-2011)

| SRT | Название | Описание |
|-----|----------|----------|
| 0 | EGTS_SR_RECORD_RESPONSE | Ответ на запись |
| 1 | EGTS_SR_TERM_IDENTITY | Идентификация терминала (TID, IMEI, IMSI) |
| 2 | EGTS_SR_MODULE_DATA | Данные модуля |
| 5 | EGTS_SR_DISPATCHER_IDENTITY | Идентификация диспетчера |
| 7 | EGTS_SR_AUTH_INFO | Информация авторизации |
| 9 | EGTS_SR_RESULT_CODE | Код результата |
| 15 | EGTS_SR_EGTS_PLUS_DATA | Расширение EGTS+ |
| 16 | EGTS_SR_POS_DATA | Основные данные позиции (навигация) |
| 17 | EGTS_SR_EXT_POS_DATA | Расширенные данные позиции (DOP, кол-во спутников) |
| 18 | EGTS_SR_AD_SENSORS_DATA | Аналого-цифровые датчики |
| 19 | EGTS_SR_COUNTERS_DATA | Счётчики |
| 21 | EGTS_SR_STATE_DATA | Состояние терминала (питание, напряжение) |
| 22 | EGTS_SR_LOOPIN_DATA | Данные шлейфов |
| 23 | EGTS_SR_ABS_DIG_SENS_DATA | Абсолютные цифровые датчики |
| 24 | EGTS_SR_ABS_AN_SENS_DATA | Абсолютные аналоговые датчики |
| 25 | EGTS_SR_ABS_CNTR_DATA | Абсолютные счётчики |
| 26 | EGTS_SR_ABS_LOOPIN_DATA | Абсолютные данные шлейфов |
| 27 | EGTS_SR_LIQUID_LEVEL_SENSOR | Датчик уровня жидкости (ДУТ) |
| 28 | EGTS_SR_PASSENGERS_COUNTERS | Счётчики пассажиров |

### Расширения RTLS (vendor, SRT 200–203)

| SRT | Название | Описание |
|-----|----------|----------|
| 200 | EGTS_SR_CUSTOM_SRT200 | Расширенные координаты RTLS (X/Y/Z в мм, quality) |
| 201 | EGTS_SR_CUSTOM_SRT201 | Данные датчиков RTLS (температура, вибрация, давление) |
| 202 | EGTS_SR_CUSTOM_SRT202 | Идентификация RTLS-метки (tag_id, zone_id, group_id, RSSI) |
| 203 | EGTS_SR_CUSTOM_SRT203 | Событийные данные RTLS (зона, тип события, время) |

#### SRT 200 — RTLS Extended Position (структура)
```
Offset  Size  Field    Описание
0       4     X        Координата X (int32, мм)
4       4     Y        Координата Y (int32, мм)
8       4     Z        Координата Z (int32, мм)
12      2     quality  Качество позиционирования 0–100 (uint16)
```

#### SRT 201 — RTLS Sensor Data (структура)
```
Offset  Size  Field            Описание
0       2     temperature_01C  Температура ×0.1°C (int16)
2       2     vibration        Вибрация (uint16, усл. ед.)
4       2     pressure_hPa     Давление (uint16, гПа)
6       1     sensor_flags     Флаги статуса датчиков
```

#### SRT 202 — RTLS Tag Identity (структура)
```
Offset  Size  Field     Описание
0       4     tag_id    ID метки (uint32)
4       2     zone_id   ID зоны (uint16)
6       2     group_id  ID группы (uint16)
8       1     rssi      RSSI (int8, дБм)
```

#### SRT 203 — RTLS Event Data (структура)
```
Offset  Size  Field        Описание
0       1     event_type   Тип события (0=none,1=enter,2=exit,3=alarm,4=low_bat,5=tamper)
1       4     zone_id      ID зоны (uint32)
5       4     event_time   Время события (uint32, сек с 2010-01-01 UTC)
9       1     event_flags  Флаги события
```

---

## Поля EGTS_SR_POS_DATA

| Поле | Тип | Описание |
|------|-----|----------|
| NTM | uint32 | Время навигации (сек с 2010-01-01 UTC) |
| LAT | uint32 | Широта = LAT/0xFFFFFFFF×90° |
| LONG | uint32 | Долгота = LONG/0xFFFFFFFF×180° |
| ALTE | bit | Наличие поля высоты |
| LOHS | bit | Знак долготы (1=западная) |
| LAHS | bit | Знак широты (1=южная) |
| MV | bit | Движение (1=в движении) |
| BB | bit | Работа от резервного питания |
| CS | bit | Тип координатной системы (0=WGS-84) |
| FIX | bit | Тип определения координат (0=2D, 1=3D) |
| VLD | bit | Достоверность навигационных данных |
| SPD | uint14 | Скорость ×0.1 км/ч |
| DIRH | bit | Старший бит направления |
| ALTS | bit | Знак высоты |
| DIR | uint8 | Направление 0–255 (≈ 0–360°) |
| ODM | uint24 | Пробег ×0.1 км |
| DIN | uint8 | Состояние дискретных входов |
| SRC | uint8 | Источник/событие |
| ALT | uint24 | Высота над уровнем моря (м), при ALTE=1 |
| SRCD | int16 | Данные источника |

---

## Быстрый старт

### SERVICE — декодирование hex-пакета (CLI)

```bash
cd SERVICE
python handler.py 0100000B007503C30501AAA600EF0C812C823F02
```

### SERVICE — разбор CSV-файла с пакетами

```bash
python handler.py --file ../egts-protocol/test/egts_packages.csv
```

### SERVICE — TCP-режим (ожидание пакетов)

```bash
python handler.py --listen 6000
```

### SERVICE — re-encode (атрибуты → бинарный)

```bash
python handler.py --encode packet.json
```

### PARSER — генерация Excel из CSV

```bash
cd PARSER
pip install openpyxl
python egts_excel_parser.py decode ../egts-protocol/test/egts_packages.csv report.xlsx
```

### PARSER — кодирование Excel → binary (с пересчётом CRC)

```bash
python egts_excel_parser.py encode report.xlsx output.bin
```

### MOBILE_APP — установка APK

```bash
# Установить на подключённый Android-устройство через ADB
adb install MOBILE_APP/egts_tracker.apk

# Или открыть файл вручную на устройстве (разрешить установку из неизвестных источников)
```

### Yandex Cloud Function — развёртывание

```bash
cd SERVICE
zip -r egts_service.zip egts/ handler.py requirements.txt

yc serverless function version create \
  --function-name egts-parser \
  --runtime python311 \
  --entrypoint handler.handler \
  --memory 256m \
  --execution-timeout 10s \
  --source-path ./egts_service.zip \
  --environment EGTS_LOG_DIR=/tmp
```

Точка входа: `handler.handler`.  
Среда выполнения: **Python 3.11** (нет внешних зависимостей).

Пример запроса:
```json
{
  "body": "0100000B007503C30501AAA600EF0C812C823F02",
  "isBase64Encoded": false
}
```

---

## CRC

- **CRC-8** (заголовок): полином `0x31`, начальное значение `0xFF`
- **CRC-16** (тело): полином `0x1021` (CRC-CCITT), начальное значение `0xFFFF`

---

## Коды результата (PC)

| Код | Константа | Описание |
|-----|-----------|----------|
| 0 | EGTS_PC_OK | Успешно |
| 1 | EGTS_PC_IN_PROGRESS | В обработке |
| 128 | EGTS_PC_UNS_PROTOCOL | Неподдерживаемый протокол |
| 130 | EGTS_PC_INC_DATAFORM | Некорректный формат данных |
| 131 | EGTS_PC_INC_HEADERFORM | Некорректный формат заголовка |
| 136 | EGTS_PC_INC_HEADERCRC | Ошибка CRC заголовка |
| 137 | EGTS_PC_INC_DATACRC | Ошибка CRC данных |
| 150 | EGTS_PC_AUTH_DENIED | Авторизация отклонена |

Полный список — в `egts-protocol/libs/egts/errors.go`.

---

## Мобильное приложение — обзор

**EGTS Tracker** — Flutter Android-приложение, которое сканирует окружающие устройства позиционирования и формирует стандартные EGTS-пакеты для отправки в Cloud Function.

### Экраны

| Экран | Описание |
|-------|----------|
| **Мониторинг → События** | Лента отправленных EGTS-пакетов с раскрываемой структурой |
| **Мониторинг → NFC** | Считанные NFC/RFID-метки |
| **Мониторинг → iBeacon** | Обнаруженные BLE-маяки с RSSI и дистанцией |
| **Мониторинг → WiFi** | Точки доступа с SSID/BSSID/RSSI |
| **Настройки → Сервер** | URL функции, IAM-токен, Terminal ID |
| **Настройки → Белые списки** | NFC (по UID), iBeacon (UUID+Major+Minor), WiFi (SSID/BSSID) |

### Логика триггеров

```
NFC/RFID считан  →  UID в белом списке?  →  Да  →  Формировать + отправить EGTS
iBeacon обнаружен → UUID+Major+Minor?    →  Да  →  Формировать + отправить EGTS
WiFi AP найдена  →  SSID/BSSID в списке? →  Да  →  Формировать + отправить EGTS
```

Пакет содержит: **SRT 16** (GPS), **SRT 17** (DOP), **SRT 21** (State), **SRT 202** (TagID), **SRT 203** (Event).

### Зависимости Flutter

| Пакет | Версия | Назначение |
|-------|--------|------------|
| `flutter_nfc_kit` | ^3.4.0 | Считывание NFC/RFID |
| `flutter_blue_plus` | ^1.32.12 | BLE сканирование → iBeacon |
| `wifi_scan` | ^0.4.1 | WiFi AP сканирование |
| `geolocator` | ^11.1.0 | GPS/ГЛОНАСС позиционирование |
| `provider` | ^6.1.2 | State management |
| `shared_preferences` | ^2.2.3 | Хранение белых списков |
| `http` | ^1.2.1 | HTTP POST на сервер |
| `flutter_slidable` | ^3.1.0 | Свайп для удаления из списка |
| `intl` | ^0.19.0 | Форматирование дат |

### Сборка из исходников

```bash
cd MOBILE_APP
flutter pub get
flutter build apk --release --target-platform android-arm64
# APK: build/app/outputs/flutter-apk/app-release.apk
```
