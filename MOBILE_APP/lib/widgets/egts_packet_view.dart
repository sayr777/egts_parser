import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:intl/intl.dart';
import 'package:egts_tracker/models/models.dart';

final _timeFmt = DateFormat('HH:mm:ss.SSS');

final _triggerIcons = <String, IconData>{
  'nfc': Icons.nfc,
  'beacon': Icons.bluetooth,
  'wifi': Icons.wifi,
};

final _triggerColors = <String, Color>{
  'nfc':    Color(0xFF1B5E20),
  'beacon': Color(0xFF0D47A1),
  'wifi':   Color(0xFF4A148C),
};

/// Карточка отображения EGTS-пакета с разворачиваемой структурой.
class EgtsPacketCard extends StatefulWidget {
  final EgtsPacketInfo packet;
  const EgtsPacketCard({super.key, required this.packet});

  @override
  State<EgtsPacketCard> createState() => _EgtsPacketCardState();
}

class _EgtsPacketCardState extends State<EgtsPacketCard> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    final p     = widget.packet;
    final color = _triggerColors[p.triggerType] ?? Colors.grey.shade700;
    final icon  = _triggerIcons[p.triggerType]  ?? Icons.data_object;

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      child: Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(10),
          border: Border(left: BorderSide(color: color, width: 4)),
        ),
        child: Column(children: [
          // ── Header row ──────────────────────────────────────────────────
          InkWell(
            borderRadius: const BorderRadius.only(
              topLeft: Radius.circular(10), topRight: Radius.circular(10)),
            onTap: () => setState(() => _expanded = !_expanded),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Row(children: [
                Icon(icon, color: color, size: 24),
                const SizedBox(width: 10),
                Expanded(child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(children: [
                      Text(_triggerLabel(p.triggerType),
                          style: TextStyle(color: color,
                              fontWeight: FontWeight.bold, fontSize: 13)),
                      const SizedBox(width: 6),
                      Expanded(child: Text(p.triggerId,
                          style: const TextStyle(fontSize: 13),
                          overflow: TextOverflow.ellipsis)),
                    ]),
                    const SizedBox(height: 3),
                    Row(children: [
                      Text('${p.bytes.length} байт',
                          style: TextStyle(fontSize: 11, color: Colors.grey.shade600)),
                      const SizedBox(width: 8),
                      Text(_timeFmt.format(p.ts),
                          style: TextStyle(fontSize: 11, color: Colors.grey.shade600)),
                      const Spacer(),
                      _statusBadge(p),
                    ]),
                  ],
                )),
                const SizedBox(width: 6),
                Icon(_expanded ? Icons.expand_less : Icons.expand_more,
                    color: Colors.grey.shade500),
              ]),
            ),
          ),

          // ── HEX preview (всегда видна) ──────────────────────────────────
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            child: _HexLine(hex: p.hexStr, onCopy: () => _copy(context, p.hexStr)),
          ),

          // ── Expanded structure ──────────────────────────────────────────
          if (_expanded) ...[
            const Divider(height: 1),
            Padding(
              padding: const EdgeInsets.all(12),
              child: _PacketStructure(decoded: p.decoded),
            ),
          ],
          const SizedBox(height: 4),
        ]),
      ),
    );
  }

  String _triggerLabel(String t) =>
      {'nfc': 'NFC', 'beacon': 'iBeacon', 'wifi': 'WiFi'}[t] ?? t.toUpperCase();

  Widget _statusBadge(EgtsPacketInfo p) {
    if (p.sent) {
      return const _Badge('Отправлен', Colors.green);
    } else if (p.sendError != null) {
      return _Badge('Ошибка', Colors.red, tooltip: p.sendError);
    }
    return const _Badge('Формируется...', Colors.orange);
  }

  void _copy(BuildContext ctx, String text) {
    Clipboard.setData(ClipboardData(text: text));
    ScaffoldMessenger.of(ctx)
        .showSnackBar(const SnackBar(content: Text('HEX скопирован')));
  }
}

class _Badge extends StatelessWidget {
  final String label;
  final Color color;
  final String? tooltip;
  const _Badge(this.label, this.color, {this.tooltip});

  @override
  Widget build(BuildContext context) {
    final chip = Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        border: Border.all(color: color.withValues(alpha: 0.5)),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(label,
          style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.bold)),
    );
    return tooltip != null ? Tooltip(message: tooltip!, child: chip) : chip;
  }
}

class _HexLine extends StatelessWidget {
  final String hex;
  final VoidCallback onCopy;
  const _HexLine({required this.hex, required this.onCopy});

  @override
  Widget build(BuildContext context) {
    final preview = hex.length > 80 ? '${hex.substring(0, 80)}…' : hex;
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: const Color(0xFFDEEAF1),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Row(children: [
        Expanded(child: Text(preview,
            style: const TextStyle(
                fontFamily: 'monospace', fontSize: 11, color: Color(0xFF1F4E79)))),
        IconButton(
          icon: const Icon(Icons.copy, size: 16),
          color: const Color(0xFF1F4E79),
          onPressed: onCopy,
          padding: EdgeInsets.zero,
          constraints: const BoxConstraints(),
        ),
      ]),
    );
  }
}

class _PacketStructure extends StatelessWidget {
  final Map<String, dynamic> decoded;
  const _PacketStructure({required this.decoded});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _section('HEADER', [
          _row('PT',     decoded['PT'] ?? ''),
          _row('FDL',    decoded['FDL'] ?? ''),
          _row('PID',    ''),
          _row('HCS',    decoded['HCS'] ?? '',
              ok: decoded['HCS_valid'] == true),
          _row('CRC16',  '',
              ok: decoded['CRC16_valid'] == true),
        ]),
        if (decoded['SDR'] is List)
          ...(decoded['SDR'] as List).map((sdr) => _sdrWidget(sdr as Map)),
      ],
    );
  }

  Widget _section(String title, List<Widget> rows) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Text(title,
            style: const TextStyle(fontWeight: FontWeight.bold,
                color: Color(0xFF1F4E79), fontSize: 13)),
      ),
      ...rows,
    ],
  );

  Widget _sdrWidget(Map sdr) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Text('SDR  RN=${sdr['RN']}  ${sdr['SST']}',
            style: const TextStyle(fontWeight: FontWeight.bold,
                color: Color(0xFF375623), fontSize: 12)),
      ),
      if (sdr['subrecords'] is List)
        ...(sdr['subrecords'] as List).map((sr) => _subrecordWidget(sr as Map)),
    ],
  );

  Widget _subrecordWidget(Map sr) {
    final fields = sr['fields'] as Map? ?? {};
    return Container(
      margin: const EdgeInsets.only(left: 8, bottom: 6),
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: Colors.grey.shade50,
        border: Border(left: BorderSide(color: Colors.grey.shade300, width: 2)),
        borderRadius: const BorderRadius.only(
          topRight: Radius.circular(6), bottomRight: Radius.circular(6)),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('SRT=${sr['SRT']}  ${sr['name']}  (${sr['SRL']} байт)',
            style: const TextStyle(fontWeight: FontWeight.w600,
                fontSize: 12, color: Color(0xFF6A1B9A))),
        const SizedBox(height: 4),
        Text(sr['hex'] as String? ?? '',
            style: const TextStyle(fontFamily: 'monospace', fontSize: 10,
                color: Color(0xFF455A64))),
        if (fields.isNotEmpty) ...[
          const SizedBox(height: 4),
          ...fields.entries.map((e) => _row(e.key.toString(), e.value)),
        ],
      ]),
    );
  }

  Widget _row(String key, dynamic value, {bool? ok}) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 1),
    child: Row(children: [
      SizedBox(width: 90,
          child: Text(key, style: TextStyle(color: Colors.grey.shade600, fontSize: 12))),
      Expanded(child: Text(value.toString(),
          style: const TextStyle(fontSize: 12, fontFamily: 'monospace'))),
      if (ok != null) Icon(ok ? Icons.check_circle : Icons.cancel,
          size: 14, color: ok ? Colors.green : Colors.red),
    ]),
  );
}
