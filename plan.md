# INDEPORA–Cyraduct partnership boundary

## Outcome
Add a versioned INDEPORA Continuity Record verification boundary to Cyraduct without making Cyraduct responsible for lineage analysis. Add a partner-facing website section explaining the complementary product design and inviting async design-partner pilots.

## Backend
- Add `app/indepora.py` with canonical record hashing, Ed25519 verification, expiry/supersession checks, and an allowlisted `EvidenceAssuranceBinding`.
- Add optional `indepora_record` input and derived `evidence_assurance` to `ActionRequest`; the raw signed record is never included in Cyraduct receipts.
- Bind the verified record hash and assurance facts into the canonical action envelope and receipts.
- Add `/v1/indepora/verify` as a standalone adapter contract endpoint.
- Add deterministic policy predicates for INDEPORA facts and a dedicated experimental policy pack, without changing existing Finance Guard defaults.
- Add regression tests for signature, mutation, expiry, agent override rejection, and hash binding.

## Website
- Add a concise INDEPORA–Cyraduct partnership design block inside the existing partner section.
- Explain: INDEPORA owns evidence continuity; Cyraduct owns authorization and execution enforcement.
- Add a focused pilot CTA that routes to the existing partner form and `hello@cyraduct.com`.

## Validation and release
Run backend tests, dependency audit, OpenAPI regeneration/drift check, frontend build, diff checks, commit and push both repositories, then deploy the API via the linked Railway service and run live health/OpenAPI smoke checks.
