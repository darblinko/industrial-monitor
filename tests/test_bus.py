import pytest

from industrial_monitor.bus import InProcessBus, topic_matches


@pytest.mark.parametrize(
    ("pattern", "topic", "expected"),
    [
        ("plant/a/pump-1/rawv2", "plant/a/pump-1/rawv2", True),
        ("plant/a/+/rawv2", "plant/a/pump-1/rawv2", True),
        ("plant/a/+/rawv2", "plant/a/pump-1/vibration", False),
        ("plant/a/+", "plant/a/pump-1/rawv2", False),
        ("plant/#", "plant/a/pump-1/rawv2", True),
        ("plant/a/#", "plant/a", True),
        ("plant/b/#", "plant/a/pump-1", False),
        ("#", "plant/a", True),
    ],
)
def test_topic_matching_follows_mqtt_wildcards(pattern, topic, expected):
    assert topic_matches(pattern, topic) is expected


def test_in_process_bus_delivers_to_matching_subscribers_only():
    bus = InProcessBus()
    received = []
    bus.subscribe("plant/a/+/rawv2", lambda topic, payload: received.append((topic, payload)))
    bus.publish("plant/a/pump-1/rawv2", b"\x05")
    bus.publish("plant/a/pump-1/vibration", b"\x01")
    assert received == [("plant/a/pump-1/rawv2", b"\x05")]


def test_in_process_bus_allows_publishing_from_a_handler():
    bus = InProcessBus()
    received = []
    bus.subscribe("in", lambda topic, payload: bus.publish("out", payload))
    bus.subscribe("out", lambda topic, payload: received.append(payload))
    bus.publish("in", b"x")
    assert received == [b"x"]
