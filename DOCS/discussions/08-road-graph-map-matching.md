# Привязка координат к графу дорог (Map Matching) в EGTS / RTLS

**Дата:** 2026-06-11  
**Автор:** Grok (для проекта sayr777/egts_parser)  
**Контекст:** Для проектов РНИС и транспорта, где ТС движется только по дорогам или выделенным полосам (автобусы, грузовики, спецтехника).

## 1. Зачем нужна привязка к графу дорог

В системах мониторинга транспорта (EGTS + RTLS) сырые координаты (GPS/Indoor) имеют ошибки:
- Погрешность GPS: 3–15 м
- RTLS Indoor: до нескольких метров
- Многолучевое распространение, туннели, плотная застройка

**Map Matching** — алгоритм проекции точек на ближайшие сегменты графа дорог. Это критично для:
- Точного расчёта пройденного пути и скорости
- Определения нарушений (выезд на встречную, выделенную полосу)
- Построения реальных маршрутов
- Аналитики (время в пробке, остановки)
- Интеграции с ГИС (Яндекс.Карты, 2ГИС, OpenStreetMap, Росреестр)

Особенно актуально для **РНИС Пермь / Камчатка / МО** — где требуется точный трекинг по дорожной сети.

## 2. Основные подходы к Map Matching

| Метод | Точность | Сложность | Подходит для |
|-------|----------|-----------|--------------|
| **Nearest Segment** | Средняя | Низкая | Простые случаи |
| **Hidden Markov Model (HMM)** | Высокая | Средняя | Классика (OSM + GPS) |
| **Particle Filter** | Очень высокая | Высокая | Реальное время, шум |
| **Machine Learning** (Graph Neural Nets) | Очень высокая | Очень высокая | Современные решения |
| **Topological + RTLS** | Высокая в помещениях | Средняя | Ваш кейс (Indoor + дороги) |

### Рекомендуемый стек для проекта:
- **Граф дорог**: OpenStreetMap (OSM) + GraphHopper / Valhalla / pgRouting (PostGIS)
- **Алгоритмы**: HMM (библиотека `hmm-map-matching` или `scikit-mobility`)
- **Интеграция**: Python (в вашем парсере) → PostGIS + PostGIS + pgRouting

## 3. Интеграция с EGTS / RTLS

- После парсинга `EGTS_SR_POS_DATA` (SRT 16) + RTLS SRT 200–203 добавлять поле **"road_segment_id"** или **"matched_coordinates"**.
- В SRT 200 (Extended Position) добавить:
  - `road_id` / `segment_id`
  - `lane_number`
  - `direction` (forward/backward)
  - `confidence` (вероятность привязки)
- RTLS Indoor → привязка к indoor-графу (здания, склады) + переход к outdoor road graph.

## 4. Рекомендации по реализации в egts_parser

1. **В models.py**:
   - Добавить dataclass `EGTS_SR_MAP_MATCH` или расширить SRT 200.

2. **В Excel-парсере**:
   - Новый лист `MAP_MATCHING` с колонками: raw_lat, raw_lon, matched_lat, matched_lon, road_name, speed_limit и т.д.

3. **CLI / Cloud Function**:
   - Опция `--map-match` с передачей OSM-графа или API (GraphHopper).

4. **Тестирование**:
   - Набор тестовых траекторий (съезд с дороги, туннель, парковка).

5. **Документация**:
   - Добавить в ТЗ RTLS v2 раздел «Map Matching и привязка к дорожному графу».

## 5. Нормативка (Россия)
- Приказ Минтранса № 285 (требования к БНСО)
- ГОСТ Р 54619, 33472
- Рекомендации по интеграции с ЕГРЮЛ/ГИС и дорожными данными

## Источники и полезные ссылки
- OSM + Valhalla: https://valhalla.readthedocs.io/
- pgRouting: https://pgrouting.org/
- Статья: "Map-matching for low-sampling-rate GPS trajectories" (HMM)
- Библиотеки: `leuven-map-matching`, `mapbox-matching`

---

**Файл создан:** `DOCS/discussions/07-road-graph-map-matching.md`