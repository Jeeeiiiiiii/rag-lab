"""Wire desk: put one question through every retriever and watch what runs.

Runs on your machine, not in Docker. It reads what the lab already exposes:

  the API (localhost:8090)  -- /search once per retriever, /ask, /ingest,
                               /healthz and /metrics, exactly as curl would
  Qdrant (localhost:6333)   -- the stored chunks, for their full text (the
                               API's /search cuts text at 300 characters)
  the eval                  -- `python -m rag_lab eval` in the app's venv,
                               the same command CI gates on

Nothing is simulated. Where the page explains a hybrid hit as "dense #3 +
BM25 #1", both ranks come from /search calls made at the same depth the
hybrid retriever uses internally, and the sum is checked against the score
the API returned.

Standard library only. Started by scripts/ops.sh.
"""

import ast
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PORT = int(os.environ.get("OPS_PORT", "8095"))
API = os.environ.get("RAG_API", "http://localhost:8090")
QDRANT = os.environ.get("QDRANT_URL", "http://localhost:6333")
CORPUS = os.path.join(ROOT, "corpus")
GOLDEN = os.path.join(ROOT, "eval", "golden.jsonl")
RRF_K = 60     # Retriever(rrf_k=60) in app/rag_lab/retrieve.py
GATE = 0.9     # the CI gate in .github/workflows/eval.yml


def depth_for(k):
    """How deep hybrid reads each retriever before fusing (retrieve.py)."""
    return max(k * 3, 20)


# --- reading the lab ------------------------------------------------------------

def http_json(method, url, body=None, timeout=60):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        try:
            detail = json.loads(detail).get("detail", detail)
        except ValueError:
            pass
        raise RuntimeError(f"{url.split('?')[0]} answered {e.code}: {detail}") from None


def http_text(url, timeout=10):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def search(q, k, mode):
    qs = urllib.parse.urlencode({"q": q, "k": k, "mode": mode})
    t0 = time.monotonic()
    hits = http_json("GET", f"{API}/search?{qs}")["hits"]
    return hits, round((time.monotonic() - t0) * 1000)


def parse_metrics(text):
    requests, answers, chunks = {}, {}, None
    for line in text.splitlines():
        m = re.match(r'rag_requests_total\{route="([^"]+)",status="(\d+)"\} (\d+)', line)
        if m:
            requests.setdefault(m[1], {})[m[2]] = int(m[3])
        m = re.match(r'rag_answers_total\{answered_by="([^"]+)"\} (\d+)', line)
        if m:
            answers[m[1]] = int(m[2])
        m = re.match(r"rag_chunks (\d+)", line)
        if m:
            chunks = int(m[1])
    return {"requests": requests, "answered_by": answers, "chunks": chunks}


class Chunks:
    """Full chunk text from Qdrant, keyed by label (source#ordinal).

    Re-read whenever the stored count changes or an ingest ran, so an edited
    corpus never shows stale text."""

    def __init__(self):
        self.lock = threading.Lock()
        self.by_label, self.collection, self.count = {}, None, -1

    def collection_name(self, chunking):
        names = [c["name"] for c in http_json("GET", f"{QDRANT}/collections")["result"]["collections"]]
        prefix = f"rag-lab-{chunking}-"
        mine = [n for n in names if n.startswith(prefix)]
        return mine[0] if mine else None

    def refresh(self, chunking, count, force=False):
        with self.lock:
            if not force and count == self.count and self.by_label:
                return
            name = self.collection_name(chunking)
            by_label, offset = {}, None
            while name:
                body = {"limit": 256, "with_payload": True, "with_vector": False}
                if offset is not None:
                    body["offset"] = offset
                page = http_json("POST", f"{QDRANT}/collections/{name}/points/scroll", body)["result"]
                for p in page["points"]:
                    pl = p["payload"]
                    by_label[f'{pl["source"]}#{pl["ordinal"]}'] = pl
                offset = page.get("next_page_offset")
                if offset is None:
                    break
            self.by_label, self.collection, self.count = by_label, name, count

    def text(self, label, fallback):
        pl = self.by_label.get(label)
        return pl["text"] if pl else fallback


CHUNKS = Chunks()


def load_golden():
    items = []
    with open(GOLDEN, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                d = json.loads(line)
                items.append({"q": d["q"], "source": d["source"],
                              "must_contain": d.get("must_contain", []),
                              "expect_flagged": bool(d.get("expect_flagged", False))})
    return items


def relevant(source, text, item):
    """evaluate.is_relevant, applied to the full chunk text."""
    if not item or item["expect_flagged"] or source != item["source"]:
        return False
    low = text.lower()
    return all(p.lower() in low for p in item["must_contain"])


def corpus_files():
    files = []
    for name in sorted(os.listdir(CORPUS)):
        if not name.endswith(".md"):
            continue
        path = os.path.join(CORPUS, name)
        with open(path, "rb") as f:
            raw = f.read()
        files.append({"name": name, "bytes": len(raw), "mtime": int(os.path.getmtime(path) * 1000),
                      "sha": hashlib.sha256(raw).hexdigest()[:12]})
    return files


# --- the desk's three jobs ----------------------------------------------------------

def file_story(q, k, golden_index=None):
    """One question, every retriever, the answer: one call, so the page
    re-files all three wires together."""
    health = http_json("GET", f"{API}/healthz", timeout=10)
    CHUNKS.refresh(health["chunking"], health["chunks"])
    golden = load_golden()
    item = None
    if golden_index is not None and 0 <= golden_index < len(golden):
        item = golden[golden_index]
    else:
        item = next((g for g in golden if g["q"].strip().lower() == q.strip().lower()), None)

    depth = depth_for(k)
    with ThreadPoolExecutor(max_workers=4) as pool:
        f_dense = pool.submit(search, q, depth, "dense")
        f_bm25 = pool.submit(search, q, depth, "bm25")
        f_hybrid = pool.submit(search, q, k, "hybrid")
        t0 = time.monotonic()
        f_ask = pool.submit(http_json, "POST", f"{API}/ask", {"question": q, "k": k, "mode": "hybrid"})
        (dense, dense_ms), (bm25, bm25_ms), (hybrid, hybrid_ms) = f_dense.result(), f_bm25.result(), f_hybrid.result()
        answer = f_ask.result()
        ask_ms = round((time.monotonic() - t0) * 1000)

    dense_rank = {h["label"]: i + 1 for i, h in enumerate(dense)}
    bm25_rank = {h["label"]: i + 1 for i, h in enumerate(bm25)}

    def card(h, rank):
        text = CHUNKS.text(h["label"], h["text"])
        return {"rank": rank, "label": h["label"], "source": h["source"], "section": h["section"],
                "score": h["score"], "flags": h["flags"], "text": text,
                "relevant": relevant(h["source"], text, item)}

    wires = {"dense": [card(h, i + 1) for i, h in enumerate(dense[:k])],
             "bm25": [card(h, i + 1) for i, h in enumerate(bm25[:k])],
             "hybrid": []}
    for i, h in enumerate(hybrid):
        c = card(h, i + 1)
        dr, br = dense_rank.get(h["label"]), bm25_rank.get(h["label"])
        parts = [1 / (RRF_K + r) for r in (dr, br) if r]
        c["fusion"] = {"dense_rank": dr, "bm25_rank": br, "depth": depth,
                       "sum": round(sum(parts), 4), "matches_api": abs(sum(parts) - h["score"]) < 1e-3}
        wires["hybrid"].append(c)

    def first_relevant(cards, full=None):
        for c in cards:
            if c["relevant"]:
                return c["rank"]
        # Not in the top k: where does it sit in the deeper list, if anywhere?
        for i, h in enumerate(full or []):
            if relevant(h["source"], CHUNKS.text(h["label"], h["text"]), item):
                return {"beyond": i + 1}
        return None

    return {
        "q": q, "k": k, "depth": depth,
        "golden": ({**item, "index": golden.index(item)} if item else None),
        "wires": wires,
        "right_copy": ({"dense": first_relevant(wires["dense"], dense), "bm25": first_relevant(wires["bm25"], bm25),
                        "hybrid": first_relevant(wires["hybrid"])} if item and not item["expect_flagged"] else None),
        "ms": {"dense": dense_ms, "bm25": bm25_ms, "hybrid": hybrid_ms, "ask": ask_ms},
        "answer": answer,
        "health": health,
    }


class Desk:
    """Slow-changing state, refreshed in the background; /api/desk reads it."""

    def __init__(self):
        self.lock = threading.Lock()
        self.intake = None          # last ingest report this desk triggered
        self.intake_files = None    # corpus file hashes at that moment
        self.audit = {"state": "idle"}

    def snapshot(self):
        errors = []
        health = metrics = None
        try:
            health = http_json("GET", f"{API}/healthz", timeout=5)
        except Exception as e:
            errors.append(f"API {API}: {e}")
        if health:
            try:
                metrics = parse_metrics(http_text(f"{API}/metrics"))
            except Exception as e:
                errors.append(f"metrics: {e}")
        files = corpus_files()
        with self.lock:
            changed = None
            if self.intake_files is not None:
                before = {f["name"]: f["sha"] for f in self.intake_files}
                changed = [f["name"] for f in files if before.get(f["name"]) != f["sha"]] + \
                          [n for n in before if n not in {f["name"] for f in files}]
            return {"health": health, "metrics": metrics, "files": files, "changed_since_intake": changed,
                    "intake": self.intake, "audit": self.audit, "golden": load_golden(),
                    "config": {"api": API, "qdrant": QDRANT, "rrf_k": RRF_K, "gate": GATE},
                    "now": int(time.time() * 1000), "errors": errors}

    def run_intake(self, full):
        files = corpus_files()
        t0 = time.monotonic()
        report = http_json("POST", f"{API}/ingest", {"full": bool(full)}, timeout=600)
        ms = round((time.monotonic() - t0) * 1000)
        health = http_json("GET", f"{API}/healthz", timeout=10)
        CHUNKS.refresh(health["chunking"], health["chunks"], force=True)
        with self.lock:
            previous = self.intake_files
            self.intake = {**report, "full": bool(full), "ms": ms, "at": int(time.time() * 1000),
                           "changed_files": ([f["name"] for f in files
                                              if {p["name"]: p["sha"] for p in previous}.get(f["name"]) != f["sha"]]
                                             if previous is not None else None)}
            self.intake_files = files
            return self.intake

    def start_audit(self):
        with self.lock:
            if self.audit.get("state") == "running":
                return self.audit
            self.audit = {"state": "running", "started": int(time.time() * 1000)}
        threading.Thread(target=self._audit, daemon=True).start()
        return self.audit

    def _audit(self):
        venv = os.path.join(ROOT, "app", ".venv")
        py = next((p for p in (os.path.join(venv, "Scripts", "python.exe"), os.path.join(venv, "bin", "python"))
                   if os.path.exists(p)), sys.executable)
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "HF_HUB_DISABLE_SYMLINKS_WARNING": "1",
               "TOKENIZERS_PARALLELISM": "false"}
        env.pop("QDRANT_URL", None)  # the eval runs in memory, as in CI
        cmd = [py, "-m", "rag_lab", "-v", "eval", "--json", "--gate", str(GATE)]
        t0 = time.monotonic()
        try:
            p = subprocess.run(cmd, cwd=os.path.join(ROOT, "app"), env=env, capture_output=True,
                               text=True, encoding="utf-8", errors="replace", timeout=900)
            result = parse_eval(p.stdout, p.stderr)
            result.update({"state": "done", "exit": p.returncode, "command": "python -m rag_lab eval --gate 0.9"})
            if not result["rows"]:
                result.update({"state": "failed", "error": (p.stderr.strip().splitlines() or ["no output"])[-1]})
        except Exception as e:
            result = {"state": "failed", "error": str(e)}
        result["seconds"] = round(time.monotonic() - t0, 1)
        result["finished"] = int(time.time() * 1000)
        with self.lock:
            self.audit = {**self.audit, **result}


MISS = re.compile(r"miss \[(\w+)/(\w+)\] (.+?) → rank (\w+), top: (\[.*\])$")
GUARD = re.compile(r"guard \[(\w+)\]: (.+?) → planted doc retrieved=(\w+), flagged=(\w+)$")
GATE_LINE = re.compile(r"gate: .*?= ([\d.]+) (?:>=|<) ([\d.]+) → (PASS|FAIL)")


def parse_eval(stdout, stderr):
    rows = []
    start = stdout.find("\n[")
    if start >= 0:
        try:
            for r in json.loads(stdout[start:]):
                chunking = r["label"].split(" ")[0]
                rows.append({"chunking": chunking, "embedder": r["label"].split("· ")[-1], "mode": r["mode"],
                             "hit1": r["hit@1"], "hitk": r["hit@k"], "mrr": r["mrr"]})
        except ValueError:
            pass
    misses, guard, gate = [], [], None
    for line in stderr.splitlines():
        line = line.strip()
        if m := MISS.search(line):
            misses.append({"chunking": m[1], "mode": m[2], "q": ast.literal_eval(m[3]),
                           "rank": None if m[4] == "None" else int(m[4]), "top": ast.literal_eval(m[5])})
        elif m := GUARD.search(line):
            guard.append({"chunking": m[1], "q": ast.literal_eval(m[2]),
                          "retrieved": m[3] == "True", "flagged": m[4] == "True"})
        elif m := GATE_LINE.search(line):
            gate = {"value": float(m[1]), "threshold": float(m[2]), "pass": m[3] == "PASS"}
    return {"rows": rows, "misses": misses, "guard": guard, "gate": gate}


DESK = Desk()


# --- HTTP ---------------------------------------------------------------------

FONT_TYPES = {".woff2": "font/woff2", ".css": "text/css"}


class Handler(BaseHTTPRequestHandler):
    def send(self, status, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            with open(os.path.join(HERE, "index.html"), "rb") as f:
                self.send(200, f.read(), "text/html; charset=utf-8")
        elif path == "/frame":
            # Capture aid: the page at a phone width inside a same-origin iframe,
            # because headless Chrome will not open a window narrower than ~500px.
            qs = urllib.parse.parse_qs(self.path.partition("?")[2])
            w = int(qs.pop("w", ["390"])[0])
            inner = urllib.parse.urlencode({k: v[0] for k, v in qs.items()})
            self.send(200, (f'<!doctype html><body style="margin:0;background:#232B25">'
                            f'<iframe src="/?{inner}" style="width:{w}px;height:100vh;border:0;display:block">'
                            f'</iframe>').encode(), "text/html; charset=utf-8")
        elif path == "/api/desk":
            self.send(200, DESK.snapshot())
        elif path.startswith("/fonts/") and "/" not in path[7:] and ".." not in path:
            f = os.path.join(HERE, "fonts", path[7:])
            if not os.path.isfile(f):
                return self.send(404, {"error": "no such font"})
            with open(f, "rb") as fh:
                self.send(200, fh.read(), FONT_TYPES.get(os.path.splitext(f)[1], "application/octet-stream"))
        else:
            self.send(404, {"error": f"no route for {path}"})

    def do_POST(self):
        path = self.path.split("?")[0]
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        except ValueError:
            return self.send(400, {"error": "body is not JSON"})
        try:
            if path == "/api/file":
                q = str(body.get("q", "")).strip()
                if len(q) < 3:
                    return self.send(400, {"error": "the assignment needs at least three characters"})
                k = max(1, min(10, int(body.get("k", 5))))
                g = body.get("golden")
                self.send(200, file_story(q, k, int(g) if g is not None else None))
            elif path == "/api/intake":
                self.send(200, DESK.run_intake(body.get("full", False)))
            elif path == "/api/audit":
                self.send(200, DESK.start_audit())
            else:
                self.send(404, {"error": f"no route for {path}"})
        except Exception as e:
            self.send(502, {"error": str(e)})

    def log_message(self, fmt, *args):
        if "/api/desk" not in self.path:
            print(f"{self.command} {self.path} -> {args[1] if len(args) > 1 else ''}", flush=True)


if __name__ == "__main__":
    print(f"wire desk on http://localhost:{PORT}  (API {API}, Qdrant {QDRANT})", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
