"""Detection rate and false-alarm rate of the detector on labeled simulator windows.

The alarm threshold is calibrated on one simulated plant (DEV_SEED) to a target per-window
false-alarm rate, then frozen and measured on a second plant with different machines, fault
onsets and noise (EVAL_SEED).
"""

import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from statistics import median

from industrial_monitor.detector import assess, fit_baseline, hypothesis_for, observation_from
from industrial_monitor.features import extract_features
from industrial_monitor.machines import MachineSpec
from industrial_monitor.signals import SAMPLE_RATE_HZ
from industrial_monitor.simulator import FaultPlan, evaluation_plant, simulate_machine

DEV_SEED = 101
EVAL_SEED = 202
MACHINES_PER_FAULT = 4
BASELINE_WINDOWS = 40
TEST_WINDOWS = 200
TARGET_FAR = 0.01
MODES = {"per_window": (1, 1), "two_of_three": (2, 3)}
THRESHOLD_GRID = [round(2.0 + 0.05 * step, 2) for step in range(361)]
ROC_GRID = [round(2.0 + 0.5 * step, 1) for step in range(17)] + [12.0, 15.0, 20.0, 30.0, 40.0]
SEVERITY_BINS = ((0.05, 0.25), (0.25, 0.45), (0.45, 0.65), (0.65, 0.85), (0.85, 1.0))
FAULT_CLASSES = ("imbalance", "bearing_wear", "temperature_drift")

Decision = tuple["ScoredWindow", bool, str | None]


@dataclass(frozen=True)
class ScoredWindow:
    machine_id: str
    index: int
    fault: str
    severity: float
    channel_z: dict[str, float]

    @property
    def score(self) -> float:
        return max(self.channel_z.values())


def score_plant(
    plant: list[tuple[MachineSpec, FaultPlan]], windows: int, baseline_windows: int, seed: int
) -> list[ScoredWindow]:
    """Channel z-scores for every post-baseline window, in machine then time order."""
    records = []
    for spec, plan in plant:
        simulated = list(simulate_machine(spec, plan, windows, seed))
        observations = [
            observation_from(extract_features(w.samples_g, SAMPLE_RATE_HZ, spec), w.temperature_c)
            for w in simulated
        ]
        baseline = fit_baseline(observations[:baseline_windows])
        for window, observation in zip(
            simulated[baseline_windows:], observations[baseline_windows:], strict=True
        ):
            channel_z = assess(baseline, observation, threshold=math.inf).channel_z
            records.append(
                ScoredWindow(
                    spec.machine_id,
                    window.index,
                    window.condition.fault,
                    window.condition.severity,
                    channel_z,
                )
            )
    return records


def persistent_alarms(flags: list[bool], required: int, window: int) -> list[bool]:
    return [sum(flags[max(0, i - window + 1) : i + 1]) >= required for i in range(len(flags))]


def decide(
    records: list[ScoredWindow], threshold: float, persistence: tuple[int, int]
) -> list[Decision]:
    """Alarm and hypothesis per window, as MachineDetector would produce them online."""
    required, window = persistence
    by_machine: dict[str, list[int]] = defaultdict(list)
    for position, record in enumerate(records):
        by_machine[record.machine_id].append(position)
    decisions: list[Decision | None] = [None] * len(records)
    for positions in by_machine.values():
        hypotheses = [hypothesis_for(records[p].channel_z, threshold) for p in positions]
        alarms = persistent_alarms([h is not None for h in hypotheses], required, window)
        for i, position in enumerate(positions):
            recent = [h for h in hypotheses[max(0, i - window + 1) : i + 1] if h is not None]
            hypothesis = recent[-1] if alarms[i] else None
            decisions[position] = (records[position], alarms[i], hypothesis)
    return [d for d in decisions if d is not None]


def _rate(values: list[bool]) -> float | None:
    return sum(values) / len(values) if values else None


def false_alarm_rate(
    records: list[ScoredWindow], threshold: float, persistence: tuple[int, int]
) -> float:
    normal = [r for r in records if r.fault == "none"]
    rate = _rate([alarm for _, alarm, _ in decide(normal, threshold, persistence)])
    return 0.0 if rate is None else rate


def calibrate_threshold(
    normal_records: list[ScoredWindow],
    target_far: float,
    persistence: tuple[int, int],
    grid: list[float] = THRESHOLD_GRID,
) -> float:
    """Lowest grid threshold whose false-alarm rate on healthy windows meets the target.

    The false-alarm rate does not increase with the threshold, so a binary search applies.
    """
    ordered = sorted(grid)
    low, high = 0, len(ordered) - 1
    if false_alarm_rate(normal_records, ordered[high], persistence) > target_far:
        raise ValueError(f"no threshold in the grid reaches a false-alarm rate of {target_far}")
    while low < high:
        middle = (low + high) // 2
        if false_alarm_rate(normal_records, ordered[middle], persistence) <= target_far:
            high = middle
        else:
            low = middle + 1
    return ordered[low]


def _severity_rates(decisions: list[Decision], fault: str) -> list[float | None]:
    return [
        _rate(
            [alarm for r, alarm, _ in decisions if r.fault == fault and low <= r.severity <= high]
        )
        for low, high in SEVERITY_BINS
    ]


def _median_delays(decisions: list[Decision]) -> dict[str, float | None]:
    onset: dict[str, int] = {}
    first_alarm: dict[str, int] = {}
    faults: dict[str, str] = {}
    for record, alarm, _ in decisions:
        if record.fault != "none":
            onset.setdefault(record.machine_id, record.index)
            faults[record.machine_id] = record.fault
            if alarm:
                first_alarm.setdefault(record.machine_id, record.index)
    delays: dict[str, list[int]] = defaultdict(list)
    for machine, start in onset.items():
        if machine in first_alarm:
            delays[faults[machine]].append(first_alarm[machine] - start)
    return {fault: (median(delays[fault]) if delays[fault] else None) for fault in FAULT_CLASSES}


def detection_report(
    records: list[ScoredWindow], threshold: float, persistence: tuple[int, int]
) -> dict:
    decisions = decide(records, threshold, persistence)
    normal = [(r, alarm, h) for r, alarm, h in decisions if r.fault == "none"]
    faulty = [(r, alarm, h) for r, alarm, h in decisions if r.fault != "none"]
    present = [f for f in FAULT_CLASSES if any(r.fault == f for r, _, _ in faulty)]
    return {
        "threshold": threshold,
        "persistence": list(persistence),
        "normal_windows": len(normal),
        "fault_windows": len(faulty),
        "false_alarm_rate": _rate([alarm for _, alarm, _ in normal]),
        "false_alarm_hypotheses": dict(Counter(h for _, alarm, h in normal if alarm)),
        "detection_rate": {
            "all": _rate([alarm for _, alarm, _ in faulty]),
            **{f: _rate([alarm for r, alarm, _ in faulty if r.fault == f]) for f in present},
        },
        "hypothesis_accuracy": {
            f: _rate([h == f for r, alarm, h in faulty if r.fault == f and alarm]) for f in present
        },
        "detection_rate_by_severity": {
            "bins": [f"{low:.2f} to {high:.2f}" for low, high in SEVERITY_BINS],
            **{f: _severity_rates(faulty, f) for f in present},
        },
        "median_delay_windows": _median_delays(decisions),
    }


def roc_curve(records: list[ScoredWindow], persistence: tuple[int, int]) -> list[dict]:
    points = []
    for threshold in ROC_GRID:
        decisions = decide(records, threshold, persistence)
        points.append(
            {
                "threshold": threshold,
                "false_alarm_rate": _rate([a for r, a, _ in decisions if r.fault == "none"]),
                "detection_rate": _rate([a for r, a, _ in decisions if r.fault != "none"]),
            }
        )
    return points


def run_detection_evaluation(
    machines_per_fault: int = MACHINES_PER_FAULT, test_windows: int = TEST_WINDOWS
) -> dict:
    """Calibrate the 2-of-3 detector on the dev plant, then measure both modes on the eval plant.

    The per-window mode reuses the calibrated threshold, so the comparison isolates the effect
    of the persistence filter.
    """
    windows = BASELINE_WINDOWS + test_windows
    scored = {}
    for name, seed in (("dev", DEV_SEED), ("eval", EVAL_SEED)):
        plant = evaluation_plant(machines_per_fault, BASELINE_WINDOWS, seed, test_windows)
        scored[name] = score_plant(plant, windows, BASELINE_WINDOWS, seed)
    dev_normal = [r for r in scored["dev"] if r.fault == "none"]
    calibrated = MODES["two_of_three"]
    threshold = calibrate_threshold(dev_normal, TARGET_FAR, calibrated)
    modes = {
        name: {
            "evaluation": detection_report(scored["eval"], threshold, persistence),
            "roc": roc_curve(scored["eval"], persistence),
        }
        for name, persistence in MODES.items()
    }
    return {
        "config": {
            "dev_seed": DEV_SEED,
            "eval_seed": EVAL_SEED,
            "machines_per_plant": machines_per_fault * (len(FAULT_CLASSES) + 1),
            "baseline_windows": BASELINE_WINDOWS,
            "test_windows": test_windows,
            "target_false_alarm_rate": TARGET_FAR,
            "sample_rate_hz": SAMPLE_RATE_HZ,
        },
        "calibration": {
            "persistence": list(calibrated),
            "threshold": threshold,
            "dev_false_alarm_rate": false_alarm_rate(dev_normal, threshold, calibrated),
        },
        "modes": modes,
    }
