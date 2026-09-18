"""Turning a document into chunks. Pure functions; the choice is measured.

Two strategies behind one signature, so the eval can compare them:

- fixed_size    : a sliding window of ~N words with overlap. Knows nothing
                  about the document. The usual default, and the baseline.
- by_heading    : split on Markdown headings, carry the heading path as the
                  chunk's section, and only fall back to windows inside a
                  section that is too long. A chunk then means something:
                  "mesh-lab > What Istio adds", not "words 400-700".

Sizes are in words, not tokens: close enough for retrieval, and no tokenizer
dependency in a pure module.
"""

from __future__ import annotations

import re
from typing import Callable

from .models import Chunk, Document

Chunker = Callable[[Document], list[Chunk]]

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_FENCE = re.compile(r"^\s*(```|~~~)")


def _words(text: str) -> list[str]:
    return text.split()


def _windows(words: list[str], size: int, overlap: int) -> list[str]:
    if not words:
        return []
    step = max(1, size - overlap)
    out = []
    for start in range(0, len(words), step):
        piece = words[start : start + size]
        out.append(" ".join(piece))
        if start + size >= len(words):
            break
    return out


def fixed_size(size: int = 220, overlap: int = 40) -> Chunker:
    def chunk(doc: Document) -> list[Chunk]:
        return [
            Chunk(source=doc.source, section="", ordinal=i, text=t)
            for i, t in enumerate(_windows(_words(doc.text), size, overlap))
        ]

    chunk.__name__ = f"fixed_size({size},{overlap})"
    return chunk


def _sections(doc: Document) -> list[tuple[str, str]]:
    """(heading path, body) per section. Headings inside code fences are ignored."""
    path: list[tuple[int, str]] = []
    sections: list[tuple[str, list[str]]] = [("", [])]
    in_fence = False
    for line in doc.text.splitlines():
        if _FENCE.match(line):
            in_fence = not in_fence
            sections[-1][1].append(line)
            continue
        m = None if in_fence else _HEADING.match(line)
        if m:
            level, title = len(m.group(1)), m.group(2).strip()
            path = [(lv, t) for lv, t in path if lv < level] + [(level, title)]
            sections.append((" > ".join(t for _, t in path), []))
        else:
            sections[-1][1].append(line)
    return [(h, "\n".join(body).strip()) for h, body in sections if "\n".join(body).strip()]


def by_heading(max_words: int = 320, overlap: int = 40) -> Chunker:
    def chunk(doc: Document) -> list[Chunk]:
        out: list[Chunk] = []
        for heading, body in _sections(doc):
            words = _words(body)
            pieces = [body] if len(words) <= max_words else _windows(words, max_words, overlap)
            for piece in pieces:
                # The heading rides along in the text so the embedding sees it too.
                text = f"{heading}\n{piece}" if heading else piece
                out.append(Chunk(source=doc.source, section=heading, ordinal=len(out), text=text))
        return out

    chunk.__name__ = f"by_heading({max_words},{overlap})"
    return chunk


STRATEGIES: dict[str, Callable[[], Chunker]] = {
    "fixed": lambda: fixed_size(),
    "heading": lambda: by_heading(),
}
