"""Plant monitor: decodes sensor messages, runs one detector per machine, publishes anomalies.

Subscribes to plant/<site>/+/rawv2 and plant/<site>/+/vibration. Each vibration burst is one
detector window; the housing temperature comes from the latest RAWv2 status of that sensor.
Each window's state is published as JSON on plant/<site>/<machine>/anomaly.
"""

import json
import logging
from collections import Counter
from dataclasses import dataclass

from industrial_monitor.burst import decode_burst
from industrial_monitor.bus import Bus
from industrial_monitor.detector import Assessment, MachineDetector, observation_from
from industrial_monitor.features import WindowFeatures, extract_features
from industrial_monitor.machines import MachineSpec
from industrial_monitor.ruuvi import decode_rawv2

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MonitorConfig:
    site: str
    threshold: float
    persistence: tuple[int, int] = (2, 3)
    baseline_windows: int = 40


@dataclass
class _MachineState:
    spec: MachineSpec
    detector: MachineDetector
    temperature_c: float | None = None
    windows: int = 0
    features: WindowFeatures | None = None
    assessment: Assessment | None = None
    alarm_since_window: int | None = None
    sequence: int | None = None


def _rounded(value: float | None, digits: int) -> float | None:
    return None if value is None else round(value, digits)


class PlantMonitor:
    def __init__(self, bus: Bus, fleet: dict[str, MachineSpec], config: MonitorConfig):
        self._bus = bus
        self._config = config
        self._machines = {
            machine_id: _MachineState(
                spec,
                MachineDetector(config.baseline_windows, config.threshold, config.persistence),
            )
            for machine_id, spec in fleet.items()
        }
        self.rejected: Counter[str] = Counter()
        bus.subscribe(f"plant/{config.site}/+/rawv2", self._on_status)
        bus.subscribe(f"plant/{config.site}/+/vibration", self._on_vibration)

    def _reject(self, reason: str, topic: str) -> None:
        self.rejected[reason] += 1
        logger.warning("rejected message on %s: %s", topic, reason)

    def _machine_for(self, topic: str) -> _MachineState | None:
        state = self._machines.get(topic.split("/")[2])
        if state is None:
            self._reject("unknown_machine", topic)
        return state

    def _on_status(self, topic: str, payload: bytes) -> None:
        state = self._machine_for(topic)
        if state is None:
            return
        try:
            reading = decode_rawv2(payload)
        except ValueError:
            self._reject("rawv2_decode", topic)
            return
        if reading.temperature_c is not None:
            state.temperature_c = reading.temperature_c

    def _on_vibration(self, topic: str, payload: bytes) -> None:
        state = self._machine_for(topic)
        if state is None:
            return
        try:
            burst = decode_burst(payload)
        except ValueError:
            self._reject("burst_decode", topic)
            return
        if state.temperature_c is None:
            self._reject("no_temperature", topic)
            return
        features = extract_features(burst.samples_g(), burst.sample_rate_hz, state.spec)
        assessment = state.detector.update(observation_from(features, state.temperature_c))
        self._record(state, burst.sequence, features, assessment)
        anomaly_topic = f"plant/{self._config.site}/{state.spec.machine_id}/anomaly"
        self._bus.publish(anomaly_topic, json.dumps(self._snapshot(state)).encode())

    def _record(
        self,
        state: _MachineState,
        sequence: int,
        features: WindowFeatures,
        assessment: Assessment | None,
    ) -> None:
        state.windows += 1
        state.sequence = sequence
        state.features = features
        state.assessment = assessment
        alarm = assessment is not None and assessment.alarm
        if not alarm:
            state.alarm_since_window = None
        elif state.alarm_since_window is None:
            state.alarm_since_window = sequence

    def _snapshot(self, state: _MachineState) -> dict:
        assessment, features = state.assessment, state.features
        if state.detector.learning:
            condition = "learning"
        else:
            condition = "alarm" if assessment is not None and assessment.alarm else "normal"
        return {
            "machine_id": state.spec.machine_id,
            "equipment": state.spec.equipment,
            "state": condition,
            "hypothesis": assessment.hypothesis if assessment else None,
            "alarm_since_window": state.alarm_since_window,
            "window": state.sequence,
            "windows": state.windows,
            "threshold": self._config.threshold,
            "channel_z": (
                {k: round(v, 2) for k, v in assessment.channel_z.items()} if assessment else {}
            ),
            "temperature_c": _rounded(state.temperature_c, 2),
            "velocity_rms_mm_s": _rounded(features.velocity_rms_mm_s if features else None, 2),
            "shaft_hz": _rounded(features.shaft_hz if features else None, 2),
            "amp_1x_g": _rounded(features.amp_1x_g if features else None, 4),
            "bearing_envelope": _rounded(features.bearing_envelope if features else None, 2),
            "kurtosis": _rounded(features.kurtosis if features else None, 2),
            "bpfo_hz": round(state.spec.bpfo_hz(), 2),
        }

    def status(self, machine_id: str) -> dict:
        """Latest state of one machine. Raises KeyError for a machine outside the fleet."""
        return self._snapshot(self._machines[machine_id])

    def snapshot(self) -> list[dict]:
        return [self._snapshot(state) for state in self._machines.values()]

    def alarms(self) -> list[dict]:
        return [status for status in self.snapshot() if status["state"] == "alarm"]
