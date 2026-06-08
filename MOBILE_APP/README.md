# EGTS Tracker — Flutter Android App

## Назначение

Мобильное приложение для мониторинга iBeacon, NFC/RFID, WiFi и LBS.
При обнаружении устройства из белого списка — немедленно формирует и отправляет
EGTS-пакет на сервер (Yandex Cloud Function).

## Экраны

### Мониторинг (4 вкладки)
| Вкладка | Что отображается |
|---------|-----------------|
| **События** | Лента EGTS-пакетов с декодированной структурой (разворачивается) |
| **NFC** | Все считанные NFC/RFID метки, отметка ✓ если в белом списке |
| **iBeacon** | Обнаруженные BLE маяки с RSSI и расстоянием |
| **WiFi** | Точки доступа с SSID, BSSID, уровнем сигнала |

- Строка статуса: GPS-координата, количество спутников, статус последней отправки
- Кнопка старт/стоп сканирования

### Настройки
| Секция | Описание |
|--------|---------|
| **Сервер EGTS** | URL Yandex Cloud Function, IAM-токен, Terminal ID |
| **Принципы формирования** | Правила: NFC/iBeacon/WiFi → EGTS |
| **Белый список NFC** | Список UID-тегов. Добавить/удалить (свайп влево) |
| **Белый список iBeacon** | UUID + Major + Minor (* = любой) |
| **Белый список WiFi** | SSID и/или BSSID точек доступа |

## Логика формирования EGTS-пакета

```
Событие обнаружено → проверить белый список
    ↓ Совпадение
Построить EGTS PT_APPDATA:
    SDR (SST=TELEDATA, OID=terminalId)
    ├── SRT 16  POS_DATA       (GPS: lat, lon, speed, course)
    ├── SRT 17  EXT_POS_DATA   (HDOP, кол-во спутников)
    ├── SRT 21  STATE_DATA     (напряжение 12V, state=active)
    ├── SRT 202 CUSTOM_SRT202  (tag_id, zone_id, rssi)
    └── SRT 203 CUSTOM_SRT203  (event_type=1/enter, zone_id, time)
    ↓
POST {"body": "<HEX>", "isBase64Encoded": false}
→ https://functions.yandexcloud.net/<function-id>
    ↓
Отображение в ленте "События" (с декодированной структурой)
```

## Быстрый старт

```bash
# Установить Flutter SDK >= 3.16
flutter pub get

# Запустить на устройстве (или эмуляторе)
flutter run

# Сборка APK
flutter build apk --release
```

## Настройка сервера

1. Откройте вкладку **Настройки**
2. Вставьте URL Yandex Cloud Function в поле **URL EGTS**:
   ```
   https://functions.yandexcloud.net/YOUR_FUNCTION_ID
   ```
3. При необходимости укажите IAM-токен
4. Нажмите **Сохранить**

## Добавление в белый список

### NFC/RFID
1. Настройки → Белый список NFC → Добавить
2. Введите UID в формате `AA:BB:CC:DD` или `AABBCCDD`
3. Поднесите карту → событие появится в ленте + отправится пакет

### iBeacon
1. Настройки → Белый список iBeacon → Добавить
2. Введите UUID маяка (например `B9407F30-F5F8-466E-AFF9-25556B57FE6D`)
3. Major/Minor: конкретное значение или `*` для любого

### WiFi
1. Настройки → Белый список WiFi → Добавить
2. SSID — название сети и/или BSSID — MAC-адрес точки доступа

## Зависимости

| Пакет | Назначение |
|-------|-----------|
| `flutter_nfc_kit` | NFC/RFID (все типы тегов) |
| `flutter_blue_plus` | BLE сканирование → iBeacon парсинг |
| `wifi_scan` | WiFi AP сканирование |
| `geolocator` | GPS/ГЛОНАСС (без Google Play Services) |
| `provider` | State management |
| `shared_preferences` | Хранение белых списков |
| `http` | HTTP POST на Cloud Function |
| `flutter_slidable` | Свайп-удаление в списках |

## Разрешения Android

| Разрешение | Назначение |
|------------|------------|
| `ACCESS_FINE_LOCATION` | GPS + BLE сканирование |
| `BLUETOOTH_SCAN` | Поиск iBeacon (Android 12+) |
| `NFC` | RFID/NFC считывание |
| `ACCESS_WIFI_STATE` | WiFi сканирование |
| `FOREGROUND_SERVICE` | Фоновая работа |
