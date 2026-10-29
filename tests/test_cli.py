import json

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
