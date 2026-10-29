from pathlib import Path

import pytest

from industrial_monitor.assistant.corpus import BM25Index, load_corpus, parse_document, tokenize

CORPUS = Path(__file__).resolve().parents[1] / "corpus"

DOCUMENT = """# Example Manual

This manual is synthetic.

## [EX-1.1] Bearing grease

Grease the bearing every 2000 hours.

## [EX-1.2] Impeller cleaning

Clean deposits from the impeller blades.
"""


def test_documents_split_into_passages_with_ids_and_titles():
    passages = parse_document(DOCUMENT, source="example.md")
    assert [p.passage_id for p in passages] == ["EX-1.1", "EX-1.2"]
    assert passages[0].title == "Bearing grease"
    assert passages[0].document == "Example Manual"
    assert passages[0].text == "Grease the bearing every 2000 hours."


def test_tokens_keep_identifiers_and_decimals():
    assert tokenize("BPFO is 83.5 Hz on the RP-1, see [RP-3.1].") == [
        "bpfo",
        "83.5",
        "hz",
        "rp-1",
        "see",
        "rp-3.1",
    ]


def test_search_ranks_the_passage_that_answers_first():
    index = BM25Index(parse_document(DOCUMENT, source="example.md"))
    results = index.search("how often to grease the bearing", k=2)
    assert results[0].passage.passage_id == "EX-1.1"
    assert results[0].score > results[1].score
    assert results[0].coverage == pytest.approx(2 / 3)


def test_shipped_corpus_has_unique_ids_and_sized_sections():
    passages = load_corpus(CORPUS)
    ids = [p.passage_id for p in passages]
    assert len(ids) == len(set(ids)) == 30
    assert all(60 <= len(p.text.split()) <= 180 for p in passages)
