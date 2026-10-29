"""Signal model tests. Spectra are computed here with plain numpy, independent of features.py."""

import numpy as np
import pytest

from industrial_monitor.machines import FLEET, BearingGeometry
from industrial_monitor.signals import Condition, housing_temperature, vibration_window

FS = 1344
PUMP = FLEET["pump-3"]


def peak_amplitude(signal: np.ndarray, f_lo: float, f_hi: float) -> float:
    window = np.hanning(len(signal))
    spectrum = np.abs(np.fft.rfft(signal * window, n=8 * len(signal))) * 2 / window.sum()
    freqs = np.fft.rfftfreq(8 * len(signal), 1 / FS)
    band = (freqs >= f_lo) & (freqs <= f_hi)
    return float(spectrum[band].max())


def mean_1x(condition: Condition, windows: int = 60) -> float:
    rng = np.random.default_rng(11)
    shaft = PUMP.shaft_hz
    return float(
        np.mean(
            [
                peak_amplitude(vibration_window(PUMP, condition, rng), 0.95 * shaft, 1.05 * shaft)
                for _ in range(windows)
            ]
        )
    )


def squared_envelope_ratio(signal: np.ndarray, frequency: float) -> float:
    squared = signal**2 - np.mean(signal**2)
    spectrum = np.abs(np.fft.rfft(squared * np.hanning(len(squared))))
    freqs = np.fft.rfftfreq(len(squared), 1 / FS)
    line = spectrum[(freqs > 0.97 * frequency) & (freqs < 1.03 * frequency)].max()
    floor = np.median(spectrum[(freqs > 20) & (freqs < 300)])
    return float(line / floor)


def test_bpfo_order_matches_hand_calculation():
    assert BearingGeometry(9, 12.7, 50.8).bpfo_order() == pytest.approx(3.375)
    assert BearingGeometry(9, 12.7, 50.8, 15.0).bpfo_order() == pytest.approx(3.41334, abs=1e-4)
    assert BearingGeometry(9, 12.7, 50.8).bpfi_order() == pytest.approx(5.625)


def test_pump_bpfo_frequency_at_running_speed():
    assert PUMP.bpfo_hz() == pytest.approx(83.53, abs=0.01)


def test_window_has_requested_length_and_is_reproducible():
    first = vibration_window(PUMP, Condition("none", 0.0), np.random.default_rng(5))
    second = vibration_window(PUMP, Condition("none", 0.0), np.random.default_rng(5))
    assert first.shape == (1024,)
    np.testing.assert_array_equal(first, second)


def test_healthy_1x_amplitude_matches_machine_spec():
    assert mean_1x(Condition("none", 0.0)) == pytest.approx(PUMP.base_1x_g, rel=0.15)


def test_full_imbalance_quadruples_1x_amplitude():
    assert mean_1x(Condition("imbalance", 1.0)) == pytest.approx(4 * PUMP.base_1x_g, rel=0.15)


def test_bearing_wear_puts_squared_envelope_line_at_bpfo():
    rng = np.random.default_rng(3)
    faulty = vibration_window(PUMP, Condition("bearing_wear", 1.0), rng)
    healthy = vibration_window(PUMP, Condition("none", 0.0), rng)
    assert squared_envelope_ratio(faulty, PUMP.bpfo_hz()) > 8
    assert squared_envelope_ratio(healthy, PUMP.bpfo_hz()) < 4


def test_temperature_drift_adds_fifteen_degrees_at_full_severity():
    rng = np.random.default_rng(8)
    drift = [
        housing_temperature(PUMP, Condition("temperature_drift", 1.0), rng) for _ in range(200)
    ]
    healthy = [housing_temperature(PUMP, Condition("none", 0.0), rng) for _ in range(200)]
    assert np.mean(drift) - PUMP.base_temp_c == pytest.approx(15.0, abs=0.2)
    assert np.mean(healthy) - PUMP.base_temp_c == pytest.approx(0.0, abs=0.2)


def test_rejects_unknown_fault():
    with pytest.raises(ValueError):
        Condition("cavitation", 0.5)
