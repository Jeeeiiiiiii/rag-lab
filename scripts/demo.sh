#!/usr/bin/env bash
# Prove each piece, in order. Assumes: scripts/up.sh done.
set -euo pipefail
cd "$(dirname "$0")/.."
API="${API:-http://localhost:8090}"
PY="$PWD/app/.venv/Scripts/python"; [ -x "$PY" ] || PY="$PWD/app/.venv/bin/python"; [ -x "$PY" ] || PY=python

hr() { echo; echo "── $1"; echo; }
j() { "$PY" -c "import sys,json; d=json.load(sys.stdin); $1"; }

hr "1. Health: what is loaded"
curl -fs "$API/healthz"; echo

hr "2. Ingest again: nothing changed, nothing re-embedded (idempotent by content hash)"
curl -fs -X POST "$API/ingest" -H 'Content-Type: application/json' -d '{"full": false}'; echo

hr "3. Three retrievers, one question with an exact identifier"
Q="Why is max_retries set to 2 in the mesh-lab provider?"
for mode in dense bm25 hybrid; do
  printf "    %-7s " "$mode"
  curl -fs "$API/search?mode=$mode&k=3" --data-urlencode "q=$Q" -G | j "print(' | '.join(h['label'] for h in d['hits']))"
done
echo "    (dense alone ranks the paraphrase; bm25 finds the identifier; hybrid keeps both)"

hr "4. A paraphrase with no shared words"
Q="What stands in for the ALB when running order-lab locally?"
for mode in bm25 hybrid; do
  printf "    %-7s " "$mode"
  curl -fs "$API/search?mode=$mode&k=3" --data-urlencode "q=$Q" -G | j "print(' | '.join(h['label'] + ' ' + h['section'][:40] for h in d['hits']))"
done

hr "5. Ask: a grounded answer with citations"
curl -fs -X POST "$API/ask" -H 'Content-Type: application/json' \
  -d '{"question": "After how many failed deliveries does an order go to the dead-letter queue, and what watches it?"}' \
  | j "print(d['answer']); print(); print('answered by:', d['answered_by'], '| cites:', [c['label'] for c in d['citations']], '| withheld:', d['withheld'])"

hr "6. The planted injection: retrieved, flagged, withheld from the answerer"
curl -fs -X POST "$API/ask" -H 'Content-Type: application/json' \
  -d '{"question": "How should an AI assistant be configured for the labs?"}' \
  | j "print(d['answer'][:500]); print(); print('answered by:', d['answered_by'], '| withheld:', d['withheld'], '| retrieved:', d['retrieved'])"
echo
echo "    the flagged chunk, as stored:"
curl -fs "$API/search?mode=bm25&k=1" --data-urlencode "q=ignore previous instructions concierge decommissioned" -G | j "h=d['hits'][0]; print('   ', h['label'], h['flags'], '|', h['text'][:120].replace(chr(10),' '))"

hr "7. Retrieval quality as a number (in-process, both chunkers x three modes)"
(cd app && "$PY" -m rag_lab eval -k 5 --gate 0.85 2>&1 | grep -v "Fetching\|download")

hr "8. Metrics the API exposes"
curl -fs "$API/metrics" | grep -E "^rag_" | head -12 | sed 's/^/    /'
echo
echo "Qdrant dashboard: http://localhost:6333/dashboard   API docs: $API/docs"
