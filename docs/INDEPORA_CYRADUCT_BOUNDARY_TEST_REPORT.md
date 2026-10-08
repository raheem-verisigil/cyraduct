# INDEPORA–Cyraduct Boundary Test Report

**Run date:** 2026-10-08  
**Scope:** Synthetic, sandbox-only, local controlled sink. No production financial, ERP, customer, or external execution system was contacted.

## Executive result

The boundary contract passed. Cyraduct accepted a signed INDEPORA Continuity Record, derived only the allowlisted assurance facts, bound the record hash and facts into the canonical action envelope, issued an Ed25519-signed authorization receipt, and reached the local sink once. Mutations, forged agent-supplied assurance, changed evidence references, and receipt replay were rejected.

The result does **not** prove that INDEPORA’s lineage analysis is correct. It proves the narrower and more important integration boundary:

> INDEPORA establishes the evidence-assurance result; Cyraduct verifies the exact result and enforces consequence-specific reliance on the exact action.

## Synthetic input

The fixture used the provisional schema `indepora.evidence_continuity_record.v1` with record ID `icr_test_001` and a test Ed25519 issuer key. The record represented eight apparent evidence references, two candidate origins, one unknown relationship, zero conflicts, `standing.status = insufficient`, and `standing.scope = sandbox`.

The record hash from this run was:

```text
c1a6767b5c208905e8a4aa58cb12cc4673e0a891b8e7e2598a67ef2cb9a6ca65
```

The record was valid for fifteen minutes and marked not superseded.

## Boundary test matrix

| Test | Attack or condition | Detection layer | Actual result |
|---|---|---|---|
| T01 | Valid signed Continuity Record | INDEPORA adapter endpoint | `valid: true` |
| T02 | Exact record consumed by Cyraduct | Canonical envelope and policy | `allow`; receipt contained record hash, standing, origin count, unknown count, expiry and key ID |
| T03 | Authorized action sent to local controlled sink | Broker enforcement | `executed: true`; exactly one sink call |
| T04 | Candidate-origin count changed from 2 to 8 after authorization | Broker-time record verification | Rejected: `indepora_record_hash_mismatch`; no sink call |
| T05 | Agent supplied a fabricated assurance binding claiming 8 origins | Policy/evaluation boundary | Rejected: `agent_supplied_assurance_fact_rejected` |
| T06 | Evidence references changed between authorization and execution | Canonical action binding | Rejected: `action_binding_mismatch` |
| T07 | Original receipt replayed after successful execution | Receipt consumption guard | Rejected: `receipt_already_consumed` |
| T08 | Same verified evidence, different action parameters | Canonical action binding | New authorization and a different action hash |

## Independent regression results

The complete Cyraduct backend suite passed:

```text
110 passed, 3 warnings
```

The dependency audit passed:

```text
No known vulnerabilities found
```

The frontend production build passed, and the committed OpenAPI contract was regenerated with **22 paths**, including `POST /v1/indepora/verify`.

The three warnings are existing ecosystem/deprecation warnings from Starlette/httpx and FastAPI `on_event`; they do not represent failed tests.

## What Cyraduct now contributes

Cyraduct provides the reusable downstream boundary:

1. Verify the INDEPORA schema, record hash, Ed25519 signature, issuer key ID, validity window and supersession state.
2. Extract only the allowlisted facts needed by policy.
3. Reject direct agent-supplied replacements for those facts.
4. Bind the INDEPORA record ID, record hash, assurance facts, evidence references, principal, action parameters and policy pack into the canonical action hash.
5. Issue a signed, time-bounded authorization receipt.
6. Re-verify the INDEPORA record at broker execution time before allowing the sink call.
7. Prevent action mutation and receipt replay.

Cyraduct does **not** determine whether evidence is truly independent, collapse lineage, infer unknown relationships, or certify the truth of the INDEPORA assessment.

## Reproduction

From the Cyraduct repository root:

```bash
python3 experiments/indepora_cyraduct_boundary_v1.py
python3 -m pytest -q
python3 -m pip_audit -r requirements.txt
```

Machine-readable output is in [`indepora_cyraduct_boundary_v1_report.json`](../experiments/indepora_cyraduct_boundary_v1_report.json). The reproducible harness is [`indepora_cyraduct_boundary_v1.py`](../experiments/indepora_cyraduct_boundary_v1.py).

## Inputs requested from INDEPORA for the next step

This test used a provisional schema and synthetic issuer key. For a real design-partner integration, INDEPORA should provide the authoritative Continuity Record schema, canonicalization version, issuer public-key distribution and rotation method, supersession/revocation semantics, and a fixture set covering dependent evidence, collapsed independent evidence, paraphrase/translation ambiguity, conflict, and multi-agent repetition.

The next joint milestone should be one real INDEPORA-issued Continuity Record consumed by this adapter, while keeping the action and sink fully synthetic.
