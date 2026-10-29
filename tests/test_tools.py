import json
from pathlib import Path

from industrial_monitor.assistant.corpus import BM25Index, load_corpus
from industrial_monitor.assistant.tools import TOOL_SCHEMAS, Toolbox

CORPUS = Path(__file__).resolve().parents[1] / "corpus"
STATUSES = [
    {"machine_id": "pump-3", "state": "alarm", "hypothesis": "bearing_wear"},
    {"machine_id": "pump-1", "state": "normal", "hypothesis": None},
]


def toolbox() -> Toolbox:
    return Toolbox(STATUSES, BM25Index(load_corpus(CORPUS)))


def test_schemas_cover_every_tool():
    assert [schema["name"] for schema in TOOL_SCHEMAS] == [
        "get_machine_status",
        "list_alarms",
        "search_manual",
    ]


def test_machine_status_accepts_spoken_names():
    output, is_error = toolbox().call("get_machine_status", {"machine_id": "Pump 3"})
    assert not is_error
    assert json.loads(output)["hypothesis"] == "bearing_wear"


def test_unknown_machine_and_tool_are_reported_as_errors():
    output, is_error = toolbox().call("get_machine_status", {"machine_id": "pump-9"})
    assert is_error
    assert "pump-1, pump-3" in output
    _, is_error = toolbox().call("open_valve", {})
    assert is_error


def test_list_alarms_returns_only_alarming_machines():
    output, _ = toolbox().call("list_alarms", {})
    assert [s["machine_id"] for s in json.loads(output)] == ["pump-3"]


def test_search_manual_returns_cited_passages():
    output, is_error = toolbox().call("search_manual", {"query": "RP-1 trip limit vibration"})
    results = json.loads(output)
    assert not is_error
    assert results[0]["id"] == "RP-2.1"
    assert set(results[0]) == {"id", "title", "document", "text", "score", "coverage"}


def test_search_manual_rejects_an_empty_query():
    _, is_error = toolbox().call("search_manual", {"query": "  "})
    assert is_error
