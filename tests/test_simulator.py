import numpy as np
import pytest

from industrial_monitor.burst import decode_burst
from industrial_monitor.machines import FLEET
from industrial_monitor.ruuvi import decode_rawv2
from industrial_monitor.simulator import (
    FaultPlan,
    evaluation_plant,
    plant_messages,
    simulate_machine,
    to_messages,
)

PUMP = FLEET["pump-3"]


def test_plan_is_healthy_before_onset_then_ramps_to_full_severity():
    plan = FaultPlan(fault="imbalance", onset_window=10, ramp_windows=5, start_severity=0.2)
    assert plan.condition(9).fault == "none"
    assert plan.condition(10).severity == pytest.approx(0.2)
    assert plan.condition(12).severity == pytest.approx(0.6)
    assert plan.condition(14).severity == pytest.approx(1.0)
    assert plan.condition(40).severity == pytest.approx(1.0)


def test_healthy_plan_never_reports_a_fault():
    plan = FaultPlan(fault="none", onset_window=0, ramp_windows=1)
    assert {plan.condition(i).fault for i in range(50)} == {"none"}


def test_simulation_is_deterministic_per_seed_and_machine():
    plan = FaultPlan("none", 0, 1)
    first = list(simulate_machine(PUMP, plan, windows=3, seed=1))
    second = list(simulate_machine(PUMP, plan, windows=3, seed=1))
    other_machine = list(simulate_machine(FLEET["pump-1"], plan, windows=3, seed=1))
    np.testing.assert_array_equal(first[2].samples_g, second[2].samples_g)
    assert not np.array_equal(first[2].samples_g, other_machine[2].samples_g)
    assert [w.index for w in first] == [0, 1, 2]


def test_messages_carry_rawv2_status_and_vibration_burst():
    window = next(simulate_machine(PUMP, FaultPlan("none", 0, 1), windows=1, seed=2))
    messages = dict(to_messages(window, PUMP, site="demo"))

    status = decode_rawv2(messages["plant/demo/pump-3/rawv2"])
    burst = decode_burst(messages["plant/demo/pump-3/vibration"])

    assert status.mac == PUMP.mac
    assert status.temperature_c == pytest.approx(window.temperature_c, abs=0.005)
    assert burst.mac == PUMP.mac
    assert burst.sample_rate_hz == 1344
    np.testing.assert_allclose(burst.samples_g(), window.samples_g, atol=0.0005)


def test_evaluation_plant_assigns_each_fault_to_the_requested_number_of_machines():
    machines = evaluation_plant(machines_per_fault=3, baseline_windows=40, seed=9)
    faults = [plan.fault for _, plan in machines]
    assert sorted(set(faults)) == ["bearing_wear", "imbalance", "none", "temperature_drift"]
    assert all(faults.count(f) == 3 for f in set(faults))
    assert len({spec.machine_id for spec, _ in machines}) == 12
    assert all(plan.onset_window >= 60 for _, plan in machines if plan.fault != "none")


def test_evaluation_plant_balances_equipment_within_every_fault_class():
    machines = evaluation_plant(machines_per_fault=4, baseline_windows=40, seed=9)
    for fault in ("none", "imbalance", "bearing_wear", "temperature_drift"):
        equipment = [spec.equipment for spec, plan in machines if plan.fault == fault]
        assert sorted(equipment) == sorted([PUMP.equipment] * 2 + [FLEET["fan-1"].equipment] * 2)


def test_plant_messages_interleave_machines_window_by_window():
    plant = [(PUMP, FaultPlan("none", 0, 1)), (FLEET["fan-1"], FaultPlan("none", 0, 1))]
    windows = list(plant_messages(plant, windows=3, seed=4, site="s"))
    assert len(windows) == 3
    assert [topic for topic, _ in windows[0]] == [
        "plant/s/pump-3/rawv2",
        "plant/s/pump-3/vibration",
        "plant/s/fan-1/rawv2",
        "plant/s/fan-1/vibration",
    ]
