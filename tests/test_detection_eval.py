import json

import pytest

from industrial_monitor.detection_eval import (
    ScoredWindow,
    calibrate_threshold,
    decide,
    detection_report,
    persistent_alarms,
    run_detection_evaluation,
    score_plant,
)
from industrial_monitor.detector import MachineDetector, observation_from
from industrial_monitor.features import extract_features
from industrial_monitor.machines import FLEET
from industrial_monitor.signals import SAMPLE_RATE_HZ
from industrial_monitor.simulator import FaultPlan, simulate_machine


def scored(machine: str, fault: str, scores: list[float]) -> list[ScoredWindow]:
    return [
        ScoredWindow(machine, i, fault, 0.5 if fault != "none" else 0.0, {"temperature_c": s})
        for i, s in enumerate(scores)
    ]


NORMAL = scored("a", "none", [1.0, 5.0, 2.0, 3.0])
FAULTY = scored("b", "temperature_drift", [6.0, 7.0, 1.0, 8.0])


def test_persistent_alarms_k_of_n():
    flags = [True, False, True, True, False, False]
    assert persistent_alarms(flags, required=2, window=3) == [False, False, True, True, True, False]


def test_report_counts_false_alarms_and_detections():
    report = detection_report(NORMAL + FAULTY, threshold=4.0, persistence=(1, 1))
    assert report["false_alarm_rate"] == pytest.approx(0.25)
    assert report["detection_rate"]["temperature_drift"] == pytest.approx(0.75)
    assert report["hypothesis_accuracy"]["temperature_drift"] == pytest.approx(1.0)
    assert report["normal_windows"] == 4
    assert report["fault_windows"] == 4


def test_calibration_picks_lowest_threshold_meeting_target():
    grid = [float(t) for t in range(1, 11)]
    assert calibrate_threshold(NORMAL, target_far=0.0, persistence=(1, 1), grid=grid) == 5.0
    assert calibrate_threshold(NORMAL, target_far=0.25, persistence=(1, 1), grid=grid) == 3.0


def test_batch_decisions_match_online_detector():
    spec = FLEET["pump-2"]
    plan = FaultPlan("bearing_wear", onset_window=30, ramp_windows=30)
    records = score_plant([(spec, plan)], windows=60, baseline_windows=20, seed=5)
    batch = [alarm for _, alarm, _ in decide(records, threshold=4.0, persistence=(2, 3))]

    detector = MachineDetector(baseline_windows=20, threshold=4.0, persistence=(2, 3))
    online = []
    for window in simulate_machine(spec, plan, windows=60, seed=5):
        features = extract_features(window.samples_g, SAMPLE_RATE_HZ, spec)
        result = detector.update(observation_from(features, window.temperature_c))
        if result is not None:
            online.append(result.alarm)

    assert batch == online
    assert any(batch)


def test_full_evaluation_calibrates_once_and_reports_both_modes():
    result = run_detection_evaluation(machines_per_fault=1, test_windows=60)
    calibration = result["calibration"]
    modes = result["modes"]
    assert calibration["persistence"] == [2, 3]
    assert calibration["dev_false_alarm_rate"] <= result["config"]["target_false_alarm_rate"]
    assert {m["evaluation"]["threshold"] for m in modes.values()} == {calibration["threshold"]}
    per_window = modes["per_window"]["evaluation"]["false_alarm_rate"]
    assert per_window >= modes["two_of_three"]["evaluation"]["false_alarm_rate"]
    json.dumps(result)
