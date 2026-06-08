/// CRC-8 (полином 0x31) и CRC-16/CCITT (полином 0x1021)
/// ГОСТ Р 54619-2011
library egts_crc;

final _crc8Table = _buildCrc8Table();
final _crc16Table = _buildCrc16Table();

List<int> _buildCrc8Table() {
  final t = List<int>.filled(256, 0);
  for (var i = 0; i < 256; i++) {
    var crc = i;
    for (var j = 0; j < 8; j++) {
      crc = (crc & 0x80) != 0 ? ((crc << 1) ^ 0x31) & 0xFF : (crc << 1) & 0xFF;
    }
    t[i] = crc;
  }
  return t;
}

List<int> _buildCrc16Table() {
  final t = List<int>.filled(256, 0);
  for (var i = 0; i < 256; i++) {
    var crc = i << 8;
    for (var j = 0; j < 8; j++) {
      crc = (crc & 0x8000) != 0 ? ((crc << 1) ^ 0x1021) & 0xFFFF : (crc << 1) & 0xFFFF;
    }
    t[i] = crc;
  }
  return t;
}

int crc8(List<int> data, {int len = -1}) {
  final n = len < 0 ? data.length : len;
  var crc = 0xFF;
  for (var i = 0; i < n; i++) {
    crc = _crc8Table[(crc ^ (data[i] & 0xFF)) & 0xFF];
  }
  return crc;
}

int crc16(List<int> data, {int offset = 0, int len = -1}) {
  final n = len < 0 ? data.length - offset : len;
  var crc = 0xFFFF;
  for (var i = offset; i < offset + n; i++) {
    crc = ((crc << 8) ^ _crc16Table[((crc >> 8) ^ (data[i] & 0xFF)) & 0xFF]) & 0xFFFF;
  }
  return crc;
}
