from types import SimpleNamespace

from industrial_monitor.assistant.claude_model import FALLBACK_BETA, ClaudeModel


class RecordingMessages:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(content=[], stop_reason="end_turn")


def test_requests_use_the_configured_model_fallbacks_and_auto_tool_choice():
    messages = RecordingMessages()
    client = SimpleNamespace(beta=SimpleNamespace(messages=messages))
    model = ClaudeModel(model="claude-opus-5-5", client=client)
    model.create(system="s", messages=[{"role": "user", "content": "q"}], tools=[{"name": "t"}])
    request = messages.calls[0]
    assert request["model"] == "claude-opus-5-5"
    assert request["betas"] == [FALLBACK_BETA]
    assert request["fallbacks"] == "default"
    assert request["output_config"] == {"effort": "medium"}
    assert "tool_choice" not in request
    assert model.name == "claude-opus-5-5"


def test_sdk_serializes_the_request_and_parses_tool_use(monkeypatch):
    anthropic = __import__("pytest").importorskip("anthropic")
    import json

    import httpx2 as httpx

    from industrial_monitor.assistant.agent import run_agent

    replies = [
        {
            "content": [{"type": "tool_use", "id": "toolu_1", "name": "list_alarms", "input": {}}],
            "stop_reason": "tool_use",
        },
        {
            "content": [{"type": "text", "text": "pump-3 [status:pump-3]."}],
            "stop_reason": "end_turn",
        },
    ]
    sent = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append((request.headers, json.loads(request.content)))
        reply = replies[len(sent) - 1]
        body = {
            "id": f"msg_{len(sent)}",
            "type": "message",
            "role": "assistant",
            "model": "claude-opus-5-5",
            "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 5},
            **reply,
        }
        return httpx.Response(200, json=body)

    client = anthropic.Anthropic(
        api_key="test", http_client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    toolbox = SimpleNamespace(schemas=[], call=lambda name, arguments: ("[]", False))
    run = run_agent("which alarms?", ClaudeModel(client=client), toolbox)

    assert run.answer == "pump-3 [status:pump-3]."
    headers, body = sent[0]
    assert FALLBACK_BETA in headers["anthropic-beta"]
    assert body["fallbacks"] == "default"
    second = sent[1][1]["messages"]
    assert second[1]["content"][0]["type"] == "tool_use"
    assert second[2]["content"][0]["tool_use_id"] == "toolu_1"
