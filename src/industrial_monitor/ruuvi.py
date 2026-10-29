"""Ruuvi RAWv2 (data format 5) payload encoding and decoding.

Layout from the Ruuvi data format 5 specification (docs.ruuvi.com): 24 bytes, big-endian.
Each field has a reserved "not available" value, decoded here as None.
"""

import struct
from collections.abc import Callable
from dataclasses import dataclass

DATA_FORMAT = 5
PAYLOAD_LENGTH = 24
MANUFACTURER_ID = 0x0499

_LAYOUT = struct.Struct(">BhHHhhhHBH6s")
_INVALID_INT16 = -32768
_INVALID_UINT16 = 0xFFFF
_INVALID_VOLTAGE = 2047
_INVALID_TX = 31
_INVALID_MOVEMENT = 0xFF
_INVALID_MAC = b"\xff" * 6


@dataclass(frozen=True)
class RuuviReading:
    temperature_c: float | None
    humidity_pct: float | None
    pressure_pa: int | None
    accel_x_mg: int | None
    accel_y_mg: int | None
    accel_z_mg: int | None
    battery_mv: int | None
    tx_power_dbm: int | None
    movement_counter: int | None
    sequence: int | None
    mac: str | None


def _none_if(value: int, invalid: int) -> int | None:
    return None if value == invalid else value


def _format_mac(raw: bytes) -> str | None:
    return None if raw == _INVALID_MAC else ":".join(f"{byte:02X}" for byte in raw)


def decode_rawv2(payload: bytes) -> RuuviReading:
    if len(payload) != PAYLOAD_LENGTH:
        raise ValueError(f"RAWv2 payload must be {PAYLOAD_LENGTH} bytes, got {len(payload)}")
    if payload[0] != DATA_FORMAT:
        raise ValueError(f"expected data format {DATA_FORMAT}, got {payload[0]}")
    (_, temp, humidity, pressure, ax, ay, az, power, movement, sequence, mac) = _LAYOUT.unpack(
        payload
    )
    voltage_raw, tx_raw = power >> 5, power & 0x1F
    raw_temp = _none_if(temp, _INVALID_INT16)
    raw_humidity = _none_if(humidity, _INVALID_UINT16)
    raw_pressure = _none_if(pressure, _INVALID_UINT16)
    raw_voltage = _none_if(voltage_raw, _INVALID_VOLTAGE)
    raw_tx = _none_if(tx_raw, _INVALID_TX)
    return RuuviReading(
        temperature_c=None if raw_temp is None else round(raw_temp * 0.005, 3),
        humidity_pct=None if raw_humidity is None else round(raw_humidity * 0.0025, 4),
        pressure_pa=None if raw_pressure is None else raw_pressure + 50000,
        accel_x_mg=_none_if(ax, _INVALID_INT16),
        accel_y_mg=_none_if(ay, _INVALID_INT16),
        accel_z_mg=_none_if(az, _INVALID_INT16),
        battery_mv=None if raw_voltage is None else raw_voltage + 1600,
        tx_power_dbm=None if raw_tx is None else raw_tx * 2 - 40,
        movement_counter=_none_if(movement, _INVALID_MOVEMENT),
        sequence=_none_if(sequence, _INVALID_UINT16),
        mac=_format_mac(mac),
    )


def _clamp(value: float, low: int, high: int) -> int:
    return int(min(max(round(value), low), high))


def _parse_mac(mac: str | None) -> bytes:
    if mac is None:
        return _INVALID_MAC
    raw = bytes.fromhex(mac.replace(":", ""))
    if len(raw) != 6:
        raise ValueError(f"MAC address must have 6 bytes: {mac!r}")
    return raw


def _or(value: float | None, invalid: int, encode: Callable[[float], int]) -> int:
    return invalid if value is None else encode(value)


def encode_rawv2(reading: RuuviReading) -> bytes:
    """Encode a reading, clamping each field to its representable range."""
    temp = _or(reading.temperature_c, _INVALID_INT16, lambda v: _clamp(v / 0.005, -32767, 32767))
    humidity = _or(reading.humidity_pct, _INVALID_UINT16, lambda v: _clamp(v / 0.0025, 0, 65534))
    pressure = _or(reading.pressure_pa, _INVALID_UINT16, lambda v: _clamp(v - 50000, 0, 65534))
    accel = [
        _or(value, _INVALID_INT16, lambda v: _clamp(v, -32767, 32767))
        for value in (reading.accel_x_mg, reading.accel_y_mg, reading.accel_z_mg)
    ]
    voltage = _or(reading.battery_mv, _INVALID_VOLTAGE, lambda v: _clamp(v - 1600, 0, 2046))
    tx = _or(reading.tx_power_dbm, _INVALID_TX, lambda v: _clamp((v + 40) / 2, 0, 30))
    movement = _or(reading.movement_counter, _INVALID_MOVEMENT, lambda v: _clamp(v, 0, 254))
    sequence = _or(reading.sequence, _INVALID_UINT16, lambda v: int(v) % 65535)
    return _LAYOUT.pack(
        DATA_FORMAT,
        temp,
        humidity,
        pressure,
        *accel,
        (voltage << 5) | tx,
        movement,
        sequence,
        _parse_mac(reading.mac),
    )
