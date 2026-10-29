"""Machine and bearing definitions for the simulated plant."""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class BearingGeometry:
    balls: int
    ball_diameter_mm: float
    pitch_diameter_mm: float
    contact_angle_deg: float = 0.0

    def _ratio(self) -> float:
        angle = math.radians(self.contact_angle_deg)
        return self.ball_diameter_mm / self.pitch_diameter_mm * math.cos(angle)

    def bpfo_order(self) -> float:
        """Ball pass frequency, outer race, as a multiple of shaft speed."""
        return self.balls / 2 * (1 - self._ratio())

    def bpfi_order(self) -> float:
        """Ball pass frequency, inner race, as a multiple of shaft speed."""
        return self.balls / 2 * (1 + self._ratio())


@dataclass(frozen=True)
class MachineSpec:
    machine_id: str
    equipment: str
    mac: str
    shaft_hz: float
    bearing: BearingGeometry
    base_1x_g: float
    noise_g: float
    base_temp_c: float
    resonance_hz: float

    def bpfo_hz(self) -> float:
        return self.bearing.bpfo_order() * self.shaft_hz


PUMP_BEARING = BearingGeometry(balls=9, ball_diameter_mm=12.7, pitch_diameter_mm=50.8)
FAN_BEARING = BearingGeometry(balls=8, ball_diameter_mm=10.0, pitch_diameter_mm=50.0)
PUMP_EQUIPMENT = "RP-1 centrifugal pump"
FAN_EQUIPMENT = "RF-1 centrifugal fan"


def _pump(number: int, base_1x_g: float, noise_g: float, base_temp_c: float) -> MachineSpec:
    return MachineSpec(
        machine_id=f"pump-{number}",
        equipment=PUMP_EQUIPMENT,
        mac=f"E0:00:00:00:01:{number:02X}",
        shaft_hz=24.75,
        bearing=PUMP_BEARING,
        base_1x_g=base_1x_g,
        noise_g=noise_g,
        base_temp_c=base_temp_c,
        resonance_hz=450.0,
    )


def _fan(number: int, base_1x_g: float, noise_g: float, base_temp_c: float) -> MachineSpec:
    return MachineSpec(
        machine_id=f"fan-{number}",
        equipment=FAN_EQUIPMENT,
        mac=f"E0:00:00:00:02:{number:02X}",
        shaft_hz=16.5,
        bearing=FAN_BEARING,
        base_1x_g=base_1x_g,
        noise_g=noise_g,
        base_temp_c=base_temp_c,
        resonance_hz=380.0,
    )


FLEET: dict[str, MachineSpec] = {
    spec.machine_id: spec
    for spec in (
        _pump(1, 0.05, 0.020, 41.0),
        _pump(2, 0.06, 0.022, 43.0),
        _pump(3, 0.05, 0.020, 42.0),
        _pump(4, 0.045, 0.018, 44.0),
        _fan(1, 0.04, 0.015, 38.0),
        _fan(2, 0.035, 0.016, 39.0),
    )
}
