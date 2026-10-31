# NCS Authority Charter — Draft v0.1

## Purpose
Define a neutral authority for assessing the native conduct of AI artifacts and the effect of subsequent deployment transformations.

## Authority boundary
The NCS authority owns normative requirements, schema versions, reference test definitions, grade compilation rules, verifier releases, certificate registry policy, appeals, and revocation policy. Assessed vendors may submit evidence and challenge findings but may not unilaterally change grades or issue certificates.

## Independence controls (required before public operation)
- Public governance charter and named maintainers/reviewers.
- At least two-person approval for normative changes and certificate issuance.
- Conflict-of-interest declarations and recusal.
- Versioned, signed releases; protected default branch and required CI.
- Public change log, decision log, appeals and correction process.
- Separation between assessment operator, technical reviewer and final approver.
- Reproducible test vectors and independent partner challenge process.

## Assessment object
The primary object is an immutable artifact identity, not a product name or marketing label. The identity record must bind model weights or provider model/version identifier, tokenizer/runtime where relevant, code, training/fine-tuning lineage, data provenance declarations, evaluation suite, and build record digest. Unavailable fields must be explicitly marked unavailable and affect evidence completeness.

## Assessment stages
1. Intake and scope declaration.
2. Artifact identity and build-record verification.
3. Native Behaviour Baseline (before deployer customization).
4. Deployment transformation inventory.
5. Policy Delta assessment.
6. Capability-specific grading and ceiling application.
7. Independent reproduction/review.
8. Decision, publication, expiry, monitoring and revocation.

## Decision rules
- No grade where artifact identity cannot be bound to the tested artifact.
- No certificate where mandatory evidence is missing, stale, unverifiable or materially inconsistent.
- A component failure cannot be averaged away; applicable ceilings dominate.
- Policy and capability results are distinct. Report capability profile by area and any overall ceiling separately.
- Certificate scope is limited to the exact artifact, test profile, configuration and validity period stated.

## Challenge and appeal
A partner may challenge a test definition, evidence omission, reproducibility failure, compiler result or decision. Each challenge receives a unique ID, scope, evidence references, status, reviewer assignment, decision rationale and immutable resolution record. Challenges do not silently alter a result; corrections create a new assessment revision.

## Current status
This is a draft charter and package-level design. It is not an incorporated standards body, independent governance board, accreditation scheme or legally recognized certification authority.
