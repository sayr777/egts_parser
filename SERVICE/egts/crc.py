"""CRC-8 и CRC-16 (ГОСТ Р 54619-2011)."""

_CRC8_TABLE: list[int] = []
_CRC16_TABLE: list[int] = []


def _build_crc8_table() -> None:
    for i in range(256):
        crc = i
        for _ in range(8):
            crc = ((crc << 1) ^ 0x31) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
        _CRC8_TABLE.append(crc)


def _build_crc16_table() -> None:
    for i in range(256):
        crc = i << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
        _CRC16_TABLE.append(crc)


_build_crc8_table()
_build_crc16_table()


def crc8(data: bytes | bytearray) -> int:
    crc = 0xFF
    for b in data:
        crc = _CRC8_TABLE[(crc ^ b) & 0xFF]
    return crc


def crc16(data: bytes | bytearray) -> int:
    crc = 0xFFFF
    for b in data:
        crc = ((crc << 8) ^ _CRC16_TABLE[((crc >> 8) ^ b) & 0xFF]) & 0xFFFF
    return crc
