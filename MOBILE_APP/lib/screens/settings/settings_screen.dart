import 'package:flutter/material.dart';
import 'package:flutter_slidable/flutter_slidable.dart';
import 'package:provider/provider.dart';
import 'package:egts_tracker/core/tracker_provider.dart';
import 'package:egts_tracker/models/models.dart';

class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Настройки'),
        backgroundColor: const Color(0xFF1F4E79),
        foregroundColor: Colors.white,
      ),
      body: ListView(children: const [
        _SectionHeader('Сервер EGTS'),
        _ServerSection(),
        _SectionHeader('Принципы формирования пакета'),
        _RuleInfo(),
        _SectionHeader('Белый список NFC/RFID'),
        _NfcWhitelistSection(),
        _SectionHeader('Белый список iBeacon'),
        _BeaconWhitelistSection(),
        _SectionHeader('Белый список WiFi'),
        _WifiWhitelistSection(),
      ]),
    );
  }
}

// ─── Section header ───────────────────────────────────────────────────────────

class _SectionHeader extends StatelessWidget {
  final String title;
  const _SectionHeader(this.title);
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.fromLTRB(16, 16, 16, 4),
    child: Text(title, style: const TextStyle(
      color: Color(0xFF1F4E79), fontWeight: FontWeight.bold, fontSize: 13)),
  );
}

// ─── Правила формирования пакета ─────────────────────────────────────────────

class _RuleInfo extends StatelessWidget {
  const _RuleInfo();
  @override
  Widget build(BuildContext context) => Card(
    margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
    color: const Color(0xFFEEF2F7),
    child: Padding(
      padding: const EdgeInsets.all(14),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        _ruleRow(Icons.nfc,       '1. NFC появился',
            'Проверяется белый список. При совпадении — '
            'формируется EGTS-пакет (SRT 16 GPS + SRT 21 State + SRT 202 TagID + SRT 203 Event) '
            'и отправляется на сервер.'),
        const SizedBox(height: 10),
        _ruleRow(Icons.bluetooth, '2. iBeacon обнаружен',
            'Проверяется белый список по UUID + Major + Minor. '
            'При совпадении — формируется и отправляется EGTS-пакет с GPS и LBS.'),
        const SizedBox(height: 10),
        _ruleRow(Icons.wifi,      '3. WiFi точка найдена',
            'Проверяется белый список по SSID и/или BSSID. '
            'При совпадении — формируется и отправляется EGTS-пакет с GPS.'),
      ]),
    ),
  );

  Widget _ruleRow(IconData icon, String title, String desc) => Row(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Icon(icon, size: 20, color: const Color(0xFF1F4E79)),
      const SizedBox(width: 10),
      Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(title, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
        const SizedBox(height: 2),
        Text(desc, style: TextStyle(fontSize: 12, color: Colors.grey.shade700)),
      ])),
    ],
  );
}

// ─── Server settings ──────────────────────────────────────────────────────────

class _ServerSection extends StatefulWidget {
  const _ServerSection();
  @override
  State<_ServerSection> createState() => _ServerSectionState();
}

class _ServerSectionState extends State<_ServerSection> {
  late TextEditingController _urlCtrl, _tokenCtrl, _tidCtrl;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final cfg = context.read<TrackerProvider>().serverConfig;
    _urlCtrl   = TextEditingController(text: cfg.url);
    _tokenCtrl = TextEditingController(text: cfg.token);
    _tidCtrl   = TextEditingController(text: cfg.terminalId.toString());
  }

  @override
  Widget build(BuildContext context) => Card(
    margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
    child: Padding(
      padding: const EdgeInsets.all(14),
      child: Column(children: [
        _field('URL Yandex Cloud Function',
            'https://functions.yandexcloud.net/...', _urlCtrl),
        const SizedBox(height: 10),
        _field('IAM-токен (необязательно)', 't1.xxx...', _tokenCtrl, obscure: true),
        const SizedBox(height: 10),
        _field('Terminal ID', '1', _tidCtrl, numeric: true),
        const SizedBox(height: 12),
        SizedBox(width: double.infinity,
          child: FilledButton(
            style: FilledButton.styleFrom(backgroundColor: const Color(0xFF375623)),
            onPressed: _save,
            child: const Text('Сохранить'),
          ),
        ),
      ]),
    ),
  );

  Widget _field(String label, String hint, TextEditingController ctrl,
      {bool obscure = false, bool numeric = false}) =>
      TextField(
        controller: ctrl,
        obscureText: obscure,
        keyboardType: numeric ? TextInputType.number : TextInputType.url,
        decoration: InputDecoration(
          labelText: label, hintText: hint,
          border: const OutlineInputBorder(), isDense: true,
        ),
        onChanged: (_) {},
      );

  Future<void> _save() async {
    final prov = context.read<TrackerProvider>();
    await prov.updateServerConfig(prov.serverConfig.copyWith(
      url:        _urlCtrl.text.trim(),
      token:      _tokenCtrl.text.trim(),
      terminalId: int.tryParse(_tidCtrl.text) ?? 1,
    ));
    if (mounted) ScaffoldMessenger.of(context)
        .showSnackBar(const SnackBar(content: Text('Настройки сервера сохранены')));
  }

  @override
  void dispose() {
    _urlCtrl.dispose(); _tokenCtrl.dispose(); _tidCtrl.dispose();
    super.dispose();
  }
}

// ─── NFC whitelist ────────────────────────────────────────────────────────────

class _NfcWhitelistSection extends StatelessWidget {
  const _NfcWhitelistSection();
  @override
  Widget build(BuildContext context) =>
      Consumer<TrackerProvider>(builder: (ctx, prov, _) {
        return _WhitelistCard<NfcEntry>(
          items: prov.nfcWhitelist,
          label: (e) => e.toString(),
          sublabel: (_) => '',
          icon: Icons.nfc,
          onDelete: (i) {
            final list = List<NfcEntry>.from(prov.nfcWhitelist)..removeAt(i);
            prov.updateNfcWhitelist(list);
          },
          onAdd: () => _addNfcDialog(ctx, prov),
        );
      });

  Future<void> _addNfcDialog(BuildContext ctx, TrackerProvider prov) async {
    final uid   = TextEditingController();
    final label = TextEditingController();
    final ok = await showDialog<bool>(
      context: ctx,
      builder: (_) => _AddDialog(title: 'Добавить NFC-метку', fields: [
        _DialogField('UID (hex)', 'AA:BB:CC:DD', uid),
        _DialogField('Название', 'Карта №1', label),
      ]),
    );
    if (ok == true && uid.text.isNotEmpty) {
      final list = List<NfcEntry>.from(prov.nfcWhitelist)
        ..add(NfcEntry(uid: uid.text.trim().toUpperCase(),
            label: label.text.trim()));
      await prov.updateNfcWhitelist(list);
    }
  }
}

// ─── Beacon whitelist ─────────────────────────────────────────────────────────

class _BeaconWhitelistSection extends StatelessWidget {
  const _BeaconWhitelistSection();
  @override
  Widget build(BuildContext context) =>
      Consumer<TrackerProvider>(builder: (ctx, prov, _) {
        return _WhitelistCard<BeaconEntry>(
          items: prov.beaconWhitelist,
          label: (e) => e.label.isNotEmpty ? e.label : e.uuid,
          sublabel: (e) => 'Major: ${e.major ?? "*"}  Minor: ${e.minor ?? "*"}',
          icon: Icons.bluetooth,
          onDelete: (i) {
            final list = List<BeaconEntry>.from(prov.beaconWhitelist)..removeAt(i);
            prov.updateBeaconWhitelist(list);
          },
          onAdd: () => _addBeaconDialog(ctx, prov),
        );
      });

  Future<void> _addBeaconDialog(BuildContext ctx, TrackerProvider prov) async {
    final uuid  = TextEditingController();
    final major = TextEditingController();
    final minor = TextEditingController();
    final label = TextEditingController();
    final ok = await showDialog<bool>(context: ctx,
      builder: (_) => _AddDialog(title: 'Добавить iBeacon', fields: [
        _DialogField('UUID', 'XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX', uuid),
        _DialogField('Major (* = любой)', '1', major),
        _DialogField('Minor (* = любой)', '*', minor),
        _DialogField('Название', 'Маяк №1', label),
      ]),
    );
    if (ok == true && uuid.text.isNotEmpty) {
      final list = List<BeaconEntry>.from(prov.beaconWhitelist)
        ..add(BeaconEntry(
          uuid:  uuid.text.trim().toUpperCase(),
          major: major.text == '*' || major.text.isEmpty ? null : int.tryParse(major.text),
          minor: minor.text == '*' || minor.text.isEmpty ? null : int.tryParse(minor.text),
          label: label.text.trim(),
        ));
      await prov.updateBeaconWhitelist(list);
    }
  }
}

// ─── WiFi whitelist ───────────────────────────────────────────────────────────

class _WifiWhitelistSection extends StatelessWidget {
  const _WifiWhitelistSection();
  @override
  Widget build(BuildContext context) =>
      Consumer<TrackerProvider>(builder: (ctx, prov, _) {
        return _WhitelistCard<WifiEntry>(
          items: prov.wifiWhitelist,
          label: (e) => e.label.isNotEmpty ? e.label : (e.ssid ?? e.bssid ?? ''),
          sublabel: (e) => [
            if (e.ssid  != null) 'SSID: ${e.ssid}',
            if (e.bssid != null) 'BSSID: ${e.bssid}',
          ].join('  '),
          icon: Icons.wifi,
          onDelete: (i) {
            final list = List<WifiEntry>.from(prov.wifiWhitelist)..removeAt(i);
            prov.updateWifiWhitelist(list);
          },
          onAdd: () => _addWifiDialog(ctx, prov),
        );
      });

  Future<void> _addWifiDialog(BuildContext ctx, TrackerProvider prov) async {
    final ssid  = TextEditingController();
    final bssid = TextEditingController();
    final label = TextEditingController();
    final ok = await showDialog<bool>(context: ctx,
      builder: (_) => _AddDialog(title: 'Добавить WiFi-сеть', fields: [
        _DialogField('SSID (название сети)', 'Office_WiFi', ssid),
        _DialogField('BSSID / MAC (необязательно)', 'AA:BB:CC:DD:EE:FF', bssid),
        _DialogField('Название', 'Офис', label),
      ]),
    );
    if (ok == true && (ssid.text.isNotEmpty || bssid.text.isNotEmpty)) {
      final list = List<WifiEntry>.from(prov.wifiWhitelist)
        ..add(WifiEntry(
          ssid:  ssid.text.trim().isEmpty  ? null : ssid.text.trim(),
          bssid: bssid.text.trim().isEmpty ? null : bssid.text.trim().toUpperCase(),
          label: label.text.trim(),
        ));
      await prov.updateWifiWhitelist(list);
    }
  }
}

// ─── Reusable whitelist card ──────────────────────────────────────────────────

class _WhitelistCard<T> extends StatelessWidget {
  final List<T> items;
  final String Function(T) label;
  final String Function(T) sublabel;
  final IconData icon;
  final void Function(int) onDelete;
  final VoidCallback onAdd;

  const _WhitelistCard({
    required this.items, required this.label, required this.sublabel,
    required this.icon, required this.onDelete, required this.onAdd,
  });

  @override
  Widget build(BuildContext context) => Card(
    margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
    child: Column(children: [
      if (items.isEmpty)
        const Padding(
          padding: EdgeInsets.all(16),
          child: Text('Список пуст. Добавьте запись.',
              style: TextStyle(color: Colors.grey)),
        ),
      ...List.generate(items.length, (i) {
        final item = items[i];
        return Slidable(
          key: ValueKey(i),
          endActionPane: ActionPane(
            motion: const BehindMotion(),
            children: [
              SlidableAction(
                onPressed: (_) => onDelete(i),
                backgroundColor: Colors.red,
                foregroundColor: Colors.white,
                icon: Icons.delete,
                label: 'Удалить',
              ),
            ],
          ),
          child: ListTile(
            leading: Icon(icon, color: const Color(0xFF1F4E79)),
            title: Text(label(item)),
            subtitle: sublabel(item).isNotEmpty ? Text(sublabel(item)) : null,
            dense: true,
          ),
        );
      }),
      Padding(
        padding: const EdgeInsets.all(8),
        child: OutlinedButton.icon(
          onPressed: onAdd,
          icon: const Icon(Icons.add),
          label: const Text('Добавить'),
          style: OutlinedButton.styleFrom(foregroundColor: const Color(0xFF1F4E79)),
        ),
      ),
    ]),
  );
}

// ─── Add entry dialog ─────────────────────────────────────────────────────────

class _DialogField {
  final String label, hint;
  final TextEditingController ctrl;
  const _DialogField(this.label, this.hint, this.ctrl);
}

class _AddDialog extends StatelessWidget {
  final String title;
  final List<_DialogField> fields;
  const _AddDialog({required this.title, required this.fields});

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: Text(title),
    content: SingleChildScrollView(
      child: Column(mainAxisSize: MainAxisSize.min,
        children: fields.map((f) => Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: TextField(
            controller: f.ctrl,
            decoration: InputDecoration(
              labelText: f.label, hintText: f.hint,
              border: const OutlineInputBorder(), isDense: true,
            ),
          ),
        )).toList(),
      ),
    ),
    actions: [
      TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Отмена')),
      FilledButton(
        onPressed: () => Navigator.pop(context, true),
        style: FilledButton.styleFrom(backgroundColor: const Color(0xFF1F4E79)),
        child: const Text('Добавить'),
      ),
    ],
  );
}
