# 18. Позиционирование по LBS (базовым станциям сотовой связи) с использованием графа дорог

**Дата:** 2026-06-12  
**Автор:** Grok (для проекта sayr777/egts_parser)  
**Контекст:** Дополнение к GPS/IMU/RTLS для точного определения положения транспортного средства именно на дорожном графе (автобусы, грузовики, спецтранспорт в РНИС). LBS особенно полезно при слабом или отсутствующем GNSS-сигнале.

## 1. Зачем нужно LBS + Map Matching

Обычные источники координат имеют ограничения:
- GPS/ГЛОНАСС — теряется в туннелях, плотной застройке, паркингах, под мостами.
- RTLS (SRT 200–203) — в основном для indoor/локальных зон.
- IMU dead-reckoning — накапливает ошибку со временем.

**LBS (Location Based Services / позиционирование по базовым станциям)** даёт грубую оценку местоположения везде, где есть сотовая связь (практически всегда на дорогах России).

Проблема: LBS-точка обычно имеет точность от десятков метров до нескольких километров. Прямая проекция на карту бесполезна.

Решение: **использовать LBS как наблюдение (observation) в алгоритме Map Matching** на графе дорог. Это позволяет «привязать» даже неточную LBS-оценку к наиболее вероятному сегменту дороги с учётом:
- Известных координат базовых станций (BS database).
- Измеренных сигналов (RSSI, Timing Advance).
- Топологии и атрибутов дорог.
- Данных от IMU (heading, скорость).
- Истории движения (предыдущие точки).

Результат — **точная точка на дороге** (road-constrained position), подходящая для расчёта пробега, нарушений ПДД, маршрутов в системах РНИС.

## 2. Данные LBS, которые можно использовать

Типичные поля от модема/терминала (через AT-команды, QMI, или встроенный в БНСО модуль):

| Параметр              | Описание                                      | Полезность для Map Matching          |
|-----------------------|-----------------------------------------------|--------------------------------------|
| serving_cell_id       | ID обслуживающей станции                      | Основной ключ для lookup в БД BS    |
| lac / tac             | Location Area / Tracking Area Code            | Уточняет регион                     |
| mcc / mnc             | Код страны и оператора                        | Фильтрация                            |
| rssi / rsrp           | Уровень сигнала (дБм)                         | Вес в likelihood функции            |
| timing_advance (TA)   | Оценка расстояния (в единицах ~550 м для GSM) | Круговая зона вокруг BS             |
| neighbor_cells        | Список соседних станций + их RSSI             | Мультилатерация / fingerprinting    |
| bs_lat / bs_lon       | Координаты станции (из справочника)           | Критично! Нужно иметь БД вышек      |

**Источники БД базовых станций:**
- Операторы (по договору).
- Crowdsourced базы (OpenCellID, Mozilla Location Service, российские аналоги).
- Собственный сбор при движении тестовых машин.

## 3. Алгоритм: LBS-aware Map Matching

Базовый pipeline (расширение идей из 08, 13, 15):

1. Получить LBS-измерения + текущую грубую позицию (если есть от GPS/IMU).
2. Найти кандидатов — сегменты дорог в радиусе R от грубой позиции (PostGIS: ST_DWithin).
3. Для каждого кандидата вычислить **emission probability** (правдоподобие наблюдения LBS):
   - Рассчитать ожидаемое расстояние/сигнал от известных BS до точки на сегменте.
   - Сравнить с реальными RSSI/TA (модель распространения сигнала или простая евклидова).
   - Учесть heading из Madgwick/IMU (вероятность направления движения по сегменту).
4. Transition probability — как раньше (расстояние по графу между сегментами).
5. Запустить Viterbi (HMM) или Particle Filter на графе.
6. Выдать snapped точку + road_segment_id + confidence.

**Улучшенная emission функция (псевдокод):**

```python
def lbs_emission_probability(
    road_point,          # точка на сегменте дороги (lat, lon)
    serving_bs,          # {lat, lon, ta, rssi}
    neighbors: list,     # список соседних BS
    sigma_ta=550,        # погрешность TA
    path_loss_model=...  # модель затухания
):
    # Расстояние до serving BS
    dist = haversine(road_point, serving_bs)
    expected_ta = dist / 550.0
    
    # Правдоподобие по TA
    ta_prob = gaussian(serving_bs.ta, expected_ta, sigma_ta)
    
    # Правдоподобие по RSSI (пример)
    expected_rssi = path_loss_model(dist)
    rssi_prob = gaussian(serving_bs.rssi, expected_rssi, 8)  # 8 дБм погрешность
    
    # Можно добавить соседей для лучшей локализации
    neighbor_prob = 1.0
    for nb in neighbors:
        ...
    
    return ta_prob * rssi_prob * neighbor_prob * direction_prior
```

## 4. Интеграция в архитектуру Sensor Fusion (расширение 13)

```
GPS (когда есть) ─┐
IMU (Madgwick/EKF)─┼─→ EKF / Particle Filter
LBS measurements ──┘
        │
        ▼
   Map Matching (HMM / PF на графе дорог)
        │
        ▼
   Финальная точка на дороге + road_id + confidence
        │
        ▼
   EGTS (SRT 16 + расширенный 200/204 или новый SRT для LBS)
```

**Рекомендуемый новый SRT (или расширение существующего):**

SRT 205 — EGTS_SR_LBS_DATA (vendor extension)

Поля (пример):
- serving_cell_id (uint32)
- lac/tac (uint16)
- rssi_dbm (int8)
- timing_advance (uint16)
- num_neighbors (uint8)
- neighbor_data (массив: cell_id + rssi)
- bs_position_quality (качество данных о станции)
- lbs_position_lat/lon (грубая LBS-точка, если терминал сам считает)
- timestamp

Можно также добавлять LBS-данные в существующий SRT 200 (Extended Position) как дополнительные поля.

## 5. Реализация

### PostGIS (рекомендуется для production, как в 11 и 15)

Расширить функцию egts_map_match, добавив параметры LBS:

```sql
CREATE OR REPLACE FUNCTION egts_lbs_map_match(
    p_lbs_json jsonb,           -- serving + neighbors
    p_heading double precision,
    p_speed double precision
) RETURNS TABLE (
    matched_lat double precision,
    matched_lon double precision,
    edge_id bigint,
    confidence double precision,
    lbs_likelihood double precision
) ...
```

Внутри — CTE с кандидатами + расчёт likelihood на PL/pgSQL или через расширение.

### Python (для прототипирования / offline)

Расширить классы из `sandbox/map_matcher.py` и `sandbox/fusion_pipeline.py`.

Добавить LBS-observation model в particle filter или HMM.

### База данных станций

- Таблица `base_stations (id, lat, lon, mcc, mnc, technology, last_updated)`
- Индексы + materialized views для быстрого поиска станций в радиусе.

## 6. Преимущества и ограничения

**Плюсы:**
- Работает в условиях полного отсутствия GPS.
- Значительно повышает точность на дорогах по сравнению с сырым LBS.
- Дешёво (модемы уже имеют LBS).
- Хорошо комбинируется с IMU (heading сильно помогает выбрать правильное направление на перекрёстках).

**Минусы / вызовы:**
- Требуется актуальная и точная БД базовых станций.
- Сигнал сильно зависит от окружения (здания, погода, нагрузка на сеть).
- Нужно калибровать модели распространения под регион.
- Приватность и доступ к данным операторов.

## 7. Рекомендации для egts_parser и РНИС

1. **В моделях и codec** — добавить поддержку SRT 205 (или расширить 200/204).
2. **В Excel-парсере** — новый лист LBS_DATA + примеры пакетов.
3. **В Cloud Function / ingestion** — опция `--use-lbs` с подключением к БД станций.
4. **В мобильном приложении** — собирать и отправлять serving + neighbors (аналогично WiFi/Beacon в текущей версии).
5. **В map matching слое** — реализовать LBS-aware emission probability (начать с PostGIS).
6. **Для РНИС** — добавить в требования к БНСО сбор LBS-данных. Это позволит улучшить качество данных в сложных условиях без замены оборудования.

## 8. Связанные обсуждения

- [08-road-graph-map-matching.md](./08-road-graph-map-matching.md) — базовая теория
- [13-sensor-fusion-architecture.md](./13-sensor-fusion-architecture.md) — место LBS в пайплайне
- [14-ekf-implementation.md](./14-ekf-implementation.md) — как добавить LBS update step
- [15-map-matching-algorithms.md](./15-map-matching-algorithms.md) — HMM / Particle Filter как основа
- [17-geopandas-map-matching.md](./17-geopandas-map-matching.md) — прототипирование

## 9. Источники и полезные ссылки

- 3GPP TS 36.355 (E-CID positioning)
- OpenCellID / Mozilla Location Service
- Статьи: "Cellular Network Based Map Matching" (various IEEE papers)
- Valhalla / OSRM + cell tower data
- Timing Advance specification (GSM/UMTS/LTE)

---

**Файл создан:** `DOCS/discussions/18-lbs-road-graph-positioning.md`

**Следующие шаги:**  
Реализовать прототип в `sandbox/` (расширение map_matcher.py + генератор синтетических LBS-данных), затем перенести в основной код. Можно добавить в ТЗ RTLS v2 как важное дополнение для outdoor-навигации.

**Sandbox реализация (продолжение):**  
- `sandbox/lbs_map_matcher.py`: `generate_synthetic_lbs()`, `lbs_likelihood()`, `lbs_aware_snap_to_road()`.
- `sandbox/srt205_lbs.py`: Полная модель SRT 205 для передачи LBS в EGTS пакетах (аналог SRT 204).
- `sandbox/generate_data.py`: `add_lbs_to_track()` — добавляет LBS к синтетическим трекам.
- `sandbox/fusion_pipeline.py`: `process_imu(..., lbs_data=...)` — теперь использует LBS для road snapping внутри пайплайна (Madgwick + EKF + LBS Map Matching).
- `sandbox/demo.py`: Полный прогон с генерацией SRT 204 + SRT 205, LBS snaps показаны в выводе (conf 0.99 на дороге).
- Запуск: `python demo.py` или `python fusion_pipeline.py` (встроен LBS пример).

LBS теперь работает как дополнительный сенсор в общей архитектуре fusion (GPS/IMU + LBS → точка на графе дорог).