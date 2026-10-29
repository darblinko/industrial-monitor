"""Windowed FFT features for one acceleration window."""

from dataclasses import dataclass

import numpy as np

from industrial_monitor.machines import MachineSpec

STANDARD_GRAVITY = 9.80665
ZERO_PAD_FACTOR = 4
VELOCITY_BAND_HZ = (10.0, 600.0)
ENVELOPE_HALF_BAND_HZ = 150.0
BEARING_HARMONICS = 3
ORDER_TOLERANCE = 0.02


@dataclass(frozen=True)
class WindowFeatures:
    shaft_hz: float
    rms_g: float
    amp_1x_g: float
    amp_2x_g: float
    velocity_rms_mm_s: float
    kurtosis: float
    crest_factor: float
    bearing_envelope: float


def amplitude_spectrum(signal: np.ndarray, sample_rate_hz: float) -> tuple[np.ndarray, np.ndarray]:
    """One-sided peak amplitude spectrum with a Hann window and zero padding."""
    window = np.hanning(len(signal))
    n_fft = ZERO_PAD_FACTOR * len(signal)
    spectrum = np.fft.rfft((signal - signal.mean()) * window, n=n_fft)
    return np.fft.rfftfreq(n_fft, 1 / sample_rate_hz), 2 * np.abs(spectrum) / window.sum()


def velocity_rms_mm_s(
    signal_g: np.ndarray, sample_rate_hz: float, band_hz: tuple[float, float] = VELOCITY_BAND_HZ
) -> float:
    """RMS velocity in mm/s, integrating acceleration in the frequency domain."""
    window = np.hanning(len(signal_g))
    spectrum = np.fft.rfft((signal_g - signal_g.mean()) * window)
    freqs = np.fft.rfftfreq(len(signal_g), 1 / sample_rate_hz)
    in_band = (freqs >= band_hz[0]) & (freqs <= band_hz[1])
    velocity = spectrum[in_band] / (2 * np.pi * freqs[in_band])
    mean_square = 2 * np.sum(np.abs(velocity) ** 2) / (len(signal_g) * np.sum(window**2))
    return float(np.sqrt(mean_square) * STANDARD_GRAVITY * 1000)


def envelope_spectrum(
    signal: np.ndarray, sample_rate_hz: float, band_hz: tuple[float, float]
) -> tuple[np.ndarray, np.ndarray]:
    """Amplitude spectrum of the Hilbert envelope of the band-passed signal."""
    spectrum = np.fft.fft(signal)
    freqs = np.fft.fftfreq(len(signal), 1 / sample_rate_hz)
    keep = (freqs >= band_hz[0]) & (freqs <= band_hz[1])
    envelope = np.abs(np.fft.ifft(2 * spectrum * keep))
    return amplitude_spectrum(envelope, sample_rate_hz)


def kurtosis(signal: np.ndarray) -> float:
    centered = signal - signal.mean()
    return float(np.mean(centered**4) / np.mean(centered**2) ** 2)


def crest_factor(signal: np.ndarray) -> float:
    centered = signal - signal.mean()
    return float(np.max(np.abs(centered)) / np.sqrt(np.mean(centered**2)))


def _band_peak(freqs: np.ndarray, amplitude: np.ndarray, center: float) -> tuple[float, float]:
    band = (freqs >= center * (1 - ORDER_TOLERANCE)) & (freqs <= center * (1 + ORDER_TOLERANCE))
    index = int(np.argmax(np.where(band, amplitude, -1.0)))
    return float(freqs[index]), float(amplitude[index])


def _bearing_envelope_ratio(
    signal: np.ndarray, sample_rate_hz: float, spec: MachineSpec, shaft_hz: float
) -> float:
    band = (spec.resonance_hz - ENVELOPE_HALF_BAND_HZ, spec.resonance_hz + ENVELOPE_HALF_BAND_HZ)
    freqs, amplitude = envelope_spectrum(signal, sample_rate_hz, band)
    bpfo = spec.bearing.bpfo_order() * shaft_hz
    lines = sum(_band_peak(freqs, amplitude, k * bpfo)[1] for k in range(1, BEARING_HARMONICS + 1))
    floor = float(np.median(amplitude[(freqs >= 10.0) & (freqs <= 300.0)]))
    return lines / floor


def extract_features(
    signal_g: np.ndarray, sample_rate_hz: float, spec: MachineSpec
) -> WindowFeatures:
    freqs, amplitude = amplitude_spectrum(signal_g, sample_rate_hz)
    shaft_hz, amp_1x = _band_peak(freqs, amplitude, spec.shaft_hz)
    _, amp_2x = _band_peak(freqs, amplitude, 2 * shaft_hz)
    centered = signal_g - signal_g.mean()
    return WindowFeatures(
        shaft_hz=shaft_hz,
        rms_g=float(np.sqrt(np.mean(centered**2))),
        amp_1x_g=amp_1x,
        amp_2x_g=amp_2x,
        velocity_rms_mm_s=velocity_rms_mm_s(signal_g, sample_rate_hz),
        kurtosis=kurtosis(signal_g),
        crest_factor=crest_factor(signal_g),
        bearing_envelope=_bearing_envelope_ratio(signal_g, sample_rate_hz, spec, shaft_hz),
    )
