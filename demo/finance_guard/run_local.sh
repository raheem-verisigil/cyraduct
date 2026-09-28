#!/usr/bin/env bash
# Run from anywhere:  demo/finance_guard/run_local.sh
# Starts a throwaway local Cyraduct (relative SQLite file, Windows-safe), runs the demo, cleans up.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; REPO="$(cd "$HERE/../.." && pwd)"
cd "$REPO"; DB="./.finance_demo.db"; rm -f "$DB"
export CYRADUCT_DATABASE_URL="sqlite:///$DB"
python -m uvicorn main:app --port 8000 --log-level warning & PID=$!
trap 'kill $PID 2>/dev/null || true; sleep 1; rm -f "$REPO/.finance_demo.db" || true' EXIT
for i in $(seq 1 40); do curl -sf localhost:8000/healthz >/dev/null && break; sleep 0.5; done
cd "$HERE" && python finance_demo.py --base-url http://localhost:8000 --out "$HERE"
