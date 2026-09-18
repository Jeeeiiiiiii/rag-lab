#!/usr/bin/env bash
# Qdrant + the API, then ingest the corpus. Idempotent: run it again after
# editing the corpus and only the changed chunks are re-embedded.
set -euo pipefail
cd "$(dirname "$0")/.."

docker compose up -d --build
echo "waiting for the api..."
for _ in $(seq 1 60); do
  if curl -fs http://localhost:8090/healthz >/dev/null 2>&1; then break; fi
  sleep 2
done
curl -fs http://localhost:8090/healthz; echo
echo "ingesting (the first run downloads the embedding model, ~130 MB)..."
curl -fs -X POST http://localhost:8090/ingest -H 'Content-Type: application/json' -d '{"full": false}'; echo
