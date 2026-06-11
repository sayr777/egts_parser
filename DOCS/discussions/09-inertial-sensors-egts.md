# Интеграция инерциальных сенсоров (магнетометр, компас, акселерометр) в расширение EGTS / RTLS

**Дата:** 2026-06-11  
**Автор:** Grok (для проекта sayr777/egts_parser)  
**Контекст:** Для точного определения направления движения и ориентации ТС в проектах РНИС, особенно при движении по дорогам, выделенным полосам, Indoor/Outdoor.

## 1. Зачем нужны инерциальные сенсоры в EGTS

- **Магнетометр + Компас**: Определение азимута (направления) относительно магнитного севера. Критично для:
  - Определения направления движения по дороге (вперёд/назад, смена полосы).
  - Коррекции GPS/RTLS в условиях слабого сигнала.
  - Выявления разворотов, манёвров.

- **Акселерометр**: Измерение ускорения по осям (X/Y/Z). Применение:
  - Детекция старта/остановки, резких торможений/ускорений.
  - Распознавание ДТП, тряски.
  - Помощь в dead reckoning (инерциальная навигация) при потере GPS.
  - Оценка качества дороги.

**Комбинация** (IMU — Inertial Measurement Unit) даёт точное heading + motion vector, особенно полезно вместе с **Map Matching**.

## 2. Предлагаемые расширения EGTS (vendor-specific SRT)

Рекомендуется добавить/расширить SRT в сервисе `EGTS_TELEDATA_SERVICE`:

### SRT 204 — EGTS_SR_INERTIAL_DATA (новый)
```python
@dataclass
class EGTS_SR_INERTIAL_DATA:
    heading: float = 0.0          # Азимут в градусах (0-359.99) от магнетометра/компаса
    heading_accuracy: float = 0.0 # Точность в градусах
    accel_x: float = 0.0          # Ускорение по X (g или m/s²)
    accel_y: float = 0.0
    accel_z: float = 0.0
    gyro_x: float = 0.0           # Опционально: угловая скорость (если есть гироскоп)
    gyro_y: float = 0.0
    gyro_z: float = 0.0
    flags: int = 0                # Биты: calibrated, magnetic_disturbance и т.д.
    timestamp: int = 0
```

Можно интегрировать в существующие SRT 200–203 или создать отдельный.

## 3. Интеграция с другими фичами

- **С Map Matching** (07-road-graph-map-matching.md): heading помогает выбрать правильное направление сегмента дороги.
- **С RTLS** (SRT 200+): улучшает Indoor позиционирование (orientation-aware).
- **Мобильное приложение (Flutter)**: уже имеет доступ к сенсорам — добавить отправку в EGTS.

## 4. Рекомендации по реализации

1. **models.py** — добавить dataclass выше.
2. **codec.py** — поддержка encode/decode SRT 204.
3. **Excel-парсер** — новый лист `INERTIAL_SENSORS` с колонками heading, accel_*, flags и т.д.
4. **Алгоритмы**:
   - Sensor fusion (Madgwick / Kalman filter) для объединения compass + accel + gyro.
   - Калибровка магнетометра (учёт hard/soft iron interference).

## 5. Добавление в ТЗ RTLS v2

**Раздел «Соответствие международным стандартам и инерциальная навигация»**:

- Соответствие ISO/IEC 24730-1 (API) + ГОСТ Р.
- Поддержка inertial data для улучшения точности RTLS (heading, acceleration).
- IEEE 802.15.4z + IMU fusion recommendations.
- Требования к точности heading (±5°), accel (±0.1g).

## Источники
- Bosch / STMicroelectronics IMU datasheets (магнетометр + акселерометр).
- Sensor Fusion algorithms (Madgwick filter, open-source).
- ГОСТ Р 54619-2011 (расширения SRT).
- Приказ Минтранса №285 (требования к БНСО — поддержка дополнительных датчиков).

---

**Файл создан:** `DOCS/discussions/08-inertial-sensors-egts.md`
