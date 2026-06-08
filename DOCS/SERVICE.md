# EGTS Parser Service — Документация

## Оглавление

1. [Назначение сервиса](#1-назначение-сервиса)
2. [Архитектура](#2-архитектура)
3. [Как работает](#3-как-работает)
4. [Установка на Yandex Cloud Functions](#4-установка-на-yandex-cloud-functions)
5. [Конфигурация](#5-конфигурация)
6. [API Reference](#6-api-reference)
7. [Форматы данных](#7-форматы-данных)
8. [Мобильное приложение](#8-мобильное-приложение)
9. [Устранение неисправностей](#9-устранение-неисправностей)

---

## 1. Назначение сервиса

**EGTS Parser Service** — серверная функция для приёма, декодирования и анализа бинарных пакетов протокола **EGTS** (ГОСТ Р 54619-2011, Приказ МинТранс РФ №285).

### Что делает сервис

| Функция | Описание |
|---------|----------|
| **Приём пакетов** | Принимает бинарные EGTS-пакеты по HTTP (hex-строка или base64) |
| **Декодирование** | Разбирает пакет на структурные части: Header, SDR, SRT-подзаписи |
| **Валидация CRC** | Проверяет CRC-8 заголовка и CRC-16 тела (ГОСТ Р 54619-2011) |
| **JSON-вывод** | Возвращает JSON с полной структурой пакета |
| **Логирование** | Записывает терминальный лог и JSON-лог файл |
| **Re-encode** | Принимает JSON пакета, изменяет атрибуты и пересчитывает бинарный вид |

### Для кого

- **Системы мониторинга транспорта** — приём телематики от GPS-трекеров
- **RTLS-системы** — приём событий от iBeacon / RFID / WiFi-меток
- **Разработчики** — отладка и тестирование EGTS-устройств
- **Интеграция** — промежуточный слой между трекерами и базой данных

---

## 2. Архитектура

```
┌─────────────────────────────────────────────────────────────────────┐
│                          КЛИЕНТЫ                                     │
│                                                                      │
│  GPS-трекер          EGTS Android App       Тестовый скрипт         │
│  (GLONASS/GPS)       (iBeacon/RFID/WiFi)    (send_egts.py)          │
└────────────┬──────────────────┬──────────────────┬───────────────────┘
             │ TCP/UDP          │ HTTPS POST        │ HTTPS POST
             │                  │ (hex JSON)         │ (hex JSON)
             ▼                  ▼                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│               YANDEX CLOUD FUNCTIONS                                 │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  handler.py — точка входа (handler(event, context))         │    │
│  │                                                             │    │
│  │  egts/                                                      │    │
│  │  ├── codec.py    — parse_packet() / build_packet()          │    │
│  │  ├── models.py   — dataclasses (encode + decode)            │    │
│  │  ├── crc.py      — CRC-8 / CRC-16                          │    │
│  │  ├── const.py    — константы SRT, PT, коды результата       │    │
│  │  └── log.py      — терминальный + файловый лог              │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  Логи: /tmp/egts_YYYYMMDD.log  +  /tmp/egts_YYYYMMDD.json          │
└─────────────────────────────────────────────────────────────────────┘
             │
             ▼ JSON response
┌─────────────────────────────────────────────────────────────────────┐
│               ПОТРЕБИТЕЛИ ДАННЫХ                                     │
│  PostgreSQL / ClickHouse / Yandex YDB / Kafka / S3                  │
└─────────────────────────────────────────────────────────────────────┘
```

### Поток обработки пакета

```
Binary EGTS (hex) 
    → Decode Header   (PRV, SKID, FLAGS, HL, HE, FDL, PID, PT)
    → Validate CRC-8  (заголовок)
    → Decode SFRD     (зависит от PT: PT_APPDATA или PT_RESPONSE)
    → Decode SDR[]    (Service Data Records)
    → Decode RD[]     (Record Data — подзаписи по типу SRT)
    → JSON output     (полная структура)
    → Log file        (txt + json)
```

---

## 3. Как работает

### 3.1 Структура пакета EGTS

```
Байты    Поле   Описание
──────────────────────────────────────────────────────────────
0        PRV    Версия протокола (всегда 0x01)
1        SKID   ID ключа шифрования (0x00 = нет шифрования)
2        FLAGS  Байт флагов: PRF(2) RTE(1) ENA(2) CMP(1) PR(2)
3        HL     Длина заголовка (11 или 16 при RTE=1)
4        HE     Метод кодирования заголовка (0x00)
5-6      FDL    Длина тела пакета (uint16 LE)
7-8      PID    Идентификатор пакета (uint16 LE)
9        PT     Тип пакета (0=PT_RESPONSE, 1=PT_APPDATA)
[10-14]  PRA,RCA,TTL  (только при RTE=1)
10/15    HCS    CRC-8 заголовка
──────────────────────────────────────────────────────────────
...      SFRD   Тело пакета (FDL байт)
...      SFRCS  CRC-16 тела (uint16 LE)
```

### 3.2 Service Data Record (SDR)

```
Байты  Поле  Описание
──────────────────────────────────────────────────────────────
0-1    RL    Длина данных записи (uint16 LE)
2-3    RN    Номер записи (uint16 LE)
4      FLAGS SSOD|RSOD|GRP|RPP|TMFE|EVFE|OBFE
[...]  OID   ID объекта (4 байта, если OBFE=1)
[...]  EVID  ID события (4 байта, если EVFE=1)
[...]  TM    Время (4 байта сек с 2010-01-01, если TMFE=1)
...    SST   Тип сервиса отправителя (1=AUTH, 2=TELEDATA)
...    RST   Тип сервиса получателя
...    RD    Данные подзаписей
```

### 3.3 Подзапись (Subrecord)

```
Байты  Поле  Описание
──────────────────────────────────────────────────────────────
0      SRT   Тип подзаписи (0-28 стандарт, 200-203 RTLS)
1-2    SRL   Длина данных подзаписи (uint16 LE)
...    SRD   Данные подзаписи (SRL байт)
```

### 3.4 Пример декодирования SRT=16 (GPS позиция)

```
SRD bytes: C3 F3 E5 10  ← NTM (сек с 2010-01-01)
           00 B5 7C 9E  ← LAT: 0x9E7CB500 / 0xFFFFFFFF × 90 = 55.71°N
           00 58 3F 35  ← LON: 0x353F5800 / 0xFFFFFFFF × 180 = 37.44°E
           93 23 80 57  ← FLAGS + SPD(14бит) + ...
           82 10 00 01  ← DIR, ODM(3б), DIN, SRC
```

---

## 4. Установка на Yandex Cloud Functions

### 4.1 Предварительные требования

- Аккаунт Yandex Cloud
- Установленный [Yandex Cloud CLI](https://cloud.yandex.ru/docs/cli/quickstart)
- Python 3.11+ (для локального тестирования)

### 4.2 Шаг 1: Создание папки и сервисного аккаунта

```bash
# Войти в Yandex Cloud
yc init

# Создать папку проекта
yc resource-manager folder create --name egts-parser

# Создать сервисный аккаунт
yc iam service-account create --name egts-sa --folder-name egts-parser

# Выдать права на вызов функций
yc resource-manager folder add-access-binding egts-parser \
  --role serverless.functions.invoker \
  --subject serviceAccount:$(yc iam service-account get egts-sa --format json | jq -r .id)
```

### 4.3 Шаг 2: Подготовка архива

```bash
cd egts_parser/SERVICE

# Создать архив (только нужные файлы, без __pycache__)
zip -r egts_service.zip egts/ handler.py requirements.txt \
    --exclude "**/__pycache__/*" "**/*.pyc"
```

**Структура архива:**
```
egts_service.zip
├── handler.py           ← точка входа
├── requirements.txt     ← (пустой, нет внешних зав-тей)
└── egts/
    ├── __init__.py
    ├── crc.py
    ├── const.py
    ├── models.py
    ├── codec.py
    └── log.py
```

### 4.4 Шаг 3: Создание функции через веб-интерфейс

1. Откройте [console.cloud.yandex.ru](https://console.cloud.yandex.ru)
2. Перейдите: **Cloud Functions → Создать функцию**
3. Заполните:

| Параметр | Значение |
|----------|----------|
| Имя | `egts-parser` |
| Среда выполнения | `python311` |
| Точка входа | `handler.handler` |
| Таймаут | `10 секунд` |
| Память | `256 МБ` |
| Сервисный аккаунт | `egts-sa` |

4. **Способ загрузки:** ZIP-архив → загрузите `egts_service.zip`
5. Нажмите **Создать версию**

### 4.5 Шаг 3 (альтернатива): CLI

```bash
# Создать функцию
yc serverless function create \
  --name egts-parser \
  --folder-name egts-parser

# Загрузить версию
yc serverless function version create \
  --function-name egts-parser \
  --folder-name egts-parser \
  --runtime python311 \
  --entrypoint handler.handler \
  --memory 256m \
  --execution-timeout 10s \
  --source-path ./egts_service.zip \
  --environment EGTS_LOG_DIR=/tmp

# Сделать функцию публичной (для тестирования)
yc serverless function allow-unauthenticated-invoke egts-parser \
  --folder-name egts-parser

# Получить URL функции
yc serverless function get egts-parser --folder-name egts-parser
```

### 4.6 Шаг 4: Переменные окружения

В консоли: **Функция → Редактировать → Переменные окружения**

| Переменная | Значение | Описание |
|------------|----------|----------|
| `EGTS_LOG_DIR` | `/tmp` | Директория для лог-файлов |

> **Внимание:** `/tmp` в Cloud Functions — временная файловая система. Логи сбрасываются при перезапуске контейнера. Для persistent-хранения подключите Yandex Object Storage (S3) или Yandex Managed Service for PostgreSQL.

### 4.7 Шаг 5: API Gateway (опционально)

Для получения фиксированного URL с кастомным доменом:

```bash
# Создать API Gateway
yc serverless api-gateway create \
  --name egts-gateway \
  --spec - <<EOF
openapi: "3.0.0"
info:
  title: EGTS Parser API
  version: "1.0"
paths:
  /parse:
    post:
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: YOUR_FUNCTION_ID
        service_account_id: YOUR_SA_ID
      operationId: parseEgts
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
      responses:
        '200':
          description: Parsed EGTS packet
EOF
```

### 4.8 Проверка установки

```bash
# Тест с реальным EGTS-пакетом
FUNCTION_URL="https://functions.yandexcloud.net/YOUR_FUNCTION_ID"

curl -X POST "$FUNCTION_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "body": "0100000B007503C30501AAA600EF0C812C823F02",
    "isBase64Encoded": false
  }'
```

Ожидаемый ответ:
```json
{
  "statusCode": 200,
  "body": {
    "ts": "2026-06-08T00:00:00Z",
    "count": 1,
    "packets": [
      {
        "HEADER": { "PRV": 1, "PT": 1, "PT_name": "EGTS_PT_APPDATA", ... },
        "SFRD": [ { "SST_name": "EGTS_TELEDATA_SERVICE", "RD": [...] } ]
      }
    ]
  }
}
```

---

## 5. Конфигурация

### 5.1 Переменные окружения

| Переменная | По умолчанию | Описание |
|------------|-------------|----------|
| `EGTS_LOG_DIR` | `.` (текущая директория) | Путь для лог-файлов |

### 5.2 Локальный запуск (CLI)

```bash
cd SERVICE

# Декодирование hex-пакета
python handler.py 0100000B00...

# Декодирование CSV-файла с пакетами
python handler.py --file ../egts-protocol/test/egts_packages.csv

# Запись в конкретный JSON-файл
python handler.py --file packets.csv --out result.json

# TCP-сервер (слушает порт 6000)
python handler.py --listen 6000

# Кодирование из JSON (re-encode с пересчётом CRC)
python handler.py --encode packet.json
```

### 5.3 Вызов как Cloud Function (Python SDK)

```python
import boto3
import json
import base64

def send_egts_to_cloud(hex_packet: str, function_url: str, token: str = ""):
    import urllib.request
    body = json.dumps({"body": hex_packet, "isBase64Encoded": False}).encode()
    req = urllib.request.Request(
        url=function_url,
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())
```

---

## 6. API Reference

### POST /

**Декодирование EGTS-пакета:**

```http
POST https://functions.yandexcloud.net/{function-id}
Content-Type: application/json

{
  "body": "<HEX_STRING>",
  "isBase64Encoded": false
}
```

| Поле | Тип | Описание |
|------|-----|----------|
| `body` | string | EGTS-пакет в виде hex-строки или base64 |
| `isBase64Encoded` | bool | `true` — base64, `false` — hex (по умолчанию) |

**Ответ 200:**

```json
{
  "ts": "2026-06-08T12:00:00Z",
  "count": 1,
  "packets": [
    {
      "hex_raw": "01000...",
      "total_bytes": 190,
      "parse_errors": [],
      "HEADER": {
        "PRV": 1,
        "SKID": 0,
        "PRF": "00",
        "RTE": "0",
        "ENA": "00",
        "CMP": "0",
        "PR": "00",
        "HL": 11,
        "HE": 0,
        "FDL": 177,
        "PID": 1475,
        "PT": 1,
        "PT_name": "EGTS_PT_APPDATA",
        "HCS": "0xEF",
        "HCS_valid": true
      },
      "SFRD_CRC16": 13056,
      "SFRD_CRC16_valid": true,
      "SFRD": [
        {
          "RL": 166,
          "RN": 0,
          "SST": 2,
          "SST_name": "EGTS_TELEDATA_SERVICE",
          "RST_svc": 2,
          "RST_name": "EGTS_TELEDATA_SERVICE",
          "RD": [
            {
              "SRT": 16,
              "SRT_name": "EGTS_SR_POS_DATA",
              "SRL": 21,
              "SRD": {
                "NTM": "2023-09-15T10:30:00+00:00",
                "LAT": 55.7181341,
                "LONG": 37.4396038,
                "VLD": 1,
                "FIX": 1,
                "MV": 0,
                "SPD_kmh": 0.0,
                "DIR_deg": 130,
                "ODM_km": 0.0,
                "DIN": 0,
                "SRC": 1,
                "ALT_m": 0
              }
            }
          ]
        }
      ]
    }
  ]
}
```

**Re-encode (изменить атрибуты → получить новый бинарный пакет):**

```http
POST https://functions.yandexcloud.net/{function-id}
Content-Type: application/json

{
  "encode": {
    "HEADER": { "PRV": 1, "PID": 42, "PT": 1, ... },
    "SFRD": [
      {
        "RN": 0, "SST": 2, "RST_svc": 2,
        "RD": [
          {
            "SRT": 16,
            "SRD": {
              "NTM": "2026-06-08T12:00:00+00:00",
              "LAT": 55.7519,
              "LONG": 37.6176,
              "VLD": 1, "FIX": 1, "MV": 1,
              "SPD_kmh": 60.0, "DIR_deg": 90
            }
          }
        ]
      }
    ]
  }
}
```

**Ответ:**
```json
{
  "statusCode": 200,
  "body": {
    "hex": "0100000B...",
    "bytes": 48
  }
}
```

**Ошибки:**

| HTTP код | Причина |
|----------|---------|
| 400 | Неверный формат тела запроса |
| 200 с `parse_errors` | Пакет принят, но содержит ошибки CRC или структуры |

---

## 7. Форматы данных

### 7.1 Поддерживаемые SRT-типы

| SRT | Название | Поля |
|-----|----------|------|
| 0 | EGTS_SR_RECORD_RESPONSE | CRN, RST, RST_desc |
| 1 | EGTS_SR_TERM_IDENTITY | TID, IMEI, IMSI, LNGC, NID |
| 7 | EGTS_SR_AUTH_INFO | UNH, SS |
| 9 | EGTS_SR_RESULT_CODE | RCD, RCD_desc |
| 16 | EGTS_SR_POS_DATA | NTM, LAT, LONG, SPD_kmh, DIR_deg, ODM_km... |
| 17 | EGTS_SR_EXT_POS_DATA | VDOP, HDOP, PDOP, SAT, NS |
| 18 | EGTS_SR_AD_SENSORS_DATA | DOUT, ADIO1-8, ANS1-8 |
| 19 | EGTS_SR_COUNTERS_DATA | CNT1-8 |
| 20/21 | EGTS_SR_STATE_DATA | ST, MPSV_V, BBV_V, IBV_V, NMS, IBU, BBU |
| 25 | EGTS_SR_ABS_CNTR_DATA | ACN, ACV |
| 27 | EGTS_SR_LIQUID_LEVEL_SENSOR | LLSEF, LLSVU, LLSN, MADDR, LLSD |
| 28 | EGTS_SR_PASSENGERS_COUNTERS | CNT_IN, CNT_OUT |
| 200 | EGTS_SR_CUSTOM_SRT200 | X_mm, Y_mm, Z_mm, quality |
| 201 | EGTS_SR_CUSTOM_SRT201 | temperature_C, vibration, pressure_hPa |
| 202 | EGTS_SR_CUSTOM_SRT202 | tag_id, zone_id, group_id, rssi_dBm |
| 203 | EGTS_SR_CUSTOM_SRT203 | event_type, zone_id, event_time, event_flags |

### 7.2 Координаты (SRT=16)

```
LAT (raw uint32) = abs(latitude_deg)  / 90.0  × 0xFFFFFFFF
LON (raw uint32) = abs(longitude_deg) / 180.0 × 0xFFFFFFFF

Знак: LAHS=1 → широта южная (–)
      LOHS=1 → долгота западная (–)

Скорость: SPD (14 бит) = speed_kmh × 10   (дискретность 0.1 км/ч)
Время:    NTM = секунды с 2010-01-01 00:00:00 UTC
```

### 7.3 Лог-файлы

После обработки сервис создаёт:

```
$EGTS_LOG_DIR/
├── egts_YYYYMMDD.log   ← текстовый лог (UTF-8)
└── egts_YYYYMMDD.json  ← JSON со всеми пакетами за день
```

**Формат JSON-лога:**
```json
{
  "generated_at": "2026-06-08T12:00:00Z",
  "packets": [ {...}, {...} ]
}
```

---

## 8. Мобильное приложение

Приложение **EGTS Tracker** (Flutter / Android) отправляет EGTS-пакеты прямо в Cloud Function.  
Готовый APK: `MOBILE_APP/egts_tracker.apk` (~18 МБ, android-arm64 release).

### 8.1 Настройка URL сервера

Через интерфейс приложения: **Настройки → URL Yandex Cloud Function**.

Поля конфигурации:

| Поле | Описание | Пример |
|------|----------|--------|
| URL | Endpoint Cloud Function | `https://functions.yandexcloud.net/<id>` |
| IAM-токен | Для авторизации (необязательно) | `t1.xxx...` |
| Terminal ID | Идентификатор устройства (OID в SDR) | `1` |

### 8.2 Стратегия отправки

| Событие | Триггер | Задержка |
|---------|---------|---------|
| iBeacon обнаружен | `flutter_blue_plus` scanResults | < 1 100 мс |
| NFC/RFID считан | `flutter_nfc_kit` poll | < 200 мс |
| WiFi AP из списка | Опрос каждые 15 сек | < 15 000 мс |

Пакет формируется **немедленно** при совпадении с белым списком и отправляется POST-запросом в фоновом `Future` без блокировки UI.

### 8.3 Состав EGTS-пакета от приложения

```
PT_APPDATA (тип пакета = 1)
└── SDR  SST=TELEDATA  RST=TELEDATA  OID=terminalId
    ├── SRT=16  EGTS_SR_POS_DATA       LAT, LON, SPD, DIR (текущий GPS)
    ├── SRT=17  EGTS_SR_EXT_POS_DATA   HDOP, кол-во спутников
    ├── SRT=21  EGTS_SR_STATE_DATA     напряжение 12V, state=active
    ├── SRT=202 EGTS_SR_CUSTOM_SRT202  tag_id, zone_id, rssi (iBeacon/NFC)
    └── SRT=203 EGTS_SR_CUSTOM_SRT203  event_type=enter, zone_id, event_time
```

Все длины (RL, FDL), **CRC-8** заголовка и **CRC-16** тела пересчитываются автоматически при каждом формировании пакета (`EgtsBuilder.dart`).

### 8.4 Разрешения Android

| Разрешение | Назначение |
|------------|------------|
| `ACCESS_FINE_LOCATION` | GPS, BLE-сканирование (обязательно для BLE API 31+) |
| `BLUETOOTH_SCAN` | Поиск iBeacon (Android 12+) |
| `BLUETOOTH_CONNECT` | Доступ к BLE-устройствам (Android 12+) |
| `NFC` | Считывание NFC/RFID-меток |
| `ACCESS_WIFI_STATE` | WiFi AP сканирование |
| `CHANGE_WIFI_STATE` | Запуск WiFi-сканирования |
| `FOREGROUND_SERVICE` | Фоновая работа сканеров |
| `INTERNET` | HTTP POST на Cloud Function |

### 8.5 Белые списки

Каждый список хранится в `SharedPreferences` (JSON-сериализация):

| Список | Ключ сопоставления | Пример записи |
|--------|--------------------|---------------|
| NFC/RFID | UID тега (hex) | `AA:BB:CC:DD` |
| iBeacon | UUID + Major + Minor (`*` = любой) | `ACFD065E-... / 1 / *` |
| WiFi | SSID и/или BSSID | `Office_WiFi / AA:BB:CC:DD:EE:FF` |

### 8.6 Архитектура Flutter-приложения

```
main.dart
└── MultiProvider
    └── TrackerProvider (ChangeNotifier)
        ├── _startGps()    → geolocator stream
        ├── _startBle()    → flutter_blue_plus → iBeacon detection
        ├── _startWifiPoll() → wifi_scan (каждые 15 сек)
        └── onNfcDetected() ← вызов из MonitoringScreen NFC poll loop

MonitoringScreen (TabBarView)
├── EventsTab     → список EgtsPacketCard
├── NfcTab        → NFC poll loop + список событий
├── BeaconTab     → список BeaconEvent с RSSI
└── WifiTab       → список WifiEvent

SettingsScreen
├── _ServerSection        → URL / Token / TerminalID
├── _NfcWhitelistSection  → CRUD NfcEntry
├── _BeaconWhitelistSection → CRUD BeaconEntry
└── _WifiWhitelistSection  → CRUD WifiEntry
```

---

## 9. Устранение неисправностей

### Ошибка: HCS mismatch

```json
"parse_errors": ["HCS mismatch: got 0xAB, calc 0xCD"]
```
**Причина:** Повреждён заголовок пакета при передаче.
**Решение:** Проверить целостность TCP/UDP соединения. Убедиться, что hex-строка полная.

### Ошибка: SFRCS mismatch

```json
"parse_errors": ["SFRCS mismatch: got 0x1234, calc 0x5678"]
```
**Причина:** Повреждено тело пакета.
**Решение:** Проверить FDL (длину тела). Убедиться, что передаётся весь пакет.

### Ошибка: Пакет слишком короткий

```json
"parse_errors": ["Пакет слишком короткий: 5 байт"]
```
**Решение:** Проверить, что передаётся полный hex без обрезания.

### SRT не декодируется (raw_hex)

```json
"SRD": { "raw_hex": "...", "note": "unimplemented decoder" }
```
**Причина:** Тип подзаписи не реализован (например SRT=15 EGTS_PLUS_DATA).
**Решение:** Добавить декодер в `egts/models.py` и зарегистрировать в `egts/codec.py`.

### Логи Cloud Function не сохраняются

**Причина:** `/tmp` в Cloud Functions очищается между вызовами.
**Решение:** Для persistent-логов подключить Object Storage:

```python
# В handler.py добавить запись в S3
import boto3

s3 = boto3.client(
    "s3",
    endpoint_url="https://storage.yandexcloud.net",
    aws_access_key_id=os.environ["S3_KEY"],
    aws_secret_access_key=os.environ["S3_SECRET"],
)

def _save_to_s3(packets: list, bucket: str):
    key = f"egts/{datetime.now().strftime('%Y/%m/%d/%H%M%S')}.json"
    s3.put_object(Bucket=bucket, Key=key,
                  Body=json.dumps(packets, default=str).encode())
```

### Большая задержка при обнаружении iBeacon

**Причина:** `flutter_blue_plus` по умолчанию выдаёт результаты пачками ~1 сек.  
**Решение:** При вызове `startScan` передать `continuousUpdates: true` (уже установлено в `tracker_provider.dart`). Дополнительно можно снизить `androidScanMode` до `AndroidScanMode.lowLatency`:

```dart
await FlutterBluePlus.startScan(
  continuousUpdates: true,
  androidScanMode: AndroidScanMode.lowLatency,
);
```

> ⚠️ `lowLatency` повышает энергопотребление — используйте только при необходимости мгновенной реакции.

---

## Дополнительные ресурсы

- [ГОСТ Р 54619-2011](../egts-protocol/docs/gost54619-2011.pdf) — стандарт протокола EGTS
- [ГОСТ Р 33472-2015](../egts-protocol/docs/gost33472-2015.pdf) — обмен данными между ДЦ
- [Приказ МинТранс №285](../egts-protocol/docs/mitransNo285.pdf) — требования к телематике
- [Yandex Cloud Functions](https://cloud.yandex.ru/docs/functions/) — документация платформы
- [flutter_blue_plus](https://pub.dev/packages/flutter_blue_plus) — BLE iBeacon сканирование (Flutter)
- [flutter_nfc_kit](https://pub.dev/packages/flutter_nfc_kit) — NFC/RFID считывание (Flutter)
- [EGTS Tracker APK](../MOBILE_APP/egts_tracker.apk) — готовый Android-пакет (~18 МБ, arm64)
