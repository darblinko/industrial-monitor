import json
from pathlib import Path

import numpy as np

from industrial_monitor.landing import (
    assistant_chart,
    build_landing_data,
    detection_charts,
    pooled_peaks,
    score_timeline,
    spectrum_charts,
)

ROOT = Path(__file__).resolve().parents[1]
DETECTION = json.loads((ROOT / "results" / "detection.json").read_text())
ASSISTANT = json.loads((ROOT / "results" / "assistant-eval-fake.json").read_text())
CHART_FIELDS = {"name", "type", "title", "subtitle", "source", "alt"}


def by_name(charts: list[dict]) -> dict[str, dict]:
    return {chart["name"]: chart for chart in charts}


def test_detection_charts_copy_rates_from_the_results_file():
    charts = by_name(detection_charts(DETECTION))
    calibrated = DETECTION["modes"]["two_of_three"]["evaluation"]
    rates = {row["label"]: row["value"] for row in charts["detection-by-fault"]["data"]}
    assert rates["Bearing wear"] == calibrated["detection_rate"]["bearing_wear"]
    assert rates["All faults"] == calibrated["detection_rate"]["all"]

    far = {row["label"]: row for row in charts["false-alarm-rate"]["data"]}
    assert far["2 of 3 windows"]["value"] == calibrated["false_alarm_rate"]
    assert far["2 of 3 windows"]["status"] == "pass"
    assert far["Every window"]["status"] == "fail"
    assert charts["false-alarm-rate"]["threshold"]["value"] == 0.01


def test_threshold_sweep_keeps_the_uniform_part_of_the_grid():
    sweep = by_name(detection_charts(DETECTION))["threshold-sweep"]
    assert sweep["x"][0] == "2.0"
    assert sweep["x"][-1] == "10.0"
    assert len(sweep["x"]) == len(sweep["series"][0]["values"]) == 17


def test_pooled_peaks_keep_the_largest_value_in_each_bin():
    freqs = np.arange(0.0, 20.0, 0.5)
    amplitude = np.zeros_like(freqs)
    amplitude[freqs == 7.5] = 3.0
    labels, values = pooled_peaks(freqs, amplitude, low_hz=0.0, high_hz=20.0, bin_hz=5.0)
    assert labels == ["0", "5", "10", "15"]
    assert values == [0.0, 3.0, 0.0, 0.0]


def test_spectrum_charts_compare_a_healthy_and_a_faulty_window():
    charts = by_name(spectrum_charts())
    envelope = charts["pump-3-envelope"]
    healthy, faulty = (series["values"] for series in envelope["series"])
    bpfo_bin = envelope["x"].index("82.5")
    assert faulty[bpfo_bin] > 10 * healthy[bpfo_bin]
    assert len(charts["pump-3-spectrum"]["x"]) == 120


def test_score_timeline_follows_the_anomaly_topic_after_the_baseline():
    timeline = score_timeline(windows=50)
    assert timeline["x"][0] == "40"
    assert timeline["x"][-1] == "49"
    names = [series["name"] for series in timeline["series"]]
    assert names[-1].startswith("threshold")
    assert set(timeline["series"][-1]["values"]) == {2.55}


def test_assistant_chart_reports_the_summary_metrics():
    chart = assistant_chart(ASSISTANT)
    values = {row["label"]: row["value"] for row in chart["data"]}
    assert values["Citation precision"] == ASSISTANT["summary"]["citation_precision"]
    assert "fake-extractive" in chart["subtitle"]


def test_every_chart_meets_the_publish_kit_schema():
    data = build_landing_data(DETECTION, ASSISTANT, "abc1234", "2026-10-28", windows=50)
    assert data["meta"] == {
        "repo": "industrial-monitor",
        "revision": "abc1234",
        "measured": "2026-10-28",
    }
    for chart in data["charts"]:
        assert chart.keys() >= CHART_FIELDS, chart["name"]
        if chart["type"] == "line":
            assert len(chart["series"]) <= 4
            assert all(isinstance(s["values"][-1], float | int) for s in chart["series"])
            assert all(len(s["values"]) == len(chart["x"]) for s in chart["series"])
    assert len({chart["name"] for chart in data["charts"]}) == len(data["charts"])
    json.dumps(data, allow_nan=False)


def test_score_timeline_reports_alarms_before_and_after_the_fault_onset():
    subtitle = score_timeline()["subtitle"]
    assert "bearing wear from window 70" in subtitle
    assert "alarm from window 71" in subtitle
    assert "false alarm at windows 59 to 60" in subtitle
