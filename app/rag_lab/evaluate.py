"""Retrieval quality as a number, so a change to chunking, embedding or
retrieval mode is a measurement and not an opinion.

Golden set: eval/golden.jsonl, one question per line with what a relevant
chunk must satisfy:

    {"q": "...", "source": "mesh-lab.md", "must_contain": ["NodePort", "30080"]}

A hit is relevant when it comes from `source` and its text contains every
phrase in `must_contain` (case-insensitive). From that:

    hit@k   did any relevant chunk land in the top k        (per question, then averaged)
    mrr     1 / rank of the first relevant chunk             (0 when none)

The same set drives a guard check: questions with "expect_flagged": true
must retrieve the planted injection document *and* see it withheld.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .models import Hit
from .retrieve import Mode, Retriever


@dataclass(frozen=True)
class GoldenItem:
    q: str
    source: str
    must_contain: tuple[str, ...]
    expect_flagged: bool = False


def load_golden(path: Path) -> list[GoldenItem]:
    items = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        d = json.loads(line)
        items.append(GoldenItem(d["q"], d["source"], tuple(d.get("must_contain", [])), bool(d.get("expect_flagged", False))))
    return items


def is_relevant(hit: Hit, item: GoldenItem) -> bool:
    if hit.chunk.source != item.source:
        return False
    text = hit.chunk.text.lower()
    return all(p.lower() in text for p in item.must_contain)


@dataclass
class QuestionResult:
    q: str
    rank: int | None
    """1-based rank of the first relevant hit, or None."""
    top: list[str]
    flagged_seen: bool = False


@dataclass
class EvalResult:
    label: str
    mode: Mode
    k: int
    questions: list[QuestionResult] = field(default_factory=list)

    @property
    def hit_at_k(self) -> float:
        qs = self.questions
        return sum(1 for r in qs if r.rank is not None and r.rank <= self.k) / len(qs) if qs else 0.0

    @property
    def hit_at_1(self) -> float:
        return sum(1 for r in self.questions if r.rank == 1) / len(self.questions) if self.questions else 0.0

    @property
    def mrr(self) -> float:
        return sum(1.0 / r.rank for r in self.questions if r.rank) / len(self.questions) if self.questions else 0.0

    @property
    def misses(self) -> list[QuestionResult]:
        return [r for r in self.questions if r.rank is None or r.rank > self.k]


def evaluate(retriever: Retriever, golden: list[GoldenItem], mode: Mode, k: int = 5, label: str = "") -> EvalResult:
    result = EvalResult(label=label or mode, mode=mode, k=k)
    for item in golden:
        hits = retriever.search(item.q, k=max(k, 10), mode=mode)
        rank = next((i + 1 for i, h in enumerate(hits) if is_relevant(h, item)), None)
        flagged_seen = any(h.chunk.flags for h in hits[:k])
        result.questions.append(QuestionResult(item.q, rank, [h.chunk.label for h in hits[:k]], flagged_seen))
    return result


def guard_check(retriever: Retriever, golden: list[GoldenItem], k: int = 5) -> list[tuple[str, bool, bool]]:
    """For each expect_flagged question: (question, the injected chunk was retrieved, it carried the flag)."""
    out = []
    for item in golden:
        if not item.expect_flagged:
            continue
        hits = retriever.search(item.q, k=k, mode="hybrid")
        injected = [h for h in hits if is_relevant(h, item)]
        out.append((item.q, bool(injected), all(h.chunk.flags for h in injected) if injected else False))
    return out


def markdown_table(results: list[EvalResult]) -> str:
    lines = ["| config | mode | hit@1 | hit@k | MRR | misses |", "|---|---|---:|---:|---:|---:|"]
    for r in results:
        lines.append(f"| {r.label} | {r.mode} | {r.hit_at_1:.2f} | {r.hit_at_k:.2f} (k={r.k}) | {r.mrr:.2f} | {len(r.misses)}/{len(r.questions)} |")
    return "\n".join(lines)
