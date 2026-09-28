# Cyraduct wedge demo - "the poisoned invoice"

A prompt-injected finance-ops agent tries to wire 480,000 to an attacker. Without Cyraduct the bank pays.
With Cyraduct the action is denied at the boundary, tampered receipts are refused, a human gate is
enforced on large wires, revocation kills live receipts, and every step leaves independently verifiable evidence.

Tested end to end against the real Cyraduct code (public repo, current `main`) on a local instance: all scenes pass.

## Run it (2 minutes)
Inside the Cyraduct repo (after `install_into_repo.sh`): `cd demo/poisoned_invoice && ./run_local.sh ../..`

Standalone:
```bash
git clone https://github.com/raheem-verisigil/cyraduct && pip install -r cyraduct/requirements.txt httpx
./run_local.sh ./cyraduct        # starts a throwaway server, runs the demo, writes evidence_report.md/.json
```
Against a running instance instead: `python demo.py --base-url URL --admin-key KEY`
(use the scoped TEST key, never the full admin key; demo traffic uses the `test-` agent namespace; key is optional; without it Scene 5 and the audit-log check are skipped).

## What is in the box
| File | Purpose |
|---|---|
| `demo.py` | The 6 scenes + evidence report. Exit code != 0 if any scene misbehaves, so it doubles as a CI test. |
| `cyraduct_guard.py` | **The integration piece.** Agent side: `client.guard(...)` decorator / `authorize()`. Sink side: `verify_at_sink()` (signature, expiry, action binding, conditional gate, server revocation check). |
| `policy_packs/finops_demo.json` | Demo pack. Copy into the repo's `policy_packs/`. |
| `run_local.sh` | One-command local run. |
| `install_into_repo.sh` | Safe, additive install on a new branch (no push, never touches main). |
| `evidence_report.md/.json` | Sample output from a real run. |

## Scenes
0. No protection: poisoned invoice -> money leaves.
1. Legit 12,000 payroll wire -> allow -> signed receipt -> bank executes -> receipt verified offline with only the public key.
2. Same poisoned invoice -> DENY (payee not on allowlist), no receipt exists, bank refuses a direct call.
3. Valid receipt reused for a different payee/amount -> `action_binding_mismatch`.
4. 75,000 wire -> `conditional` -> bank refuses until a human approves.
5. `revoke-agent` -> a still-unexpired receipt is refused (`receipt_revoked`).

## Key design point for the engineer
`enrich()` in `demo.py` computes `payee_on_allowlist` in trusted code and puts it in the payload. The model
never sees or controls it. That is why an injected instruction cannot talk its way past the policy. Real
integrations should follow this pattern: policy facts come from code and data the agent cannot write to.

## Honest limits - read before recording or pitching
1. **The agent brain is scripted.** It obeys instructions hidden in a document so the demo is reproducible
   without an LLM. Do not present Scene 0/2 as a live model being fooled. Next step: swap in a real LLM
   agent (Claude with a `wire_transfer` tool) behind the same guard.
2. **This exercises Tier 2 (Attested), not Tier 3 (Broker).** The broker's SSRF check requires a public
   `https` webhook and rejects localhost, so a local demo cannot use it. A Tier 3 scene needs a deployed
   sink. Not tested here.
3. **Replay:** `/verify` does not consume receipts, so at Tier 2 an exact replay of the same action with
   the same receipt is not stopped by Cyraduct. Only the broker's single-use claim does that. Say so plainly.
4. **Fail-open on custom payload conditions.** A rule like `payee_on_allowlist: false` only fires if the
   field exists (`policy_engine.py` fallback compares `payload.get(key) != expected`; missing -> no match).
   The guard always sets it, but the engine should gain a fail-closed "field required" condition.
5. **Broker vs. `conditional` receipts:** `broker.py` never checks `decision == "conditional"`, so a
   conditional receipt executes at Tier 3 without a human. Decide whether that is intended; this demo's
   sink enforces the human gate itself.
6. `cyraduct_guard.action_hash()` mirrors `app/receipts.py:_action_hash`. It must change in lockstep.
   Better: ship it as an official SDK and add a server-side "check binding" endpoint.
7. Human approval is a stub (`human_approved=True`). Demo pack is unsigned (pack signing is still roadmap).

## Suggested integration tasks
1. Add `finops_demo.json` and run the demo in CI on every commit (regression = red build).
2. Package `cyraduct_guard.py` as a pip SDK; add a LangChain / OpenAI-tools wrapper around `guard`.
3. Add fail-closed field conditions (limit 4) and decide limit 5.
4. Add a Tier 3 scene against a deployed public sink.
5. Replace the scripted agent with a real LLM agent, then record the 60-90 second demo from `run_local.sh`.
