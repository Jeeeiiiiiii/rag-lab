"""Where vectors live. Two adapters behind one interface.

- QdrantStore : a real vector database in Docker. Upsert by chunk id, cosine
                distance, payload carries the chunk so a hit is self-contained.
- MemoryStore : numpy matrix in-process. Same interface, no daemon, for tests
                and the CLI.

Both are keyed by Chunk.id (a content hash), which is what makes re-ingestion
idempotent: the same text lands on the same id and overwrites itself.
"""

from __future__ import annotations

import uuid
from typing import Protocol

import numpy as np

from .models import Chunk


class VectorStore(Protocol):
    name: str

    def reset(self, dim: int) -> None: ...
    def existing_ids(self) -> set[str]: ...
    def upsert(self, chunks: list[Chunk], vectors: np.ndarray) -> None: ...
    def search(self, vector: np.ndarray, k: int) -> list[tuple[Chunk, float]]: ...
    def all_chunks(self) -> list[Chunk]: ...
    def count(self) -> int: ...


def _chunk_to_payload(c: Chunk) -> dict:
    return {"id": c.id, "source": c.source, "section": c.section, "ordinal": c.ordinal, "text": c.text, "flags": list(c.flags)}


def _payload_to_chunk(p: dict) -> Chunk:
    return Chunk(source=p["source"], section=p["section"], ordinal=int(p["ordinal"]), text=p["text"], flags=tuple(p.get("flags", [])))


class MemoryStore:
    name = "memory"

    def __init__(self) -> None:
        self._chunks: dict[str, Chunk] = {}
        self._vecs: dict[str, np.ndarray] = {}
        self._dim = 0

    def reset(self, dim: int) -> None:
        self._chunks.clear()
        self._vecs.clear()
        self._dim = dim

    def existing_ids(self) -> set[str]:
        return set(self._chunks)

    def upsert(self, chunks: list[Chunk], vectors: np.ndarray) -> None:
        for c, v in zip(chunks, vectors):
            self._chunks[c.id] = c
            self._vecs[c.id] = np.asarray(v, dtype=np.float32)

    def search(self, vector: np.ndarray, k: int) -> list[tuple[Chunk, float]]:
        if not self._vecs:
            return []
        ids = list(self._vecs)
        m = np.vstack([self._vecs[i] for i in ids])
        scores = m @ np.asarray(vector, dtype=np.float32)
        top = np.argsort(-scores)[:k]
        return [(self._chunks[ids[i]], float(scores[i])) for i in top]

    def all_chunks(self) -> list[Chunk]:
        return list(self._chunks.values())

    def count(self) -> int:
        return len(self._chunks)


class QdrantStore:
    name = "qdrant"

    def __init__(self, url: str, collection: str = "rag-lab") -> None:
        from qdrant_client import QdrantClient

        self._client = QdrantClient(url=url, timeout=30)
        self._collection = collection

    @staticmethod
    def _point_id(chunk_id: str) -> str:
        # Qdrant wants UUIDs or ints; derive a stable UUID from the content id.
        return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))

    def reset(self, dim: int) -> None:
        from qdrant_client.models import Distance, VectorParams

        self._client.recreate_collection(
            collection_name=self._collection,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )

    def _ensure(self, dim: int) -> None:
        if not self._client.collection_exists(self._collection):
            self.reset(dim)

    def existing_ids(self) -> set[str]:
        if not self._client.collection_exists(self._collection):
            return set()
        ids: set[str] = set()
        offset = None
        while True:
            points, offset = self._client.scroll(self._collection, limit=256, offset=offset, with_payload=["id"], with_vectors=False)
            ids.update(p.payload["id"] for p in points)
            if offset is None:
                return ids

    def upsert(self, chunks: list[Chunk], vectors: np.ndarray) -> None:
        from qdrant_client.models import PointStruct

        if not chunks:
            return
        self._ensure(int(vectors.shape[1]))
        points = [
            PointStruct(id=self._point_id(c.id), vector=np.asarray(v, dtype=np.float32).tolist(), payload=_chunk_to_payload(c))
            for c, v in zip(chunks, vectors)
        ]
        for i in range(0, len(points), 128):
            self._client.upsert(self._collection, points=points[i : i + 128], wait=True)

    def search(self, vector: np.ndarray, k: int) -> list[tuple[Chunk, float]]:
        if not self._client.collection_exists(self._collection):
            return []
        res = self._client.query_points(self._collection, query=np.asarray(vector, dtype=np.float32).tolist(), limit=k, with_payload=True)
        return [(_payload_to_chunk(p.payload), float(p.score)) for p in res.points]

    def all_chunks(self) -> list[Chunk]:
        if not self._client.collection_exists(self._collection):
            return []
        out: list[Chunk] = []
        offset = None
        while True:
            points, offset = self._client.scroll(self._collection, limit=256, offset=offset, with_payload=True, with_vectors=False)
            out.extend(_payload_to_chunk(p.payload) for p in points)
            if offset is None:
                return out

    def count(self) -> int:
        if not self._client.collection_exists(self._collection):
            return 0
        return int(self._client.count(self._collection, exact=True).count)
