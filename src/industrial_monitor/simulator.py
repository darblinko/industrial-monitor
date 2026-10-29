"""Simulated plant: labeled sensor windows and their MQTT messages."""

import zlib
from collections.abc import Iterator
from dataclasses import dataclass, replace

import numpy as np

from industrial_monitor.burst import VibrationBurst, encode_burst
from industrial_monitor.machines import FLEET, MachineSpec
from industrial_monitor.ruuvi import RuuviReading, encode_rawv2
from industrial_monitor.signals import (
    FAULTS,
    SAMPLE_RATE_HZ,
    Condition,
    housing_temperature,
    vibration_window,
)

HEALTHY = Condition("none", 0.0)


@dataclass(frozen=True)
class FaultPlan:
    fault: str
    onset_window: int
    ramp_windows: int
    start_severity: float = 0.05

    def condition(self, index: int) -> Condition:
        if self.fault == "none" or index < self.onset_window:
            return HEALTHY
        progress = min((index - self.onset_window) / max(self.ramp_windows - 1, 1), 1.0)
        return Condition(self.fault, self.start_severity + (1 - self.start_severity) * progress)


@dataclass(frozen=True)
class SimulatedWindow:
    machine_id: str
    index: int
    condition: Condition
    samples_g: np.ndarray
    temperature_c: float
    humidity_pct: float
    pressure_pa: int


def machine_rng(spec: MachineSpec, seed: int) -> np.random.Generator:
    return np.random.default_rng([seed, zlib.crc32(spec.machine_id.encode())])


def simulate_machine(
    spec: MachineSpec, plan: FaultPlan, windows: int, seed: int
) -> Iterator[SimulatedWindow]:
    rng = machine_rng(spec, seed)
    for index in range(windows):
        condition = plan.condition(index)
        yield SimulatedWindow(
            machine_id=spec.machine_id,
            index=index,
            condition=condition,
            samples_g=vibration_window(spec, condition, rng),
            temperature_c=housing_temperature(spec, condition, rng),
            humidity_pct=float(np.clip(45.0 + rng.normal(0, 2.0), 0, 100)),
            pressure_pa=int(101325 + rng.normal(0, 150)),
        )


def to_messages(window: SimulatedWindow, spec: MachineSpec, site: str) -> list[tuple[str, bytes]]:
    """One RAWv2 status payload and one vibration burst per window."""
    status = RuuviReading(
        temperature_c=window.temperature_c,
        humidity_pct=window.humidity_pct,
        pressure_pa=window.pressure_pa,
        accel_x_mg=round(float(window.samples_g[-1]) * 1000),
        accel_y_mg=0,
        accel_z_mg=1000,
        battery_mv=2950,
        tx_power_dbm=4,
        movement_counter=0,
        sequence=window.index,
        mac=spec.mac,
    )
    burst = VibrationBurst.from_g(spec.mac, window.index, SAMPLE_RATE_HZ, window.samples_g)
    prefix = f"plant/{site}/{spec.machine_id}"
    return [(f"{prefix}/rawv2", encode_rawv2(status)), (f"{prefix}/vibration", encode_burst(burst))]


def _variant(base: MachineSpec, number: int, rng: np.random.Generator) -> MachineSpec:
    return replace(
        base,
        machine_id=f"unit-{number:02d}",
        mac=f"E0:00:00:00:0F:{number:02X}",
        base_1x_g=base.base_1x_g * rng.uniform(0.7, 1.3),
        noise_g=base.noise_g * rng.uniform(0.8, 1.25),
        base_temp_c=float(rng.uniform(36.0, 46.0)),
    )


def evaluation_plant(
    machines_per_fault: int, baseline_windows: int, seed: int, test_windows: int = 200
) -> list[tuple[MachineSpec, FaultPlan]]:
    """Varied pumps and fans, each fault class on the same number of machines."""
    rng = np.random.default_rng(seed)
    templates = (FLEET["pump-1"], FLEET["fan-1"])
    plant = []
    for number in range(1, len(FAULTS) * machines_per_fault + 1):
        fault = FAULTS[(number - 1) % len(FAULTS)]
        spec = _variant(templates[number % 2], number, rng)
        onset = int(rng.integers(baseline_windows + 20, baseline_windows + 81))
        ramp = baseline_windows + test_windows - onset
        plant.append((spec, FaultPlan(fault, onset, ramp)))
    return plant
