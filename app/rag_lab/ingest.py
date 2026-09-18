"""Corpus directory -> chunks -> vectors -> store. Idempotent.

    ingest(corpus_dir, deps) -> IngestReport

Every chunk id is a content hash, so a second run over the same files finds
its ids already present and skips them; an edited paragraph gets a new id
and is upserted; nothing is ever duplicated. A `full=True` run drops the
collection first, which is what a chunking-strategy change needs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .chunking import Chunker
from .embed import Embedder
from .guard import guard
from .models import Chunk, Document, IngestReport
from .store import VectorStore

Logger = Callable[[str, dict], None]


@dataclass
class IngestDeps:
    chunker: Chunker
    embedder: Embedder
    store: VectorStore
    log: Logger = lambda msg, fields: None


def load_corpus(corpus_dir: Path, suffixes: tuple[str, ...] = (".md", ".txt")) -> list[Document]:
    root = Path(corpus_dir)
    docs = []
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix.lower() in suffixes:
            docs.append(Document(source=p.relative_to(root).as_posix(), text=p.read_text(encoding="utf-8")))
    return docs


def chunk_corpus(docs: list[Document], chunker: Chunker) -> list[Chunk]:
    out: list[Chunk] = []
    for d in docs:
        out.extend(guard(c) for c in chunker(d))
    return out


def ingest(corpus_dir: Path, deps: IngestDeps, full: bool = False, batch: int = 64) -> IngestReport:
    docs = load_corpus(corpus_dir)
    chunks = chunk_corpus(docs, deps.chunker)
    flagged = sum(1 for c in chunks if c.flags)

    if full:
        deps.store.reset(deps.embedder.dim)
    existing = deps.store.existing_ids()
    todo = [c for c in chunks if c.id not in existing]
    deps.log("ingest planned", {"documents": len(docs), "chunks": len(chunks), "new": len(todo), "flagged": flagged, "full": full})

    for i in range(0, len(todo), batch):
        part = todo[i : i + batch]
        vectors = deps.embedder.embed([c.text for c in part])
        deps.store.upsert(part, vectors)

    return IngestReport(
        documents=len(docs),
        chunks=len(chunks),
        upserted=len(todo),
        unchanged=len(chunks) - len(todo),
        flagged=flagged,
        chunking=getattr(deps.chunker, "__name__", "chunker"),
        embedder=deps.embedder.name,
        store=deps.store.name,
    )
