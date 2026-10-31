# NCS Runner — production-readiness boundary (v0.1)

## Implemented contract in this branch
- Provider adapter is injected; no credentials or network calls are embedded.
- Fixed-order case execution and explicit repeat indices.
- Provider exceptions become INDETERMINATE records; no implicit retries.
- Output digest and character count are retained; raw prompts/outputs are not serialized into the manifest.
- Attempted and executed tool events are represented separately in the synthetic Kestrel environment.
- Manifest integrity digest is calculated over canonical JSON before adding the integrity field.

## Not yet production-ready
1. No live provider adapter has been implemented or run.
2. No signed attestation: SHA-256 detects changes but does not authenticate the runner or signer.
3. No append-only transparency log or trusted timestamp.
4. No real tool gateway; KestrelToolEnv is a deterministic simulator only.
5. No production log ingestion, privacy review, tenant isolation or access-control layer.
6. No validated oracle implementations for the 24-rule suite.
7. No human-judge validation dataset or inter-rater agreement report.
8. No retry/backoff policy. A production adapter must record each retry as a distinct attempt.
9. No held-out-set decryption/release workflow; sealed data must remain outside routine development.
10. No lifecycle/risk-tier decision engine; those remain governed by published policy and human approval.

## Required gates before a live pilot
- Pin exact provider/model/version/config and document provider-native safety instructions.
- Approve data residency, retention, privacy and synthetic-data plan.
- Validate all deterministic oracles against hand-labelled examples.
- Validate judge-based rules on at least 100 outputs each and meet the pre-registered agreement threshold, or exclude them from primary analysis.
- Verify attempted-vs-effect semantics against actual tool execution traces.
- Add signer identity, key management, signature verification and transparency anchoring.
- Run a development-only pilot; do not expose sealed cases until runner/oracles are frozen and hashed.
- Record failures, timeouts and retries without deleting failed attempts.

Passing local contract tests is not evidence of model quality, policy compliance, safety, or deployment readiness.
