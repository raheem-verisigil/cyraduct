# NCS Live Evidence Status API v0.1

## Deployed service
- Railway project: NCS Evidence Status API
- Railway service: ncs-evidence-status-api
- Public base URL: https://ncs-evidence-status-api-production.up.railway.app
- Health path: /health
- Status path: /v1/status
- Deployment ID: 2ffa74b6-7b8e-424b-90b0-cb720d0ef52e
- Railway deployment state: SUCCESS; environment reports one online replica and no deployment warnings/criticals at inspection.

## What it does
Reads public GitHub Actions workflow metadata for:
- NCS selected harness on ncs/experiment-runner-v0.1
- Cyraduct full suite on main
- VeriSigil legacy API workflow on main

Returns branch, commit SHA, run ID, workflow status, conclusion and run links. Cache lifetime is 60 seconds.

## Routes
- GET /health — service health response
- GET /v1/status — structured project evidence status
- OPTIONS — CORS preflight

## Assurance limits
- This is a read-only status aggregator, not an evidence verifier or certification authority.
- GitHub Actions status is not a complete product security assessment.
- VeriSigil remains NOT_VERIFIED because the inspected workflow does not require its Node jurisdiction conformance runner, and legacy API/current VCB website artifact equivalence is unverified.
- Deployment health is deliberately reported as NOT_INCLUDED in the GitHub status payload. Railway health is checked separately.
- Certificate status is NOT_ISSUED.
- The API does not call AI models, execute tests, access customer data or mutate product systems.
- GitHub public API rate limits may produce NOT_VERIFIED. A missing run is NO_RUNS, not PASS.
- No website has yet been wired to consume this endpoint.

## Website integration
The NCS dashboard is served at the base URL. The VeriSigil static website homepage now links to it from its navigation (commit 7033ca5). Cyraduct's repository README also links to it (commit created alongside this documentation update). No website is allowed to turn NOT_VERIFIED, NO_RUNS or IN_PROGRESS into a green pass. Display source commit, run ID, timestamp and limitation text. Keep deployment state and certificate status in separate UI fields.

## Runtime source
The deployed Railway Function was updated directly and is not connected to GitHub auto-deploy. A reference implementation is mirrored at ncs_harness/status_api/index.ts in the NCS development branch. The Railway source and mirror should be kept synchronised and reviewed before future releases. The public endpoint has not yet had an independent HTTP smoke test from this session; Railway reports the deployment successful and one replica online.
