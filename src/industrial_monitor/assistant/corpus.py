"""Manual corpus: section parsing and BM25 retrieval, standard library only.

A corpus document is Markdown with a level-1 title and level-2 sections headed
`## [ID] Title`. Each section is one retrievable passage, cited by its ID.
"""

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

_SECTION = re.compile(r"^## \[([^\]]+)\] ([^\n]+)\n\n(.+?)(?=\n## |\Z)", re.MULTILINE | re.DOTALL)
_TOKEN = re.compile(r"[a-z0-9]+(?:[.\-][a-z0-9]+)*")
STOPWORDS = frozenset(
    (  # noqa: SIM905
        "a an and any are as at be by can do does for from how i if in is it its me my of on or "
        "should so the there this to what when which why with"
    ).split()
)
K1 = 1.5
B = 0.75


@dataclass(frozen=True)
class Passage:
    passage_id: str
    title: str
    document: str
    source: str
    text: str


@dataclass(frozen=True)
class SearchResult:
    passage: Passage
    score: float
    coverage: float


def tokenize(text: str) -> list[str]:
    return [token for token in _TOKEN.findall(text.lower()) if token not in STOPWORDS]


def parse_document(markdown: str, source: str) -> list[Passage]:
    title_line = markdown.split("\n", 1)[0]
    if not title_line.startswith("# "):
        raise ValueError(f"{source}: the first line must be a '# ' title")
    document = title_line[2:].strip()
    return [
        Passage(match[1], match[2].strip(), document, source, match[3].strip())
        for match in _SECTION.finditer(markdown)
    ]


def load_corpus(directory: Path) -> list[Passage]:
    passages = []
    for path in sorted(directory.glob("*.md")):
        passages.extend(parse_document(path.read_text(encoding="utf-8"), source=path.name))
    if not passages:
        raise ValueError(f"no passages found in {directory}")
    return passages


class BM25Index:
    def __init__(self, passages: list[Passage]):
        self.passages = passages
        self._terms = [Counter(tokenize(f"{p.document} {p.title} {p.text}")) for p in passages]
        self._lengths = [sum(terms.values()) for terms in self._terms]
        self._average_length = sum(self._lengths) / len(self._lengths)
        frequency = Counter(term for terms in self._terms for term in terms)
        count = len(passages)
        self._idf = {
            term: math.log((count - df + 0.5) / (df + 0.5) + 1) for term, df in frequency.items()
        }

    def _score(self, position: int, query: list[str]) -> float:
        terms, length = self._terms[position], self._lengths[position]
        score = 0.0
        for term in query:
            tf = terms.get(term, 0)
            if tf:
                norm = tf + K1 * (1 - B + B * length / self._average_length)
                score += self._idf[term] * tf * (K1 + 1) / norm
        return score

    def search(self, query: str, k: int = 4) -> list[SearchResult]:
        """Top-k passages. Coverage is the share of distinct query terms the passage contains."""
        terms = list(dict.fromkeys(tokenize(query)))
        ranked = sorted(
            range(len(self.passages)), key=lambda i: self._score(i, terms), reverse=True
        )
        return [
            SearchResult(
                self.passages[i],
                self._score(i, terms),
                sum(t in self._terms[i] for t in terms) / len(terms) if terms else 0.0,
            )
            for i in ranked[:k]
        ]

    def get(self, passage_id: str) -> Passage | None:
        return next((p for p in self.passages if p.passage_id == passage_id), None)
