import 'package:flutter/material.dart';
import 'package:flutter_nfc_kit/flutter_nfc_kit.dart';
import 'package:provider/provider.dart';
import 'package:egts_tracker/core/tracker_provider.dart';
import 'package:egts_tracker/models/models.dart';
import 'package:egts_tracker/screens/survey/survey_map_screen.dart';
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
    _tabs = TabController(length: 5, vsync: this);
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

  // ─── NFC polling ──────────────────────────────────────────────────────────

  Future<void> _startNfcPolling() async {
    final avail = await FlutterNfcKit.nfcAvailability;
    if (avail != NFCAvailability.available) return;
    _nfcPoll = true;
    while (_nfcPoll && mounted) {
      try {
        final tag = await FlutterNfcKit.poll(timeout: const Duration(seconds: 3));
        if (!mounted) break;
        final uid = tag.id.toUpperCase();
        final evt = NfcEvent(uid: uid, techList: [tag.type.toString()]);
        if (mounted) context.read<TrackerProvider>().onNfcDetected(evt);
        await FlutterNfcKit.finish();
      } catch (_) {
        await Future.delayed(const Duration(milliseconds: 500));
      }
    }
  }

  void _openMap({NfcEvent? nfc, BeaconEvent? beacon,
                 WifiEvent? wifi, LbsEvent? lbs}) {
    Navigator.push(context, MaterialPageRoute(
      builder: (_) => SurveyMapScreen(
          nfc: nfc, beacon: beacon, wifi: wifi, lbs: lbs),
    ));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Радиообстановка'),
        bottom: TabBar(
          controller: _tabs,
          labelColor: Colors.white,
          unselectedLabelColor: Colors.white60,
          indicatorColor: Colors.white,
          isScrollable: true,
          tabs: const [
            Tab(icon: Icon(Icons.inbox),      text: 'Пакеты'),
            Tab(icon: Icon(Icons.wifi),        text: 'WiFi'),
            Tab(icon: Icon(Icons.nfc),         text: 'NFC'),
            Tab(icon: Icon(Icons.bluetooth),   text: 'iBeacon'),
            Tab(icon: Icon(Icons.cell_tower),  text: 'LBS'),
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
          _StatusBar(prov: prov),
          Expanded(child: TabBarView(controller: _tabs, children: [
            _PacketsTab(prov: prov),
            _WifiTab(prov: prov, onSelect: (w) => _openMap(wifi: w)),
            _NfcTab(prov: prov, onSelect: (n) => _openMap(nfc: n)),
            _BeaconTab(prov: prov, onSelect: (b) => _openMap(beacon: b)),
            _LbsTab(prov: prov, onSelect: (l) => _openMap(lbs: l)),
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
        Icon(Icons.gps_fixed, size: 16,
            color: gps.isValid ? Colors.green : Colors.grey),
        const SizedBox(width: 4),
        Expanded(child: Text(
          gps.isValid
              ? 'GPS ${gps.lat.toStringAsFixed(5)}, ${gps.lon.toStringAsFixed(5)}'
              : 'GPS: ожидание...',
          style: const TextStyle(fontSize: 12),
          overflow: TextOverflow.ellipsis,
        )),
        Text(prov.statusMsg,
            style: const TextStyle(fontSize: 11, color: Color(0xFF375623))),
        if (prov.scanning) ...[
          const SizedBox(width: 6),
          const SizedBox.square(dimension: 10,
              child: CircularProgressIndicator(strokeWidth: 2,
                  color: Color(0xFF1F4E79))),
        ],
      ]),
    );
  }
}

// ─── Tab: EGTS-пакеты ─────────────────────────────────────────────────────────

class _PacketsTab extends StatelessWidget {
  final TrackerProvider prov;
  const _PacketsTab({required this.prov});

  @override
  Widget build(BuildContext context) {
    if (prov.packets.isEmpty) {
      return const _Empty(icon: Icons.inbox_outlined,
          text: 'EGTS-пакеты появятся здесь\nпосле отправки с карты');
    }
    return ListView.builder(
      itemCount: prov.packets.length,
      itemBuilder: (_, i) => EgtsPacketCard(packet: prov.packets[i]),
    );
  }
}

// ─── Tab: WiFi ────────────────────────────────────────────────────────────────

class _WifiTab extends StatelessWidget {
  final TrackerProvider prov;
  final void Function(WifiEvent) onSelect;
  const _WifiTab({required this.prov, required this.onSelect});

  @override
  Widget build(BuildContext context) {
    if (prov.wifiEvents.isEmpty) {
      return const _Empty(icon: Icons.wifi_find, text: 'Сканируем WiFi сети...');
    }
    return ListView.builder(
      itemCount: prov.wifiEvents.length,
      itemBuilder: (_, i) {
        final e = prov.wifiEvents[i];
        return ListTile(
          leading: _SignalIcon(rssi: e.rssi, color: Colors.blue),
          title: Text(e.ssid.isNotEmpty ? e.ssid : '(скрытая сеть)',
              style: const TextStyle(fontWeight: FontWeight.w600)),
          subtitle: Text('${e.bssid}  •  ${e.frequency} МГц  •  канал ${e.channel}'),
          trailing: Row(mainAxisSize: MainAxisSize.min, children: [
            Text('${e.rssi} дБм',
                style: TextStyle(color: _rssiColor(e.rssi), fontWeight: FontWeight.bold)),
            const SizedBox(width: 4),
            const Icon(Icons.chevron_right),
          ]),
          onTap: () => onSelect(e),
        );
      },
    );
  }
}

// ─── Tab: NFC ─────────────────────────────────────────────────────────────────

class _NfcTab extends StatelessWidget {
  final TrackerProvider prov;
  final void Function(NfcEvent) onSelect;
  const _NfcTab({required this.prov, required this.onSelect});

  @override
  Widget build(BuildContext context) {
    if (prov.nfcEvents.isEmpty) {
      return const _Empty(icon: Icons.nfc,
          text: 'Поднесите NFC/RFID метку к телефону');
    }
    return ListView.builder(
      itemCount: prov.nfcEvents.length,
      itemBuilder: (_, i) {
        final e = prov.nfcEvents[i];
        return ListTile(
          leading: const CircleAvatar(
              backgroundColor: Colors.green,
              child: Icon(Icons.nfc, color: Colors.white, size: 20)),
          title: Text(e.uid, style: const TextStyle(fontWeight: FontWeight.w600,
              fontFamily: 'monospace')),
          subtitle: Text(e.techList.join(', ')),
          trailing: const Icon(Icons.chevron_right),
          onTap: () => onSelect(e),
        );
      },
    );
  }
}

// ─── Tab: iBeacon ─────────────────────────────────────────────────────────────

class _BeaconTab extends StatelessWidget {
  final TrackerProvider prov;
  final void Function(BeaconEvent) onSelect;
  const _BeaconTab({required this.prov, required this.onSelect});

  @override
  Widget build(BuildContext context) {
    if (prov.beaconEvents.isEmpty) {
      return const _Empty(icon: Icons.bluetooth_searching,
          text: 'Ищем iBeacon маяки поблизости...');
    }
    return ListView.builder(
      itemCount: prov.beaconEvents.length,
      itemBuilder: (_, i) {
        final e = prov.beaconEvents[i];
        return ListTile(
          leading: _SignalIcon(rssi: e.rssi, color: Colors.purple),
          title: Text('${e.major} / ${e.minor}',
              style: const TextStyle(fontWeight: FontWeight.w600)),
          subtitle: Text(e.uuid, style: const TextStyle(fontSize: 11)),
          trailing: Row(mainAxisSize: MainAxisSize.min, children: [
            Text('${e.rssi} дБм',
                style: TextStyle(color: _rssiColor(e.rssi), fontWeight: FontWeight.bold)),
            const SizedBox(width: 4),
            const Icon(Icons.chevron_right),
          ]),
          onTap: () => onSelect(e),
        );
      },
    );
  }
}

// ─── Tab: LBS ─────────────────────────────────────────────────────────────────

class _LbsTab extends StatelessWidget {
  final TrackerProvider prov;
  final void Function(LbsEvent) onSelect;
  const _LbsTab({required this.prov, required this.onSelect});

  @override
  Widget build(BuildContext context) {
    return Column(children: [
      // Кнопка обновления
      Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
        child: OutlinedButton.icon(
          onPressed: () => context.read<TrackerProvider>().refreshLbs(),
          icon: const Icon(Icons.refresh, size: 18),
          label: const Text('Обновить список сот'),
        ),
      ),
      Expanded(child: prov.lbsCells.isEmpty
          ? const _Empty(icon: Icons.cell_tower,
              text: 'Нет данных о базовых станциях.\nТребуется разрешение READ_PHONE_STATE.')
          : ListView.builder(
              itemCount: prov.lbsCells.length,
              itemBuilder: (_, i) {
                final e = prov.lbsCells[i];
                return ListTile(
                  leading: CircleAvatar(
                    backgroundColor: Colors.orange.shade100,
                    child: const Icon(Icons.cell_tower, color: Colors.orange, size: 20),
                  ),
                  title: Text('CID ${e.cellId}',
                      style: const TextStyle(fontWeight: FontWeight.w600)),
                  subtitle: Text(
                    'MCC=${e.mcc}  MNC=${e.mnc}  LAC=${e.lac}',
                    style: const TextStyle(fontSize: 12),
                  ),
                  trailing: Row(mainAxisSize: MainAxisSize.min, children: [
                    Text('${e.rssi} дБм',
                        style: TextStyle(
                            color: _rssiColor(e.rssi),
                            fontWeight: FontWeight.bold)),
                    const SizedBox(width: 4),
                    const Icon(Icons.chevron_right),
                  ]),
                  onTap: () => onSelect(e),
                );
              },
            )),
    ]);
  }
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

Color _rssiColor(int rssi) {
  if (rssi >= -50) return Colors.green;
  if (rssi >= -65) return Colors.lightGreen;
  if (rssi >= -75) return Colors.orange;
  return Colors.red;
}

class _SignalIcon extends StatelessWidget {
  final int rssi;
  final Color color;
  const _SignalIcon({required this.rssi, required this.color});

  @override
  Widget build(BuildContext context) => CircleAvatar(
    backgroundColor: color.withOpacity(0.15),
    child: Icon(Icons.signal_cellular_alt, color: color, size: 20),
  );
}

class _Empty extends StatelessWidget {
  final IconData icon;
  final String text;
  const _Empty({required this.icon, required this.text});

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
