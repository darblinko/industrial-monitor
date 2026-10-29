"""Synthetic sensor signals for healthy and faulty machines.

The models are deliberately simple and documented so the detector's results can be
interpreted:
- healthy: 1x and 2x running-speed lines with load-dependent amplitude, broadband noise, and
  occasional single process transients (a source of false alarms)
- imbalance: the 1x amplitude grows by a factor of (1 + 3 x severity)
- bearing_wear: an outer-race impact train at BPFO, each impact ringing the housing resonance
- temperature_drift: housing temperature rises by 15 C x severity
"""

from dataclasses import dataclass

import numpy as np

from industrial_monitor.machines import MachineSpec

FAULTS = ("none", "imbalance", "bearing_wear", "temperature_drift")
SAMPLE_RATE_HZ = 1344
WINDOW_SAMPLES = 1024
TRANSIENT_PROBABILITY = 0.03
MAX_TEMPERATURE_RISE_C = 15.0
TEMPERATURE_NOISE_C = 0.3


@dataclass(frozen=True)
class Condition:
    fault: str
    severity: float

    def __post_init__(self) -> None:
        if self.fault not in FAULTS:
            raise ValueError(f"unknown fault {self.fault!r}; expected one of {FAULTS}")
        if not 0.0 <= self.severity <= 1.0:
            raise ValueError(f"severity must be in [0, 1], got {self.severity}")


def _ringing_impacts(
    times: np.ndarray, impact_times: np.ndarray, amplitudes: np.ndarray, resonance_hz: float
) -> np.ndarray:
    decay_s = 0.002
    signal = np.zeros_like(times)
    for start, amplitude in zip(impact_times, amplitudes, strict=True):
        local = times - start
        active = (local >= 0) & (local < 10 * decay_s)
        signal[active] += (
            amplitude
            * np.exp(-local[active] / decay_s)
            * np.sin(2 * np.pi * resonance_hz * local[active])
        )
    return signal


def _bearing_impacts(
    spec: MachineSpec, shaft_hz: float, severity: float, times: np.ndarray, rng: np.random.Generator
) -> np.ndarray:
    period = 1.0 / (spec.bearing.bpfo_order() * shaft_hz)
    count = int(times[-1] / period) + 1
    jitter = rng.normal(0.0, 0.01 * period, count)
    impact_times = rng.uniform(0, period) + np.arange(count) * period + jitter
    amplitudes = severity * rng.uniform(0.8, 1.2, count)
    return _ringing_impacts(times, impact_times, amplitudes, spec.resonance_hz)


def _process_transient(
    spec: MachineSpec, times: np.ndarray, rng: np.random.Generator
) -> np.ndarray:
    start = np.array([rng.uniform(0, times[-1])])
    amplitude = np.array([rng.uniform(0.3, 1.0)])
    return _ringing_impacts(times, start, amplitude, spec.resonance_hz * rng.uniform(0.8, 1.2))


def vibration_window(
    spec: MachineSpec,
    condition: Condition,
    rng: np.random.Generator,
    sample_rate_hz: int = SAMPLE_RATE_HZ,
    samples: int = WINDOW_SAMPLES,
) -> np.ndarray:
    """Radial acceleration in g for one acquisition window."""
    times = np.arange(samples) / sample_rate_hz
    shaft_hz = spec.shaft_hz * (1 + rng.normal(0, 0.003))
    load = rng.lognormal(0.0, 0.15)
    amp_1x = spec.base_1x_g * load
    if condition.fault == "imbalance":
        amp_1x *= 1 + 3 * condition.severity
    phases = rng.uniform(0, 2 * np.pi, 2)
    signal = amp_1x * np.sin(2 * np.pi * shaft_hz * times + phases[0])
    signal += 0.3 * spec.base_1x_g * load * np.sin(4 * np.pi * shaft_hz * times + phases[1])
    signal += rng.normal(0.0, spec.noise_g * rng.lognormal(0.0, 0.1), samples)
    if condition.fault == "bearing_wear" and condition.severity > 0:
        signal += _bearing_impacts(spec, shaft_hz, condition.severity, times, rng)
    if rng.random() < TRANSIENT_PROBABILITY:
        signal += _process_transient(spec, times, rng)
    return signal


def housing_temperature(spec: MachineSpec, condition: Condition, rng: np.random.Generator) -> float:
    """Bearing housing surface temperature in C, as the RAWv2 temperature field reports it."""
    rise = (
        MAX_TEMPERATURE_RISE_C * condition.severity if condition.fault == "temperature_drift" else 0
    )
    return float(spec.base_temp_c + rise + rng.normal(0.0, TEMPERATURE_NOISE_C))
