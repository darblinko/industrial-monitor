import json

from industrial_monitor.bus import InProcessBus
from industrial_monitor.machines import FLEET
from industrial_monitor.monitor import MonitorConfig, PlantMonitor
from industrial_monitor.ruuvi import decode_rawv2
from industrial_monitor.simulator import FaultPlan, plant_messages

CONFIG = MonitorConfig(site="t", threshold=3.0, persistence=(2, 3), baseline_windows=20)
PUMP_3 = FLEET["pump-3"]
HEALTHY_PUMP = FLEET["pump-1"]


def run_plant(plant, windows, seed=3):
    bus = InProcessBus()
    anomalies = []
    bus.subscribe("plant/t/+/anomaly", lambda topic, payload: anomalies.append(payload))
    monitor = PlantMonitor(bus, {spec.machine_id: spec for spec, _ in plant}, CONFIG)
    for messages in plant_messages(plant, windows, seed, site="t"):
        for topic, payload in messages:
            bus.publish(topic, payload)
    return monitor, anomalies


def test_monitor_reports_learning_until_the_baseline_is_complete():
    monitor, anomalies = run_plant([(PUMP_3, FaultPlan("none", 0, 1))], windows=10)
    assert monitor.status("pump-3")["state"] == "learning"
    assert monitor.status("pump-3")["windows"] == 10
    assert len(anomalies) == 10


def test_monitor_flags_bearing_fault_and_publishes_anomaly_state():
    plant = [
        (PUMP_3, FaultPlan("bearing_wear", onset_window=30, ramp_windows=20)),
        (HEALTHY_PUMP, FaultPlan("none", 0, 1)),
    ]
    monitor, anomalies = run_plant(plant, windows=60)
    status = monitor.status("pump-3")
    assert status["state"] == "alarm"
    assert status["hypothesis"] == "bearing_wear"
    assert status["alarm_since_window"] >= 30
    assert status["bpfo_hz"] == round(PUMP_3.bpfo_hz(), 2)
    assert [s["machine_id"] for s in monitor.alarms()] == ["pump-3"]
    pump_3_updates = [u for u in map(json.loads, anomalies) if u["machine_id"] == "pump-3"]
    assert len(pump_3_updates) == 60
    assert pump_3_updates[-1]["state"] == "alarm"


def test_monitor_counts_rejected_messages():
    bus = InProcessBus()
    monitor = PlantMonitor(bus, {"pump-3": PUMP_3}, CONFIG)
    bus.publish("plant/t/pump-3/rawv2", b"not a payload")
    bus.publish("plant/t/pump-9/rawv2", b"")
    bus.publish("plant/t/pump-3/vibration", b"\x01")
    assert monitor.rejected == {"rawv2_decode": 1, "unknown_machine": 1, "burst_decode": 1}


def test_monitor_skips_vibration_until_a_temperature_is_known():
    plant = [(PUMP_3, FaultPlan("none", 0, 1))]
    bus = InProcessBus()
    monitor = PlantMonitor(bus, {"pump-3": PUMP_3}, CONFIG)
    windows = list(plant_messages(plant, windows=2, seed=1, site="t"))
    for messages in windows:
        bus.publish(*messages[1])
    assert monitor.rejected == {"no_temperature": 2}
    assert monitor.status("pump-3")["windows"] == 0

    topic, status_payload = windows[-1][0]
    bus.publish(topic, status_payload)
    expected = round(decode_rawv2(status_payload).temperature_c, 2)
    assert monitor.status("pump-3")["temperature_c"] == expected


def test_snapshot_file_round_trip(tmp_path):
    from industrial_monitor.monitor import load_snapshot, save_snapshot

    monitor, _ = run_plant([(PUMP_3, FaultPlan("none", 0, 1))], windows=3)
    path = tmp_path / "state" / "plant.json"
    save_snapshot(path, monitor.snapshot())
    assert load_snapshot(path) == monitor.snapshot()
    assert [p.name for p in path.parent.iterdir()] == ["plant.json"]


def _burst_topic_and_payload(machine, sequence, samples_g, rate_hz=1344):
    import numpy as np

    from industrial_monitor.burst import VibrationBurst, encode_burst

    burst = VibrationBurst.from_g(machine.mac, sequence, rate_hz, np.asarray(samples_g))
    return f"plant/t/{machine.machine_id}/vibration", encode_burst(burst)


def _healthy_monitor(windows):
    plant = [(PUMP_3, FaultPlan("none", 0, 1))]
    bus = InProcessBus()
    monitor = PlantMonitor(bus, {"pump-3": PUMP_3}, CONFIG)
    stream = list(plant_messages(plant, windows=windows, seed=5, site="t"))
    return bus, monitor, stream


def test_invalid_bursts_are_rejected_without_entering_the_baseline():
    bus, monitor, stream = _healthy_monitor(windows=CONFIG.baseline_windows + 5)
    bus.publish(*stream[0][0])
    bus.publish(*_burst_topic_and_payload(PUMP_3, 900, [0.1]))
    bus.publish(*_burst_topic_and_payload(PUMP_3, 901, [0.1] * 1024))
    bus.publish(*_burst_topic_and_payload(PUMP_3, 902, [0.0, 0.1] * 512, rate_hz=0))
    bus.publish(*_burst_topic_and_payload(PUMP_3, 903, [0.0, 0.1] * 512, rate_hz=200))
    assert monitor.rejected == {
        "burst_too_short": 1,
        "flat_signal": 1,
        "burst_decode": 1,
        "sample_rate_too_low": 1,
    }
    assert monitor.status("pump-3")["windows"] == 0
    for messages in stream:
        for topic, payload in messages:
            bus.publish(topic, payload)
    status = monitor.status("pump-3")
    assert status["state"] == "normal"
    assert status["windows"] == len(stream)


def test_a_burst_with_an_empty_envelope_band_is_rejected_as_invalid():
    bus, monitor, stream = _healthy_monitor(windows=1)
    bus.publish(*stream[0][0])
    bus.publish(*_burst_topic_and_payload(PUMP_3, 0, [0.0, 0.1] * 512))
    assert monitor.rejected == {"invalid_features": 1}
    assert monitor.status("pump-3")["windows"] == 0
