import json
import os
import threading
import time

import pytest

from industrial_monitor.cli import main


def test_evaluate_detector_writes_results_file(tmp_path):
    output = tmp_path / "detection.json"
    code = main(
        [
            "evaluate-detector",
            "--machines-per-fault",
            "1",
            "--test-windows",
            "60",
            "--output",
            str(output),
        ]
    )
    assert code == 0
    result = json.loads(output.read_text())
    assert set(result["modes"]) == {"per_window", "two_of_three"}


def test_demo_prints_machine_states(capsys):
    assert main(["demo", "--windows", "50"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].split() == ["machine", "state", "hypothesis", "since", "vel_mm_s", "temp_c"]
    assert len(lines) == 7


@pytest.mark.broker
@pytest.mark.skipif("MQTT_HOST" not in os.environ, reason="set MQTT_HOST to run broker tests")
def test_monitor_tracks_the_simulated_plant_through_the_broker(tmp_path, monkeypatch):
    monkeypatch.setenv("SITE", "cli-test")
    state_file = tmp_path / "state.json"
    monitor = threading.Thread(
        target=main, args=(["monitor", "--duration", "20", "--state-file", str(state_file)],)
    )
    monitor.start()
    time.sleep(1.0)
    assert main(["simulate", "--windows", "45", "--interval", "0.02"]) == 0
    deadline = time.monotonic() + 15
    statuses = []
    while time.monotonic() < deadline:
        if state_file.exists():
            statuses = json.loads(state_file.read_text())
            if statuses and all(s["windows"] == 45 for s in statuses):
                break
        time.sleep(0.2)
    monitor.join()
    assert len(statuses) == 6
    assert {s["windows"] for s in statuses} == {45}
    assert {s["state"] for s in statuses} <= {"normal", "alarm"}
