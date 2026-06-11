# 18. Интеграция IMU в Flutter-приложение (Dart код)

## Сбор данных с сенсоров

```dart
import 'package:sensors_plus/sensors_plus.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

class ImuManager {
  StreamSubscription? _accelSub;
  StreamSubscription? _gyroSub;
  StreamSubscription? _magSub;

  double heading = 0.0;
  List<double> accel = [0,0,0];
  List<double> gyro = [0,0,0];
  List<double> mag = [0,0,0];

  void startListening() {
    _accelSub = accelerometerEvents.listen((AccelerometerEvent event) {
      accel = [event.x, event.y, event.z];
    });
    // аналогично для gyroscopeEvents и magnetometerEvents
  }

  Future<void> sendToServer() async {
    // Формирование SRT 204 payload
    final payload = {
      "srt_type": 204,
      "accel": accel,
      "gyro": gyro,
      "mag": mag,
      "heading": heading,
      "timestamp": DateTime.now().millisecondsSinceEpoch,
    };

    await http.post(Uri.parse('your-cloud-function-url'), body: jsonEncode(payload));
  }
}
```

## Рекомендации
- Использовать `sensor_plus` package
- Применять Kalman/EKF на устройстве или на сервере
- Background service для постоянного трекинга
