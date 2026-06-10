# EGTS Excel Parser — bidirectional инструмент для тестирования и документации

**Дата:** 2026-06-11  
**Автор:** Grok (анализ для egts_parser)

## Обзор

`PARSER/egts_excel_parser.py` — одна из самых мощных фич проекта.

Это **двунаправленный** инструмент:
- **Decode**: HEX / binary / CSV → структурированный Excel-файл
- **Encode**: Редактирование в Excel → binary пакет + обновление HEX

## Основные возможности

- Автоматическое создание листов по типам SRT (POS_DATA, RTLS 200-203, STATE_DATA и др.)
- Цветовая разметка:
  - Жёлтый — поля для редактирования
  - Синий — HEX-представление
  - Серый — системные/вычисляемые
- Автоматический пересчёт:
  - Длин пакетов
  - CRC-8 / CRC-16
  - Всех заголовков
- Roundtrip: decode → edit → encode → decode = идентичный пакет
- Поддержка нескольких пакетов в одном файле (лист PACKETS)

## Применение в РНИС-проектах

- Подготовка тестовых пакетов для ПМИ / И3.1 / формуляров
- Валидация данных от БНСО
- Анализ edge-кейсов (RTLS, ошибки CRC, routed header)
- Документация: сохранение "золотых" пакетов в Excel для ГОСТ-документов

## Рекомендации

1. Добавить шаблоны (template.xlsx) для разных сценариев (RTLS, ДУТ, sensors)
2. Макросы VBA для быстрого generate / validate
3. Поддержка batch-обработки нескольких файлов
4. Интеграция с n8n (node для Excel ↔ EGTS)

## Пример использования

```bash
python egts_excel_parser.py decode --input test.hex --output test.xlsx
python egts_excel_parser.py encode --input test_edited.xlsx --output test.bin
```

**Файл создан:** `DOCS/discussions/05-excel-parser.md`