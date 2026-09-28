#!/usr/bin/env bash
# Usage: ./run_local.sh /path/to/cyraduct-checkout
# Starts a throwaway local Cyraduct with the demo policy pack, runs the demo, cleans up.
set -euo pipefail
REPO="${1:?path to cyraduct checkout}"; HERE="$(cd "$(dirname "$0")" && pwd)"
cp "$HERE/policy_packs/finops_demo.json" "$REPO/policy_packs/"
cd "$REPO"
export CYRADUCT_ADMIN_KEY=demo-admin-key CYRADUCT_TEST_ADMIN_KEY=demo-test-key CYRADUCT_DATABASE_URL="sqlite:////tmp/cyraduct_demo.db"
rm -f /tmp/cyraduct_demo.db
python -m uvicorn main:app --port 8000 --log-level warning & PID=$!
trap 'kill $PID 2>/dev/null' EXIT
for i in $(seq 1 30); do curl -sf localhost:8000/healthz >/dev/null && break; sleep 0.5; done
cd "$HERE" && python demo.py --base-url http://localhost:8000 --admin-key demo-test-key --out "$HERE"
