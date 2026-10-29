"""Deterministic offline stand-in for the language model: a scripted extractive policy.

This is not a language model. It follows a fixed plan (read the machine state, search the
manual, copy the best matching sentences with their citations) so the agent loop, tools and
evaluation run offline and give a reproducible baseline for a real model to be compared with.
"""

import json
import re
from dataclasses import dataclass

from industrial_monitor.assistant.agent import DECLINE
from industrial_monitor.assistant.corpus import tokenize

MIN_COVERAGE = 0.5
PASSAGES_PER_ANSWER = 2
SENTENCES_PER_PASSAGE = 2
HYPOTHESIS_QUERIES = {
    "bearing_wear": "responding to a bearing defect indication outer race",
    "imbalance": "imbalance shaft frequency 1x",
    "temperature_drift": "elevated bearing housing temperature",
    "unclassified": "unclassified impulsive alarm kurtosis",
}
CHANNEL_NAMES = {
    "amp_1x_g": "1x amplitude",
    "bearing_envelope": "bearing envelope",
    "temperature_c": "housing temperature",
    "kurtosis": "kurtosis",
}
_MACHINE = re.compile(r"\b(pump|fan)[\s-]*(\d+)\b", re.IGNORECASE)
_ALARM_LIST = re.compile(r"\bwhich machines\b|\bright now\b", re.IGNORECASE)
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+")
_EQUIPMENT = re.compile(r"\b(RP|RF)-1\b", re.IGNORECASE)
GENERAL_PREFIX = "VG-"


@dataclass(frozen=True)
class TextBlock:
    text: str
    type: str = "text"


@dataclass(frozen=True)
class ToolUseBlock:
    id: str
    name: str
    input: dict
    type: str = "tool_use"


@dataclass(frozen=True)
class FakeMessage:
    content: list
    stop_reason: str


def _history(messages: list[dict]) -> list[tuple[str, dict, str, bool]]:
    """(tool name, input, output, is_error) for every completed tool call, in order."""
    uses: dict[str, ToolUseBlock] = {}
    history = []
    for message in messages[1:]:
        for block in message["content"]:
            if message["role"] == "assistant" and block.type == "tool_use":
                uses[block.id] = block
            elif message["role"] == "user" and block["type"] == "tool_result":
                use = uses[block["tool_use_id"]]
                history.append(
                    (use.name, use.input, block["content"], block.get("is_error", False))
                )
    return history


def _cite(sentence: str, source: str) -> str:
    return f"{sentence.rstrip('.')} [{source}]."


def _state_sentences(status: dict) -> list[str]:
    machine, source = status["machine_id"], f"status:{status['machine_id']}"
    channel, z = max(status["channel_z"].items(), key=lambda item: item[1], default=("-", 0.0))
    if status["state"] == "learning":
        return [_cite(f"{machine} is still learning its baseline and has no alarm state", source)]
    if status["state"] != "alarm":
        return [
            _cite(
                f"{machine} is in state normal; the largest channel deviation is "
                f"{CHANNEL_NAMES.get(channel, channel)} at z = {z}",
                source,
            )
        ]
    hypothesis = status["hypothesis"].replace("_", " ")
    return [
        _cite(
            f"{machine} ({status['equipment']}) is in alarm since window "
            f"{status['alarm_since_window']} with hypothesis {hypothesis}; the "
            f"{CHANNEL_NAMES.get(channel, channel)} channel is at z = {z} against its baseline",
            source,
        ),
        _cite(
            f"Vibration velocity is {status['velocity_rms_mm_s']} mm/s RMS and housing "
            f"temperature is {status['temperature_c']} C",
            source,
        ),
    ]


def _best_sentences(text: str, query: str, count: int) -> list[str]:
    sentences = _SENTENCE_BREAK.split(text)
    terms = set(tokenize(query))
    ranked = sorted(
        range(len(sentences)), key=lambda i: (-len(terms & set(tokenize(sentences[i]))), i)
    )
    return [sentences[i] for i in sorted(ranked[:count])]


def _matches_equipment(passage_id: str, query: str) -> bool:
    """Keep passages from the manual of the equipment named in the query, plus the guide."""
    equipment = _EQUIPMENT.search(query)
    if equipment is None or passage_id.startswith(GENERAL_PREFIX):
        return True
    return passage_id.startswith(equipment[1].upper() + "-")


def _compose(statuses: list[dict], query: str, results: list[dict], direct: bool) -> str:
    chosen = [
        r
        for r in results
        if _matches_equipment(r["id"], query) and (not direct or r["coverage"] >= MIN_COVERAGE)
    ]
    if not chosen:
        return DECLINE
    lines = [sentence for status in statuses for sentence in _state_sentences(status)]
    for result in chosen[:PASSAGES_PER_ANSWER]:
        for sentence in _best_sentences(result["text"], query, SENTENCES_PER_PASSAGE):
            lines.append(_cite(sentence, result["id"]))
    return " ".join(lines)


def _first_call(question: str) -> ToolUseBlock:
    machine = _MACHINE.search(question)
    if machine:
        machine_id = f"{machine[1].lower()}-{machine[2]}"
        return ToolUseBlock("call-1", "get_machine_status", {"machine_id": machine_id})
    if _ALARM_LIST.search(question):
        return ToolUseBlock("call-1", "list_alarms", {})
    return ToolUseBlock("call-1", "search_manual", {"query": question})


def _alarm_list_answer(alarms: list[dict]) -> str:
    if not alarms:
        return "No machine is in alarm."
    return " ".join(
        _cite(
            f"{a['machine_id']} is in alarm with hypothesis {a['hypothesis'].replace('_', ' ')} "
            f"since window {a['alarm_since_window']}",
            f"status:{a['machine_id']}",
        )
        for a in alarms
    )


def _next_action(question: str, history: list[tuple[str, dict, str, bool]]) -> ToolUseBlock | str:
    if not history:
        return _first_call(question)
    name, arguments, output, is_error = history[-1]
    if is_error:
        return f"The tool {name} returned an error: {output}"
    if name == "list_alarms":
        return _alarm_list_answer(json.loads(output))
    if name == "get_machine_status":
        status = json.loads(output)
        if status["state"] != "alarm":
            return " ".join(_state_sentences(status))
        query = f"{status['equipment']} {HYPOTHESIS_QUERIES[status['hypothesis']]} {question}"
        return ToolUseBlock(f"call-{len(history) + 1}", "search_manual", {"query": query})
    statuses = [json.loads(out) for tool, _, out, err in history if tool == "get_machine_status"]
    return _compose(statuses, arguments["query"], json.loads(output), direct=not statuses)


class FakeModel:
    name = "fake-extractive"

    def create(self, *, system: str, messages: list[dict], tools: list[dict]) -> FakeMessage:
        action = _next_action(messages[0]["content"], _history(messages))
        if isinstance(action, ToolUseBlock):
            return FakeMessage([action], "tool_use")
        return FakeMessage([TextBlock(action)], "end_turn")
