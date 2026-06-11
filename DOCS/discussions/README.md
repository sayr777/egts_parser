# Discussions / Обсуждения

**Папка содержит ключевые обсуждения и анализы проекта EGTS Parser.**  
Файлы пронумерованы последовательно (01–17) и сгруппированы по темам.  
Это структурированный экспорт идей из оригинального Grok-чата.

> **Оригинальный источник чата:**  
> [grok.com/project/... (private)](https://grok.com/project/141c898d-eabd-44f4-bd3c-14ff027bc028?chat=40590679-37f2-48f0-b26a-50f69a97e272&rid=096e52bb-7c58-4b50-afa7-39bbddc23b5d)  
> Подробности: [SOURCE_CHAT.md](./SOURCE_CHAT.md)

**Дата обновления:** 2026-06-12  
**Авторы:** Anton Tenyakov / Grok / Claude

---

## Как пользоваться этой папкой

1. **README** (этот файл) — главный индекс с группировкой, статусом реализации и ссылками.
2. **Нумерованные файлы** — детальные обсуждения (одна тема = один файл).
3. **RTLS_v2_full_draft.md** — черновик ТЗ, собирающий выводы.
4. **SOURCE_CHAT.md** — ссылка на первоисточник.
5. **Связанный ресурс:** [`sandbox/README.md`](../../sandbox/README.md) — executable-прототипы всех идей (Madgwick, EKF, SRT 204, fusion pipeline, map matching и т.д.).

**Рекомендуемый порядок чтения:**
- Сначала этот README.
- Базовый анализ (01–02).
- RTLS и стандарты (03, 04, 06).
- Инструменты (05, 07).
- Основная серия: позиционирование и сенсоры (08 → 17 последовательно).
- Итоговый черновик ТЗ.
- Затем переходи в `sandbox/` и запускай `demo.py`.

---

## Базовый анализ проекта

| # | Файл | Описание | Sandbox |
|---|------|----------|---------|
| 01 | [01-project-analysis.md](./01-project-analysis.md) | Полный технический анализ проекта (сильные/слабые стороны, стек) | Общий обзор |
| 02 | [02-recommendations-improvements.md](./02-recommendations-improvements.md) | Конкретные рекомендации по доработкам (тесты, производительность, интеграции) | `demo.py`, генераторы данных |

## RTLS-расширения и стандарты

| # | Файл | Описание | Sandbox |
|---|------|----------|---------|
| 03 | [03-rtls-extensions.md](./03-rtls-extensions.md) | Анализ RTLS-расширений SRT 200–203 | `srt204.py` (расширение паттерна) |
| 04 | [04-rtls-iso-standard.md](./04-rtls-iso-standard.md) | RTLS как стандарт ISO/IEC 24730 (API + Air Interface) | Упоминания в `srt204.py` |
| 06 | [06-rtls-standards-deep-dive.md](./06-rtls-standards-deep-dive.md) | Глубокий анализ стандартов + рекомендации по UWB / IEEE 802.15.4z | — |

## Инструменты и интеграции

| # | Файл | Описание | Sandbox |
|---|------|----------|---------|
| 05 | [05-excel-parser.md](./05-excel-parser.md) | Bidirectional Excel-парсер как мощный инструмент тестирования и документации | Рекомендации по новым листам (INERTIAL, MAP_MATCH) |
| 07 | [07-egts-rnis-integration.md](./07-egts-rnis-integration.md) | Интеграция с российскими РНИС (Пермь, Камчатка, МО) | `map_matcher.py` (PostGIS направление) |

## Позиционирование и сенсоры (основная серия)

Эта серия описывает **3-уровневую архитектуру** Sensor Fusion для EGTS RTLS v2:

**Madgwick (heading/orientation) → EKF (position + velocity) → Map Matching (snap to road)**

| # | Файл | Описание | Реализация в sandbox/ |
|---|------|----------|-----------------------|
| 08 | [08-road-graph-map-matching.md](./08-road-graph-map-matching.md) | Зачем нужен Map Matching для транспорта + обзор методов | `map_matcher.py` (geometric + теория HMM) |
| 09 | [09-inertial-sensors-egts.md](./09-inertial-sensors-egts.md) | **Предложение SRT 204** (IMU: heading, accel, gyro, flags) | `srt204.py` (полная модель + encode/decode) |
| 10 | [10-vibration-filtering-algorithms.md](./10-vibration-filtering-algorithms.md) | Фильтрация вибраций (LPF, Median, Kalman, Madgwick) + метрики | `vibration.py` (Butterworth LPF, median, RMS/peak/freq) |
| 11 | [11-postgis-map-matching.md](./11-postgis-map-matching.md) | Пример реализации Map Matching на PostGIS + pgRouting | `map_matcher.py` (SQL-шаблоны + интеграция) |
| 12 | [12-flutter-imu-integration.md](./12-flutter-imu-integration.md) | Сбор IMU в Flutter (Dart) и отправка SRT 204 | Эквивалент в `fusion_pipeline.py` + комментарии |
| 13 | [13-sensor-fusion-architecture.md](./13-sensor-fusion-architecture.md) | **Архитектура**: три уровня (Madgwick → EKF → Map Matching) | `fusion_pipeline.py` (ядро) |
| 14 | [14-ekf-implementation.md](./14-ekf-implementation.md) | Полная реализация EGTS_EKF (predict, GPS update, heading update) | `ekf.py` (готовая библиотека) |
| 15 | [15-map-matching-algorithms.md](./15-map-matching-algorithms.md) | Сравнение алгоритмов (Geometric / Topological / HMM+Viterbi / Particle Filter) + библиотеки | `map_matcher.py` (сравнение + stubs) |
| 16 | [16-madgwick-filter-implementation.md](./16-madgwick-filter-implementation.md) | Полная MadgwickFilter (MARG + IMU-only, β-тюнинг, Euler) | `madgwick.py` (полная чистая реализация) |
| 17 | [17-geopandas-map-matching.md](./17-geopandas-map-matching.md) | Прототипирование Map Matching с GeoPandas + OSMnx + leuven | `map_matcher.py` (GeoPandas-раздел + примеры) |
| 18 | [18-lbs-road-graph-positioning.md](./18-lbs-road-graph-positioning.md) | Позиционирование по LBS (базовым станциям сотовой связи) + граф дорог для точной точки на дороге | `lbs_map_matcher.py`, `srt205_lbs.py`, integrated in `fusion_pipeline.py` + `demo.py` (full LBS + IMU + GPS snapping) |

**Ключевой результат серии (08–18):**  
Чёткая многоуровневая архитектура + готовые прототипы кода (в sandbox/), которые можно переносить в `SERVICE/egts/filters/`, мобильное приложение и Excel-парсер. LBS + road graph snapping (18) теперь работает вместе с IMU/EKF для точной дороги даже без GNSS.

## Черновики и ТЗ

| Файл | Описание | Статус |
|------|----------|--------|
| [RTLS_v2_full_draft.md](./RTLS_v2_full_draft.md) | Черновик ТЗ на расширение EGTS RTLS v2 (стандарты, SRT 204, fusion, map matching, vibration) | Минимальный. Рекомендуется наполнить на основе 03–17 + sandbox |
| [SOURCE_CHAT.md](./SOURCE_CHAT.md) | Ссылка на оригинальный Grok-чаты + пояснения | Актуально |

---

## Статус реализации идей

Большинство предложений из этой папки **уже прототипированы** в изолированном виде:

- `sandbox/demo.py` — сквозной прогон (реальные GPS-сиды + синтетический IMU + fusion + map matching + генерация SRT 204).
- `sandbox/srt204.py`, `madgwick.py`, `ekf.py`, `vibration.py`, `fusion_pipeline.py`, `map_matcher.py`, `generate_data.py`.

**Следующие шаги (рекомендуемые):**
- Перенести зрелые классы в `SERVICE/egts/filters/` и добавить SRT 204 в `models.py` + `codec.py`.
- Расширить Excel-парсер (новые листы INERTIAL / MAP_MATCHING).
- Добавить IMU-сбор в мобильное приложение и реальную отправку SRT 204.
- Наполнить `RTLS_v2_full_draft.md` и ТЗ.

---

**Метаданные и конвенции в этой папке (рекомендуется соблюдать при добавлении новых файлов):**

- Имя файла: `NN-короткое-описание.md` (NN — порядковый номер).
- Заголовок первого уровня: `# NN. Человекочитаемое название`.
- В начале: `**Дата:**`, `**Автор:**`, при необходимости `**Контекст:**`.
- В конце: секция "Зависимости" (ссылки на другие обсуждения) и "Источники".
- При добавлении новой темы — обновляй этот README и таблицу статуса.

---

*Все идеи в этой папке напрямую легли в основу `sandbox/`. Локальные файлы — это структурированная версия обсуждений из указанного выше приватного Grok-чата.*
