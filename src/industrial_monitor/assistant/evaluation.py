"""Evaluation of the maintenance assistant against the golden question set.

Metrics, all micro-averaged over questions:
- citation precision and recall: cited passage IDs against the golden relevant set
- citation validity: share of bracketed citations that name a passage or machine state
  retrieved by a tool call in the same run, so a fabricated or malformed citation counts
  against it
- sentence coverage: share of answer sentences that carry a citation
- lexical support: share of sentences whose content words appear mostly (SUPPORT_THRESHOLD)
  in the text they cite; a proxy for groundedness that does not judge meaning
- expected terms: share of questions whose answer contains every expected term
- decline behaviour on unanswerable and answerable questions; only an answer that is exactly
  the decline reply, ignoring surrounding whitespace, counts as a decline
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from industrial_monitor.assistant.agent import DECLINE, AgentRun, Model, Tools, run_agent
from industrial_monitor.assistant.corpus import tokenize

SUPPORT_THRESHOLD = 0.6
_PASSAGE_ID = re.compile(r"[A-Z]{2}-\d+(?:\.\d+)?")
_STATE_ID = re.compile(r"status:([a-z]+-\d+)")
_ANY_CITATION = re.compile(r"\[([^\]]+)\]")
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class GoldenQuestion:
    id: str
    question: str
    machine: str | None
    answerable: bool
    relevant: list[str]
    expected_terms: list[str]


def load_golden(path: Path) -> list[GoldenQuestion]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [GoldenQuestion(**json.loads(line)) for line in lines if line.strip()]


def citation_candidates(text: str) -> list[str]:
    """Contents of every bracketed span, in order of first appearance."""
    return list(dict.fromkeys(_ANY_CITATION.findall(text)))


def classify_citations(text: str) -> tuple[list[str], list[str], list[str]]:
    """Passage IDs, machine IDs and malformed citations, from one pass over the candidates."""
    passages, machines, malformed = [], [], []
    for candidate in citation_candidates(text):
        state = _STATE_ID.fullmatch(candidate)
        if state:
            machines.append(state[1])
        elif _PASSAGE_ID.fullmatch(candidate):
            passages.append(candidate)
        else:
            malformed.append(candidate)
    return passages, machines, malformed


def parse_citations(answer: str) -> tuple[list[str], list[str]]:
    passages, machines, _ = classify_citations(answer)
    return passages, machines


def is_decline(answer: str) -> bool:
    return " ".join(answer.split()) == DECLINE


def _retrieved(run: AgentRun) -> tuple[dict[str, str], dict[str, str]]:
    """Text of every passage and machine state that a tool returned during the run."""
    passages: dict[str, str] = {}
    states: dict[str, str] = {}
    for call in run.tool_calls:
        if call.is_error:
            continue
        output = json.loads(call.output)
        if call.name == "search_manual":
            passages.update({item["id"]: item["text"] for item in output})
        elif call.name == "get_machine_status":
            states[output["machine_id"]] = call.output
        elif call.name == "list_alarms":
            states.update({item["machine_id"]: json.dumps(item) for item in output})
    return passages, states


def _supported(sentence: str, passages: dict[str, str], states: dict[str, str]) -> bool:
    cited_passages, cited_machines = parse_citations(sentence)
    sources = [passages[p] for p in cited_passages if p in passages]
    sources += [states[m] for m in cited_machines if m in states]
    words = set(tokenize(_ANY_CITATION.sub(" ", sentence)))
    if not sources or not words:
        return False
    source_words = set(tokenize(" ".join(sources)))
    return len(words & source_words) / len(words) >= SUPPORT_THRESHOLD


def score_run(question: GoldenQuestion, run: AgentRun) -> dict:
    passages, states = _retrieved(run)
    cited, machines, malformed = classify_citations(run.answer)
    declined = is_decline(run.answer)
    sentences = [] if declined else [s for s in _SENTENCE_BREAK.split(run.answer) if s.strip()]
    lowered = run.answer.lower()
    return {
        "id": question.id,
        "answerable": question.answerable,
        "stop_reason": run.stop_reason,
        "declined": declined,
        "relevant": question.relevant,
        "cited": cited,
        "cited_machines": machines,
        "malformed_citations": malformed,
        "relevant_cited": len(set(cited) & set(question.relevant)),
        "invalid_citations": [p for p in cited if p not in passages]
        + [f"status:{m}" for m in machines if m not in states]
        + malformed,
        "sentences": len(sentences),
        "cited_sentences": sum(bool(_ANY_CITATION.search(s)) for s in sentences),
        "supported_sentences": sum(_supported(s, passages, states) for s in sentences),
        "expected_terms_found": (
            all(term.lower() in lowered for term in question.expected_terms)
            if question.expected_terms
            else None
        ),
    }


def _ratio(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def _any_citation(score: dict) -> bool:
    return bool(score["cited"] or score["cited_machines"] or score["malformed_citations"])


def summarize(scores: list[dict]) -> dict:
    with_relevant = [s for s in scores if s["relevant"]]
    answerable = [s for s in scores if s["answerable"]]
    unanswerable = [s for s in scores if not s["answerable"]]
    citations = sum(
        len(s["cited"]) + len(s["cited_machines"]) + len(s["malformed_citations"]) for s in scores
    )
    with_terms = [s for s in scores if s["expected_terms_found"] is not None]
    sentences = sum(s["sentences"] for s in scores)
    return {
        "questions": len(scores),
        "answerable": len(answerable),
        "unanswerable": len(unanswerable),
        "citation_precision": _ratio(
            sum(s["relevant_cited"] for s in with_relevant),
            sum(len(s["cited"]) for s in with_relevant),
        ),
        "citation_recall": _ratio(
            sum(s["relevant_cited"] for s in with_relevant),
            sum(len(s["relevant"]) for s in with_relevant),
        ),
        "citation_validity": _ratio(
            citations - sum(len(s["invalid_citations"]) for s in scores), citations
        ),
        "sentence_coverage": _ratio(sum(s["cited_sentences"] for s in scores), sentences),
        "lexical_support": _ratio(sum(s["supported_sentences"] for s in scores), sentences),
        "expected_terms_rate": _ratio(
            sum(s["expected_terms_found"] for s in with_terms), len(with_terms)
        ),
        "unanswerable_declined": _ratio(
            sum(s["declined"] and not _any_citation(s) for s in unanswerable), len(unanswerable)
        ),
        "answerable_declined": _ratio(sum(s["declined"] for s in answerable), len(answerable)),
        "refusals": sum(s["stop_reason"] == "refusal" for s in scores),
        "incomplete_runs": sum(s["stop_reason"] not in ("end_turn", "refusal") for s in scores),
    }


def evaluate(model: Model, toolbox: Tools, golden: list[GoldenQuestion]) -> dict:
    records = []
    for question in golden:
        run = run_agent(question.question, model, toolbox)
        records.append(
            {
                **score_run(question, run),
                "question": question.question,
                "answer": run.answer,
                "tool_calls": [
                    {"name": c.name, "arguments": c.arguments, "is_error": c.is_error}
                    for c in run.tool_calls
                ],
            }
        )
    return {"model": model.name, "summary": summarize(records), "questions": records}
