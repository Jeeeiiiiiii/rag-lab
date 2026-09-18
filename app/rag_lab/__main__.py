"""The lab from a terminal.

    python -m rag_lab ingest [--full]
    python -m rag_lab search "how does httpbin refuse POST" [--mode dense|bm25|hybrid] [-k 5]
    python -m rag_lab ask "what does the order-lab DLQ alarm watch"
    python -m rag_lab eval                 # every chunking x mode, one table
    python -m rag_lab eval --gate 0.8      # exit 1 if hybrid hit@5 is below the gate (CI)

Defaults come from the environment (see config.py). With no QDRANT_URL the
store is in-memory and `ingest` happens implicitly before search/ask/eval.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from .config import Settings, Wiring
from .evaluate import evaluate, guard_check, load_golden, markdown_table
from .ingest import ingest


def _wiring(a: argparse.Namespace) -> Wiring:
    s = Settings.from_env(chunking=a.chunking, embedder=a.embedder, store=a.store, answerer=getattr(a, "answerer", None))
    return Wiring(s)


def _ensure_ingested(w: Wiring, full: bool = False) -> None:
    if full or w.store.count() == 0:
        r = ingest(w.s.corpus_dir, w.ingest_deps(), full=full)
        print(f"ingested: {r.documents} docs → {r.chunks} chunks ({r.upserted} new, {r.unchanged} unchanged, {r.flagged} flagged) · {r.chunking} · {r.embedder} · {r.store}", file=sys.stderr)


def cmd_ingest(a):
    w = _wiring(a)
    _ensure_ingested(w, full=a.full or True)


def cmd_search(a):
    w = _wiring(a)
    _ensure_ingested(w)
    for h in w.retriever.search(a.q, k=a.k, mode=a.mode):
        flag = "  ⚠ " + ",".join(h.chunk.flags) if h.chunk.flags else ""
        print(f"{h.score:8.4f}  [{h.chunk.label}] {h.chunk.section or h.chunk.source}{flag}")
        if a.verbose:
            print("          " + " ".join(h.chunk.text.split())[:240])


def cmd_ask(a):
    w = _wiring(a)
    _ensure_ingested(w)
    hits = w.retriever.search(a.q, k=a.k, mode=a.mode)
    ans = w.answerer().answer(a.q, hits)
    print(ans.text)
    print()
    print(f"answered by {ans.answered_by}" + (" · context judged insufficient" if ans.refused else ""))
    if ans.citations:
        print("cites: " + ", ".join(c.label for c in ans.citations))
    if ans.flagged_sources:
        print("withheld (flagged as injection): " + ", ".join(ans.flagged_sources))


def cmd_eval(a):
    golden = load_golden(Path(Settings.from_env().golden))
    results = []
    chunkings = [a.chunking] if a.chunking else ["fixed", "heading"]
    modes = [a.mode] if a.mode else ["dense", "bm25", "hybrid"]
    gate_value = None
    for chunking in chunkings:
        s = Settings.from_env(chunking=chunking, embedder=a.embedder, store="memory")
        w = Wiring(s)
        _ensure_ingested(w, full=True)
        for mode in modes:
            r = evaluate(w.retriever, golden, mode=mode, k=a.k, label=f"{chunking} · {w.embedder.name}")
            results.append(r)
            if chunking == "heading" and mode == "hybrid":
                gate_value = r.hit_at_k
            if a.verbose:
                for m in r.misses:
                    print(f"  miss [{chunking}/{mode}] {m.q!r} → rank {m.rank}, top: {m.top}", file=sys.stderr)
        for q, retrieved, flagged in guard_check(w.retriever, golden, k=a.k):
            print(f"guard [{chunking}]: {q!r} → planted doc retrieved={retrieved}, flagged={flagged}", file=sys.stderr)
    print(markdown_table(results))
    if a.json:
        print(json.dumps([{"label": r.label, "mode": r.mode, "hit@1": r.hit_at_1, "hit@k": r.hit_at_k, "mrr": r.mrr} for r in results], indent=1))
    if a.gate is not None:
        if gate_value is None:
            print("gate: heading/hybrid was not evaluated", file=sys.stderr)
            return 2
        ok = gate_value >= a.gate
        print(f"gate: heading·hybrid hit@{a.k} = {gate_value:.2f} {'>=' if ok else '<'} {a.gate} → {'PASS' if ok else 'FAIL'}", file=sys.stderr)
        return 0 if ok else 1
    return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(prog="rag-lab", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--chunking", choices=["fixed", "heading"], default=None)
    p.add_argument("--embedder", choices=["fastembed", "hashing"], default=None)
    p.add_argument("--store", choices=["qdrant", "memory"], default=None)
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("ingest")
    s.add_argument("--full", action="store_true", help="drop and rebuild the collection")
    s.set_defaults(fn=cmd_ingest)

    for name, fn in (("search", cmd_search), ("ask", cmd_ask)):
        s = sub.add_parser(name)
        s.add_argument("q")
        s.add_argument("-k", type=int, default=5)
        s.add_argument("--mode", choices=["dense", "bm25", "hybrid"], default="hybrid")
        if name == "ask":
            s.add_argument("--answerer", choices=["auto", "claude", "extractive"], default=None)
        s.set_defaults(fn=fn)

    s = sub.add_parser("eval")
    s.add_argument("-k", type=int, default=5)
    s.add_argument("--mode", choices=["dense", "bm25", "hybrid"], default=None)
    s.add_argument("--gate", type=float, default=None, help="minimum heading·hybrid hit@k; exit 1 below it")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_eval)

    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO if a.verbose else logging.WARNING, format="%(message)s", stream=sys.stderr)
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    return a.fn(a) or 0


if __name__ == "__main__":
    sys.exit(main())
