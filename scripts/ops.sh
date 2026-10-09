#!/usr/bin/env bash
# The wire desk: one question through every retriever, the answer, intake
# and the audit, read live from the running lab. Start the lab first
# (scripts/up.sh); this only reads it. Standard library, so any python3 works.
set -euo pipefail
cd "$(dirname "$0")/.."

PY="$(command -v python3 || command -v python)"
echo "open http://localhost:${OPS_PORT:-8095}"
exec "$PY" ops/server.py
