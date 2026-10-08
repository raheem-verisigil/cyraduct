# INDEPORA–Cyraduct Boundary Sandbox

This directory contains a synthetic, local-only contract experiment. It is **not** an INDEPORA implementation and it does not contact production systems.

## Run

```bash
python3 experiments/indepora_cyraduct_boundary_v1.py
```

The script writes the complete request/response artifact to:

```text
experiments/indepora_cyraduct_boundary_v1_report.json
```

## Layers

1. **Synthetic Stemma producer** creates eight apparent evidence items:
   - four derived from origin A;
   - two from origin B;
   - one republication from origin A;
   - one unknown lineage.
2. **Trusted adapter** verifies the Ed25519-signed Continuity Record and extracts only structured lineage facts.
3. **Cyraduct** evaluates the exact action using `indepora_sandbox_v1`, binds the record hash into the canonical action hash, and signs the receipt.
4. **Local sink** receives a request only after the broker verifies the receipt and action binding.

## Expected outcome

The Stemma says:

```text
8 apparent items → 2 candidate origins; 1 relationship remains unknown.
```

The sandbox policy allows the action only because it is explicitly marked `sandbox_only`. This demonstrates that authorization of a synthetic sandbox action is separate from a claim that evidence is independent.

The trusted adapter rejects an agent claim of eight independent origins. Cyraduct rejects changes to the result hash, evidence references, or action parameters after authorization. The broker rejects receipt replay. A second action with the same evidence but different parameters receives a different action hash and receipt.

## Security boundary tested

```text
Evidence assurance → trusted adapter → canonical authorization → controlled execution
```

The Ed25519 key in this fixture is synthetic and local-only. A real integration should use INDEPORA’s authoritative issuer key distribution, canonicalization version, rotation, and supersession/revocation contract.
