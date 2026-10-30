import os
import threading

import paho.mqtt.client as mqtt
import pytest
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.reasoncodes import ReasonCode

from industrial_monitor.mqtt_bus import MqttBus


def test_incoming_messages_are_dispatched_by_topic_filter():
    bus = MqttBus("localhost", 1883)
    received = []
    bus.subscribe("plant/+/pump-1/rawv2", lambda topic, payload: received.append((topic, payload)))
    message = mqtt.MQTTMessage(topic=b"plant/a/pump-1/rawv2")
    message.payload = b"\x05"
    bus._on_message(None, None, message)
    other = mqtt.MQTTMessage(topic=b"plant/a/pump-1/vibration")
    bus._on_message(None, None, other)
    assert received == [("plant/a/pump-1/rawv2", b"\x05")]


def test_a_failing_handler_is_logged_and_does_not_stop_dispatch(caplog):
    bus = MqttBus("localhost", 1883)
    received = []

    def failing(topic, payload):
        raise RuntimeError("boom")

    bus.subscribe("t", failing)
    bus.subscribe("t", lambda topic, payload: received.append(payload))
    message = mqtt.MQTTMessage(topic=b"t")
    message.payload = b"x"
    bus._on_message(None, None, message)
    assert received == [b"x"]
    assert "handler for t failed" in caplog.text


def _bus_with_acknowledged_subscriptions(monkeypatch, reason_codes):
    bus = MqttBus("localhost", 1883)
    mids = iter(range(1, 100))
    monkeypatch.setattr(
        bus._client, "subscribe", lambda pattern, qos: (mqtt.MQTT_ERR_SUCCESS, next(mids))
    )
    bus._connected = True
    for pattern in reason_codes:
        bus.subscribe(pattern, lambda topic, payload: None)
    for mid, code in enumerate(reason_codes.values(), start=1):
        bus._on_subscribe(None, None, mid, [ReasonCode(PacketTypes.SUBACK, identifier=code)], None)
    return bus


def test_a_rejected_subscription_fails_the_wait_with_its_topic_and_reason(monkeypatch):
    bus = _bus_with_acknowledged_subscriptions(
        monkeypatch, {"plant/demo/+/rawv2": 0x01, "plant/demo/+/vibration": 0x87}
    )
    with pytest.raises(ConnectionError, match=r"plant/demo/\+/vibration: Not authorized"):
        bus.wait_for_subscriptions(timeout_s=0.1)


def test_granted_subscriptions_pass_the_wait(monkeypatch):
    bus = _bus_with_acknowledged_subscriptions(monkeypatch, {"a/+": 0x01, "b/#": 0x00})
    bus.wait_for_subscriptions(timeout_s=0.1)


@pytest.mark.broker
@pytest.mark.skipif("MQTT_HOST" not in os.environ, reason="set MQTT_HOST to run broker tests")
def test_round_trip_through_a_broker():
    host, port = os.environ["MQTT_HOST"], int(os.environ.get("MQTT_PORT", "1883"))
    arrived = threading.Event()
    received = []

    def on_message(topic, payload):
        received.append((topic, payload))
        arrived.set()

    with MqttBus(host, port) as subscriber, MqttBus(host, port) as publisher:
        subscriber.subscribe("test/industrial-monitor/+", on_message)
        subscriber.wait_for_subscriptions()
        publisher.publish("test/industrial-monitor/a", b"\x01\x02")
        assert arrived.wait(5.0)
    assert received == [("test/industrial-monitor/a", b"\x01\x02")]
