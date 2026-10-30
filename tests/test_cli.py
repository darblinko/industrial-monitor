import json
import os
import threading
import time
from pathlib import Path

import pytest

from industrial_monitor.cli import main

ROOT = Path(__file__).resolve().parents[1]


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


def test_scan_ble_explains_the_missing_extra(monkeypatch, capsys):
    monkeypatch.setitem(__import__("sys").modules, "bleak", None)
    assert main(["scan-ble", "--map", "C1:00:00:00:00:2A=pump-3"]) == 2
    assert "uv sync --extra ble" in capsys.readouterr().err


def test_scan_ble_rejects_a_malformed_map(capsys):
    with pytest.raises(SystemExit):
        main(["scan-ble", "--map", "pump-3"])


def test_ask_answers_from_the_saved_plant_state_with_the_fake_model(capsys):
    assert main(["ask", "Why is pump 3 alarming and what do I check?", "--model", "fake"]) == 0
    output = capsys.readouterr().out
    assert "[status:pump-3]" in output
    assert "tools: get_machine_status, search_manual" in output


def test_claude_model_requires_an_api_key(monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert main(["ask", "Is pump 1 running normally?", "--model", "claude"]) == 2
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err


def test_evaluate_assistant_writes_scores(tmp_path):
    output = tmp_path / "assistant.json"
    assert main(["evaluate-assistant", "--model", "fake", "--output", str(output)]) == 0
    result = json.loads(output.read_text())
    assert result["model"] == "fake-extractive"
    assert result["summary"]["questions"] == 20


def test_export_landing_writes_chart_data(tmp_path):
    output = tmp_path / "data.json"
    code = main(
        [
            "export-landing",
            "--output",
            str(output),
            "--revision",
            "abc1234",
            "--measured",
            "2026-10-28",
            "--windows",
            "50",
        ]
    )
    assert code == 0
    data = json.loads(output.read_text())
    assert data["meta"]["revision"] == "abc1234"
    assert "detection-by-fault" in {chart["name"] for chart in data["charts"]}


def test_assistant_commands_run_outside_the_checkout(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["ask", "Why is pump 3 alarming and what do I check?"]) == 0
    assert "[status:pump-3]" in capsys.readouterr().out
    output = tmp_path / "assistant.json"
    assert main(["evaluate-assistant", "--output", str(output)]) == 0
    assert json.loads(output.read_text())["summary"]["questions"] == 20


def test_ask_reads_an_explicit_corpus_directory(tmp_path, capsys):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "manual.md").write_text(
        "# Test manual\n\n## [TM-1] Trip limit\n\nThe trip limit for pump vibration is 9.9 mm/s.\n"
    )
    question = "What is the trip limit for pump vibration?"
    assert main(["ask", question, "--corpus-dir", str(corpus)]) == 0
    assert "[TM-1]" in capsys.readouterr().out


def test_ask_names_the_plant_state_it_answered_from(tmp_path, capsys):
    assert main(["ask", "Is pump 1 running normally?"]) == 0
    assert "plant state: recorded demo plant" in capsys.readouterr().out
    state_file = tmp_path / "live.json"
    state_file.write_text((ROOT / "eval" / "plant-state.json").read_text())
    assert main(["ask", "Is pump 1 running normally?", "--state-file", str(state_file)]) == 0
    assert f"plant state: {state_file}" in capsys.readouterr().out
