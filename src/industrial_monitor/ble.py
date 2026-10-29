"""Optional BLE scanner for real Ruuvi tags. Requires the `ble` extra (bleak).

Ruuvi tags broadcast RAWv2 as manufacturer-specific data under company ID 0x0499. Each
advertisement carries one acceleration sample, so this path feeds the status topic and the
temperature channel only. Vibration bursts need a sensor that streams raw samples.
"""

import asyncio
import logging
from collections.abc import Mapping

from industrial_monitor.bus import Bus
from industrial_monitor.ruuvi import DATA_FORMAT, MANUFACTURER_ID, PAYLOAD_LENGTH, decode_rawv2

logger = logging.getLogger(__name__)


def rawv2_from_advertisement(manufacturer_data: Mapping[int, bytes]) -> bytes | None:
    payload = manufacturer_data.get(MANUFACTURER_ID)
    if payload is None or len(payload) != PAYLOAD_LENGTH or payload[0] != DATA_FORMAT:
        return None
    return bytes(payload)


def machine_for_tag(mac: str, names: Mapping[str, str]) -> str:
    return names.get(mac, "tag-" + mac.replace(":", "").lower())


async def scan(bus: Bus, site: str, duration_s: float, names: Mapping[str, str]) -> int:
    """Publish every RAWv2 advertisement heard for duration_s. Returns the message count."""
    from bleak import BleakScanner

    published = 0

    def on_advertisement(device, advertisement) -> None:
        nonlocal published
        payload = rawv2_from_advertisement(advertisement.manufacturer_data)
        if payload is None:
            return
        mac = decode_rawv2(payload).mac or device.address
        bus.publish(f"plant/{site}/{machine_for_tag(mac, names)}/rawv2", payload)
        published += 1

    async with BleakScanner(detection_callback=on_advertisement):
        await asyncio.sleep(duration_s)
    logger.info("published %d RAWv2 advertisements", published)
    return published
