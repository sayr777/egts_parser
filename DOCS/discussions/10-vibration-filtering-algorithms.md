# 10. Алгоритмы фильтрации вибраций в инерциальных сенсорах EGTS/RTLS

**Дата:** 2026-06-11  
**Контекст:** Расширение EGTS для РНИС (транспорт, БНСО, Indoor/Outdoor позиционирование)

## Введение

Вибрации — основной источник шума в акселерометрах, гироскопах и магнетометрах на транспортных средствах. Без эффективной фильтрации это приводит к дрейфу heading, ошибкам map-matching и ложным срабатываниям.

## Основные алгоритмы фильтрации

### 1. Простые фильтры (низкая вычислительная сложность — для микроконтроллеров БНСО)

- **Low-Pass Filter (LPF)**  
  - Moving Average / Exponential Moving Average (EMA)  
  - FIR / IIR фильтры (Butterworth, Chebyshev)  
  - Рекомендация: cutoff 5–20 Hz для автомобильных вибраций

- **Median Filter**  
  - Отлично удаляет импульсные выбросы (удары по подвеске)

### 2. Адаптивные и продвинутые фильтры

- **Kalman Filter (KF) / Extended Kalman Filter (EKF)**  
  - Лучший выбор для sensor fusion (акселерометр + магнетометр + GPS)  
  - Оценивает состояние (позиция, скорость, ориентация) и covariance

- **Complementary Filter**  
  - Простая комбинация high-pass (гироскоп) + low-pass (акселерометр)  
  - Используется в IMU для heading

- **Madgwick Filter** / Mahony Filter  
  - Градиентный descent для quaternion-based ориентации  
  - Очень эффективен на embedded устройствах

- **Unscented Kalman Filter (UKF)**  
  - Для сильно нелинейных систем (высокие вибрации)

### 3. Frequency-domain фильтры

- **FFT / Wavelet denoising**  
  - Удаление конкретных частот двигателя/дороги  
  - Adaptive Notch Filter для известных гармоник

### 4. Machine Learning подходы (для edge/Cloud)

- Neural Networks (LSTM, CNN) для предсказания и подавления вибрационного шума
- Autoencoders для denoising

## Рекомендации для EGTS RTLS (SRT 204)

Добавить в `EGTS_SR_INERTIAL_DATA` поля:
- `vibration_rms_x/y/z` (float)
- `vibration_peak` 
- `dominant_frequency` (Hz)
- `filter_type` (enum: none, lpf, kalman, madgwick)
- `fusion_confidence`

## Реализация в проекте

- **В мобильном приложении (Flutter):** использовать `sensors_plus` + Madgwick/Kalman библиотеку
- **В Python (SERVICE):** scipy.signal + pykalman / filterpy
- **В Excel-парсере:** колонка `filtered_heading`, графики спектра

## Пример кода (Python)

```python
import numpy as np
from scipy.signal import butter, lfilter

def butter_lowpass(cutoff, fs, order=5):
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    b, a = butter(order, normal_cutoff, btype='low', analog=False)
    return b, a

def lowpass_filter(data, cutoff=10.0, fs=100.0, order=5):
    b, a = butter_lowpass(cutoff, fs, order=order)
    y = lfilter(b, a, data)
    return y
```

## Интеграция в ТЗ RTLS v2

Добавить подраздел:  
**«Алгоритмы фильтрации вибраций и sensor fusion»** с требованиями к точности heading (±2–5°) при вибрациях до 5g.

## Ссылки
- Madgwick: https://x-io.co.uk/open-source-imu-and-ahrs-algorithms/
- Kalman для IMU: стандартные библиотеки filterpy
- Автомобильные вибрации: ISO 2631, SAE стандарты

---
**Автор:** Grok + Anton Tenyakov
