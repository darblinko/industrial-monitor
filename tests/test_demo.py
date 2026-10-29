from industrial_monitor.demo import DEMO_PLANS, run_demo


def test_demo_plant_ends_with_one_alarm_per_injected_fault():
    monitor = run_demo()
    states = {s["machine_id"]: (s["state"], s["hypothesis"]) for s in monitor.snapshot()}
    expected_alarms = {machine: (plan.fault) for machine, plan in DEMO_PLANS.items()}
    assert {m: h for m, (state, h) in states.items() if state == "alarm"} == expected_alarms
    assert expected_alarms["pump-3"] == "bearing_wear"
    assert monitor.rejected == {}
