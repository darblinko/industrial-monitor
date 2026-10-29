"""Claude API adapter for the assistant loop. Requires the `claude` extra (anthropic).

Requests opt into server-side refusal fallbacks ("default" routing) through the beta Messages
API. A refusal that survives the fallback chain ends the run with stop_reason "refusal"; see
agent.run_agent. The API key is read by the SDK from ANTHROPIC_API_KEY.
"""

from typing import Any

from industrial_monitor.settings import DEFAULT_MODEL

FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_TOKENS = 8000
EFFORT = "medium"


class ClaudeModel:
    def __init__(self, model: str = DEFAULT_MODEL, client: Any = None, effort: str = EFFORT):
        if client is None:
            import anthropic

            client = anthropic.Anthropic()
        self.name = model
        self._client = client
        self._effort = effort

    def create(self, *, system: str, messages: list[dict], tools: list[dict]) -> Any:
        return self._client.beta.messages.create(
            model=self.name,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=messages,
            tools=tools,
            output_config={"effort": self._effort},
            betas=[FALLBACK_BETA],
            fallbacks="default",
        )
