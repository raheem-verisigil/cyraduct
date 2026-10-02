#!/usr/bin/env bash
# Usage (inside the repo):  cd demo/poisoned_invoice && ./run_local.sh ../..
# Usage (standalone):       ./run_local.sh /path/to/cyraduct-checkout
# Starts a throwaway local Cyraduct with the demo policy pack, runs the demo, cleans up.
set -euo pipefail
REPO="$(cd "${1:?path to cyraduct checkout}" && pwd)"; HERE="$(cd "$(dirname "$0")" && pwd)"
[ -f "$HERE/policy_packs/finops_demo.json" ] && cp "$HERE/policy_packs/finops_demo.json" "$REPO/policy_packs/"
[ -f "$REPO/policy_packs/finops_demo.json" ] || { echo "finops_demo.json not found in $REPO/policy_packs"; exit 1; }
cd "$REPO"; DB="./.demo_poisoned.db"; rm -f "$DB"
export CYRADUCT_ADMIN_KEY=demo-admin-key CYRADUCT_TEST_ADMIN_KEY=demo-test-key CYRADUCT_DATABASE_URL="sqlite:///$DB"
python -m uvicorn main:app --port 8000 --log-level warning & PID=$!
trap 'kill $PID 2>/dev/null || true; sleep 1; rm -f "$REPO/.demo_poisoned.db" || true' EXIT
for i in $(seq 1 40); do curl -sf localhost:8000/healthz >/dev/null && break; sleep 0.5; done
cd "$HERE" && python demo.py --base-url http://localhost:8000 --admin-key demo-test-key --out "$HERE"
