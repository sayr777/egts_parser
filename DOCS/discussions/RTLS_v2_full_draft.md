# ТЗ на расширение EGTS RTLS v2

**Статус:** Черновик (на основе обсуждений 03–17 из `DOCS/discussions/` + прототипов в `sandbox/`).  
**Дата:** 2026-06-12  
**Связанные материалы:** [README.md](./README.md), [SOURCE_CHAT.md](./SOURCE_CHAT.md), [`sandbox/README.md`](../../sandbox/README.md)

---

## 1. Цель

Расширение протокола EGTS (ГОСТ Р 54619-2011) для поддержки высокоточного **Real-Time Locating System (RTLS)** — indoor/outdoor позиционирования транспортных средств и объектов с использованием:

- Vendor-specific подзаписей (SRT 200–204).
- Инерциальных сенсоров (IMU).
- Sensor Fusion.
- Привязки к графу дорог (Map Matching).

Расширение должно полностью укладываться в существующую инфраструктуру **РНИС** (Пермь, Камчатка, Московская область и др.) без изменения транспортного уровня.

---

## 2. Соответствие стандартам

- **ISO/IEC 24730-1:2014** — Application Programming Interface (API) для RTLS.
- **ISO/IEC 24730-61/62** — Ultra Wide Band (UWB) PHY/MAC.
- **IEEE 802.15.4z-2020** — Enhanced Ultra Wideband (UWB) для ranging (ToF, TDoA).
- **ГОСТ Р ИСО/МЭК 24730-1-2017** (гармонизированная версия).
- **Приказ Минтранса РФ № 285** — требования к БНСО (дополнительные датчики, точность).
- **ГОСТ Р 54619-2011** — базовый EGTS (SRT > 127 зарезервированы для vendor extensions).

**Подход:** Не реализуем Air Interface напрямую (BLE / Wi-Fi / UWB остаются на стороне терминала/меток). Фокус — на транспортном и прикладном уровне через EGTS TELEDATA_SERVICE.

**Рекомендация:** Везде явно указывать соответствие ISO/IEC 24730-1 + ссылки на ГОСТ.

---

## 3. Поддерживаемые расширения EGTS (SRT)

### Уже реализовано в основном коде
- **SRT 200** — RTLS Extended Position (X/Y/Z в мм + quality).
- **SRT 201** — RTLS Sensor Data (температура, вибрация, давление).
- **SRT 202** — RTLS Tag Identity (tag_id, zone_id, group_id, RSSI).
- **SRT 203** — RTLS Event Data (enter/exit/alarm и т.д.).

### Предлагается добавить
- **SRT 204** — EGTS_SR_INERTIAL_DATA (см. обсуждение 09)

**Структура SRT 204 (предлагаемая):**
- heading, roll, pitch (в 0.01°)
- accel_x/y/z, gyro_x/y/z
- vibration_rms, vibration_peak, dominant_freq_hz
- filter_type (none / lpf / madgwick / ekf / hybrid)
- ekf_confidence, cov_trace
- road_segment_id, matched_lat/lon, snap_confidence (после Map Matching)
- flags, timestamp

**Интеграция:** В `SERVICE/egts/models.py` + `codec.py` (по аналогии с 200–203). Добавить в Excel-парсер новый лист `INERTIAL_SENSORS`.

---

## 4. Inertial Sensors и Sensor Fusion

**Архитектура (см. 13):**

```
IMU (100–200 Hz: accel + gyro + mag)
        │
        ▼  Madgwick Filter (ориентация: roll/pitch/yaw)
        │
        ▼  Extended Kalman Filter (EKF)
        │     (позиция + скорость + heading bias + covariance)
        │
        ▼  Map Matching (HMM / geometric)
        │
   EGTS-пакет (SRT 16/200/201/204) → РНИС
```

**Компоненты:**

- **Madgwick Filter** (16) — быстрый, низкий дрейф, подходит для embedded и Flutter. β = 0.033 (рекомендуется для РНИС). Поддержка MARG и IMU-only режимов.
- **EKF** (14) — нелинейная модель, учёт bias гироскопа, confidence через trace ковариации. Predict на IMU, update на GPS + heading.
- **Vibration Filtering** (10) — предобработка перед Madgwick (LPF Butterworth cutoff 5–20 Гц, Median filter). Добавлять в SRT 204 поля `vibration_*` и `filter_type`.

**Требования к точности (предлагаемые):**
- Heading: ±2–5° при вибрациях до 5g.
- Позиция после fusion + map matching: значительно лучше сырых GPS/RTLS.

**Реализация в sandbox:** `madgwick.py`, `ekf.py`, `vibration.py`, `fusion_pipeline.py`.

---

## 5. Map Matching

**Необходимость:** Сырые координаты (GPS/RTLS) имеют ошибки 3–15+ м. Транспорт движется строго по дорогам/выделенным полосам → критично для расчёта пробега, нарушений, аналитики в РНИС.

**Рекомендуемый стек:**

- **Production:** PostGIS + pgRouting (или pgMapMatch). HMM + Viterbi (золотой стандарт для РНИС).
- **Прототипирование / анализ:** GeoPandas + OSMnx + leuven-map-matching (17).

---

## 6. LBS — позиционирование по базовым станциям сотовой связи

**Проблема:** В туннелях, плотной застройке, парковках и под мостами GNSS часто отсутствует или сильно деградирует.

**Решение:** Использовать LBS (Cell ID + Timing Advance + RSSI от serving и neighbor станций) как дополнительное наблюдение в Map Matching.

**Ключевые идеи (см. отдельную дискуссию 18):**
- Требуется база данных координат базовых станций (оператор / OpenCellID / crowdsourcing).
- Для каждого кандидата сегмента дороги считается **likelihood** того, насколько хорошо LBS-измерения объясняют положение на этом сегменте (по расстоянию от TA и по RSSI).
- LBS-aware Map Matching даёт гораздо более точную точку именно на дороге, чем сырая LBS-позиция.
- Отлично комбинируется с IMU (heading) и предыдущим EKF.

**Интеграция в EGTS:**
- Новый vendor SRT 205 (EGTS_SR_LBS_DATA) или расширение SRT 200/204.
- Поля: serving_cell_id, lac/tac, rssi, timing_advance, neighbors, raw_lbs_position и т.д.

**Sandbox + реальная реализация:** 
- `lbs_map_matcher.py` + `srt205_lbs.py`.
- **Реальный код в SERVICE:** SrCustom205 (с NeighborCell) в models.py, константа в const.py, регистрация в codec.py.
- Интеграция: `fusion_pipeline.py` принимает lbs_data и использует snap для обновления EKF (как GPS measurement). `demo.py` генерирует реальные EGTS-пакеты (через SERVICE.codec) с SRT204 + SRT205 (LBS).
- Пример: LBS snap с conf=0.99 даёт точную точку на дороге.

**Рекомендация для ТЗ:** Добавить LBS как важный источник данных для outdoor-навигации в сложных условиях (дополнение к RTLS indoor).

---

## 8. Мобильное приложение (Flutter)

**Необходимость:** Сырые координаты (GPS/RTLS) имеют ошибки 3–15+ м. Транспорт движется строго по дорогам/выделенным полосам → критично для расчёта пробега, нарушений, аналитики в РНИС.

**Рекомендуемый стек:**

- **Production:** PostGIS + pgRouting (или pgMapMatch). HMM + Viterbi (золотой стандарт для РНИС).
- **Прототипирование / анализ:** GeoPandas + OSMnx + leuven-map-matching (17).
- **Простые случаи:** Geometric nearest segment (08, 15).

**Интеграция:**
- После EKF — snap координат.
- Результаты: `road_segment_id`, `matched_lat/lon`, `snap_confidence`.
- Хранить в SRT 200 (расширить) или SRT 204.
- В Excel — новый лист `MAP_MATCHING`.

**SQL-пример и Python-интеграция:** см. 11 и 15.

**Sandbox:** `map_matcher.py` (geometric + заглушки + сравнение алгоритмов).

---

## 8. Мобильное приложение (Flutter)

- Использовать `sensors_plus` для акселерометра / гироскопа / магнетометра (12).
- Формировать SRT 204 payload.
- Отправлять вместе с GPS / BLE / Wi-Fi / NFC событиями.
- Background service + оффлайн-очередь (рекомендация из 02).

**Sandbox:** Примеры Dart-кода в обсуждении 12 + эквивалентная логика в `fusion_pipeline.py`.

---

## 9. Инструментарий и интеграции

- **Excel-парсер (05):** Добавить шаблоны для RTLS + inertial + map-matched пакетов. Поддержка roundtrip с пересчётом CRC. Макросы / batch.
- **Cloud Function / CLI (07):** Опция `--map-match`, `--fuse-imu`. Загрузка в PostGIS / ClickHouse.
- **Тестирование:** Реальные пакеты из БНСО, edge-кейсы (вибрации, потеря GPS, indoor/outdoor переход).

---

## 10. Roadmap реализации (предлагаемый)

1. **Phase 1 (быстро):** Добавить SRT 204 в модели + codec. Перенести `madgwick.py` и `ekf.py` в `SERVICE/egts/filters/`.
2. **Phase 2:** Интеграция в `fusion_pipeline` на стороне сервиса. Предобработка вибраций.
3. **Phase 3:** Map Matching слой (сначала geometric + PostGIS stub, потом полноценный HMM).
4. **Phase 4:** Flutter — реальный сбор и отправка IMU + SRT 204.
5. **Phase 5:** Расширение Excel-парсера и тестов. Обновление ТЗ и документации.
6. **Phase 6 (опционально):** UWB-метрики, более продвинутые алгоритмы (Particle Filter), калибровка магнетометра.

---

## 11. Открытые вопросы

- Точный формат SRT 204 (битность полей, масштабирование) — согласовать с требованиями РНИС.
- Частота отправки inertial данных (100 Гц на устройстве → агрегация перед отправкой?).
- Хранение графа дорог (OSM + osm2pgsql vs. готовые источники).
- Требования к точности и валидации для конкретных контрактов РНИС.

---

**Готово к использованию в качестве основы для полноценного ТЗ.**

Следующий шаг: наполнить этот документ деталями из 08–17 + результатами тестирования прототипов из `sandbox/`. При необходимости добавить разделы по безопасности, производительности и compliance (ФСТЭК/ФСБ).
