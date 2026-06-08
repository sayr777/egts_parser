import 'package:flutter/material.dart';
import 'package:flutter_nfc_kit/flutter_nfc_kit.dart';
import 'package:provider/provider.dart';
import 'package:egts_tracker/core/tracker_provider.dart';
import 'package:egts_tracker/models/models.dart';
import 'package:egts_tracker/widgets/event_card.dart';
import 'package:egts_tracker/widgets/egts_packet_view.dart';

class MonitoringScreen extends StatefulWidget {
  const MonitoringScreen({super.key});
  @override
  State<MonitoringScreen> createState() => _MonitoringScreenState();
}

class _MonitoringScreenState extends State<MonitoringScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabs;
  bool _nfcPoll = false;

  @override
  void initState() {
    super.initState();
    _tabs = TabController(length: 4, vsync: this);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<TrackerProvider>().startScanning();
      _startNfcPolling();
    });
  }

  @override
  void dispose() {
    _tabs.dispose();
    _nfcPoll = false;
    super.dispose();
  }

  // ─── NFC polling loop ─────────────────────────────────────────────────────

  Future<void> _startNfcPolling() async {
    final avail = await FlutterNfcKit.nfcAvailability;
    if (avail != NFCAvailability.available) return;
    _nfcPoll = true;
    while (_nfcPoll && mounted) {
      try {
        final tag = await FlutterNfcKit.poll(timeout: const Duration(seconds: 3));
        if (!mounted) break;
        final uid = tag.id.toUpperCase();
        final techList = [tag.type.toString()];
        context.read<TrackerProvider>().onNfcDetected(
            NfcEvent(uid: uid, techList: techList));
        await FlutterNfcKit.finish();
      } catch (_) {
        // таймаут или нет метки — ждём
        await Future.delayed(const Duration(milliseconds: 500));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Мониторинг'),
        backgroundColor: const Color(0xFF1F4E79),
        foregroundColor: Colors.white,
        bottom: TabBar(
          controller: _tabs,
          labelColor: Colors.white,
          unselectedLabelColor: Colors.white60,
          indicatorColor: Colors.white,
          tabs: const [
            Tab(icon: Icon(Icons.sensors), text: 'События'),
            Tab(icon: Icon(Icons.nfc), text: 'NFC'),
            Tab(icon: Icon(Icons.bluetooth), text: 'iBeacon'),
            Tab(icon: Icon(Icons.wifi), text: 'WiFi'),
          ],
        ),
        actions: [
          Consumer<TrackerProvider>(builder: (_, p, __) => IconButton(
            icon: Icon(p.scanning ? Icons.pause : Icons.play_arrow),
            tooltip: p.scanning ? 'Стоп' : 'Старт',
            onPressed: () => p.scanning ? p.stopScanning() : p.startScanning(),
          )),
        ],
      ),
      body: Consumer<TrackerProvider>(builder: (_, prov, __) {
        return Column(children: [
          // ─── Status bar ──────────────────────────────────────────────
          _StatusBar(prov: prov),
          // ─── Tab content ─────────────────────────────────────────────
          Expanded(child: TabBarView(controller: _tabs, children: [
            _EventsTab(prov: prov),
            _NfcTab(prov: prov),
            _BeaconTab(prov: prov),
            _WifiTab(prov: prov),
          ])),
        ]);
      }),
    );
  }
}

// ─── Status bar ───────────────────────────────────────────────────────────────

class _StatusBar extends StatelessWidget {
  final TrackerProvider prov;
  const _StatusBar({required this.prov});

  @override
  Widget build(BuildContext context) {
    final gps = prov.gps;
    return Container(
      color: const Color(0xFFEEF2F7),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      child: Row(children: [
        Icon(Icons.gps_fixed,
            size: 16, color: gps.isValid ? Colors.green : Colors.grey),
        const SizedBox(width: 4),
        Expanded(child: Text(
          gps.isValid
              ? 'GPS ${gps.lat.toStringAsFixed(5)}, ${gps.lon.toStringAsFixed(5)}'
                  '  ${gps.satellites} спутн.'
              : 'GPS: ожидание...',
          style: const TextStyle(fontSize: 12),
          overflow: TextOverflow.ellipsis,
        )),
        const SizedBox(width: 8),
        Text(prov.statusMsg,
            style: const TextStyle(fontSize: 11, color: Color(0xFF375623))),
        if (prov.scanning) ...[
          const SizedBox(width: 6),
          const SizedBox.square(dimension: 10,
            child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFF1F4E79))),
        ],
      ]),
    );
  }
}

// ─── Tab: EGTS-события ────────────────────────────────────────────────────────

class _EventsTab extends StatelessWidget {
  final TrackerProvider prov;
  const _EventsTab({required this.prov});

  @override
  Widget build(BuildContext context) {
    if (prov.packets.isEmpty) {
      return const Center(child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.inbox_outlined, size: 64, color: Colors.grey),
          SizedBox(height: 12),
          Text('EGTS-пакеты появятся здесь\nпри совпадении с белым списком',
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.grey)),
        ],
      ));
    }
    return ListView.builder(
      itemCount: prov.packets.length,
      itemBuilder: (_, i) => EgtsPacketCard(packet: prov.packets[i]),
    );
  }
}

// ─── Tab: NFC ─────────────────────────────────────────────────────────────────

class _NfcTab extends StatelessWidget {
  final TrackerProvider prov;
  const _NfcTab({required this.prov});

  @override
  Widget build(BuildContext context) {
    if (prov.nfcEvents.isEmpty) {
      return const _EmptyHint(
          icon: Icons.nfc, text: 'Поднесите NFC/RFID метку к телефону');
    }
    return ListView.builder(
      itemCount: prov.nfcEvents.length,
      itemBuilder: (_, i) {
        final evt = prov.nfcEvents[i];
        final inList = prov.nfcWhitelist.any(
            (e) => e.uid.toUpperCase() == evt.uid.toUpperCase());
        return NfcEventCard(event: evt, inWhitelist: inList);
      },
    );
  }
}

// ─── Tab: iBeacon ─────────────────────────────────────────────────────────────

class _BeaconTab extends StatelessWidget {
  final TrackerProvider prov;
  const _BeaconTab({required this.prov});

  @override
  Widget build(BuildContext context) {
    if (prov.beaconEvents.isEmpty) {
      return const _EmptyHint(
          icon: Icons.bluetooth_searching,
          text: 'Ищем iBeacon маяки поблизости...');
    }
    return ListView.builder(
      itemCount: prov.beaconEvents.length,
      itemBuilder: (_, i) {
        final evt = prov.beaconEvents[i];
        final inList = prov.beaconWhitelist.any(
            (e) => e.matches(evt.uuid, evt.major, evt.minor));
        return BeaconEventCard(event: evt, inWhitelist: inList);
      },
    );
  }
}

// ─── Tab: WiFi ────────────────────────────────────────────────────────────────

class _WifiTab extends StatelessWidget {
  final TrackerProvider prov;
  const _WifiTab({required this.prov});

  @override
  Widget build(BuildContext context) {
    if (prov.wifiEvents.isEmpty) {
      return const _EmptyHint(icon: Icons.wifi_find, text: 'Сканируем WiFi сети...');
    }
    return ListView.builder(
      itemCount: prov.wifiEvents.length,
      itemBuilder: (_, i) {
        final evt = prov.wifiEvents[i];
        final inList = prov.wifiWhitelist.any((e) => e.matches(evt.ssid, evt.bssid));
        return WifiEventCard(event: evt, inWhitelist: inList);
      },
    );
  }
}

class _EmptyHint extends StatelessWidget {
  final IconData icon;
  final String text;
  const _EmptyHint({required this.icon, required this.text});

  @override
  Widget build(BuildContext context) => Center(child: Column(
    mainAxisSize: MainAxisSize.min,
    children: [
      Icon(icon, size: 64, color: Colors.grey.shade400),
      const SizedBox(height: 12),
      Text(text, textAlign: TextAlign.center,
          style: TextStyle(color: Colors.grey.shade600)),
    ],
  ));
}
