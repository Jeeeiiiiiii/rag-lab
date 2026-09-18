"""Question -> ranked chunks. Three modes behind one call, so the eval can
put a number on each:

- dense  : cosine similarity over embeddings. Good at paraphrase, weak on
           exact identifiers ("NodePort 30080", "PLANT_VULN=1").
- bm25   : lexical. The opposite strengths.
- hybrid : both, fused with reciprocal rank fusion (RRF). Rank-based, so the
           two score scales never have to be reconciled.

The BM25 index is rebuilt from the store's chunks after invalidate(); it is
small (hundreds of chunks) and keeping one source of truth beats keeping two
in sync. Ingest calls invalidate(); a count-based check would miss an edit
that keeps the chunk count the same.
"""

from __future__ import annotations

import re
import threading
from typing import Literal

from rank_bm25 import BM25Okapi

from .embed import Embedder
from .models import Chunk, Hit
from .store import VectorStore

Mode = Literal["dense", "bm25", "hybrid"]

_TOKEN = re.compile(r"[a-z0-9]+(?:[-_.][a-z0-9]+)*")


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


class Retriever:
    def __init__(self, embedder: Embedder, store: VectorStore, rrf_k: int = 60) -> None:
        self._embedder = embedder
        self._store = store
        self._rrf_k = rrf_k
        # (index, chunks) swapped as one tuple, so a concurrent reader never
        # sees a new chunk list with an old index. Rebuilt after invalidate().
        self._lex: tuple[BM25Okapi | None, list[Chunk]] | None = None
        self._lock = threading.Lock()

    def invalidate(self) -> None:
        """Call after any ingest; the next lexical query rebuilds from the store."""
        self._lex = None

    def _lexical(self) -> tuple[BM25Okapi | None, list[Chunk]]:
        lex = self._lex
        if lex is not None:
            return lex
        with self._lock:
            if self._lex is None:
                chunks = self._store.all_chunks()
                index = BM25Okapi([tokenize(c.text) for c in chunks]) if chunks else None
                self._lex = (index, chunks)
            return self._lex

    def dense(self, question: str, k: int) -> list[Hit]:
        vec = self._embedder.embed([question])[0]
        return [Hit(c, s, "dense") for c, s in self._store.search(vec, k)]

    def bm25(self, question: str, k: int) -> list[Hit]:
        index, chunks = self._lexical()
        if index is None:
            return []
        scores = index.get_scores(tokenize(question))
        order = sorted(range(len(chunks)), key=lambda i: -scores[i])[:k]
        return [Hit(chunks[i], float(scores[i]), "bm25") for i in order if scores[i] > 0]

    def hybrid(self, question: str, k: int) -> list[Hit]:
        # Pull deeper from each side than we return; RRF rewards agreement.
        depth = max(k * 3, 20)
        fused: dict[str, float] = {}
        by_id: dict[str, Chunk] = {}
        for ranked in (self.dense(question, depth), self.bm25(question, depth)):
            for rank, hit in enumerate(ranked):
                by_id[hit.chunk.id] = hit.chunk
                fused[hit.chunk.id] = fused.get(hit.chunk.id, 0.0) + 1.0 / (self._rrf_k + rank + 1)
        top = sorted(fused.items(), key=lambda kv: -kv[1])[:k]
        return [Hit(by_id[cid], score, "hybrid") for cid, score in top]

    def search(self, question: str, k: int = 5, mode: Mode = "hybrid") -> list[Hit]:
        return {"dense": self.dense, "bm25": self.bm25, "hybrid": self.hybrid}[mode](question, k)
