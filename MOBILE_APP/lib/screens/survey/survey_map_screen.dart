import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:provider/provider.dart';
import 'package:egts_tracker/core/tracker_provider.dart';
import 'package:egts_tracker/models/models.dart';

/// Экран карты для исследователя.
///
/// Отображает карту OSM с булавкой в центре экрана.
/// Пользователь перемещает карту под булавкой для выбора координат.
/// Нажатие «Отправить» формирует EGTS-пакет и отправляет на сервер.
class SurveyMapScreen extends StatefulWidget {
  final NfcEvent?    nfc;
  final BeaconEvent? beacon;
  final WifiEvent?   wifi;
  final LbsEvent?    lbs;

  const SurveyMapScreen({super.key, this.nfc, this.beacon, this.wifi, this.lbs})
      : assert(nfc != null || beacon != null || wifi != null || lbs != null,
            'Нужен хотя бы один объект');

  @override
  State<SurveyMapScreen> createState() => _SurveyMapScreenState();
}

class _SurveyMapScreenState extends State<SurveyMapScreen> {
  final MapController _mapCtrl = MapController();
  LatLng _center = const LatLng(55.751244, 37.618423); // Москва как дефолт
  bool _sending = false;
  String? _resultMsg;
  bool _resultOk = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final gps = context.read<TrackerProvider>().gps;
      if (gps.isValid) {
        final pos = LatLng(gps.lat, gps.lon);
        setState(() => _center = pos);
        _mapCtrl.move(pos, 19);
      }
    });
  }

  String get _title {
    if (widget.wifi    != null) return 'WiFi: ${widget.wifi!.ssid}';
    if (widget.nfc     != null) return 'NFC: ${widget.nfc!.uid}';
    if (widget.beacon  != null) return 'iBeacon: ${widget.beacon!.uuid.substring(0, 8)}…';
    if (widget.lbs     != null) return 'LBS: CID ${widget.lbs!.cellId}';
    return 'Обследование';
  }

  Color get _markerColor {
    if (widget.wifi    != null) return Colors.blue;
    if (widget.nfc     != null) return Colors.green;
    if (widget.beacon  != null) return Colors.purple;
    if (widget.lbs     != null) return Colors.orange;
    return Colors.red;
  }

  IconData get _markerIcon {
    if (widget.wifi    != null) return Icons.wifi;
    if (widget.nfc     != null) return Icons.nfc;
    if (widget.beacon  != null) return Icons.bluetooth;
    if (widget.lbs     != null) return Icons.cell_tower;
    return Icons.location_on;
  }

  Future<void> _send() async {
    setState(() { _sending = true; _resultMsg = null; });
    final pos = _mapCtrl.camera.center;
    final result = await context.read<TrackerProvider>().sendSurveyPacket(
      markerPos: pos,
      nfc:    widget.nfc,
      beacon: widget.beacon,
      wifi:   widget.wifi,
      lbs:    widget.lbs,
    );
    setState(() {
      _sending  = false;
      _resultOk = result.success;
      _resultMsg = result.success
          ? 'Пакет отправлен ✓'
          : 'Ошибка: ${result.error}';
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(_title, overflow: TextOverflow.ellipsis)),
      body: Stack(children: [
        // ── Карта ──────────────────────────────────────────────────────────
        FlutterMap(
          mapController: _mapCtrl,
          options: MapOptions(
            initialCenter: _center,
            initialZoom: 19,
            minZoom: 12,
            maxZoom: 22,
            onMapEvent: (event) {
              if (event is MapEventMove) setState(() {});
            },
          ),
          children: [
            TileLayer(
              urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
              userAgentPackageName: 'com.egts.egts_tracker',
              maxZoom: 22,
              maxNativeZoom: 19,
              additionalOptions: const {
                'User-Agent': 'EGTSTracker/1.0 (com.egts.egts_tracker)',
              },
              fallbackUrl: 'https://a.tile.openstreetmap.org/{z}/{x}/{y}.png',
            ),
            // GPS-позиция (синий кружок)
            Consumer<TrackerProvider>(builder: (_, p, __) {
              if (!p.gps.isValid) return const SizedBox.shrink();
              return MarkerLayer(markers: [
                Marker(
                  point: LatLng(p.gps.lat, p.gps.lon),
                  width: 18, height: 18,
                  child: Container(
                    decoration: BoxDecoration(
                      color: Colors.blue.withOpacity(0.7),
                      shape: BoxShape.circle,
                      border: Border.all(color: Colors.white, width: 2),
                    ),
                  ),
                ),
              ]);
            }),
          ],
        ),

        // ── Булавка по центру (неподвижна, карта движется под ней) ─────────
        Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: _markerColor,
                  shape: BoxShape.circle,
                  boxShadow: [BoxShadow(
                    color: Colors.black38, blurRadius: 6, offset: const Offset(0, 3))],
                ),
                child: Icon(_markerIcon, color: Colors.white, size: 24),
              ),
              // Острие булавки
              CustomPaint(
                size: const Size(16, 10),
                painter: _ArrowPainter(_markerColor),
              ),
            ],
          ),
        ),

        // ── Координаты под булавкой ─────────────────────────────────────────
        Positioned(
          top: 8, left: 0, right: 0,
          child: Center(child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
            decoration: BoxDecoration(
              color: Colors.black54,
              borderRadius: BorderRadius.circular(16),
            ),
            child: Builder(builder: (_) {
              final c = _mapCtrl.camera.center;
              return Text(
                '${c.latitude.toStringAsFixed(6)}, ${c.longitude.toStringAsFixed(6)}',
                style: const TextStyle(color: Colors.white, fontSize: 13),
              );
            }),
          )),
        ),

        // ── Инфо-карточка снизу ────────────────────────────────────────────
        Positioned(
          bottom: 0, left: 0, right: 0,
          child: _InfoCard(
            widget: widget,
            markerColor: _markerColor,
            sending: _sending,
            resultMsg: _resultMsg,
            resultOk: _resultOk,
            onSend: _send,
          ),
        ),

        // ── Zoom controls ──────────────────────────────────────────────────
        Positioned(
          right: 12, bottom: 220,
          child: Column(children: [
            _ZoomButton(icon: Icons.add, onTap: () {
              final z = (_mapCtrl.camera.zoom + 1).clamp(12.0, 22.0);
              _mapCtrl.move(_mapCtrl.camera.center, z);
            }),
            const SizedBox(height: 4),
            _ZoomButton(icon: Icons.remove, onTap: () {
              final z = (_mapCtrl.camera.zoom - 1).clamp(12.0, 22.0);
              _mapCtrl.move(_mapCtrl.camera.center, z);
            }),
          ]),
        ),
      ]),
    );
  }
}

// ─── Info card ────────────────────────────────────────────────────────────────

class _InfoCard extends StatelessWidget {
  final SurveyMapScreen widget;
  final Color markerColor;
  final bool sending;
  final String? resultMsg;
  final bool resultOk;
  final VoidCallback onSend;

  const _InfoCard({
    required this.widget,
    required this.markerColor,
    required this.sending,
    required this.resultMsg,
    required this.resultOk,
    required this.onSend,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
        boxShadow: [BoxShadow(color: Colors.black26, blurRadius: 8)],
      ),
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
      child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
        // Drag indicator
        Center(child: Container(
          width: 36, height: 4,
          decoration: BoxDecoration(
            color: Colors.grey.shade300, borderRadius: BorderRadius.circular(2)),
        )),
        const SizedBox(height: 12),

        // Device info
        _deviceInfo(),
        const SizedBox(height: 4),

        // LBS hint
        Consumer<TrackerProvider>(builder: (_, p, __) {
          final lbs = p.lbsCells.firstOrNull;
          if (lbs == null) return const SizedBox.shrink();
          return Text(
            'LBS: MCC=${lbs.mcc} MNC=${lbs.mnc} LAC=${lbs.lac} CID=${lbs.cellId}  ${lbs.rssi} dBm',
            style: TextStyle(fontSize: 11, color: Colors.grey.shade600),
          );
        }),
        const SizedBox(height: 12),

        // Result message
        if (resultMsg != null) ...[
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: resultOk ? Colors.green.shade50 : Colors.red.shade50,
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text(resultMsg!,
                style: TextStyle(
                    color: resultOk ? Colors.green.shade700 : Colors.red.shade700,
                    fontWeight: FontWeight.w500)),
          ),
          const SizedBox(height: 8),
        ],

        // Send button
        SizedBox(
          width: double.infinity,
          child: ElevatedButton.icon(
            style: ElevatedButton.styleFrom(
              backgroundColor: markerColor,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(vertical: 14),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            ),
            onPressed: sending ? null : onSend,
            icon: sending
                ? const SizedBox.square(dimension: 18,
                    child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                : const Icon(Icons.send),
            label: Text(sending ? 'Отправка...' : 'Отправить EGTS-пакет',
                style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
          ),
        ),
      ]),
    );
  }

  Widget _deviceInfo() {
    final w = widget;
    if (w.wifi != null) {
      return _row([
        _chip('WiFi', Colors.blue),
        Text('${w.wifi!.ssid}', style: const TextStyle(fontWeight: FontWeight.bold)),
        const Spacer(),
        Text('${w.wifi!.rssi} dBm  ${w.wifi!.channel > 0 ? "канал ${w.wifi!.channel}" : ""}',
            style: TextStyle(color: Colors.grey.shade600, fontSize: 13)),
      ]);
    }
    if (w.nfc != null) {
      return _row([
        _chip('NFC', Colors.green),
        Expanded(child: Text(w.nfc!.uid,
            style: const TextStyle(fontWeight: FontWeight.bold),
            overflow: TextOverflow.ellipsis)),
      ]);
    }
    if (w.beacon != null) {
      return _row([
        _chip('iBeacon', Colors.purple),
        Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('${w.beacon!.major}/${w.beacon!.minor}',
              style: const TextStyle(fontWeight: FontWeight.bold)),
          Text(w.beacon!.uuid, style: TextStyle(fontSize: 11, color: Colors.grey.shade500),
              overflow: TextOverflow.ellipsis),
        ])),
        Text('${w.beacon!.rssi} dBm',
            style: TextStyle(color: Colors.grey.shade600, fontSize: 13)),
      ]);
    }
    if (w.lbs != null) {
      return _row([
        _chip('LBS', Colors.orange),
        Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('CID ${w.lbs!.cellId}', style: const TextStyle(fontWeight: FontWeight.bold)),
          Text('MCC=${w.lbs!.mcc} MNC=${w.lbs!.mnc} LAC=${w.lbs!.lac}',
              style: TextStyle(fontSize: 11, color: Colors.grey.shade500)),
        ])),
        Text('${w.lbs!.rssi} dBm',
            style: TextStyle(color: Colors.grey.shade600, fontSize: 13)),
      ]);
    }
    return const SizedBox.shrink();
  }

  Widget _chip(String label, Color color) => Container(
    margin: const EdgeInsets.only(right: 8),
    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
    decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(12)),
    child: Text(label, style: const TextStyle(color: Colors.white, fontSize: 12,
        fontWeight: FontWeight.bold)),
  );

  Widget _row(List<Widget> children) => Row(
    crossAxisAlignment: CrossAxisAlignment.center,
    children: children,
  );
}

// ─── Arrow painter (острие булавки) ──────────────────────────────────────────

class _ArrowPainter extends CustomPainter {
  final Color color;
  const _ArrowPainter(this.color);

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()..color = color..style = PaintingStyle.fill;
    final path = ui.Path();
    path.moveTo(0, 0);
    path.lineTo(size.width, 0);
    path.lineTo(size.width / 2, size.height);
    path.close();
    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(_ArrowPainter old) => old.color != color;
}

// ─── Zoom button ──────────────────────────────────────────────────────────────

class _ZoomButton extends StatelessWidget {
  final IconData icon;
  final VoidCallback onTap;
  const _ZoomButton({required this.icon, required this.onTap});

  @override
  Widget build(BuildContext context) => GestureDetector(
    onTap: onTap,
    child: Container(
      width: 40, height: 40,
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(8),
        boxShadow: const [BoxShadow(color: Colors.black26, blurRadius: 4)],
      ),
      child: Icon(icon, size: 22),
    ),
  );
}
