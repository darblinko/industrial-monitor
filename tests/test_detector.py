import math

import pytest

from industrial_monitor.detector import (
    MachineDetector,
    assess,
    fit_baseline,
)

MAD_TO_SIGMA = 1.4826


def observation(**overrides: float) -> dict[str, float]:
    values = {"amp_1x_g": 0.05, "bearing_envelope": 4.0, "kurtosis": 2.5, "temperature_c": 40.0}
    values.update(overrides)
    return values


def flat_baseline():
    temps = [38.0, 39.0, 40.0, 41.0, 42.0]
    return fit_baseline([observation(temperature_c=t) for t in temps])


def test_baseline_uses_median_and_mad():
    baseline = fit_baseline([observation(temperature_c=t) for t in (1.0, 2.0, 3.0, 4.0, 100.0)])
    assert baseline.center["temperature_c"] == 3.0
    assert baseline.scale["temperature_c"] == pytest.approx(MAD_TO_SIGMA)


def test_ratio_channels_are_modelled_in_log_space():
    baseline = fit_baseline([observation(amp_1x_g=a) for a in (0.04, 0.05, 0.0625)])
    assert baseline.center["amp_1x_g"] == pytest.approx(math.log(0.05))


def test_constant_channel_gets_a_scale_floor():
    baseline = fit_baseline([observation() for _ in range(5)])
    result = assess(baseline, observation(kurtosis=2.6), threshold=4.0)
    assert all(math.isfinite(z) for z in result.channel_z.values())


def test_temperature_excursion_alarms_as_temperature_drift():
    baseline = flat_baseline()  # center 40, scale 1.4826
    result = assess(baseline, observation(temperature_c=40.0 + 5 * MAD_TO_SIGMA), threshold=4.0)
    assert result.channel_z["temperature_c"] == pytest.approx(5.0)
    assert result.alarm
    assert result.hypothesis == "temperature_drift"


def test_decrease_does_not_alarm():
    result = assess(flat_baseline(), observation(temperature_c=20.0), threshold=4.0)
    assert not result.alarm
    assert result.hypothesis is None


def test_specific_pattern_wins_over_generic_impulsiveness():
    baseline = fit_baseline(
        [observation(bearing_envelope=e, kurtosis=k) for e, k in ((3, 2.4), (4, 2.5), (5, 2.6))]
    )
    result = assess(baseline, observation(bearing_envelope=40.0, kurtosis=30.0), threshold=4.0)
    assert result.channel_z["kurtosis"] > result.channel_z["bearing_envelope"]
    assert result.hypothesis == "bearing_wear"


def test_impulsiveness_alone_is_unclassified():
    baseline = fit_baseline([observation(kurtosis=k) for k in (2.4, 2.5, 2.6)])
    result = assess(baseline, observation(kurtosis=30.0), threshold=4.0)
    assert result.alarm
    assert result.hypothesis == "unclassified"


def test_machine_detector_learns_then_assesses():
    detector = MachineDetector(baseline_windows=3, threshold=4.0, persistence=(1, 1))
    for temp in (39.0, 40.0, 41.0):
        assert detector.update(observation(temperature_c=temp)) is None
    assert detector.update(observation(temperature_c=40.0)).alarm is False
    assert detector.update(observation(temperature_c=60.0)).alarm is True


def test_persistence_requires_repeated_exceedance():
    detector = MachineDetector(baseline_windows=3, threshold=4.0, persistence=(2, 3))
    for temp in (39.0, 40.0, 41.0):
        detector.update(observation(temperature_c=temp))
    assert detector.update(observation(temperature_c=60.0)).alarm is False
    assert detector.update(observation(temperature_c=40.0)).alarm is False
    assert detector.update(observation(temperature_c=60.0)).alarm is True


@pytest.mark.parametrize(
    "bad",
    [
        {"amp_1x_g": 0.0},
        {"bearing_envelope": -1.0},
        {"kurtosis": math.nan},
        {"temperature_c": math.inf},
    ],
)
def test_detector_rejects_invalid_observations_without_storing_them(bad):
    detector = MachineDetector(baseline_windows=3, threshold=3.0, persistence=(1, 1))
    detector.update(observation())
    with pytest.raises(ValueError, match=next(iter(bad))):
        detector.update(observation(**bad))
    detector.update(observation(temperature_c=41.0))
    detector.update(observation(temperature_c=39.0))
    assert not detector.learning
    assert detector.update(observation()) is not None
