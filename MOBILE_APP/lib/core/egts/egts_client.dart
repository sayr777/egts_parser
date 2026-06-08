import 'dart:convert';
import 'dart:typed_data';
import 'package:http/http.dart' as http;
import 'package:egts_tracker/models/models.dart';

class SendResult {
  final bool success;
  final int httpCode;
  final String? error;
  const SendResult({required this.success, this.httpCode = 0, this.error});
}

class EgtsClient {
  final ServerConfig config;
  EgtsClient(this.config);

  Future<SendResult> send(Uint8List packet) async {
    if (config.url.isEmpty) {
      return const SendResult(success: false, error: 'URL не настроен');
    }
    final hex = packet.map((b) => b.toRadixString(16).padLeft(2, '0')).join('').toUpperCase();
    final body = jsonEncode({'body': hex, 'isBase64Encoded': false});
    try {
      final uri = Uri.parse(config.url);
      final headers = <String, String>{
        'Content-Type': 'application/json; charset=utf-8',
        if (config.token.isNotEmpty) 'Authorization': 'Bearer ${config.token}',
        'X-EGTS-Terminal': '${config.terminalId}',
      };
      final resp = await http
          .post(uri, headers: headers, body: body)
          .timeout(Duration(milliseconds: config.timeoutMs));

      return SendResult(
        success: resp.statusCode >= 200 && resp.statusCode < 300,
        httpCode: resp.statusCode,
        error: resp.statusCode >= 300 ? 'HTTP ${resp.statusCode}' : null,
      );
    } on Exception catch (e) {
      return SendResult(success: false, error: e.toString());
    }
  }
}
