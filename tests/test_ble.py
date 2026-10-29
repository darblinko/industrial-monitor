from industrial_monitor.ble import machine_for_tag, rawv2_from_advertisement
from industrial_monitor.ruuvi import MANUFACTURER_ID, RuuviReading, decode_rawv2, encode_rawv2

TAG_MAC = "C1:00:00:00:00:2A"
READING = RuuviReading(
    temperature_c=21.5,
    humidity_pct=40.0,
    pressure_pa=100500,
    accel_x_mg=4,
    accel_y_mg=-8,
    accel_z_mg=1000,
    battery_mv=2900,
    tx_power_dbm=4,
    movement_counter=3,
    sequence=17,
    mac=TAG_MAC,
)


def test_rawv2_is_taken_from_ruuvi_manufacturer_data():
    payload = encode_rawv2(READING)
    assert rawv2_from_advertisement({MANUFACTURER_ID: payload}) == payload
    assert decode_rawv2(rawv2_from_advertisement({MANUFACTURER_ID: payload})).sequence == 17


def test_other_manufacturers_and_formats_are_ignored():
    payload = encode_rawv2(READING)
    assert rawv2_from_advertisement({0x004C: payload}) is None
    assert rawv2_from_advertisement({MANUFACTURER_ID: b"\x03" + payload[1:]}) is None
    assert rawv2_from_advertisement({MANUFACTURER_ID: payload[:10]}) is None


def test_tags_map_to_machines_or_fall_back_to_their_mac():
    names = {TAG_MAC: "pump-3"}
    assert machine_for_tag(TAG_MAC, names) == "pump-3"
    assert machine_for_tag("C1:00:00:00:00:2B", names) == "tag-c1000000002b"
