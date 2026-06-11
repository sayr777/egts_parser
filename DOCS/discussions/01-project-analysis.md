# Анализ проекта EGTS Parser (sayr777/egts_parser)

**Дата анализа:** 2026-06-11

## Общая оценка
Полноценная bidirectional-экосистема для работы с протоколом EGTS (ГОСТ Р 54619-2011 + RTLS-расширения).

**Цель**: Полноценный bidirectional парсер + инструменты для тестирования, отладки, мобильного сбора данных и RTLS (Indoor-позиционирование).

**Языки/стек**: Python 3.11 (core), Flutter/Dart (мобильное приложение), Go (read-only submodule).

**Статус**: Активный, но небольшой (6 коммитов). Хорошо документирован, с примерами и нормативкой.

## Сильные стороны
- Полная реализация decode/encode с пересчётом CRC.
- Excel-инструмент для ручного редактирования пакетов (идеально для тестирования/ГОСТ-документации).
- Расширения под RTLS (SRT 200–203).
- Готовый Cloud Function (Yandex) + CLI + TCP listener.
- Flutter-приложение для сбора данных.

## Слабые стороны
- Небольшой размер проекта, возможны edge-кейсы в редких SRT.
- Flutter-приложение — преимущественно демонстрационное.

## Структура репозитория
```
egts_parser/
├── DOCS/                  # Документация + ТЗ RTLS + landing PDF
├── SERVICE/               # Основной Python-парсер + Yandex Cloud Function + CLI
│   └── egts/              # codec, models (dataclasses), crc, const
├── PARSER/                # egts_excel_parser.py — bidirectional Excel
├── MOBILE_APP/            # Flutter Android app (APK готов)
└── egts-protocol/         # Go-реализация (submodule)
```

## Подробный разбор компонентов
### 1. SERVICE (ядро)
- `handler.py` — единая точка входа (Cloud Function, CLI, TCP listener).
- Полный parse_stream → список EGTSPacket.
- Поддержка PT_APPDATA/PT_RESPONSE, большинство SRT + RTLS.

### 2. PARSER (Excel-инструмент)
- Bidirectional: decode ↔ encode.
- Красивый XLSX с листами по SRT, цветовой разметкой, roundtrip.
- Идеально для отладки и подготовки тестовых пакетов.

### 3. MOBILE_APP
- Flutter Android app для GPS + BLE + WiFi + NFC.
- Отправка EGTS-пакетов на Cloud Function.

## Рекомендации
См. файл 02-recommendations-improvements.md