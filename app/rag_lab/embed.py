"""Text -> vector. Two adapters behind one interface.

- FastEmbedEmbedder : BAAI/bge-small-en-v1.5 through fastembed (ONNX, CPU,
                      384 dims, ~130 MB downloaded once). Real semantics.
- HashingEmbedder   : a bag-of-words hashed into N buckets, L2-normalised.
                      No download, deterministic, milliseconds. What the
                      tests and CI use; it retrieves by word overlap only,
                      which is exactly why the eval has to be run with both.
"""

from __future__ import annotations

import hashlib
import re
from typing import Iterable, Protocol

import numpy as np


class Embedder(Protocol):
    name: str
    dim: int

    def embed(self, texts: Iterable[str]) -> np.ndarray:
        """Row per text, L2-normalised, shape (n, dim)."""
        ...


# Static names per setting, so a collection can be named without constructing
# (and therefore downloading) the embedder.
EMBEDDER_NAMES = {"fastembed": "bge-small-en-v1.5", "hashing": "hashing"}


_TOKEN = re.compile(r"[a-z0-9]+")


class HashingEmbedder:
    name = "hashing"

    def __init__(self, dim: int = 1024) -> None:
        self.dim = dim

    def embed(self, texts: Iterable[str]) -> np.ndarray:
        rows = []
        for text in texts:
            v = np.zeros(self.dim, dtype=np.float32)
            for tok in _TOKEN.findall(text.lower()):
                h = int(hashlib.blake2b(tok.encode(), digest_size=4).hexdigest(), 16)
                v[h % self.dim] += 1.0
            n = np.linalg.norm(v)
            rows.append(v / n if n else v)
        return np.vstack(rows) if rows else np.zeros((0, self.dim), dtype=np.float32)


class FastEmbedEmbedder:
    name = "bge-small-en-v1.5"
    dim = 384

    def __init__(self, model: str = "BAAI/bge-small-en-v1.5") -> None:
        from fastembed import TextEmbedding  # imported here: the dependency is optional

        self._model = TextEmbedding(model)
        self.name = model.split("/")[-1]

    def embed(self, texts: Iterable[str]) -> np.ndarray:
        vecs = list(self._model.embed(list(texts)))
        if not vecs:
            return np.zeros((0, self.dim), dtype=np.float32)
        m = np.vstack(vecs).astype(np.float32)
        norms = np.linalg.norm(m, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return m / norms
