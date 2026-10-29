from industrial_monitor.demo import DEMO_PLANS, run_demo


def test_demo_plant_ends_with_one_alarm_per_injected_fault():
    monitor = run_demo()
    states = {s["machine_id"]: (s["state"], s["hypothesis"]) for s in monitor.snapshot()}
    expected_alarms = {machine: (plan.fault) for machine, plan in DEMO_PLANS.items()}
    assert {m: h for m, (state, h) in states.items() if state == "alarm"} == expected_alarms
    assert expected_alarms["pump-3"] == "bearing_wear"
    assert monitor.rejected == {}


def test_publish_demo_paces_windows_with_the_given_interval():
    from industrial_monitor.bus import InProcessBus
    from industrial_monitor.demo import publish_demo

    bus = InProcessBus()
    topics = []
    bus.subscribe("plant/demo/#", lambda topic, payload: topics.append(topic))
    sleeps = []
    publish_demo(bus, windows=3, interval_s=0.5, sleep=sleeps.append)
    assert len(topics) == 3 * 6 * 2
    assert sleeps == [0.5, 0.5]
