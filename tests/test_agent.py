from dataclasses import dataclass, field

from industrial_monitor.assistant.agent import run_agent


@dataclass(frozen=True)
class Text:
    text: str
    type: str = "text"


@dataclass(frozen=True)
class ToolUse:
    id: str
    name: str
    input: dict
    type: str = "tool_use"


@dataclass(frozen=True)
class Reply:
    content: list
    stop_reason: str


@dataclass
class ScriptedModel:
    replies: list
    name: str = "scripted"
    requests: list = field(default_factory=list)

    def create(self, *, system, messages, tools):
        self.requests.append([dict(m) for m in messages])
        return self.replies[len(self.requests) - 1]


class EchoToolbox:
    def __init__(self):
        self.schemas = []

    def call(self, name, arguments):
        if name == "fail":
            return "bad input", True
        return f"{name}:{arguments}", False


def test_tool_results_are_fed_back_until_the_model_answers():
    model = ScriptedModel(
        [
            Reply([Text("checking"), ToolUse("t1", "list_alarms", {})], "tool_use"),
            Reply([Text("pump-3 [status:pump-3]")], "end_turn"),
        ]
    )
    run = run_agent("which alarms?", model, EchoToolbox())
    assert run.answer == "pump-3 [status:pump-3]"
    assert run.stop_reason == "end_turn"
    assert [(c.name, c.output) for c in run.tool_calls] == [("list_alarms", "list_alarms:{}")]
    second = model.requests[1]
    assert second[1]["content"] == model.replies[0].content
    assert second[2]["content"] == [
        {"type": "tool_result", "tool_use_id": "t1", "content": "list_alarms:{}"}
    ]


def test_tool_errors_are_flagged_to_the_model():
    model = ScriptedModel(
        [Reply([ToolUse("t1", "fail", {})], "tool_use"), Reply([Text("ok")], "end_turn")]
    )
    run = run_agent("q", model, EchoToolbox())
    assert model.requests[1][2]["content"][0]["is_error"] is True
    assert run.tool_calls[0].is_error


def test_refusal_ends_the_run_without_an_answer():
    run = run_agent("q", ScriptedModel([Reply([], "refusal")]), EchoToolbox())
    assert run.stop_reason == "refusal"
    assert run.answer == ""


def test_turn_limit_stops_a_model_that_never_answers():
    looping = [Reply([ToolUse(f"t{i}", "list_alarms", {})], "tool_use") for i in range(3)]
    run = run_agent("q", ScriptedModel(looping), EchoToolbox(), max_turns=3)
    assert run.stop_reason == "max_turns"
    assert len(run.tool_calls) == 3
