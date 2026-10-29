"""Maintenance assistant: a manual tool-use loop over the plant state and manual tools.

The loop is written out rather than using the SDK tool runner so that the same code runs
against the offline fake model and the Claude API, and so every tool call is recorded for
the groundedness metrics in evaluation.py.
"""

from dataclasses import dataclass
from typing import Any, Protocol

DECLINE = "The manual does not cover this."
SYSTEM_PROMPT = f"""You are the maintenance assistant for a plant of RP-1 centrifugal pumps \
and RF-1 centrifugal fans. Answer questions from technicians about alarms, limits and \
procedures.

Use the tools. get_machine_status and list_alarms give the live monitor state. search_manual \
searches the equipment manuals and the vibration field guide; search before stating any \
limit, frequency or procedure.

Rules for the answer:
- End every sentence with at least one citation: a manual passage as [RP-3.2], or the live \
state of a machine as [status:pump-3].
- Cite only passage IDs that search_manual returned in this conversation, and only machines \
whose state you retrieved.
- Do not state limits, frequencies or procedures that are not in a retrieved passage.
- If the retrieved passages do not answer the question, reply with exactly: {DECLINE}
- Plain text, no headings or lists, at most 8 sentences."""
MAX_TURNS = 8


class Model(Protocol):
    name: str

    def create(self, *, system: str, messages: list[dict], tools: list[dict]) -> Any: ...


class Tools(Protocol):
    schemas: list[dict]

    def call(self, name: str, arguments: dict) -> tuple[str, bool]: ...


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict
    output: str
    is_error: bool


@dataclass(frozen=True)
class AgentRun:
    question: str
    answer: str
    stop_reason: str
    tool_calls: list[ToolCall]
    turns: int


def _text(content: list) -> str:
    return "\n".join(block.text for block in content if block.type == "text").strip()


def _run_tools(blocks: list, toolbox: Tools, calls: list[ToolCall]) -> list[dict]:
    results = []
    for block in blocks:
        output, is_error = toolbox.call(block.name, dict(block.input))
        calls.append(ToolCall(block.name, dict(block.input), output, is_error))
        result = {"type": "tool_result", "tool_use_id": block.id, "content": output}
        if is_error:
            result["is_error"] = True
        results.append(result)
    return results


def run_agent(question: str, model: Model, toolbox: Tools, max_turns: int = MAX_TURNS) -> AgentRun:
    messages: list[dict] = [{"role": "user", "content": question}]
    calls: list[ToolCall] = []
    for turn in range(1, max_turns + 1):
        response = model.create(system=SYSTEM_PROMPT, messages=messages, tools=toolbox.schemas)
        if response.stop_reason == "refusal":
            return AgentRun(question, "", "refusal", calls, turn)
        messages.append({"role": "assistant", "content": response.content})
        tool_uses = [block for block in response.content if block.type == "tool_use"]
        if response.stop_reason != "tool_use" or not tool_uses:
            return AgentRun(question, _text(response.content), response.stop_reason, calls, turn)
        messages.append({"role": "user", "content": _run_tools(tool_uses, toolbox, calls)})
    return AgentRun(question, "", "max_turns", calls, max_turns)
