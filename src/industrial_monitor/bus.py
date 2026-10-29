"""Message bus interface with an in-process implementation for tests and the offline demo."""

from collections.abc import Callable
from typing import Protocol

Handler = Callable[[str, bytes], None]


class Bus(Protocol):
    def publish(self, topic: str, payload: bytes) -> None: ...

    def subscribe(self, pattern: str, handler: Handler) -> None: ...


def topic_matches(pattern: str, topic: str) -> bool:
    """MQTT topic filter matching: '+' is one level, a trailing '#' is any remaining levels."""
    pattern_levels = pattern.split("/")
    topic_levels = topic.split("/")
    for position, level in enumerate(pattern_levels):
        if level == "#":
            return True
        if position >= len(topic_levels):
            return False
        if level not in ("+", topic_levels[position]):
            return False
    return len(pattern_levels) == len(topic_levels)


class InProcessBus:
    """Synchronous delivery to every matching subscriber, in subscription order."""

    def __init__(self) -> None:
        self._subscriptions: list[tuple[str, Handler]] = []

    def subscribe(self, pattern: str, handler: Handler) -> None:
        self._subscriptions.append((pattern, handler))

    def publish(self, topic: str, payload: bytes) -> None:
        for pattern, handler in list(self._subscriptions):
            if topic_matches(pattern, topic):
                handler(topic, payload)
