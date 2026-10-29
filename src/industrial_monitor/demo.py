"""Demo plant: the six-machine fleet with three injected faults, replayed in process."""

from industrial_monitor.bus import InProcessBus
from industrial_monitor.machines import FLEET
from industrial_monitor.monitor import MonitorConfig, PlantMonitor
from industrial_monitor.settings import CALIBRATED_THRESHOLD
from industrial_monitor.simulator import FaultPlan, plant_messages

DEMO_SITE = "demo"
DEMO_SEED = 7
DEMO_WINDOWS = 160
DEMO_PLANS = {
    "pump-3": FaultPlan("bearing_wear", onset_window=70, ramp_windows=80),
    "pump-4": FaultPlan("temperature_drift", onset_window=90, ramp_windows=60),
    "fan-2": FaultPlan("imbalance", onset_window=80, ramp_windows=70),
}
HEALTHY_PLAN = FaultPlan("none", onset_window=0, ramp_windows=1)


def demo_plant() -> list:
    return [(spec, DEMO_PLANS.get(machine_id, HEALTHY_PLAN)) for machine_id, spec in FLEET.items()]


def run_demo(
    windows: int = DEMO_WINDOWS, seed: int = DEMO_SEED, threshold: float = CALIBRATED_THRESHOLD
) -> PlantMonitor:
    bus = InProcessBus()
    monitor = PlantMonitor(bus, FLEET, MonitorConfig(site=DEMO_SITE, threshold=threshold))
    for messages in plant_messages(demo_plant(), windows, seed, DEMO_SITE):
        for topic, payload in messages:
            bus.publish(topic, payload)
    return monitor
