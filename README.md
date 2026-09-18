# RAG Lab

Retrieval-augmented generation where **retrieval quality is a number**, not an
opinion. The corpus is the READMEs of the other labs in this folder, so every
question has a known answer in a known section; a golden set turns chunking
strategy, embedding model and retrieval mode into a table of hit@k and MRR,
and that table is a CI gate.

The chat is beside the point. Two chunkers, two embedders, three retrievers,
two answerers and two stores sit behind the same seams, so each choice is
measured against the others rather than assumed. A planted prompt-injection
document in the corpus proves the guard works — or would prove that it does
not.

```
   corpus/*.md ──▶ chunk ──▶ guard ──▶ embed ──▶ store          eval/golden.jsonl
                  fixed |    flags     bge-small |   Qdrant |          │
                  heading  injection   hashing     memory            ▼
                                                     │       ┌──────────────────┐
   question ──▶ retrieve ─────────────────────────────┘       │ hit@1 hit@5 MRR  │
                dense · bm25 · hybrid (RRF)                  │ per config       │
                    │                                        │ + guard check    │
                    ▼                                        │ → CI gate ≥ 0.9  │
                answer ──▶ text + citations (labels only     └──────────────────┘
                Claude |   from the passages it was given)
                extractive   flagged chunks withheld
```

## The result

28 questions, phrased differently from the documents. `bge-small-en-v1.5`,
in-process, `k = 5`:

| config | mode | hit@1 | hit@5 | MRR | misses |
|---|---|---:|---:|---:|---:|
| fixed (220 words, 40 overlap) | dense | 0.43 | 0.86 | 0.62 | 4/28 |
| fixed | bm25 | 0.54 | 0.93 | 0.72 | 2/28 |
| fixed | hybrid | 0.46 | 0.96 | 0.68 | 1/28 |
| heading-aware (≤ 320 words) | dense | 0.61 | 0.89 | 0.74 | 3/28 |
| heading-aware | bm25 | 0.71 | 0.93 | 0.80 | 2/28 |
| **heading-aware** | **hybrid** | **0.79** | **0.96** | **0.86** | 1/28 |

What the misses say: dense retrieval loses exact identifiers (`max_retries`,
`15017`) that BM25 finds trivially; BM25 loses paraphrases ("what stands in
for the ALB" → `socat`) that the embedding catches. Reciprocal rank fusion
keeps both. Heading-aware chunks help every mode because the heading path
rides along inside the chunk text — "Order Lab > The decision" is context an
embedding can use and a window of 220 words cannot. The one remaining miss
("network load balancer instead of an application load balancer" → a
sentence that says "NLB, not ALB") is a genuine paraphrase gap in a small
model, reported, not tuned away.

## The decisions

| Decision | Why |
|---|---|
| **The corpus is the other labs' READMEs.** Six documents, ~57 chunks, one of them planted. | Questions with known answers in known sections are what make an eval honest. A synthetic corpus would prove nothing about retrieval over real engineering prose with tables, code fences and identifiers. |
| **Two adapters at every seam.** Chunking: fixed \| heading. Embedder: fastembed \| hashing. Store: Qdrant \| memory. Retriever: dense \| bm25 \| hybrid. Answerer: Claude \| extractive. | One adapter is a hypothetical seam; two is a real one, and the second is always the one that runs with no daemon, no download and no key. That is what lets 20 tests and the whole eval run in under a second, and the CI gate run without an API key. |
| **Retrieval quality is a CI gate.** `python -m rag_lab eval --gate 0.9` exits 1 if heading·hybrid hit@5 drops. | A chunking change that quietly loses three questions is a regression like any other. The table lands in the job summary so the number is visible on every pull request. |
| **Hybrid by reciprocal rank fusion, not score mixing.** | BM25 scores and cosine similarities live on different scales; RRF only needs ranks. It rewards agreement and never needs a weight tuned per corpus. |
| **Heading path inside the chunk text.** | The cheapest possible context injection. A chunk that starts "Pipeline Lab > The pipeline, stage by stage" embeds differently from the same table alone, and the section name is what a citation shows the reader. |
| **Idempotent ingestion by content hash.** A chunk's id hashes source, section, position, flags and text; the store upserts by it and deletes ids the corpus no longer produces. | Re-running ingest over the same corpus embeds nothing; an edited paragraph re-embeds only itself; a deleted file or a moved section leaves nothing behind; a guard-pattern change re-flags exactly the chunks it touches. A chunking change is a `full=True` rebuild into its own collection (`rag-lab-<chunking>-<embedder>`), never a mixed one. |
| **The extractive answerer is the floor.** It returns the top passages, labelled, and says no model was used. The Claude answerer wraps it: citations must be labels it was given (others are dropped), `sufficient=false` is an honest "not in the documents", and any failure — API error, refusal, no typed answer — falls back. | The same principle as the finops agent's rules floor: the model makes the answer better; it never decides whether there is one. `answered_by` on every response says which path wrote the words. |
| **Retrieved text is data, in two layers.** At ingest, chunks that look like instructions to a model get `flags=('injection',)` and are stored, not dropped. At answer time flagged chunks are withheld from the context and listed as `withheld` in the response; the system prompt says the rest is data. | Dropping the planted document would hide the attack from the eval. Keeping it flagged means the guard check can assert both halves: the injected chunk *is* retrieved for the question that targets it, and it *is* flagged. The guard is a small regex list — explainable, and it had a false positive (the finops README's phrase "the system prompt says…") that a test caught and the pattern now avoids. |

## What is where

```
corpus/                 mesh-lab.md order-lab.md pipeline-lab.md finops-agent.md signal-desk.md
                        onboarding-notes.md  <- carries the planted injection (section "Assistant configuration")
eval/golden.jsonl       28 questions: source + must_contain phrases; one with expect_flagged
app/rag_lab/
  chunking.py           fixed_size() | by_heading(): pure functions, Document -> [Chunk]
  guard.py              injection_reasons(), guard(): flags, never deletes
  embed.py              FastEmbedEmbedder | HashingEmbedder
  store.py              QdrantStore | MemoryStore, keyed by content hash
  retrieve.py           Retriever: dense, bm25, hybrid (RRF)
  ingest.py             ingest(corpus_dir, deps) -> IngestReport, idempotent
  answer.py             ClaudeAnswerer | ExtractiveAnswerer; citations checked, flagged withheld
  evaluate.py           load_golden, evaluate -> hit@1 / hit@k / MRR, guard_check, markdown_table
  config.py             env -> Settings -> Wiring (the only module that reads os.environ)
  api.py                FastAPI: /ingest /search /ask /healthz /metrics
  __main__.py           CLI: ingest · search · ask · eval [--gate]
app/tests/              20 tests, hashing embedder + memory store, no network
docker-compose.yml      qdrant + api (corpus and eval mounted read-only)
scripts/                up.sh  demo.sh  down.sh
.github/workflows/      eval.yml: pytest + the gated eval on every PR
docs/                   architecture.html (interactive) and its archify source
```

## Running it

Prerequisites: Docker, Python 3.12. Commands are bash; on Windows run them
from Git Bash or `bash scripts/...` from PowerShell.

```powershell
# 0. No daemon, no key: tests and the eval in a terminal
cd app
python -m venv .venv && .venv\Scripts\pip install -r requirements.txt -r requirements-dev.txt
.venv\Scripts\python -m pytest -q                         # 20 passed, hashing embedder
.venv\Scripts\python -m rag_lab eval                      # the table above (first run downloads bge-small, ~130 MB)
.venv\Scripts\python -m rag_lab search "what stands in for the ALB locally" --mode hybrid
.venv\Scripts\python -m rag_lab ask "after how many failures does an order reach the DLQ"

# 1. Qdrant + the API in Docker, corpus ingested                (~2 min first time)
cd ..
bash scripts/up.sh

# 2. Prove each piece
bash scripts/demo.sh

# 3. Tear down
bash scripts/down.sh
```

`scripts/demo.sh` runs eight steps: health; a second ingest that re-embeds
nothing; the three retrievers on a question with an exact identifier; a
paraphrase with no shared words; a grounded answer with citations; the
planted injection retrieved, flagged and withheld; the full eval table with
the gate; the Prometheus metrics the API exposes.

### With Claude

```bash
ANTHROPIC_API_KEY=sk-ant-... app/.venv/Scripts/python -m rag_lab ask "why does signal-desk ingest on Lambda" --answerer claude
# or for the container:
ANTHROPIC_API_KEY=sk-ant-... docker compose up -d api
```

The model gets the passages (flagged ones withheld) and one tool, `answer`,
with `text`, `citations` and `sufficient`. Citations that are not labels from
the passages are dropped and logged. `claude-opus-5`, adaptive thinking,
medium effort, 45 s timeout, one retry, then the extractive floor.

### Poking at it

```bash
curl "http://localhost:8090/search?mode=dense&k=3" -G --data-urlencode "q=who may call httpbin"
curl -X POST http://localhost:8090/ask -H 'Content-Type: application/json' -d '{"question":"what does PLANT_VULN=1 prove"}'
curl http://localhost:8090/metrics
# edit a file under corpus/, then:
curl -X POST http://localhost:8090/ingest -d '{"full": false}' -H 'Content-Type: application/json'   # only the changed chunks
```

## Next steps

1. **A reranker.** A cross-encoder over the hybrid top-20 before cutting to k. The eval will say exactly what it buys on this corpus.
2. **Answer faithfulness as a metric.** With a key: for each golden question, ask Claude and check every claim against its cited passages (an LLM judge over `cited_text`), so the table gains a column the retrieval numbers cannot give.
3. **Chunk-size sweep.** `by_heading(max_words)` across 160/240/320/480 as one command, plotted.
4. **Semantic guard.** Embed a few known injection phrasings and flag chunks by cosine distance as a second layer behind the regexes.
5. **Feedback loop.** A thumbs-up/down on `/ask` written back beside the finding, so the golden set can grow from real questions.
6. **Put it on the pipeline.** `pipeline-lab`'s stages work on `app/` unchanged; the eval gate becomes a stage between build and deploy.

## What is real and what is not

- **Qdrant is real**, in Docker, with cosine distance, payloads and idempotent upserts by UUID derived from the content hash.
- **The embeddings are real**: `BAAI/bge-small-en-v1.5` through fastembed (ONNX, CPU, 384 dims), the same vectors in the container and in the eval.
- **The numbers in the table are real** and reproducible: `python -m rag_lab eval` prints them from the committed corpus and golden set.

The gaps, stated here rather than left to be found:

1. **The golden set is small and self-authored.** 28 questions over six documents by the person who wrote the documents. It measures relative changes well — chunking vs chunking, mode vs mode — and absolute numbers less so.
2. **The Claude answerer is verified with a scripted client, not a live call.** No API key was available when this was built. Grounding, citation checking, withholding and the fallbacks are covered by tests; a real run is one environment variable away.
3. **The guard is regexes.** It catches the planted document and the common phrasings; a determined attacker writes around it. The second layer (the model told it is data, and citations checked) is what limits the damage, and the honest fix is the semantic guard in *Next steps*.
4. **`onnxruntime` is pinned to 1.20.1.** The current release segfaulted on import on the machine this was built on; the pin is a workaround, not a preference.
5. **BM25 is rebuilt from the store after each ingest.** Fine for hundreds of chunks; a large corpus wants a persisted lexical index or Qdrant's sparse vectors.
6. **A code-review pass found six things after the first end-to-end run**, all fixed: the CLI's `--full` flag was always on; `/healthz` could trigger the model download (and race on it); the BM25 cache was invalidated by chunk *count* only; content-hash ids ignored position and flags and never removed deleted documents; the CI gate watched a branch name the repo did not use; `withheld` was reported even when nothing was withheld.
