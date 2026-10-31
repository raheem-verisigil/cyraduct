# NCS Cross-Project Infrastructure Report — 31 October 2026

## Authority and portal package
Created a staging package under `ncs-authority/` containing an authority charter, JSON schemas, provisional assessment compiler, offline evidence digest verifier, certificate lifecycle policy and read-only partner portal preview.

## What is implemented
- Machine-readable evidence-manifest and assessment-record schema drafts.
- Deterministic provisional compiler that blocks incomplete required stages and never emits a grade or certificate.
- Offline SHA-256 evidence-file verifier with path traversal protection.
- Certificate lifecycle policy draft.
- Read-only portal preview with clear scope and limitation labels.

## What is not implemented
- Dedicated independently governed GitHub repository (repository creation is not available through the connected GitHub actions in this session).
- Signed evidence and certificate issuance.
- Transparency log anchoring, identity assurance, ZK completeness proof.
- Live browser-side manifest upload/verification.
- Authenticated partner accounts, durable challenge submissions, reviewer workflow or notifications.
- Independent governance board, external reproduction, live model-provider runs.

## Cyraduct
Verified CI at commit `726babe4f76344493e7a340f260f49b1cd099a07`: NCS Finance Guard run #240 93/93 passed, 0 failed, 4 warnings; Cyraduct run #226 235/235 passed, 0 failed, 4 warnings. These are harness/product CI results only. Native model assessment remains outstanding.

## VeriSigilAI / VCB
The NCS assessment registration and website status must continue to say runtime assessment is blocked/not run. Static code review identified that VEC-043–VEC-058 fall through to `assert(true)` in the Node conformance runner. API tests in the current workflow are configured `continue-on-error: true`. No fix or new VeriSigil run is claimed.

## Release decision
Keep NCS in pre-alpha, do not issue grades/certificates, do not describe the portal as a live partner service, and do not merge these staging artifacts into product main branches until the dedicated authority repository and review controls are in place.
