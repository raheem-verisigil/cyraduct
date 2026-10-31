# NCS Policy-Fit Experiment Harness — Audit and Integration Decision

**Version:** 0.1  
**Review date:** 31 October 2026  
**Source artifact:** user-supplied `ncs_experiment_harness.zip`  
**Disposition:** accepted as an experimental research harness; not approved as the production NCS execution core.

## 1. Independent verification

The supplied archive was extracted and tested in an isolated environment.

| Check | Result |
|---|---:|
| Unit tests | 61 passed, 0 failed |
| Full development-set mock run, no-policy arm | 2,020 records |
| Full development-set mock run, policy + controls arm | 2,020 records |
| Provider errors in either mock run | 0 |
| Evidence verification, no-policy arm | V1–V6 passed |
| Evidence verification, policy arm | V1–V6 passed |
| Conduct Delta comparison | Completed |
| Local HTTP protocol smoke: OpenAI-compatible adapter | Passed |
| Local HTTP protocol smoke: Anthropic-shaped adapter | Passed |
| Live provider calls | Not run; no provider credentials or endpoint access supplied |

Each 2,020-record arm consists of 1,920 development cases plus 100 benign utility cases. The four judge-dependent rules remain pending: R3, S1, S2 and T2 (80 cases per rule in each arm).

The held-out suite hash supplied by the package is:

`e182597df9cd25209b30ad3c9888a9d7cdc29dfcf40f6d7b483b8bcf8e9b7894`

The held-out cases must remain sealed from profiling, policy design and tuning. Do not include them in routine CI or publish their contents.

## 2. Mock-run observations — plumbing only

The deterministic mock produced these effect-level changes from no policy to example policy plus controls:

| Rule | No-policy | Policy + controls | Delta |
|---|---:|---:|---:|
| A1 | 0.562 | 0.000 | -0.562 |
| A4 | 0.750 | 0.000 | -0.750 |
| E1 | 1.000 | 0.250 | -0.750 |
| R2 | 0.188 | 0.000 | -0.188 |
| R4 | 0.375 | 0.000 | -0.375 |

Macro-average delta across scored rules: -0.13125.

These values are a demonstration that the runner, controls, oracles and paired comparison execute. They are **not model-performance evidence** and must not be used as product claims.

The benign utility suite reported 20% task success and 0% over-refusal for the mock in both arms. This is a further indication that the mock is not a competent customer-support model and that the utility result is only a plumbing check.

The policy arm still had 25% effect-level E1 violations; E2, E3, E4 and T1 remained at 100% in both arms. The experiment therefore does not show that the example policy is sufficient.

## 3. Adapter protocol smoke

Both provider adapters were exercised against a disposable local HTTP server that returned protocol-shaped responses and tool calls. Both parsed text and tool-call arguments correctly in this local test.

This does **not** establish compatibility with Anthropic or any live OpenAI-compatible provider. A live 5-case smoke test is still required for each real provider/model endpoint, followed by transcript review and a controlled development-set run.

## 4. Defects and assurance gaps found

1. **File handling warning:** the CLI used unclosed `open(...)` calls when loading account data, arm JSON, policy text and control JSON. A local patch replaced these with context-managed UTF-8 file reads. The 61 tests then passed with `ResourceWarning` promoted to an error.
2. **Model pinning is self-declared:** the CLI's `--pinned` flag is copied into the manifest; the verifier does not independently establish that the provider returned the requested immutable model revision. Production evidence must distinguish `requested_model_id`, `observed_model_id`, `provider_revision` and `pin_verification_status`. A caller flag must never be sufficient to claim a pinned model.
3. **Signer identity is not established:** the embedded public key verifies integrity since signing, but does not establish who controlled the private key. Production signing requires an organisation-controlled KMS/HSM identity, key rotation/revocation and an externally anchored checkpoint.
4. **Raw transcripts are stored:** `results.jsonl` includes conversation content and tool traces. The aggregate Experiment Record excludes message content, but that does not make the full run privacy-minimised. Production must use a customer-controlled encrypted evidence vault, data minimisation, configurable retention, access logging and redaction. A digest alone is not proof that omitted activity did not occur.
5. **Judge validation is outstanding:** R3, S1, S2 and T2 remain unscored pending a judge validated against at least 100 hand-labelled outputs per rule and a pre-registered agreement threshold.
6. **Deterministic oracle validity is outstanding:** heuristic text oracles require hand-labelled false-positive/false-negative evaluation. Passing unit tests proves implementation behaviour, not construct validity.
7. **Fairness cohort labels are placeholders:** no real demographic or protected-group fairness conclusion is permitted until cohort definitions are community-reviewed and legally/ethically approved.
8. **No production tenancy or operator controls:** the package has no production API, identity provider, tenant isolation, delegated roles, approval workflow, encrypted evidence storage, monitoring service or deployment gate.

## 5. Architecture decision

Keep two execution paths distinct:

### A. Canonical NCS assessment core

Continue hardening `ncs_harness/week2_runner` as the production-oriented, provider-neutral contract. It must own:

- exact model/configuration identity and explicit assessment mode (NATIVE_BASELINE, POLICY_CONFIGURED, EFFECTIVE_SYSTEM);
- privacy-minimised result metadata and explicit PASS / FAIL / INDETERMINATE / NOT_TESTED states;
- tool-event contract separating attempted, executed, denied and downstream effect;
- deterministic case orchestration and repeat identity;
- versioned oracle interface and explicit judge-pending state;
- signed evidence from a trusted organisational identity and external append-only checkpoint;
- change-impact and lifecycle links.

The current runner contract intentionally avoids hidden provider I/O and does not issue grades or deployment authorisations. Preserve this boundary.

### B. Kestrel Policy-Fit Experiment Harness

Retain the supplied `ncs_exp` package as a research/validation harness for synthetic telecom scenarios, policy design, utility testing, fairness method development and Conduct Delta experiments. It can inform the canonical runner's tool-event, retry, resume and analysis requirements, but must not become the production evidence authority in its current form.

Do not copy its sealed held-out cases into the public repository or ordinary CI. Do not expose raw transcripts in a public test-results dashboard.

## 6. Required production changes before pilot

### Runner and adapters
- Define a typed provider-neutral conversation/tool-call contract, not only one-shot text invocation.
- Implement separately reviewed OpenAI-compatible and Anthropic adapters.
- Record request IDs, provider response IDs, requested and observed model IDs, revision/region where available, retry attempt IDs, latency, token counts and provider errors.
- Verify model pinning from provider-returned metadata or mark it UNVERIFIED.
- Fail closed on malformed tool arguments; never silently replace malformed JSON with empty arguments.
- Record every retry as a separate attempt and exclude provider errors from model failure denominators.

### Evidence and privacy
- Separate raw evidence vault from shareable aggregate records.
- Encrypt evidence at rest and in transit; enforce tenant-scoped access and retention/deletion rules.
- Sign manifests with a customer-controlled KMS/HSM key; publish/checkpoint manifest roots to an independently verifiable transparency service.
- Include suite, policy, tool schema, adapter code, runner code and environment digests.
- Make completeness limits explicit: the record proves what the instrumented path captured, not all activity outside it.

### Product and operator workflow
- Add lifecycle state, risk tier, tolerance profile, Control Register, named accountable roles, risk acceptance expiry, monitoring cadence and incident workflow to the case model.
- Derive risk tier from demonstrated capability, granted authority, impact domain and exposure. Treat the initial four-tier scheme as pilot hypotheses, not universal truth.
- Start continuous monitoring with privacy-light tool-log audits, then scheduled canaries and sampled content checks where justified.
- Add retirement as a gated workflow: revoke credentials and access, verify shutdown by test, preserve required evidence and record the human approver.
- Keep legal obligations as versioned external data and evidence mappings. NCS records evidence; it does not provide legal advice or certify legal compliance.

## 7. Release gates

A customer-facing MVP must not claim production assurance until all of the following are satisfied:

1. Live adapter smoke tests pass for each supported provider and exact model endpoint.
2. Native baseline, policy-configured and effective-system runs are reproducible and bound to immutable suite/config digests.
3. Oracle validation reports include hand-labelled sample sizes, confusion matrices and uncertainty.
4. Judge-based rules are either validated to the pre-registered threshold or excluded from primary scores.
5. Tool attempt, execution, denial and sink-effect semantics are verified against an instrumented test sink.
6. Signer identity, key lifecycle and independent checkpoint verification are operational.
7. Tenant isolation, RBAC, encrypted storage, retention, backup/restore and security review pass.
8. CI and deployment expose only aggregate, non-sensitive test status; no prompts, outputs, credentials or held-out cases are public.
9. The human approval workflow and evidence export are tested end-to-end.
10. Pilot users accept the limitations and the system's role as evidence infrastructure, not a compliance guarantee.

## 8. Immediate next engineering milestone

Build the **NCS Runner Service v0.2** around the canonical contract, adding:
- provider adapter interface with typed tool calls;
- local deterministic adapter tests plus opt-in live 5-case smoke tests;
- model identity/pinning verification states;
- encrypted raw-evidence storage interface and content-free aggregate export;
- event records for attempts, executions, denials and observed sink effects;
- API endpoints for creating, starting, resuming, verifying and exporting an assessment run.

The Kestrel harness remains the regression/reference experiment pack. No real customer data, payment endpoint or production agent action is used in this milestone.
