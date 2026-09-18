"""The HTTP face. Thin: every route calls one function from the package.

    POST /ingest   {"full": false}                 -> IngestReport
    GET  /search   ?q=...&k=5&mode=hybrid          -> hits with labels, scores, flags
    POST /ask      {"question": "...", "k": 5}     -> Answer with citations
    GET  /healthz                                  -> store + chunk count
    GET  /metrics                                  -> Prometheus text: requests, latency, chunks
"""

from __future__ import annotations

import time
from collections import Counter, defaultdict
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from .config import Settings, Wiring, log_event
from .ingest import ingest
from .retrieve import Mode

app = FastAPI(title="rag-lab", version="0.1.0")
_settings = Settings.from_env()
_wiring = Wiring(_settings)
_answerer = None

_requests: Counter[str] = Counter()
_latency_sum: dict[str, float] = defaultdict(float)
_answered_by: Counter[str] = Counter()


def _get_answerer():
    global _answerer
    if _answerer is None:
        _answerer = _wiring.answerer()
    return _answerer


@app.middleware("http")
async def _observe(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    route = request.url.path
    _requests[f'{route},status="{response.status_code}"'] += 1
    _latency_sum[route] += time.perf_counter() - started
    return response


class IngestBody(BaseModel):
    full: bool = False


class AskBody(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    k: int = Field(default=5, ge=1, le=20)
    mode: Mode = "hybrid"


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    # Reports configuration, not readiness of the model: a health check must not trigger a 130 MB download.
    return {"ok": True, "store": _wiring.store.name, "chunks": _wiring.store.count(), "chunking": _settings.chunking, "embedder": _settings.embedder}


@app.post("/ingest")
def do_ingest(body: IngestBody) -> dict[str, Any]:
    report = ingest(_settings.corpus_dir, _wiring.ingest_deps(), full=body.full)
    log_event("ingested", report.__dict__)
    return report.__dict__


@app.get("/search")
def search(q: str = Query(min_length=2), k: int = Query(5, ge=1, le=20), mode: Mode = "hybrid") -> dict[str, Any]:
    if _wiring.store.count() == 0:
        raise HTTPException(409, "nothing ingested yet; POST /ingest first")
    hits = _wiring.retriever.search(q, k=k, mode=mode)
    return {
        "q": q,
        "mode": mode,
        "hits": [
            {"label": h.chunk.label, "source": h.chunk.source, "section": h.chunk.section, "score": round(h.score, 4), "flags": list(h.chunk.flags), "text": h.chunk.text[:300]}
            for h in hits
        ],
    }


@app.post("/ask")
def ask(body: AskBody) -> dict[str, Any]:
    if _wiring.store.count() == 0:
        raise HTTPException(409, "nothing ingested yet; POST /ingest first")
    hits = _wiring.retriever.search(body.question, k=body.k, mode=body.mode)
    answer = _get_answerer().answer(body.question, hits)
    _answered_by[answer.answered_by] += 1
    log_event("answered", {"answered_by": answer.answered_by, "citations": len(answer.citations), "refused": answer.refused, "withheld": answer.flagged_sources})
    return {
        "question": answer.question,
        "answer": answer.text,
        "answered_by": answer.answered_by,
        "refused": answer.refused,
        "citations": [c.__dict__ for c in answer.citations],
        "withheld": answer.flagged_sources,
        "retrieved": [h.chunk.label for h in answer.hits],
    }


@app.get("/metrics", response_class=PlainTextResponse)
def metrics() -> str:
    lines = ["# TYPE rag_requests_total counter"]
    for key, n in sorted(_requests.items()):
        route, status = key.split(",", 1)
        lines.append(f'rag_requests_total{{route="{route}",{status}}} {n}')
    lines.append("# TYPE rag_request_seconds_sum counter")
    for route, s in sorted(_latency_sum.items()):
        lines.append(f'rag_request_seconds_sum{{route="{route}"}} {s:.6f}')
    lines.append("# TYPE rag_answers_total counter")
    for by, n in sorted(_answered_by.items()):
        lines.append(f'rag_answers_total{{answered_by="{by}"}} {n}')
    lines.append("# TYPE rag_chunks gauge")
    lines.append(f"rag_chunks {_wiring.store.count()}")
    return "\n".join(lines) + "\n"
