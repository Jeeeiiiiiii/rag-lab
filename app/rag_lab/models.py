"""The nouns. Plain dataclasses that cross every seam.

A Chunk's id is derived from its content, so ingesting the same corpus twice
produces the same ids and the store upserts instead of duplicating.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Document:
    source: str
    """Path relative to the corpus root, e.g. 'mesh-lab.md'."""
    text: str

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class Chunk:
    source: str
    section: str
    """Heading path, e.g. 'Mesh Lab > What Istio adds'. '' when unknown."""
    ordinal: int
    """Position within the document, 0-based."""
    text: str
    flags: tuple[str, ...] = ()
    """Guard findings, e.g. ('injection',). Empty when clean."""

    @property
    def id(self) -> str:
        return hashlib.sha256(f"{self.source}\n{self.text}".encode("utf-8")).hexdigest()[:24]

    @property
    def label(self) -> str:
        return f"{self.source}#{self.ordinal}"


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float
    """Higher is better; comparable only within one retriever's result list."""
    via: str
    """'dense' | 'bm25' | 'hybrid'."""


@dataclass(frozen=True)
class Citation:
    label: str
    source: str
    section: str


@dataclass
class Answer:
    question: str
    text: str
    citations: list[Citation] = field(default_factory=list)
    hits: list[Hit] = field(default_factory=list)
    answered_by: str = "extractive"
    """'claude' | 'extractive' | 'claude→extractive'."""
    refused: bool = False
    """True when the answerer judged the context insufficient."""
    flagged_sources: list[str] = field(default_factory=list)
    """Chunk labels the guard flagged among the retrieved set."""


@dataclass
class IngestReport:
    documents: int
    chunks: int
    upserted: int
    unchanged: int
    flagged: int
    chunking: str
    embedder: str
    store: str
