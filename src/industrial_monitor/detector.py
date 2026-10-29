"""Per-machine anomaly detector: robust baseline, one-sided z-scores, fault hypothesis.

Each channel maps to the fault it indicates. Channels with a specific signature take
precedence over the generic impulsiveness channel (kurtosis), which only produces an
"unclassified" hypothesis when nothing specific exceeds the threshold.
"""

import math
from collections import deque
from dataclasses import dataclass, replace

import numpy as np

from industrial_monitor.features import WindowFeatures

CHANNELS: dict[str, str] = {
    "amp_1x_g": "imbalance",
    "bearing_envelope": "bearing_wear",
    "temperature_c": "temperature_drift",
    "kurtosis": "unclassified",
}
GENERIC_CHANNELS = frozenset({"kurtosis"})
LOG_CHANNELS = frozenset({"amp_1x_g", "bearing_envelope", "kurtosis"})
MAD_TO_SIGMA = 1.4826
SCALE_FLOOR = {"amp_1x_g": 0.02, "bearing_envelope": 0.02, "kurtosis": 0.02, "temperature_c": 0.05}


@dataclass(frozen=True)
class Baseline:
    center: dict[str, float]
    scale: dict[str, float]


@dataclass(frozen=True)
class Assessment:
    score: float
    alarm: bool
    hypothesis: str | None
    channel_z: dict[str, float]


def observation_from(features: WindowFeatures, temperature_c: float) -> dict[str, float]:
    return {
        "amp_1x_g": features.amp_1x_g,
        "bearing_envelope": features.bearing_envelope,
        "kurtosis": features.kurtosis,
        "temperature_c": temperature_c,
    }


def _transform(channel: str, value: float) -> float:
    return math.log(value) if channel in LOG_CHANNELS else value


def fit_baseline(observations: list[dict[str, float]]) -> Baseline:
    center, scale = {}, {}
    for channel in CHANNELS:
        values = np.array([_transform(channel, obs[channel]) for obs in observations])
        median = float(np.median(values))
        mad = float(np.median(np.abs(values - median)))
        center[channel] = median
        scale[channel] = max(MAD_TO_SIGMA * mad, SCALE_FLOOR[channel])
    return Baseline(center, scale)


def hypothesis_for(channel_z: dict[str, float], threshold: float) -> str | None:
    """Fault class of the strongest exceeding channel, preferring specific signatures."""
    exceeding = {channel: z for channel, z in channel_z.items() if z > threshold}
    specific = {c: z for c, z in exceeding.items() if c not in GENERIC_CHANNELS}
    candidates = specific or exceeding
    if not candidates:
        return None
    return CHANNELS[max(candidates, key=candidates.__getitem__)]


def assess(baseline: Baseline, observation: dict[str, float], threshold: float) -> Assessment:
    channel_z = {
        channel: (_transform(channel, observation[channel]) - baseline.center[channel])
        / baseline.scale[channel]
        for channel in CHANNELS
    }
    score = max(channel_z.values())
    hypothesis = hypothesis_for(channel_z, threshold)
    return Assessment(score, hypothesis is not None, hypothesis, channel_z)


class MachineDetector:
    """Learns a baseline from the first windows, then applies a k-of-n persistence filter."""

    def __init__(self, baseline_windows: int, threshold: float, persistence: tuple[int, int]):
        self.baseline_windows = baseline_windows
        self.threshold = threshold
        self.required, window = persistence
        self._training: list[dict[str, float]] = []
        self._baseline: Baseline | None = None
        self._recent: deque[str | None] = deque(maxlen=window)

    @property
    def learning(self) -> bool:
        return self._baseline is None

    def update(self, observation: dict[str, float]) -> Assessment | None:
        if self._baseline is None:
            self._training.append(observation)
            if len(self._training) >= self.baseline_windows:
                self._baseline = fit_baseline(self._training)
            return None
        raw = assess(self._baseline, observation, self.threshold)
        self._recent.append(raw.hypothesis)
        exceedances = [h for h in self._recent if h is not None]
        alarm = len(exceedances) >= self.required
        return replace(raw, alarm=alarm, hypothesis=exceedances[-1] if alarm else None)
