import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:egts_tracker/models/models.dart';

final _timeFmt = DateFormat('HH:mm:ss');

// ─── Карточка NFC-события ──────────────────────────────────────────────────

class NfcEventCard extends StatelessWidget {
  final NfcEvent event;
  final bool inWhitelist;

  const NfcEventCard({super.key, required this.event, required this.inWhitelist});

  @override
  Widget build(BuildContext context) => _EventCard(
    color: inWhitelist ? const Color(0xFF1B5E20) : Colors.grey.shade700,
    icon: Icons.nfc,
    title: event.uid,
    subtitle: event.techList.join(', '),
    time: _timeFmt.format(event.ts),
    badge: inWhitelist ? '✓ В списке' : null,
    badgeColor: const Color(0xFF4CAF50),
  );
}

// ─── Карточка iBeacon-события ──────────────────────────────────────────────

class BeaconEventCard extends StatelessWidget {
  final BeaconEvent event;
  final bool inWhitelist;

  const BeaconEventCard({super.key, required this.event, required this.inWhitelist});

  @override
  Widget build(BuildContext context) => _EventCard(
    color: inWhitelist ? const Color(0xFF0D47A1) : Colors.blueGrey.shade700,
    icon: Icons.bluetooth,
    title: '${event.major} / ${event.minor}',
    subtitle: event.uuid,
    time: _timeFmt.format(event.ts),
    badge: inWhitelist ? '✓ В списке' : null,
    badgeColor: const Color(0xFF2196F3),
    trailing: '${event.rssi} дБм  •  ${event.distance.toStringAsFixed(1)} м',
  );
}

// ─── Карточка WiFi-события ──────────────────────────────────────────────────

class WifiEventCard extends StatelessWidget {
  final WifiEvent event;
  final bool inWhitelist;

  const WifiEventCard({super.key, required this.event, required this.inWhitelist});

  @override
  Widget build(BuildContext context) => _EventCard(
    color: inWhitelist ? const Color(0xFF4A148C) : Colors.purple.shade800,
    icon: Icons.wifi,
    title: event.ssid.isEmpty ? '(скрытая сеть)' : event.ssid,
    subtitle: '${event.bssid}  •  ch ${event.channel}',
    time: _timeFmt.format(event.ts),
    badge: inWhitelist ? '✓ В списке' : null,
    badgeColor: const Color(0xFF9C27B0),
    trailing: '${event.rssi} дБм',
  );
}

// ─── Карточка LBS ──────────────────────────────────────────────────────────

class LbsEventCard extends StatelessWidget {
  final LbsEvent event;
  const LbsEventCard({super.key, required this.event});

  @override
  Widget build(BuildContext context) => _EventCard(
    color: const Color(0xFF880E4F),
    icon: Icons.cell_tower,
    title: 'MCC ${event.mcc}  MNC ${event.mnc}',
    subtitle: 'LAC ${event.lac}  CID ${event.cellId}',
    time: _timeFmt.format(event.ts),
    trailing: '${event.rssi} дБм',
  );
}

// ─── Базовая карточка ──────────────────────────────────────────────────────

class _EventCard extends StatelessWidget {
  final Color color;
  final IconData icon;
  final String title, subtitle, time;
  final String? badge, trailing;
  final Color? badgeColor;

  const _EventCard({
    required this.color, required this.icon,
    required this.title, required this.subtitle, required this.time,
    this.badge, this.badgeColor, this.trailing,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      child: Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(10),
          border: Border(left: BorderSide(color: color, width: 4)),
        ),
        padding: const EdgeInsets.all(12),
        child: Row(children: [
          Icon(icon, color: color, size: 28),
          const SizedBox(width: 12),
          Expanded(child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(children: [
                Expanded(child: Text(title,
                    style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15))),
                Text(time, style: TextStyle(color: Colors.grey.shade600, fontSize: 12)),
              ]),
              const SizedBox(height: 2),
              Text(subtitle,
                  style: TextStyle(color: Colors.grey.shade600, fontSize: 12),
                  overflow: TextOverflow.ellipsis),
              if (badge != null || trailing != null) ...[
                const SizedBox(height: 6),
                Row(children: [
                  if (badge != null) Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                    decoration: BoxDecoration(
                      color: badgeColor ?? color,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(badge!,
                        style: const TextStyle(color: Colors.white, fontSize: 11)),
                  ),
                  if (badge != null && trailing != null) const SizedBox(width: 8),
                  if (trailing != null) Text(trailing!,
                      style: TextStyle(color: Colors.grey.shade700, fontSize: 12)),
                ]),
              ],
            ],
          )),
        ]),
      ),
    );
  }
}
