# Cyraduct

An open, vendor-neutral **reliance and consequence-boundary protocol** for AI agent actions.
Cyraduct converts governance and assurance evidence into machine-enforceable reliance limits,
with independent Ed25519-signed receipts, revocation, evidence registration, and conformance testing.

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
| **3. Broker-Enforced** | Inside the execution path | No bypass exists for integrated actions holding a valid receipt | Availability/latency now depend on Cyraduct uptime |

**Broker mode is a two-step flow, not one call.** The broker does not mint its own
authorization — it validates a receipt you already hold (from a prior `/v1/attested/evaluate`
call) before executing:
POST /v1/attested/evaluate → issues a signed receipt (if allowed)
POST /v1/broker/execute?receipt_id=<id>&execution_webhook=<url>
→ checks: exists → not revoked → signature valid → not expired
→ action/agent binding matches the presented request
→ only then calls the execution webhook

That last check — action/agent binding — exists specifically to stop a receipt issued
for one action from being replayed against a different action with the same ID.

Every receipt carries a **consequence-class-appropriate expiry** (see `app/config.py`).
A receipt valid until explicitly revoked is treated as a design flaw, not a feature.

## What's real vs. roadmap

Built and tested in this repo:
- **Ed25519-signed receipts**, independently verifiable with no server trust required (`verify_receipt.py` — runs standalone, air-gapped)
- **Receipt chaining** per agent (`prev_receipt_hash`, covered by the signature)
- **Rule-based consequence scoring** — transparent heuristic, not a black-box model (`app/consequence.py`)
- **Evidence registration** — hash-referenced assurance packages a receipt can cite (`/v1/evidence`)
- **Agent-scoped revocation** — kill every active receipt an agent holds in one call (`/v1/attested/revoke-agent/{agent_id}`)
- **Queryable receipts** by agent and time range (`/v1/receipts`)
- **Broker-side receipt validation** — full check sequence (existence, revocation, signature, expiry, action/agent binding) before any execution webhook is called
- Three tiers, policy packs, tamper-evident hash-chained audit log, kill switch, conformance suite — 22 automated tests, including 6 broker-specific negative cases

Explicitly **not** built here yet — real Phase 2/3 items, not implied by anything on the site:
- Framework SDKs (LangChain, Semantic Kernel, Bedrock Agents, etc.)
- A policy language / visual policy studio (policy packs are hand-written JSON)
- OpenTelemetry / SIEM export
- Federated multi-org broker mode
- Evidence-to-limit automatic binding (evidence can be *referenced* on a receipt; it does not yet *change* what a policy allows)
- A certification/marketplace program

## Project structure

cyraduct/
├── main.py # FastAPI app entrypoint, public-key endpoint
├── generate_key.py # One-time signing keypair generator for deployment
├── verify_receipt.py # Standalone receipt verifier (no server trust required)
├── app/
│ ├── config.py # Expiry policy, admin key
│ ├── crypto.py # Ed25519 signing/verification
│ ├── consequence.py # Transparent consequence scoring heuristic
│ ├── models.py # Pydantic models: ActionRequest, Receipt, etc.
│ ├── policy_engine.py # Loads + evaluates policy packs
│ ├── receipts.py # Issues, hashes, chains, expires receipts
│ ├── storage.py # SQLite: receipts, revocations, audit log, evidence, kill switch
│ └── routers/
│ ├── advisory.py # Tier 1
│ ├── attested.py # Tier 2 (evaluate / verify / revoke / revoke-agent)
│ ├── broker.py # Tier 3 (validates a receipt, then executes via webhook)
│ ├── conformance.py # Published test-vector runner
│ ├── evidence.py # Evidence package registration
│ ├── receipts.py # Receipt querying by agent/time range
│ └── admin.py # Kill switch + audit log
├── policy_packs/
│ ├── generic.json
│ ├── banking.json
│ ├── healthcare.json
│ └── fixtures.json # Positive AND negative conformance cases
├── tests/
│ └── test_conformance.py
├── LICENSE # Apache 2.0
├── requirements.txt
├── railway.json
├── Procfile
└── .env.example


## Run locally

```bash
python -m venv venv
source venv/Scripts/activate   # Windows Git Bash; use "source venv/bin/activate" on Mac/Linux
pip install -r requirements.txt
cp .env.example .env   # edit secrets before any real use
uvicorn main:app --reload
```

Open `http://localhost:8000/docs` for interactive API docs.

Run the test suite (includes the negative conformance fixtures and broker validation tests):

```bash
pip install pytest pytest-asyncio
pytest -v
```

## Generate a signing key

```bash
python generate_key.py
```

Prints a private key (set as `CYRADUCT_PRIVATE_KEY_B64` — a deployment secret, never commit it)
and its corresponding public key. In deployed environments, always set `CYRADUCT_PRIVATE_KEY_B64`
explicitly — without it, a fresh key is generated on disk at every boot, which is fine for local
dev but means the signing identity resets on every redeploy on most PaaS platforms.

## Verify a receipt independently

```bash
curl http://localhost:8000/v1/public-key | python -c "import json,sys; print(json.load(sys.stdin)['public_key_b64'])" > public_key.txt
curl -X POST http://localhost:8000/v1/attested/evaluate -H "Content-Type: application/json" \
  -d '{"agent_id":"agent-1","action_type":"read_public_doc","consequence_class":"low_risk","policy_pack":"generic","payload":{}}' \
  > receipt.json
python verify_receipt.py receipt.json public_key.txt
```

This runs with zero network calls to Cyraduct after the two curls above — the point is that
verification does not require trusting or even reaching the server.

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

# Tier 3 — broker-enforced. Requires a receipt_id from a prior /v1/attested/evaluate call —
# the broker validates and executes against a receipt you already hold, it does not mint its own.
curl -X POST "http://localhost:8000/v1/broker/execute?receipt_id=<receipt_id>&execution_webhook=https://your-sink.example.com/execute" \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"agent-1","action_type":"wire_transfer","consequence_class":"financial_transfer","purpose":"payroll","policy_pack":"generic","payload":{"amount":75000}}'

# Run the published conformance suite (positive AND negative cases)
curl -X POST http://localhost:8000/v1/conformance/run
```

## Deploy to Railway

1. Push this repo to GitHub.
2. In Railway: **New Project → Deploy from GitHub repo** → select this repo.
3. Railway auto-detects `railway.json` / `Procfile` and uses Nixpacks to build.
4. Set environment variables in the Railway dashboard (Settings → Variables):
   - `CYRADUCT_PRIVATE_KEY_B64` — from `python generate_key.py`, mark as secret. Keeps the
     signing identity stable across redeploys — do not skip this.
   - `CYRADUCT_ADMIN_KEY` — long random string (gates kill switch, revocation, audit log)
   - (optional) `CYRADUCT_KEY_ID` — a label for your key, e.g. `cyraduct-prod-1`
5. Deploy. Railway assigns a public URL; `/docs` will be live there.

## Known limitations (MVP, by design)

- **Storage is SQLite on local disk.** Fine for a pilot; on Railway this resets on
  redeploy unless you attach a persistent volume or migrate to Postgres. Do not use
  this as-is for anything carrying real financial or health-record consequences.
- **Broker execution is a generic webhook proxy**, not a real MCP/A2A/protocol
  terminator. Treat `/v1/broker/execute` as a proof of the *pattern* (in-path
  enforcement with receipt validation), not a production broker.
- **Policy packs are unsigned placeholders.** The `signed_by` field names where a
  real domain-authority signature would go. Cryptographic pack signing is not yet
  implemented — see `app/policy_engine.py` for where to add it.
- **No multi-tenant auth model yet.** One shared admin key. Fine for a single pilot
  deployment; not fine for multiple customers on one instance.

These are the honest next steps, not hidden gaps — consistent with the project's
own non-goals: Cyraduct does not claim guarantees it hasn't built yet.