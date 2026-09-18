"""Environment -> the pieces. The only module that reads os.environ or builds
clients, so "what is this process talking to?" has one answer.

    RAG_CORPUS_DIR   path to the markdown corpus          (default ../corpus)
    RAG_GOLDEN       path to the golden set               (default ../eval/golden.jsonl)
    RAG_CHUNKING     heading | fixed                      (default heading)
    RAG_EMBEDDER     fastembed | hashing                  (default fastembed)
    RAG_STORE        qdrant | memory                      (default: qdrant if QDRANT_URL is set, else memory)
    QDRANT_URL       e.g. http://localhost:6333
    RAG_COLLECTION   collection name; the chunking + embedder are appended so
                     configs never share a collection    (default rag-lab)
    RAG_ANSWERER     auto | claude | extractive           (auto: claude if a key exists)
    RAG_MODEL        model id                              (default claude-opus-5)
    ANTHROPIC_API_KEY
    RAG_INCLUDE_FLAGGED  1 to hand flagged chunks to the answerer anyway (for demos)
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .answer import Answerer, ClaudeAnswerer, ExtractiveAnswerer
from .chunking import STRATEGIES, Chunker
from .embed import EMBEDDER_NAMES, Embedder, FastEmbedEmbedder, HashingEmbedder
from .ingest import IngestDeps
from .retrieve import Retriever
from .store import MemoryStore, QdrantStore, VectorStore

HERE = Path(__file__).resolve().parent
log = logging.getLogger("rag")


def log_event(msg: str, fields: dict[str, Any]) -> None:
    log.info(json.dumps({"msg": msg, **fields}, default=str))


@dataclass
class Settings:
    corpus_dir: Path
    golden: Path
    chunking: str = "heading"
    embedder: str = "fastembed"
    store: str = "memory"
    qdrant_url: str | None = None
    collection: str = "rag-lab"
    answerer: str = "auto"
    model: str = "claude-opus-5"
    api_key: str | None = None
    include_flagged: bool = False

    @classmethod
    def from_env(cls, **overrides: Any) -> "Settings":
        env = os.environ
        qdrant_url = env.get("QDRANT_URL") or None
        s = cls(
            corpus_dir=Path(env.get("RAG_CORPUS_DIR") or HERE.parent.parent / "corpus"),
            golden=Path(env.get("RAG_GOLDEN") or HERE.parent.parent / "eval" / "golden.jsonl"),
            chunking=env.get("RAG_CHUNKING") or "heading",
            embedder=env.get("RAG_EMBEDDER") or "fastembed",
            store=env.get("RAG_STORE") or ("qdrant" if qdrant_url else "memory"),
            qdrant_url=qdrant_url,
            collection=env.get("RAG_COLLECTION") or "rag-lab",
            answerer=env.get("RAG_ANSWERER") or "auto",
            model=env.get("RAG_MODEL") or "claude-opus-5",
            api_key=env.get("ANTHROPIC_API_KEY") or None,
            include_flagged=env.get("RAG_INCLUDE_FLAGGED") == "1",
        )
        for k, v in overrides.items():
            if v is not None:
                setattr(s, k, v)
        return s


class Wiring:
    """Builds the pieces lazily and once. A memory/hashing/extractive run
    touches no network and downloads nothing."""

    def __init__(self, s: Settings) -> None:
        self.s = s
        self._embedder: Embedder | None = None
        self._store: VectorStore | None = None
        self._retriever: Retriever | None = None
        self.answers_via = "extractive"

    @property
    def chunker(self) -> Chunker:
        return STRATEGIES[self.s.chunking]()

    @property
    def embedder(self) -> Embedder:
        if self._embedder is None:
            self._embedder = FastEmbedEmbedder() if self.s.embedder == "fastembed" else HashingEmbedder()
        return self._embedder

    @property
    def store(self) -> VectorStore:
        if self._store is None:
            if self.s.store == "qdrant":
                if not self.s.qdrant_url:
                    raise RuntimeError("RAG_STORE=qdrant needs QDRANT_URL")
                # One collection per (chunking, embedder): the vectors are not comparable across them.
                # Named from settings so touching the store never constructs (downloads) the embedder.
                self._store = QdrantStore(self.s.qdrant_url, f"{self.s.collection}-{self.s.chunking}-{EMBEDDER_NAMES[self.s.embedder]}")
            else:
                self._store = MemoryStore()
        return self._store

    @property
    def retriever(self) -> Retriever:
        if self._retriever is None:
            self._retriever = Retriever(self.embedder, self.store)
        return self._retriever

    def ingest_deps(self) -> IngestDeps:
        return IngestDeps(chunker=self.chunker, embedder=self.embedder, store=self.store, log=log_event)

    def answerer(self) -> Answerer:
        floor = ExtractiveAnswerer(include_flagged=self.s.include_flagged)
        if self.s.answerer == "extractive":
            return floor
        if not self.s.api_key:
            if self.s.answerer == "claude":
                log_event("answerer=claude requested but ANTHROPIC_API_KEY is not set; using extractive", {})
            return floor
        from anthropic import Anthropic

        self.answers_via = "claude"
        client = Anthropic(api_key=self.s.api_key, timeout=45.0, max_retries=1)
        return ClaudeAnswerer(client, model=self.s.model, include_flagged=self.s.include_flagged, fallback=floor, log=log_event)
