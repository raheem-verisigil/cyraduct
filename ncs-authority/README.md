# Native Conduct Standard — Independent Authority (staging package)

**Status:** pre-alpha reference implementation package, staged in Cyraduct pending creation of a separately governed GitHub repository. This directory is NOT yet an independent authority repository and issues no grades or certificates.

## Mission
NCS assesses the native conduct of an AI artifact before deployment and records the effect of deployer-added configuration. Assessment authority is independent of the products being assessed.

## Components
- `spec/`: normative assessment and authority rules.
- `schemas/`: machine-readable artifact, evidence, assessment, and certificate schemas.
- `compiler/`: deterministic policy/grade compilation prototype.
- `verifier/`: offline evidence-manifest verification.
- `certificates/`: lifecycle and invalidation rules.
- `portal/`: partner evidence/challenge portal prototype.
- `reports/`: cross-project status reports.

## Non-negotiable separation
1. Product repositories submit evidence; they do not assign NCS grades.
2. NCS verifier checks integrity and completeness; it does not infer truth from a valid hash.
3. Compiler output is provisional until a reproducible assessment run and authorized review.
4. A certificate binds to immutable artifact and evidence-manifest digests, has an expiry, and is invalidated by material change or revocation.
5. A missing or unverifiable mandatory evidence item caps the result; strong sub-scores cannot compensate.

## Current limitations
The assessment runner is not yet connected to live model providers. The verifier currently validates manifest structure and SHA-256 file digests only. Signature verification, transparency-log anchoring, identity proofing, ZK completeness proofs, independent partner reproduction, and formal certificate issuance are not implemented.

## Transfer plan
Create a dedicated repository named `native-conduct-standard`, move this package without product-specific dependencies, enable branch protection and CODEOWNERS, and appoint an independent standards/review group before any public certification.
