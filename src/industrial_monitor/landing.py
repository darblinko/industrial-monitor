"""Chart data for the README figures and the landing page (docs/data.json).

Detection and assistant charts copy their numbers from the results files. Spectrum and score
charts are computed from the deterministic demo plant, so the export reproduces them exactly.
"""

import json

import numpy as np

from industrial_monitor.bus import InProcessBus
from industrial_monitor.demo import DEMO_PLANS, DEMO_SEED, DEMO_SITE, DEMO_WINDOWS, publish_demo
from industrial_monitor.features import ENVELOPE_HALF_BAND_HZ, amplitude_spectrum, envelope_spectrum
from industrial_monitor.machines import FLEET
from industrial_monitor.monitor import MonitorConfig, PlantMonitor
from industrial_monitor.settings import CALIBRATED_THRESHOLD
from industrial_monitor.signals import SAMPLE_RATE_HZ
from industrial_monitor.simulator import FaultPlan, SimulatedWindow, simulate_machine

REPO = "industrial-monitor"
DETECTION_SOURCE = "results/detection.json"
ASSISTANT_SOURCE = "results/assistant-eval-fake.json"
DEMO_SOURCE = f"industrial-monitor export-landing (demo plant, seed {DEMO_SEED})"
FOCUS_MACHINE = "pump-3"
HEALTHY_WINDOW = 60
SWEEP_MAX_THRESHOLD = 10.0
FAULT_LABELS = {
    "imbalance": "Imbalance",
    "bearing_wear": "Bearing wear",
    "temperature_drift": "Temperature drift",
}
SCORE_CHANNELS = {
    "bearing_envelope": "bearing envelope z",
    "amp_1x_g": "1x amplitude z",
    "temperature_c": "temperature z",
}
ASSISTANT_METRICS = {
    "citation_precision": "Citation precision",
    "citation_recall": "Citation recall",
    "citation_validity": "Citation validity",
    "sentence_coverage": "Sentences with a citation",
    "lexical_support": "Lexical support",
    "expected_terms_rate": "Expected terms found",
    "unanswerable_declined": "Unanswerable questions declined",
    "answerable_declined": "Answerable questions declined",
}


def _percent(value: float, digits: int = 1) -> str:
    return f"{value * 100:.{digits}f}%"


def _headline(detection: dict) -> dict:
    evaluation = detection["modes"]["two_of_three"]["evaluation"]
    delays = evaluation["median_delay_windows"]
    return {
        "name": "headline",
        "type": "stats",
        "title": "Detector on the held-out simulated plant",
        "subtitle": "Threshold calibrated on a separate plant, then frozen",
        "source": DETECTION_SOURCE,
        "alt": (
            f"{_percent(evaluation['detection_rate']['all'])} of fault windows detected, "
            f"{_percent(evaluation['false_alarm_rate'], 2)} false alarms on healthy windows."
        ),
        "tiles": [
            {
                "label": "Fault windows detected",
                "value": _percent(evaluation["detection_rate"]["all"]),
                "note": f"{evaluation['fault_windows']:,} labeled fault windows",
            },
            {
                "label": "False alarms",
                "value": _percent(evaluation["false_alarm_rate"], 2),
                "note": f"{evaluation['normal_windows']:,} healthy windows",
            },
            {
                "label": "Alarm threshold (z)",
                "value": f"{evaluation['threshold']:g}",
                "note": f"dev seed {detection['config']['dev_seed']}",
            },
            {
                "label": "Median alarm delay, windows",
                "value": f"{delays['bearing_wear']:g}",
                "note": (
                    f"bearing wear; imbalance {delays['imbalance']:g}, "
                    f"temperature {delays['temperature_drift']:g}"
                ),
            },
        ],
    }


def _detection_by_fault(evaluation: dict) -> dict:
    rates = evaluation["detection_rate"]
    rows = [{"label": label, "value": rates[fault]} for fault, label in FAULT_LABELS.items()]
    rows.append({"label": "All faults", "value": rates["all"]})
    return {
        "name": "detection-by-fault",
        "type": "hbar",
        "title": "Detection rate per fault class",
        "subtitle": (
            f"Share of labeled fault windows in alarm, threshold {evaluation['threshold']:g}, "
            "2 of 3 persistence"
        ),
        "source": DETECTION_SOURCE,
        "alt": ", ".join(f"{r['label']} {_percent(r['value'])}" for r in rows) + ".",
        "format": "percent",
        "max": 1,
        "data": rows,
    }


def _false_alarm_rate(detection: dict) -> dict:
    target = detection["config"]["target_false_alarm_rate"]
    rows = []
    for mode, label in (("per_window", "Every window"), ("two_of_three", "2 of 3 windows")):
        evaluation = detection["modes"][mode]["evaluation"]
        alarms = sum(evaluation["false_alarm_hypotheses"].values())
        rate = evaluation["false_alarm_rate"]
        rows.append(
            {
                "label": label,
                "value": rate,
                "status": "pass" if rate <= target else "fail",
                "note": f"{alarms} of {evaluation['normal_windows']:,} healthy windows",
            }
        )
    return {
        "name": "false-alarm-rate",
        "type": "hbar",
        "title": "False-alarm rate on healthy windows by persistence rule",
        "subtitle": "Same threshold for both rules; the target applies to the 2 of 3 rule",
        "source": DETECTION_SOURCE,
        "alt": ", ".join(f"{r['label']} {_percent(r['value'], 2)}" for r in rows)
        + f", against a target of {_percent(target, 0)}.",
        "format": "percent",
        "threshold": {"value": target, "label": f"target {_percent(target, 0)}"},
        "data": rows,
    }


def _detection_by_severity(evaluation: dict) -> dict:
    by_severity = evaluation["detection_rate_by_severity"]
    series = [{"name": label, "values": by_severity[f]} for f, label in FAULT_LABELS.items()]
    weakest = by_severity["imbalance"][0]
    others = [
        value
        for fault in FAULT_LABELS
        for position, value in enumerate(by_severity[fault])
        if value is not None and (fault, position) != ("imbalance", 0)
    ]
    return {
        "name": "detection-by-severity",
        "type": "columns",
        "title": "Detection rate by fault severity",
        "subtitle": "Severity 0 is healthy and 1 is the end of the fault ramp",
        "source": DETECTION_SOURCE,
        "alt": (
            f"Imbalance below severity 0.25 is detected in {_percent(weakest)} of windows; "
            f"every other bin is at {_percent(min(others))} or above."
        ),
        "format": "percent",
        "max": 1,
        "categories": by_severity["bins"],
        "series": series,
    }


def _threshold_sweep(detection: dict) -> dict:
    points = [
        p
        for p in detection["modes"]["two_of_three"]["roc"]
        if p["threshold"] <= SWEEP_MAX_THRESHOLD
    ]
    return {
        "name": "threshold-sweep",
        "type": "line",
        "title": "Detection and false-alarm rate against the alarm threshold",
        "subtitle": "Held-out plant, 2 of 3 persistence; x axis is the z-score threshold",
        "source": DETECTION_SOURCE,
        "alt": (
            f"From threshold {points[0]['threshold']:.1f} to {points[-1]['threshold']:.1f} the "
            f"detection rate falls from {_percent(points[0]['detection_rate'])} to "
            f"{_percent(points[-1]['detection_rate'])} and the false-alarm rate from "
            f"{_percent(points[0]['false_alarm_rate'], 2)} to "
            f"{_percent(points[-1]['false_alarm_rate'], 2)}."
        ),
        "format": "percent",
        "min": 0,
        "max": 1,
        "x": [f"{p['threshold']:.1f}" for p in points],
        "series": [
            {"name": "Detection rate", "values": [p["detection_rate"] for p in points]},
            {"name": "False-alarm rate", "values": [p["false_alarm_rate"] for p in points]},
        ],
    }


def detection_charts(detection: dict) -> list[dict]:
    evaluation = detection["modes"]["two_of_three"]["evaluation"]
    return [
        _headline(detection),
        _detection_by_fault(evaluation),
        _false_alarm_rate(detection),
        _detection_by_severity(evaluation),
        _threshold_sweep(detection),
    ]


def pooled_peaks(
    freqs: np.ndarray, amplitude: np.ndarray, low_hz: float, high_hz: float, bin_hz: float
) -> tuple[list[str], list[float]]:
    """Largest amplitude in each frequency bin, labeled by the bin's lower edge in Hz."""
    labels, values = [], []
    for index in range(round((high_hz - low_hz) / bin_hz)):
        start = low_hz + index * bin_hz
        in_bin = amplitude[(freqs >= start) & (freqs < start + bin_hz)]
        labels.append(f"{start:g}")
        values.append(round(float(in_bin.max()), 5) if in_bin.size else 0.0)
    return labels, values


def _condition_label(window: SimulatedWindow) -> str:
    fault = window.condition.fault
    return "healthy" if fault == "none" else FAULT_LABELS[fault].lower()


def _windows_note(healthy: SimulatedWindow, faulty: SimulatedWindow) -> str:
    return f"Windows {healthy.index} and {faulty.index} (severity {faulty.condition.severity:.2f})"


def _spectrum_chart(name: str, title: str, subtitle: str, x: list[str], series: list) -> dict:
    (healthy_name, healthy), (faulty_name, faulty) = series
    peak = int(np.argmax(faulty))
    return {
        "name": name,
        "type": "line",
        "title": title,
        "subtitle": subtitle,
        "source": DEMO_SOURCE,
        "alt": (
            f"Largest bin in the faulty window is {x[peak]} Hz at {faulty[peak]:.3f} g, "
            f"against {healthy[peak]:.3f} g in the healthy window."
        ),
        "format": "decimal3",
        "x": x,
        "series": [
            {"name": healthy_name, "values": healthy},
            {"name": faulty_name, "values": faulty},
        ],
    }


def spectrum_charts() -> list[dict]:
    """Acceleration and envelope spectra of the focus machine, healthy and at the demo's end."""
    spec = FLEET[FOCUS_MACHINE]
    plan = DEMO_PLANS[FOCUS_MACHINE]
    simulated = list(simulate_machine(spec, plan, DEMO_WINDOWS, DEMO_SEED))
    chosen = (simulated[HEALTHY_WINDOW], simulated[-1])
    band = (spec.resonance_hz - ENVELOPE_HALF_BAND_HZ, spec.resonance_hz + ENVELOPE_HALF_BAND_HZ)
    raw, envelope = [], []
    for window in chosen:
        freqs, amplitude = amplitude_spectrum(window.samples_g, SAMPLE_RATE_HZ)
        x_raw, peaks = pooled_peaks(freqs, amplitude, 0.0, 600.0, 5.0)
        raw.append((_condition_label(window), peaks))
        freqs, amplitude = envelope_spectrum(window.samples_g, SAMPLE_RATE_HZ, band)
        x_env, peaks = pooled_peaks(freqs, amplitude, 0.0, 300.0, 2.5)
        envelope.append((_condition_label(window), peaks))
    machine = FOCUS_MACHINE.replace("-", " ").capitalize()
    windows = _windows_note(*chosen)
    return [
        _spectrum_chart(
            f"{FOCUS_MACHINE}-spectrum",
            f"{machine} acceleration spectrum, healthy and bearing-wear windows",
            f"{windows}; peak g per 5 Hz bin; resonance {spec.resonance_hz:g} Hz",
            x_raw,
            raw,
        ),
        _spectrum_chart(
            f"{FOCUS_MACHINE}-envelope",
            f"{machine} envelope spectrum, healthy and bearing-wear windows",
            f"{windows}; band {band[0]:g} to {band[1]:g} Hz; peak g per 2.5 Hz bin; "
            f"BPFO {spec.bpfo_hz():.1f} Hz",
            x_env,
            envelope,
        ),
    ]


def _anomaly_messages(windows: int, machine_id: str) -> list[dict]:
    bus = InProcessBus()
    PlantMonitor(bus, FLEET, MonitorConfig(site=DEMO_SITE, threshold=CALIBRATED_THRESHOLD))
    received: list[dict] = []
    topic = f"plant/{DEMO_SITE}/{machine_id}/anomaly"
    bus.subscribe(topic, lambda _topic, payload: received.append(json.loads(payload)))
    publish_demo(bus, windows=windows)
    return [message for message in received if message["channel_z"]]


def _window_ranges(windows: list[int]) -> str:
    ranges: list[list[int]] = []
    for window in windows:
        if ranges and window == ranges[-1][1] + 1:
            ranges[-1][1] = window
        else:
            ranges.append([window, window])
    return " and ".join(f"{a} to {b}" if b > a else str(a) for a, b in ranges)


def _alarm_summary(messages: list[dict], plan: FaultPlan) -> str:
    alarm_windows = [m["window"] for m in messages if m["state"] == "alarm"]
    early = [w for w in alarm_windows if w < plan.onset_window]
    late = [w for w in alarm_windows if w >= plan.onset_window]
    parts = [f"{FAULT_LABELS[plan.fault].lower()} from window {plan.onset_window}"]
    parts.append(f"alarm from window {late[0]}" if late else "no alarm after the onset")
    if early:
        parts.append(f"false alarm at windows {_window_ranges(early)}")
    return ", ".join(parts)


def _peak_sentence(bearing_scores: list[float], messages: list[dict]) -> str:
    peak = max(bearing_scores)
    window = messages[bearing_scores.index(peak)]["window"]
    return f"The bearing envelope z-score peaks at {peak:g} at window {window}."


def score_timeline(windows: int = DEMO_WINDOWS, machine_id: str = FOCUS_MACHINE) -> dict:
    """Channel z-scores of a demo machine with an injected fault, from its anomaly topic."""
    messages = _anomaly_messages(windows, machine_id)
    series = [
        {"name": label, "values": [m["channel_z"][channel] for m in messages]}
        for channel, label in SCORE_CHANNELS.items()
    ]
    threshold = messages[0]["threshold"]
    series.append({"name": f"threshold {threshold:g}", "values": [threshold] * len(messages)})
    summary = _alarm_summary(messages, DEMO_PLANS[machine_id])
    machine = machine_id.replace("-", " ").capitalize()
    return {
        "name": f"{machine_id}-scores",
        "type": "line",
        "title": f"{machine} channel z-scores from the anomaly topic",
        "subtitle": f"Demo plant: {summary}",
        "source": DEMO_SOURCE,
        "alt": f"{machine}: {summary}. {_peak_sentence(series[0]['values'], messages)}",
        "format": "decimal2",
        "x": [str(m["window"]) for m in messages],
        "series": series,
    }


def assistant_chart(assistant_eval: dict) -> dict:
    summary = assistant_eval["summary"]
    rows = [{"label": label, "value": summary[key]} for key, label in ASSISTANT_METRICS.items()]
    return {
        "name": "assistant-metrics",
        "type": "hbar",
        "title": "Maintenance assistant on the golden question set",
        "subtitle": (
            f"{summary['questions']} questions ({summary['unanswerable']} unanswerable), "
            f"model {assistant_eval['model']}, offline"
        ),
        "source": ASSISTANT_SOURCE,
        "alt": ", ".join(f"{r['label']} {_percent(r['value'])}" for r in rows) + ".",
        "format": "percent",
        "max": 1,
        "data": rows,
    }


def build_landing_data(
    detection: dict,
    assistant_eval: dict,
    revision: str,
    measured: str,
    windows: int = DEMO_WINDOWS,
) -> dict:
    charts = [
        *detection_charts(detection),
        score_timeline(windows),
        *spectrum_charts(),
        assistant_chart(assistant_eval),
    ]
    return {"meta": {"repo": REPO, "revision": revision, "measured": measured}, "charts": charts}
