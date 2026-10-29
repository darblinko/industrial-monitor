"""Tools the maintenance assistant can call: live plant state and manual search."""

import json
import re
from collections.abc import Callable

from industrial_monitor.assistant.corpus import BM25Index

SEARCH_RESULTS = 4
_MACHINE_NAME = re.compile(r"^\s*([a-z]+)[\s_-]*(\d+)\s*$")

TOOL_SCHEMAS: list[dict] = [
    {
        "name": "get_machine_status",
        "description": (
            "Live monitor state of one machine: alarm state, fault hypothesis, channel z-scores "
            "against its baseline, vibration velocity, housing temperature and bearing defect "
            "frequency. Call this before explaining an alarm on a named machine."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "machine_id": {"type": "string", "description": "For example pump-3 or fan-2."}
            },
            "required": ["machine_id"],
        },
    },
    {
        "name": "list_alarms",
        "description": "Every machine currently in alarm, with its live state.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "search_manual",
        "description": (
            "Search the equipment manuals and the vibration field guide. Returns the best "
            "matching passages with their IDs, which answers must cite as [ID]."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Keywords or a question."}},
            "required": ["query"],
        },
    },
]


def normalize_machine_id(name: str) -> str:
    match = _MACHINE_NAME.match(name.lower())
    return f"{match[1]}-{match[2]}" if match else name.strip().lower()


class Toolbox:
    """Executes tool calls against a plant state snapshot and a manual index."""

    def __init__(self, statuses: list[dict], index: BM25Index):
        self.schemas = TOOL_SCHEMAS
        self._statuses = {status["machine_id"]: status for status in statuses}
        self._index = index
        self._tools: dict[str, Callable[[dict], object]] = {
            "get_machine_status": self._machine_status,
            "list_alarms": self._list_alarms,
            "search_manual": self._search_manual,
        }

    def call(self, name: str, arguments: dict) -> tuple[str, bool]:
        """Returns (output, is_error). Errors are returned to the model, not raised."""
        tool = self._tools.get(name)
        if tool is None:
            return f"unknown tool {name!r}", True
        try:
            return json.dumps(tool(arguments)), False
        except (KeyError, TypeError, ValueError) as error:
            return str(error), True

    def _machine_status(self, arguments: dict) -> dict:
        machine_id = normalize_machine_id(str(arguments["machine_id"]))
        if machine_id not in self._statuses:
            known = ", ".join(sorted(self._statuses))
            raise ValueError(f"no machine {machine_id!r}; known machines: {known}")
        return self._statuses[machine_id]

    def _list_alarms(self, arguments: dict) -> list[dict]:
        return [status for status in self._statuses.values() if status["state"] == "alarm"]

    def _search_manual(self, arguments: dict) -> list[dict]:
        query = str(arguments["query"])
        if not query.strip():
            raise ValueError("query must not be empty")
        return [
            {
                "id": result.passage.passage_id,
                "title": result.passage.title,
                "document": result.passage.document,
                "text": result.passage.text,
                "score": round(result.score, 3),
                "coverage": round(result.coverage, 3),
            }
            for result in self._index.search(query, k=SEARCH_RESULTS)
        ]
