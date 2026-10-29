import numpy as np
import pytest

from industrial_monitor.features import (
    amplitude_spectrum,
    crest_factor,
    envelope_spectrum,
    extract_features,
    kurtosis,
    velocity_rms_mm_s,
)
from industrial_monitor.machines import FLEET
from industrial_monitor.signals import Condition, vibration_window

FS = 1344
N = 1024
TIMES = np.arange(N) / FS
PUMP = FLEET["pump-3"]


def test_amplitude_spectrum_recovers_sine_amplitude_between_bins():
    signal = 0.2 * np.sin(2 * np.pi * 24.9 * TIMES)
    freqs, amplitude = amplitude_spectrum(signal, FS)
    peak = int(np.argmax(amplitude))
    assert freqs[peak] == pytest.approx(24.9, abs=0.4)
    assert amplitude[peak] == pytest.approx(0.2, rel=0.02)


def test_velocity_rms_of_100_hz_sine():
    # 0.1 g at 100 Hz: 0.1 * 9.80665 / (2 pi 100) m/s peak, divided by sqrt 2, in mm/s
    signal = 0.1 * np.sin(2 * np.pi * 100.0 * TIMES)
    assert velocity_rms_mm_s(signal, FS) == pytest.approx(1.1036, rel=0.03)


def test_velocity_rms_ignores_content_below_10_hz():
    signal = 0.1 * np.sin(2 * np.pi * 3.0 * TIMES)
    assert velocity_rms_mm_s(signal, FS) < 0.2


def test_envelope_spectrum_finds_modulation_frequency():
    carrier = np.sin(2 * np.pi * 450.0 * TIMES)
    signal = (1 + 0.5 * np.sin(2 * np.pi * 80.0 * TIMES)) * carrier
    freqs, amplitude = envelope_spectrum(signal, FS, band_hz=(300.0, 600.0))
    peak = int(np.argmax(amplitude))
    assert freqs[peak] == pytest.approx(80.0, abs=1.0)
    assert amplitude[peak] == pytest.approx(0.5, rel=0.1)


def test_kurtosis_and_crest_factor_reference_values():
    alternating = np.array([1.0, -1.0, 1.0, -1.0])
    assert kurtosis(alternating) == pytest.approx(1.0)
    assert crest_factor(np.sin(2 * np.pi * 21.0 * TIMES)) == pytest.approx(np.sqrt(2), rel=0.01)


def test_features_of_healthy_pump_window():
    window = vibration_window(PUMP, Condition("none", 0.0), np.random.default_rng(1))
    features = extract_features(window, FS, PUMP)
    assert features.shaft_hz == pytest.approx(PUMP.shaft_hz, rel=0.01)
    assert features.amp_1x_g == pytest.approx(PUMP.base_1x_g, rel=0.4)
    # sine plus Gaussian noise sits between 1.5 (pure sine) and 3 (pure noise)
    assert 1.5 < features.kurtosis < 3.2


def test_imbalance_raises_1x_feature():
    rng = np.random.default_rng(2)
    healthy = extract_features(vibration_window(PUMP, Condition("none", 0.0), rng), FS, PUMP)
    faulty = extract_features(vibration_window(PUMP, Condition("imbalance", 1.0), rng), FS, PUMP)
    assert faulty.amp_1x_g > 2.5 * healthy.amp_1x_g
    assert faulty.velocity_rms_mm_s > 2.5 * healthy.velocity_rms_mm_s


def test_bearing_wear_raises_envelope_feature():
    rng = np.random.default_rng(4)
    healthy = extract_features(vibration_window(PUMP, Condition("none", 0.0), rng), FS, PUMP)
    faulty = extract_features(vibration_window(PUMP, Condition("bearing_wear", 0.5), rng), FS, PUMP)
    assert faulty.bearing_envelope > 3 * healthy.bearing_envelope
