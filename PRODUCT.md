# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Static HTML/CSS/JS in one file (`ops/index.html`), served by a standard-library Python server (`ops/server.py`) on the operator's machine, started by `scripts/ops.sh`. It talks to the rag-lab API on :8090 (FastAPI + Qdrant in Docker) and runs the eval through the app's own venv (`app/.venv`). No build step, nothing new deployed. Chosen by the user, matching order-lab's flow view.

## Users

One DevOps engineer, the lab's owner, learning retrieval-augmented generation on their own Windows laptop with the lab running locally. They know infrastructure well and RAG less; they want to *see* why one retrieval mode finds a chunk another misses, rather than read it in a table. They prefer plain-language explanations and cause → effect they can trigger themselves.

## Product Purpose

The ops page puts the lab's claims in front of them as things they can poke: one question run through dense, BM25 and hybrid retrieval side by side; an answer with its citations and the planted injection chunk retrieved but withheld; a re-ingest that shows which chunks were (or were not) re-embedded; the golden-set eval run live with its gate. Success: they can explain, from what they watched, why dense loses exact identifiers, why BM25 loses paraphrases, why rank fusion keeps both, why the injected chunk is stored but never reaches the answerer, and what hit@1, hit@5 and MRR measure.

Scenario scope (inferred: the user confirmed the stack and the learning goal, not the list): retriever comparison, ask + citations + guard, ingest report, live eval. Out of scope: editing corpus files from the page (the user edits files themselves, the page re-ingests).

## Positioning

Every result shown comes from the running API, Qdrant, and the lab's own eval command; nothing is precomputed or simulated in the page. The retriever scores are the real scores (cosine for dense, BM25 scores, RRF sums for hybrid), each on its own scale, and the page says so.

## Operating Context

- Started after `bash scripts/up.sh` (Qdrant + API in Docker, corpus ingested). Commands are bash, run from Git Bash or `bash ...` from PowerShell.
- The answerer is extractive locally (no `ANTHROPIC_API_KEY` on this machine); `answered_by` says which path wrote the words. The page must show that, not imply a model answered.
- The eval runs in-process with the fastembed embedder (first run downloads bge-small, ~130 MB) and takes seconds, not milliseconds.

## Capabilities and Constraints

- API: `GET /search?q&k&mode`, `POST /ask {question,k,mode}`, `POST /ingest {full}`, `GET /healthz`, `GET /metrics`.
- Terminology: chunk, label (`source > section #n`), flags (`injection`), withheld, answered_by, hit@1, hit@k, MRR, golden set, gate (heading·hybrid hit@5 ≥ 0.9).
- Corpus: `corpus/*.md`, the other labs' READMEs plus `onboarding-notes.md` carrying the planted injection. Golden set: `eval/golden.jsonl`, 28 questions.
- `onnxruntime` is pinned to 1.20.1 on this machine.

## Evidence on Hand

The README's eval table (heading-aware hybrid: hit@1 0.79, hit@5 0.96, MRR 0.86) and its explanation of the misses. No live Claude answers exist; the page must not show any.

## Product Principles

1. Show the mechanism, not just the verdict: every ranked chunk says which retriever found it and at what rank.
2. Real numbers only, each labelled with its scale.
3. Explain beside the evidence in plain words; the page is a teacher, not a dashboard.
4. Make the guard visible: the planted chunk is shown being caught, not hidden.
