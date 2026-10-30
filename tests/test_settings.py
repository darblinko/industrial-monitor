import json
import math
from pathlib import Path

import pytest

from industrial_monitor.monitor import MonitorConfig
from industrial_monitor.settings import CALIBRATED_THRESHOLD, Settings

RESULTS = Path(__file__).resolve().parents[1] / "results" / "detection.json"


def test_default_threshold_matches_the_committed_calibration():
    calibration = json.loads(RESULTS.read_text())["calibration"]
    assert calibration["threshold"] == CALIBRATED_THRESHOLD


def test_settings_read_environment_with_defaults():
    settings = Settings.from_env({"MQTT_PORT": "1884", "SITE": "north"})
    assert settings.mqtt_host == "localhost"
    assert settings.mqtt_port == 1884
    assert settings.site == "north"
    assert settings.threshold == CALIBRATED_THRESHOLD


def test_settings_reject_invalid_numbers():
    with pytest.raises(ValueError, match="MQTT_PORT"):
        Settings.from_env({"MQTT_PORT": "abc"})


@pytest.mark.parametrize("raw", ["nan", "inf", "-inf", "0", "-1"])
def test_settings_reject_a_threshold_that_is_not_finite_and_positive(raw):
    with pytest.raises(ValueError, match="DETECTOR_THRESHOLD"):
        Settings.from_env({"DETECTOR_THRESHOLD": raw})


@pytest.mark.parametrize("threshold", [math.nan, math.inf, 0.0, -2.0])
def test_monitor_config_rejects_a_threshold_that_is_not_finite_and_positive(threshold):
    with pytest.raises(ValueError, match="threshold"):
        MonitorConfig(site="t", threshold=threshold)
