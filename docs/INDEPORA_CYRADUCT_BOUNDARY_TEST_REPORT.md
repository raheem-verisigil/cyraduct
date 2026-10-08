# INDEPORA–Cyraduct Evidence Reliance Boundary Test Report

**Run date:** 2026-10-08  
**Scope:** Synthetic, sandbox-only, local controlled sink. No production financial, ERP, customer, or external execution system was contacted.

## Executive result

The Evidence Reliance Boundary passed the expanded test. INDEPORA is treated as the authority for the evidence state and reliance boundary; Cyraduct is treated as the authority for consequence-specific policy, authorization, exact action binding and execution integrity. Datrisk can use the generated machine-readable report as the adversarial test fixture.

Cyraduct accepted a signed INDEPORA Continuity Record, extracted only allowlisted facts, bound the record and charter context into the canonical action envelope, issued an Ed25519-signed authorization receipt, and reached the local sink once. It denied insufficient or conflicting reliance states, qualified unknown lineage, rejected expired/superseded records, and rejected post-seal mutations.

This does **not** prove that INDEPORA’s lineage analysis is correct. It proves the narrower integration boundary:

> INDEPORA establishes the evidence-reliance state; Cyraduct verifies the exact state and enforces consequence-specific reliance on the exact action.

## Synthetic record contract

The fixture uses the provisional schema `indepora.evidence_continuity_record.v1` and a synthetic Ed25519 issuer key. The record contains record ID, subject, evidence references, lineage snapshot, origin assessment, Standing, Charter ID/version/hash, validity window, continuity/supersession state and a canonical record hash.

The baseline fixture represents **four candidate origins, zero unknown relationships and zero conflicts**, with a sandbox-only scope. Other cases use the same signed-record contract with controlled changes to the reliance state.

## Evidence Reliance Boundary matrix

| Case | INDEPORA result | Cyraduct expected | Actual result |
|---|---|---|---|
| A | Four candidate origins; no unknowns; no conflicts | Allow sandbox action | **Allow**; authorization receipt issued |
| B | One origin repeated eight times | Block | **Deny**: fewer than two candidate origins |
| C | Two origins plus unknown lineage | Qualify / escalate | **Conditional**: unknown lineage requires qualification or review |
| D | Conflicting origins | Block / escalate | **Deny**: conflicting origins |
| E1 | Validly signed record, expired | Block | **Deny**: `indepora_record_expired` |
| E2 | Validly signed record, superseded | Block | **Deny**: `indepora_record_superseded` |

The conditional result in Case C is not sent to the sink: Cyraduct’s broker treats a conditional receipt as requiring human approval.

## Adversarial and mutation results

| Test | Mutation | Detection layer | Actual result |
|---|---|---|---|
| T04 | Candidate-origin count changed after authorization | Broker-time record verification | Rejected: `indepora_record_hash_mismatch` |
| T05 | Agent supplied fabricated assurance facts | Trusted adapter / policy boundary | Rejected: `agent_supplied_assurance_fact_rejected` |
| T06 | Evidence references changed | Canonical action binding | Rejected: `action_binding_mismatch` |
| T07 | Receipt replayed after successful execution | Receipt consumption guard | Rejected: `receipt_already_consumed` |
| M1 | `standing` changed after signing | Record hash verification | Rejected: `indepora_record_hash_mismatch` |
| M2 | `charter_hash` changed after signing | Record hash verification | Rejected: `indepora_record_hash_mismatch` |
| M3 | `valid_until` changed after signing | Record hash verification | Rejected: `indepora_record_hash_mismatch` |
| M4 | `record_id` changed after signing | Record hash verification | Rejected: `indepora_record_hash_mismatch` |
| T08 | Same evidence, different action parameters | Canonical action binding | New receipt and different action hash |

## Independent verification results

The complete Cyraduct backend suite passed:

```text
110 passed, 3 warnings
```

The dependency audit passed:

```text
No known vulnerabilities found
```

The canonical website production build passed. The committed OpenAPI contract contains **22 paths**, including `POST /v1/indepora/verify`.

The warnings are existing ecosystem/deprecation warnings from Starlette/httpx and FastAPI `on_event`; they do not represent failed tests.

## What Cyraduct contributes

1. Verify the INDEPORA schema, canonical record hash, Ed25519 signature, issuer key ID, validity window and supersession state.
2. Extract only bounded facts: record ID/hash, schema, Standing, candidate origin count, unknown count, conflict count, Charter ID/hash, issue/expiry time and sandbox scope.
3. Reject direct agent-supplied replacements for those facts.
4. Bind the verified record hash, Charter context, evidence references, principal, action parameters and policy pack into the canonical action hash.
5. Issue a signed, time-bounded authorization receipt.
6. Re-verify the Continuity Record at broker execution time.
7. Prevent action mutation and receipt replay.

Cyraduct does **not** determine whether evidence is truly independent, collapse lineage, infer unknown relationships, or certify the truth of the INDEPORA assessment.

## Reproduction and artifacts

From the Cyraduct repository root:

```bash
python3 experiments/indepora_cyraduct_boundary_v1.py
python3 -m pytest -q
python3 -m pip_audit -r requirements.txt
```

Machine-readable report: [`indepora_cyraduct_boundary_v1_report.json`](../experiments/indepora_cyraduct_boundary_v1_report.json)

Reproducible harness: [`indepora_cyraduct_boundary_v1.py`](../experiments/indepora_cyraduct_boundary_v1.py)

## Inputs requested from INDEPORA

For the next design-partner step, INDEPORA should provide the authoritative Continuity Record schema, canonicalization version, issuer public-key distribution and rotation method, supersession/revocation semantics, and fixtures covering dependent evidence, collapsed independent evidence, paraphrase/translation ambiguity, conflict, and multi-agent repetition.

The next joint milestone should be one real INDEPORA-issued Continuity Record consumed by this adapter, while keeping the action and sink fully synthetic.
