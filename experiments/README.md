# INDEPORA–Cyraduct Evidence Reliance Boundary

This directory contains a synthetic, local-only contract experiment. It is **not** an INDEPORA implementation and it does not contact production systems.

## Run

```bash
python3 experiments/indepora_cyraduct_boundary_v1.py
```

The script writes the complete request/response artifact to:

```text
experiments/indepora_cyraduct_boundary_v1_report.json
```

## Boundary roles

- **INDEPORA** supplies the signed Evidence Reliance Result / Continuity Record. It owns lineage, dependence, candidate origins, unknowns, conflicts, Standing and Charter.
- **Cyraduct** verifies the exact record, consumes only bounded facts, applies consequence-specific policy, authorizes the exact action, and protects execution integrity.
- **Datrisk** can act as the adversarial tester: mutate the record, seal fields, evidence references, policy context, or action parameters and verify that the boundary blocks or escalates correctly.

## Matrix exercised

| Case | Synthetic INDEPORA state | Cyraduct result |
|---|---|---|
| A | Four candidate origins, no unknowns or conflicts | Allow sandbox action |
| B | One origin repeated eight times | Deny |
| C | Two origins plus unknown lineage | Conditional / qualify |
| D | Conflicting origins | Deny |
| E | Expired or superseded record | Deny before policy reliance |

The harness also changes `standing`, `charter_hash`, `valid_until`, and `record_id` after signing. Each mutation must fail the signed record verification boundary. It tests evidence-reference mutation, agent-supplied assurance overrides, action mutation and receipt replay as well.

## Security boundary

```text
AI / RAG / Agent trace
        ↓
INDEPORA Evidence Reliance Result / Continuity Record
        ↓ verify signature, hash, validity, supersession
Trusted Adapter
        ↓ bounded facts
Cyraduct policy → authorization receipt → exact action binding
        ↓
Controlled sandbox sink
```

The Ed25519 key in this fixture is synthetic and local-only. A real integration should use INDEPORA’s authoritative issuer key distribution, canonicalization version, rotation, and supersession/revocation contract.
