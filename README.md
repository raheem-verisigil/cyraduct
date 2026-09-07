# Cyraduct

An open, vendor-neutral **reliance and consequence-boundary protocol** for AI agent actions.
Cyraduct converts governance and assurance evidence into machine-enforceable reliance limits,
with independent receipts, revocation, simulation, and conformance testing.

This repository is the reference implementation. It is intentionally an MVP: the protocol
concepts (tiers, receipts, expiry, conformance fixtures, tamper-evident audit log) are real
and tested; the storage layer (SQLite) and broker execution (webhook proxy) are placeholders
meant to be swapped for production-grade infrastructure.

## The three enforcement tiers

Cyraduct does not claim one enforcement guarantee — it offers three, explicitly:

| Tier | Where it sits | What it guarantees | What it does NOT guarantee |
|---|---|---|---|
| **1. Advisory** | Outside the execution path | A documented decision trail | That a flagged action is actually stopped |
| **2. Attested** | Outside the path, but sinks must check | No compliant sink acts without a valid, unexpired receipt | Protection if a sink ignores the receipt requirement |
| **3. Broker-Enforced** | Inside the execution path | No bypass exists for integrated actions | Availability/latency now depend on Cyraduct uptime |

Every receipt carries a **consequence-class-appropriate expiry** (see `app/config.py`).
A receipt valid until explicitly revoked is treated as a design flaw, not a feature.

Full non-goals and tier definitions: see `docs/positioning.md` (copy of the published
positioning language) if you added it to this repo, or the project's positioning document.

## What's real vs. roadmap

Built and tested in this repo:
- **Ed25519-signed receipts**, independently verifiable with no server trust required (`verify_receipt.py` — runs standalone, air-gapped)
- **Receipt chaining** per agent (`prev_receipt_hash`, covered by the signature)
- **Rule-based consequence scoring** — transparent heuristic, not a black-box model (`app/consequence.py`)
- **Evidence registration** — hash-referenced assurance packages a receipt can cite (`/v1/evidence`)
- **Agent-scoped revocation** — kill every active receipt an agent holds in one call (`/v1/attested/revoke-agent/{agent_id}`)
- **Queryable receipts** by agent and time range (`/v1/receipts`)
- Everything from the original MVP: three tiers, policy packs, tamper-evident hash-chained audit log, kill switch, conformance suite (now 16 automated tests)

Explicitly **not** built here yet — real Phase 2/3 items, not implied by anything on the site:
- Framework SDKs (LangChain, Semantic Kernel, Bedrock Agents, etc.)
- A policy language / visual policy studio (policy packs are hand-written JSON)
- OpenTelemetry / SIEM export
- Federated multi-org broker mode
- Evidence-to-limit automatic binding (evidence can be *referenced* on a receipt; it does not yet *change* what a policy allows)
- A certification/marketplace program

## Project structure

```
cyraduct/
├── main.py                  # FastAPI app entrypoint
├── app/
│   ├── config.py             # Signing secret, expiry policy, admin key
│   ├── models.py              # Pydantic models: ActionRequest, Receipt, etc.
│   ├── policy_engine.py       # Loads + evaluates policy packs
│   ├── receipts.py            # Signs, hashes, expires receipts
│   ├── storage.py             # SQLite: receipts, revocations, hash-chained audit log, kill switch
│   └── routers/
│       ├── advisory.py        # Tier 1
│       ├── attested.py        # Tier 2 (evaluate / verify / revoke)
│       ├── broker.py          # Tier 3 (execute via webhook)
│       ├── conformance.py     # Published test-vector runner
│       └── admin.py           # Kill switch + audit log
├── policy_packs/
│   ├── generic.json
│   ├── banking.json
│   ├── healthcare.json
│   └── fixtures.json          # Positive AND negative conformance cases
├── tests/
│   └── test_conformance.py
├── requirements.txt
├── railway.json
├── Procfile
└── .env.example
```

## Run locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit secrets before any real use
uvicorn main:app --reload
```

Open `http://localhost:8000/docs` for interactive API docs.

Run the test suite (includes the negative conformance fixtures):

```bash
pip install pytest
pytest -v
```

## Verify a receipt independently

```bash
curl http://localhost:8000/v1/public-key | python3 -c "import json,sys; print(json.load(sys.stdin)['public_key_b64'])" > public_key.txt
curl -X POST http://localhost:8000/v1/attested/evaluate -H "Content-Type: application/json" \
  -d '{"agent_id":"agent-1","action_type":"read_public_doc","consequence_class":"low_risk","policy_pack":"generic","payload":{}}' \
  > receipt.json
python3 verify_receipt.py receipt.json public_key.txt
```

This runs with zero network calls to Cyraduct after the two curls above — the point is that verification does not require trusting or even reaching the server.

## Try it

```bash
# Tier 1 — advisory only, no receipt
curl -X POST http://localhost:8000/v1/advisory/evaluate \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"agent-1","action_type":"read_public_doc","consequence_class":"low_risk","policy_pack":"generic","payload":{}}'

# Tier 2 — attested, issues a receipt on allow/conditional
curl -X POST http://localhost:8000/v1/attested/evaluate \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"agent-1","action_type":"wire_transfer","consequence_class":"financial_transfer","purpose":"payroll","policy_pack":"generic","payload":{"amount":75000}}'

# Verify a receipt (this is what a sink calls before acting)
curl http://localhost:8000/v1/attested/verify/<receipt_id>

# Run the published conformance suite (positive AND negative cases)
curl -X POST http://localhost:8000/v1/conformance/run
```

## Deploy to Railway

1. Push this repo to GitHub (see below).
2. In Railway: **New Project → Deploy from GitHub repo** → select this repo.
3. Railway auto-detects `railway.json` / `Procfile` and uses Nixpacks to build.
4. Set environment variables in the Railway dashboard (Settings → Variables):
   - `CYRADUCT_SIGNING_SECRET` — long random string
   - `CYRADUCT_ADMIN_KEY` — long random string
   - (optional) `CYRADUCT_DATABASE_URL` — leave default for SQLite, or point at a
     Railway Postgres plugin once you migrate storage (see Known limitations).
5. Deploy. Railway assigns a public URL; `/docs` will be live there.

## Push to GitHub

```bash
cd cyraduct
git init
git add .
git commit -m "Cyraduct reference implementation: tiered enforcement, receipts, conformance suite"
git branch -M main
git remote add origin https://github.com/<your-username>/cyraduct.git
git push -u origin main
```

## Known limitations (MVP, by design)

- **Storage is SQLite on local disk.** Fine for a pilot; on Railway this resets on
  redeploy unless you attach a persistent volume or migrate to Postgres. Do not use
  this as-is for anything carrying real financial or health-record consequences.
- **Broker execution is a generic webhook proxy**, not a real MCP/A2A/protocol
  terminator. Treat `/v1/broker/execute` as a proof of the *pattern* (in-path
  enforcement), not a production broker.
- **Policy packs are unsigned placeholders.** The `signed_by` field names where a
  real domain-authority signature would go. Cryptographic pack signing is not yet
  implemented — see `app/policy_engine.py` for where to add it.
- **No multi-tenant auth model yet.** One shared admin key. Fine for a single pilot
  deployment; not fine for multiple customers on one instance.

These are the honest next steps, not hidden gaps — consistent with the project's
own non-goals: Cyraduct does not claim guarantees it hasn't built yet.
