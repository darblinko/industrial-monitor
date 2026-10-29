"""RAWv2 (data format 5) tests. Vectors are the published examples at docs.ruuvi.com."""

import pytest

from industrial_monitor.ruuvi import RuuviReading, decode_rawv2, encode_rawv2

VALID = bytes.fromhex("0512FC5394C37C0004FFFC040CAC364200CDCBB8334C884F")
MAXIMUM = bytes.fromhex("057FFFFFFEFFFE7FFF7FFF7FFFFFDEFEFFFECBB8334C884F")
MINIMUM = bytes.fromhex("058001000000008001800180010000000000CBB8334C884F")
INVALID = bytes.fromhex("058000FFFFFFFF800080008000FFFFFFFFFFFFFFFFFFFFFF")


def test_decodes_published_valid_vector():
    reading = decode_rawv2(VALID)
    assert reading.temperature_c == pytest.approx(24.3)
    assert reading.humidity_pct == pytest.approx(53.49)
    assert reading.pressure_pa == 100044
    assert (reading.accel_x_mg, reading.accel_y_mg, reading.accel_z_mg) == (4, -4, 1036)
    assert reading.battery_mv == 2977
    assert reading.tx_power_dbm == 4
    assert reading.movement_counter == 66
    assert reading.sequence == 205
    assert reading.mac == "CB:B8:33:4C:88:4F"


def test_decodes_published_maximum_vector():
    reading = decode_rawv2(MAXIMUM)
    assert reading.temperature_c == pytest.approx(163.835)
    assert reading.humidity_pct == pytest.approx(163.835)
    assert reading.pressure_pa == 115534
    assert reading.accel_x_mg == 32767
    assert reading.battery_mv == 3646
    assert reading.tx_power_dbm == 20
    assert reading.movement_counter == 254
    assert reading.sequence == 65534


def test_decodes_published_minimum_vector():
    reading = decode_rawv2(MINIMUM)
    assert reading.temperature_c == pytest.approx(-163.835)
    assert reading.humidity_pct == 0.0
    assert reading.pressure_pa == 50000
    assert reading.accel_z_mg == -32767
    assert reading.battery_mv == 1600
    assert reading.tx_power_dbm == -40
    assert reading.sequence == 0


def test_invalid_markers_decode_to_none():
    reading = decode_rawv2(INVALID)
    fields = [
        reading.temperature_c,
        reading.humidity_pct,
        reading.pressure_pa,
        reading.accel_x_mg,
        reading.accel_y_mg,
        reading.accel_z_mg,
        reading.battery_mv,
        reading.tx_power_dbm,
        reading.movement_counter,
        reading.sequence,
        reading.mac,
    ]
    assert fields == [None] * len(fields)


@pytest.mark.parametrize("payload", [VALID[:23], VALID + b"\x00", b"\x03" + VALID[1:]])
def test_rejects_wrong_length_or_format(payload):
    with pytest.raises(ValueError):
        decode_rawv2(payload)


def test_encode_reproduces_published_vector():
    reading = RuuviReading(
        temperature_c=24.3,
        humidity_pct=53.49,
        pressure_pa=100044,
        accel_x_mg=4,
        accel_y_mg=-4,
        accel_z_mg=1036,
        battery_mv=2977,
        tx_power_dbm=4,
        movement_counter=66,
        sequence=205,
        mac="CB:B8:33:4C:88:4F",
    )
    assert encode_rawv2(reading) == VALID


def test_encode_clamps_out_of_range_values():
    reading = RuuviReading(
        temperature_c=500.0,
        humidity_pct=-3.0,
        pressure_pa=20000,
        accel_x_mg=40000,
        accel_y_mg=-40000,
        accel_z_mg=0,
        battery_mv=9000,
        tx_power_dbm=99,
        movement_counter=300,
        sequence=70000,
        mac="00:11:22:33:44:55",
    )
    decoded = decode_rawv2(encode_rawv2(reading))
    assert decoded.temperature_c == pytest.approx(163.835)
    assert decoded.humidity_pct == 0.0
    assert decoded.pressure_pa == 50000
    assert (decoded.accel_x_mg, decoded.accel_y_mg) == (32767, -32767)
    assert decoded.battery_mv == 3646
    assert decoded.tx_power_dbm == 20
    assert decoded.movement_counter == 254
    assert decoded.sequence == 70000 % 65535
