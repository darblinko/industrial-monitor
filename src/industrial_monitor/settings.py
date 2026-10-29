"""Runtime configuration from environment variables. See .env.example."""

import os
from collections.abc import Mapping
from dataclasses import dataclass

# Calibrated by `industrial-monitor evaluate-detector`; recorded in results/detection.json.
CALIBRATED_THRESHOLD = 2.55
DEFAULT_MODEL = "claude-opus-5-5"


def _number(env: Mapping[str, str], name: str, default: str, kind: type) -> int | float:
    raw = env.get(name, default)
    try:
        return kind(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be a {kind.__name__}, got {raw!r}") from error


@dataclass(frozen=True)
class Settings:
    mqtt_host: str
    mqtt_port: int
    site: str
    threshold: float
    claude_model: str
    anthropic_api_key: str | None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        env = os.environ if env is None else env
        return cls(
            mqtt_host=env.get("MQTT_HOST", "localhost"),
            mqtt_port=int(_number(env, "MQTT_PORT", "1883", int)),
            site=env.get("SITE", "demo"),
            threshold=float(_number(env, "DETECTOR_THRESHOLD", str(CALIBRATED_THRESHOLD), float)),
            claude_model=env.get("CLAUDE_MODEL", DEFAULT_MODEL),
            anthropic_api_key=env.get("ANTHROPIC_API_KEY") or None,
        )
