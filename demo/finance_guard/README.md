# Cyraduct Finance Guard - reference application (v0)

Cyraduct is the protocol. Finance Guard is its first vertical: a trusted adapter that stops **vendor
bank-detail changes and outbound payments** from executing unless the required human evidence exists
and a valid, unexpired, unrevoked, action-bound receipt is presented to the sink.

Run it (from the repo root, Git Bash or Linux/macOS):
```bash
bash demo/finance_guard/run_local.sh          # starts a throwaway server, runs 6 scenes, writes finance_evidence.md/.json
```

## What is new in this change (all additive, tested: 73 tests pass on Linux; on Windows expect only the one known migration-test failure)
| Change | File | Why |
|---|---|---|
| New consequence class `vendor_master_change` (15 min receipts) | `app/config.py`, `app/consequence.py` | `financial_transfer` *requires a numeric `amount`* (`policy_engine._validate_financial_transfer`), so a vendor bank-detail change cannot use it. |
| Generic `<field>_missing` condition | `app/policy_engine.py` | Fail-closed building block. Before this, a rule on a payload field silently did not match when the field was absent, so default-allow applied. Existing packs are unaffected (16 tests + full suite). |
| `finance_vendor_change_v1` policy pack | `policy_packs/` | 4 action types: `update_vendor_bank_details`, `update_vendor_remittance_details`, `initiate_ach_payment`, `initiate_wire_transfer`. Every required fact is denied when absent. |
| Adapter + 6-scene demo | `demo/finance_guard/` | Shows the pattern the product will follow. |
| Tests | `tests/test_finance_pack.py` | 16 cases incl. fail-closed and the BEC shape. |

## The pattern (do not break this)
`finance_guard.py` computes every policy fact in **trusted code** from the vendor master and the human review record:
`new_beneficiary`, `sender_domain_match`, `callback_channel_preexisting`, `callback_verified`, `dual_approval`,
`days_since_bank_change`. The requester, the email text and any LLM cannot set them. Only SHA-256 fingerprints of
account details go to Cyraduct. If a fact is not supplied, the pack denies.

## Scenes
1. Legit change (known domain, callback to the number already in the master, two humans) -> allow -> ERP applies it.
2. BEC (lookalike domain, callback to the number in the email, one reviewer) -> deny, no receipt, ERP refuses.
3. Caller omits the verification facts -> deny (fail-closed).
4. Payment right after a bank change -> conditional -> bank refuses until a named human escalates.
5. Normal payments allowed; 150,000 wire needs two approvers.
6. Legit receipt reused to redirect to a different account -> `action_binding_mismatch`.

## Corrections to the two research memos this is based on (verified against the code)
- The memo's example request uses `consequence_class: financial_transfer` for a vendor change with no `amount`.
  The engine would **deny it** (`financial_transfer_amount_must_be_numeric`), so this change adds a proper class.
- The memo's sink checklist says to "confirm the action hash matches". `GET /v1/attested/verify/{id}` does **not**
  check action binding; only `/v1/broker/execute` does. `cyraduct_guard.verify_at_sink()` recomputes the hash
  client-side (mirrors `app/receipts.py:_action_hash`). Ship this as an official SDK and add a server-side binding check.
- Replay/idempotency is already handled at Tier 3 (single-use claim), not at Tier 2 `/verify`.
- Stats used in pitch material were spot-checked: AFP 2025 (79% attempted/actual fraud, 63% BEC, 45% vendor imposter)
  are correct for 2024; the AFP **2026** survey (released 14 Apr 2026) shows 76% and BEC at 74% for 2025 - use the newer numbers.
  Nacha fraud-monitoring Phase 2 took effect 22 Jun 2026, so the buying trigger is **already live**. Never claim
  "Nacha compliant"; say the product supplies controls and evidence.

## Honest limits
1. Humans are simulated records; ERP and bank are in-memory stand-ins; no email/mailbox extraction exists yet.
2. Exercises Tier 2 (attested). A Tier 3 scene needs a deployed public sink (broker SSRF rules reject localhost).
3. Policy pack is unsigned (pack signing is roadmap). One shared admin key; no multi-tenant auth; SQLite default.
   **Do not put real customer finance data through this until the trust-layer tasks below are done.**
4. Broker still ignores `decision == "conditional"` (a conditional receipt executes at Tier 3 with no human). Decide and fix.
5. The two known fragile tests (live DNS in the broker test; SQLite file left open on Windows) still need a hardening PR.

## Engineer task list, in order
1. Trust layer before any real customer: Postgres by default, tenant auth + per-tenant signing keys, key rotation, signed packs, webhook allowlists.
2. Official SDKs (Python/Node/Go) with `verify_at_sink` and a `@requires_receipt` decorator; add server-side binding check.
3. Real approval queue (Slack/Teams) that emits the `ReviewRecord`; real mailbox intake (Gmail/M365 read-only) that extracts requests into the fixed schema.
4. One real ERP sink (QuickBooks Online or NetSuite) behind receipt verification. Add the Tier 3 scene on a deployed sink.
5. Audit-packet export (PDF/JSON) and OpenTelemetry/SIEM export.
6. Add `finance_vendor_change_v1` conformance fixtures to `policy_packs/fixtures.json`.
