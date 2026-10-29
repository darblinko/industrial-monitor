"""MQTT implementation of the Bus interface, using paho-mqtt 2.x.

Subscriptions are kept locally and renewed on every (re)connect. Messages are dispatched on
the paho network thread, so handlers run one at a time.
"""

import logging
import threading
import time

import paho.mqtt.client as mqtt

from industrial_monitor.bus import Handler, topic_matches

logger = logging.getLogger(__name__)
QOS = 1


class MqttBus:
    def __init__(self, host: str, port: int, keepalive_s: int = 30):
        self._host, self._port, self._keepalive_s = host, port, keepalive_s
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.on_subscribe = self._on_subscribe
        self._state = threading.Condition()
        self._subscriptions: list[tuple[str, Handler]] = []
        self._pending_subscriptions: set[int] = set()
        self._connected = False
        self._unacknowledged: list[mqtt.MQTTMessageInfo] = []

    def __enter__(self) -> "MqttBus":
        self.connect()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def connect(self, timeout_s: float = 10.0) -> None:
        self._client.connect(self._host, self._port, self._keepalive_s)
        self._client.loop_start()
        with self._state:
            if not self._state.wait_for(lambda: self._connected, timeout_s):
                self.close()
                raise ConnectionError(f"no connection to {self._host}:{self._port}")

    def close(self, flush_timeout_s: float = 10.0) -> None:
        """Wait for outstanding QoS 1 publishes, then disconnect."""
        deadline = time.monotonic() + flush_timeout_s
        for info in self._unacknowledged:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not self._wait(info, remaining):
                logger.error("disconnecting with unacknowledged messages")
                break
        self._client.disconnect()
        self._client.loop_stop()

    @staticmethod
    def _wait(info: mqtt.MQTTMessageInfo, timeout_s: float) -> bool:
        try:
            info.wait_for_publish(timeout_s)
        except RuntimeError:
            return False
        return info.is_published()

    def _request(self, pattern: str) -> None:
        """Send SUBSCRIBE. The caller holds self._state."""
        result, mid = self._client.subscribe(pattern, qos=QOS)
        if result != mqtt.MQTT_ERR_SUCCESS:
            raise ConnectionError(f"subscribe to {pattern} failed: {mqtt.error_string(result)}")
        self._pending_subscriptions.add(mid)

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        if reason_code.is_failure:
            logger.error(
                "broker %s:%s refused the connection: %s", self._host, self._port, reason_code
            )
            return
        with self._state:
            for pattern in dict.fromkeys(pattern for pattern, _ in self._subscriptions):
                self._request(pattern)
            self._connected = True
            self._state.notify_all()

    def _on_subscribe(self, client, userdata, mid, reason_codes, properties) -> None:
        for code in reason_codes:
            if code.is_failure:
                logger.error("broker rejected subscription %s: %s", mid, code)
        with self._state:
            self._pending_subscriptions.discard(mid)
            self._state.notify_all()

    def subscribe(self, pattern: str, handler: Handler) -> None:
        with self._state:
            self._subscriptions.append((pattern, handler))
            if self._connected:
                self._request(pattern)

    def wait_for_subscriptions(self, timeout_s: float = 5.0) -> None:
        with self._state:
            if not self._state.wait_for(lambda: not self._pending_subscriptions, timeout_s):
                raise TimeoutError("broker did not acknowledge every subscription")

    def publish(self, topic: str, payload: bytes) -> None:
        info = self._client.publish(topic, payload, qos=QOS)
        # While reconnecting, paho queues QoS 1 messages and reports MQTT_ERR_NO_CONN.
        if info.rc not in (mqtt.MQTT_ERR_SUCCESS, mqtt.MQTT_ERR_NO_CONN):
            raise ConnectionError(f"publish to {topic} failed: {mqtt.error_string(info.rc)}")
        if len(self._unacknowledged) >= 1000:
            self._unacknowledged = [i for i in self._unacknowledged if not i.is_published()]
        self._unacknowledged.append(info)

    def _on_message(self, client, userdata, message: mqtt.MQTTMessage) -> None:
        with self._state:
            handlers = [h for p, h in self._subscriptions if topic_matches(p, message.topic)]
        for handler in handlers:
            try:
                handler(message.topic, message.payload)
            except Exception:
                logger.exception("handler for %s failed", message.topic)
