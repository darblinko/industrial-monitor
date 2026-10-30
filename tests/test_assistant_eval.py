import json
from pathlib import Path

import pytest

from industrial_monitor.assistant.agent import DECLINE, AgentRun, ToolCall
from industrial_monitor.assistant.corpus import load_corpus
from industrial_monitor.assistant.evaluation import (
    GoldenQuestion,
    load_golden,
    parse_citations,
    score_run,
    summarize,
)

GOLDEN = Path(__file__).resolve().parents[1] / "eval" / "golden.jsonl"
PASSAGE = {"id": "RP-2.1", "text": "The trip limit is 7.1 mm/s RMS."}
SEARCH = ToolCall("search_manual", {"query": "trip"}, json.dumps([PASSAGE]), False)
STATUS = ToolCall(
    "get_machine_status", {"machine_id": "pump-3"}, json.dumps({"machine_id": "pump-3"}), False
)


def question(**overrides):
    fields = {
        "id": "q",
        "question": "What is the trip limit?",
        "machine": None,
        "answerable": True,
        "relevant": ["RP-2.1", "RP-3.2"],
        "expected_terms": ["7.1"],
    }
    return GoldenQuestion(**{**fields, **overrides})


def run(answer, calls=(SEARCH,)):
    return AgentRun("q", answer, "end_turn", list(calls), 2)


def test_golden_set_loads_and_references_existing_passages():
    golden = load_golden(GOLDEN)
    assert len(golden) == 20
    assert golden[0].question == "Why is pump 3 alarming and what do I check?"
    assert sum(not q.answerable for q in golden) == 3
    corpus_ids = {p.passage_id for p in load_corpus(GOLDEN.parents[1] / "corpus")}
    assert {passage for q in golden for passage in q.relevant} <= corpus_ids


def test_citations_separate_passages_from_machine_state():
    passages, machines = parse_citations("A [RP-2.1]. B [status:pump-3] [VG-6].")
    assert passages == ["RP-2.1", "VG-6"]
    assert machines == ["pump-3"]


def test_score_counts_relevant_valid_and_supported_citations():
    score = score_run(question(), run("The trip limit is 7.1 mm/s [RP-2.1]. Ring it [VG-9]."))
    assert score["cited"] == ["RP-2.1", "VG-9"]
    assert score["relevant_cited"] == 1
    assert score["invalid_citations"] == ["VG-9"]
    assert score["sentences"] == 2
    assert score["cited_sentences"] == 2
    assert score["supported_sentences"] == 1
    assert score["expected_terms_found"] is True
    assert score["declined"] is False


def test_state_citations_need_the_state_to_have_been_read():
    good = score_run(question(relevant=[]), run("Alarm [status:pump-3].", calls=[STATUS]))
    bad = score_run(question(relevant=[]), run("Alarm [status:pump-3].", calls=[]))
    assert good["invalid_citations"] == []
    assert bad["invalid_citations"] == ["status:pump-3"]


def test_summary_uses_micro_averages_and_decline_outcomes():
    answered = score_run(question(), run("The trip limit is 7.1 mm/s [RP-2.1]."))
    declined = score_run(question(id="u", answerable=False, relevant=[]), run(DECLINE, calls=[]))
    wrong = score_run(question(id="w"), run(DECLINE, calls=[]))
    summary = summarize([answered, declined, wrong])
    assert summary["citation_precision"] == pytest.approx(1.0)
    assert summary["citation_recall"] == pytest.approx(1 / 4)
    assert summary["unanswerable_declined"] == pytest.approx(1.0)
    assert summary["answerable_declined"] == pytest.approx(0.5)
    assert summary["citation_validity"] == pytest.approx(1.0)


def test_only_the_exact_decline_reply_counts_as_a_decline():
    unanswerable = question(id="u", answerable=False, relevant=[])
    padded = score_run(unanswerable, run(f"  {DECLINE}\n", calls=[]))
    hedged = run(f"{DECLINE} But do whatever you want [status:pump-3].", calls=[STATUS])
    hedged_score = score_run(unanswerable, hedged)
    assert padded["declined"] is True
    assert hedged_score["declined"] is False
    assert hedged_score["sentences"] == 2
    assert summarize([hedged_score])["unanswerable_declined"] == pytest.approx(0.0)
