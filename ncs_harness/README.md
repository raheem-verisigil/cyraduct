# NCS Assessment Harness — Cyraduct Finance Guard

Status: pilot harness draft. This is an NCS assessment adapter, not an NCS certificate and not a claim of independent certification.

## Governance Operations Workbench (prototype v0.1)

The first local workflow/domain slice is in `workbench/`. It registers AI assurance cases against a frozen model-configuration digest, assigns multidisciplinary roles, tracks risk gaps, records evidence provenance and explicit human decisions, marks evidence stale after material configuration changes, exports a case manifest and verifies a per-case hash-chained event history.

Run its focused tests from the repository root:

```bash
python -m pytest -q tests/test_ncs_workbench.py
```

This is a local SQLite prototype. It does not yet provide a production API/UI, authentication, tenant isolation, verified delegated authority, protected evidence vault, external signed checkpoint or deployment approval. See `workbench/README.md` for the exact limits. The workbench records governance operations; it does not determine legal compliance.

## Purpose

Exercise Cyraduct's Finance Guard policy and receipt boundaries with synthetic vendor/payment data. Keep three evidence classes separate:

1. **AI conduct** — what the model/agent proposed or said (not measured by these deterministic API tests).
2. **Application control** — policy decision, receipt issuance/verification, broker response.
3. **Consequence evidence** — whether the isolated test sink was actually called and what state it changed.

These tests currently measure classes 2 and selected parts of 3. They do not measure a foundation model's Native Behavior Baseline. A future NCS adapter must capture model identity, exact prompt/input, raw output, model configuration, and policy delta separately.

## Safety boundary

- Run only in a local development/test environment with synthetic data.
- Do not point tests at Railway, production, a real ERP, a bank, or a payment endpoint.
- Do not place API keys, private keys, real vendor records, or customer data in fixtures or reports.
- Broker tests must mock the HTTP client or use a local disposable sink.
- A passing test proves only the specific assertion in that test under that test configuration.

## Run

Install the repository requirements plus pytest:

```bash
pip install -r requirements.txt pytest pytest-asyncio
pytest -q tests/test_ncs_finance_guard.py tests/test_ncs_sink_guard_compat.py
```

The tests import the FastAPI application and use its local TestClient. They do not call a deployed service.

## Scenario catalogue

See `scenarios.json`. The initial policy-delta set includes a valid vendor change, missing callback evidence, requester-supplied callback channel, missing reviewer, new beneficiary without dual approval, payment without purpose, recent bank-detail change, and wire amount above the policy ceiling.

## Receipt verifier compatibility correction

The original sink helper used a pipe-delimited subset of receipt fields, while the issuer and standalone verifier use canonical JSON over all immutable claims. The assessment branch now updates `examples/sink_guard.py` to delegate signature verification to the standalone canonical verifier. Tests now require a current receipt to verify and require tampered claims, an incorrect expected action hash, and expired receipts to be rejected. Revocation remains a separate mutable lifecycle check and must be checked against a current trusted source or broker protocol.

## Evidence collector

`collector.py` builds a schema-shaped evidence record from explicit observations. It hashes the input payload instead of storing raw payload values, keeps unobserved sink execution as `null`, and independently compares the observed decision with the expected decision. A mismatch is recorded as a failed assertion even if caller-supplied assertions say pass.

`append_hash_chained_record()` writes JSONL envelopes linked by SHA-256. `verify_hash_chain()` detects changes to records and broken links. This local chain is tamper-evident only relative to a protected external checkpoint; it is not by itself an independently operated transparency log, signed completeness proof, or protection against an attacker who can rewrite the entire file and its checkpoint.

Generate a JSON summary after a ledger has been produced:

```bash
python -m ncs_harness.report path/to/evidence.jsonl
```

The report verifies the local chain before summarizing record counts. It never issues a grade.

Run collector unit tests with:

```bash
pytest -q tests/test_ncs_evidence_collector.py
```


## Native Behavior Baseline (experimental v0.1)

The Native Behavior Baseline is a separate NCS assessment layer. It tests the AI system before deployer-specific policy instructions are introduced. It is not the same as Cyraduct's application policy tests.

### Probe pack

`native-baseline-pack-0.1.json` defines six initial dimensions and six controlled probes:

- Instruction fidelity.
- Authority boundary.
- Evidence discipline.
- Uncertainty handling.
- Change sensitivity.
- Policy-conflict disclosure.

The probes use synthetic finance-workflow situations but assess the model's response, not Cyraduct's enforcement. They require no tools in v0.1.

### Execution protocol

1. Freeze and record provider, exact model/version or artifact digest, system-prompt digest, temperature and other available generation settings.
2. Run each probe in a fresh, documented session with no deployer-specific policy overlay and tools disabled.
3. Repeat each probe at least three times. Preserve the exact raw response in access-controlled evidence storage; store its SHA-256 digest and a protected reference in the observation record.
4. Evaluate each required assertion using the versioned rubric. Human review is the preferred initial adjudication method. Model-assisted evaluation is provisional and must not be treated as independent proof unless separately validated.
5. Missing assertions are `not-assessed`, never pass. Any model/version or execution-context change requires a separate assessment.
6. Generate a per-probe repeatability summary. The summary deliberately has no aggregate score and cannot issue an NCS grade.

### Implementation

- `native_baseline.py` loads probes, hashes exact prompt/response bytes, validates evaluator assertions, and summarizes repeatability.
- `native-baseline-observation.schema.json` defines each observation's identity, context, hashes and evaluator provenance.
- `tests/test_ncs_native_baseline.py` tests the protocol without calling a model provider.

Example usage from Python:

```python
from ncs_harness.native_baseline import load_probe_pack, get_probe, build_observation, summarize_baseline

pack = load_probe_pack()
probe = get_probe("NBB-001", pack)
print(probe["prompt"])  # Submit this exact prompt to the frozen model configuration.

# After the external model call and independent review, build one observation.
# Repeat for every probe at least three times before interpreting stability.
```

This is a protocol utility, not a live model connector. No model API is called and no provider identity is independently attested by this code. A digest proves the identity of the bytes supplied to the collector, not that a provider generated them.


## Policy Delta Engine (experimental v0.1)

`policy_delta.py` compares paired native and policy-configured observations. It does not call a model provider and does not issue a score or grade.

### Pairing requirements

- Same assessment, probe ID and run index.
- Same exact model identity.
- Same exact probe prompt digest.
- Same generation temperature and tool-disabled condition.
- Policy observation cryptographically bound by digest to its exact native observation, with a separate digest of the policy-run raw response.
- One policy pack/version/digest per comparison.

If any of these differ, the comparison is rejected rather than attributing the difference to policy.

### Change classifications

- `improved-observed`: assertion changed from fail to pass.
- `regressed-observed`: assertion changed from pass to fail.
- `unchanged`: same observed result in both conditions.
- `unresolved`: either side is not assessed.
- `changed-unclassified`: reserved for any future non-binary evaluator states.

These are directional observations, not causal proof that the policy alone produced the change. Model nondeterminism and provider-side changes remain possible.

### Files and tests

- `policy_delta.py`: paired observation construction and comparison.
- `policy-delta-observation.schema.json`: policy-run evidence schema.
- `tests/test_ncs_policy_delta.py`: tests for improvements, regressions, missing evidence, model/prompt/config mismatches, run coverage and policy identity changes.

The report deliberately includes no aggregate score, Effective Conduct grade, or certification. A later Evidence Weave must preserve Native Baseline and Policy Delta as separate evidence streams before any grade compiler is considered.


## Evidence Weave (experimental v0.1)

`evidence_weave.py` assembles three distinct evidence streams under one assessment ID:

1. Native Behavior Baseline summary.
2. Policy Delta summary.
3. Application-control and consequence evidence records.

The weave records a canonical SHA-256 digest for each supplied stream, reports missing streams and selected coverage indicators, and adds an integrity digest over the weave manifest. It does not merge the underlying observations into one conduct claim.

### Integrity and scope boundaries

- Assessment IDs must match across supplied streams.
- Native and policy summaries must be the expected report schemas and must not issue grades.
- Application records must explicitly remain grade-ineligible.
- Missing streams remain missing; unobserved sink consequences remain unobserved.
- A valid weave digest detects changes to the manifest after creation, but does not authenticate the source, prove that source events occurred, or prove completeness outside the declared scope.
- The weave is deliberately marked `grade_compiler_input: false`. It is not a grade, certificate, deployment decision or proof of universal safety.

### Files and tests

- `evidence_weave.py`: evidence binding, stream coverage and manifest verification.
- `evidence-weave.schema.json`: output contract.
- `tests/test_ncs_evidence_weave.py`: stream mismatch, missing evidence, consequence coverage, failure preservation and tamper detection.


## Capability Profile Compiler (experimental v0.1)

`grade_compiler.py` compiles per-dimension native and policy-configured observation states and checks them against one explicitly declared policy requirements profile. It does not issue a numeric score, letter grade, certificate or deployment authorization.

### Compiler rules

- Requires a complete Evidence Weave and verifies its digest and the exact digests of all three supplied source streams.
- Requires matching assessment identity, probe-pack identity and exact policy pack/version/digest.
- Reports native behaviour and policy-configured behaviour separately for every declared probe dimension.
- A failure observed in any repeat remains visible even when the minimum repeat count has not been reached; evidence sufficiency is reported separately.
- Variable or insufficient observations are not treated as passes.
- Policy fit is limited to the exact policy requirements profile supplied by the assessor.
- Application consequence evidence is reported in its own assurance section and cannot replace model-conduct evidence.

### Output boundary

The current output always sets grade, letter grade and aggregate score to null; `grade_issued`, `certificate_issued` and `deployment_authorized` are false. The global ceiling remains `EXPERIMENTAL_NOT_GRADEABLE` until construct validity, evaluator reliability, evidence authenticity, thresholds and independent validation have been established.

### Files and tests

- `grade_compiler.py`: capability profile and declared-policy fit compiler.
- `capability-profile-compiler.schema.json`: output contract.
- `tests/test_ncs_grade_compiler.py`: policy fit, failure, insufficient evidence, source digest mismatch and stream separation tests.

This is a deterministic engineering prototype, not a calibrated grading scheme or an NCS certificate.


## Certificate Lifecycle and Change Impact (experimental v0.1)

`certificate_lifecycle.py` adds two non-issuing operations:

1. `build_certificate_candidate` prepares a candidate envelope bound to the Evidence Weave, Capability Profile and exact model artifact digest. It reports missing Build Record evidence and unimplemented scheme requirements as blockers.
2. `assess_change_impact` maps declared model, prompt, policy, probe, evaluator and application changes to affected evidence streams and reassessment scope.

### Certificate status boundary

- The current prototype always returns `certificate_status: NOT_ISSUED` and `issuance_eligible: false`.
- No certificate ID, signature, issue/expiry timestamp, transparency receipt or revocation state is fabricated.
- Missing or unverified artifact and Build Record evidence is a blocker.
- A material change to model weights, base model, adapter, tokenizer, quantization or model version requires full native and derived reassessment.
- A policy change triggers policy delta and fit reassessment; application connector/sink changes trigger application assurance reassessment.
- Unknown change types are rejected for manual classification.
- If a future issued certificate is affected, the engine recommends suspension/revocation review but does not mutate certificate status.

### Files and tests

- `certificate_lifecycle.py`: non-issuing candidate and change-impact operations.
- `certificate-candidate.schema.json`: explicit NOT_ISSUED candidate contract.
- `tests/test_ncs_certificate_lifecycle.py`: artifact and Build Record blockers, change classification, unknown changes and digest tampering.

These rules are experimental. They are not yet a normative NCS change taxonomy or a production certificate authority.


## Assessment Registry and Durable Test Record

The machine-readable assessment record for this integration is:

`assessment_registry/NCS-CYR-FG-2026-001.json`

Assessment ID: `NCS-CYR-FG-2026-001`

This record preserves the actual CI run identity, tested commit, pass/fail counts, failure diagnosis, remediation commit and pending rerun state. It must not be overwritten when a new run occurs: append a new run entry or create a versioned immutable event record, then update only the registry's latest pointer.

### Cross-project record ownership

- NCS is the assessment authority and owns the master assessment interpretation and any future certificate.
- Cyraduct is the assessed system and owns its implementation-side evidence, source commits and application-control test history.
- VeriSigilAI/VCB is a separate future assessment target. It was **not assessed** by this Cyraduct run and must not display this result as a VeriSigilAI test.
- A mirrored public record must preserve the same assessment ID, tested commit, run ID, result status and result digest. Each project may add its own perspective, but may not alter the shared outcome.

The current NCS harness is hosted inside this Cyraduct repository as an integration prototype. A dedicated NCS repository and independent public registry are still required for a clean separation of ownership.


## NCS Internal Assessment Programme

The portfolio plan is maintained in `programme/NCS-INTERNAL-ASSESSMENT-PROGRAMME-0.1.json`.

NCS is the assessment protocol. Cyraduct, VeriSigilAI/VCB and other eligible portfolio projects are separate assessment subjects. The NCS engine itself is tested through a separate self-conformance suite; it cannot independently certify itself.

### Assessment sequence

1. Lock the exact subject: repository commit, artifact digest, model/provider/version, runtime and configuration.
2. Run the Native Behavior Baseline before applying the deployer policy.
3. Run paired tests under the exact policy/configuration and compile the Policy Delta Profile.
4. Observe the application decision and sink/consequence state separately.
5. Assemble and review the Evidence Weave.
6. Compile capability profiles and declared-policy fit.
7. Run change-impact tests and record any required reassessment.

Do not infer an AI test subject from a project proposal or website. A portfolio project enters execution only when its actual AI component, immutable identity, configuration and repeatable test interface are available. A deterministic rules engine or static website is not model conduct.

### Programme project IDs

- `NCS-CYR-FG-2026-001`: Cyraduct Finance Guard (first integration; CI rerun pending).
- `NCS-VSA-VCB-2026-001`: VeriSigilAI / VCB (separate assessment; subject inventory pending).
- `NCS-ALIF-2026-001`: ALIF (candidate; codebase and AI subject inventory required).
- `NCS-FS-2026-001`: FreightSigil (candidate; codebase and AI subject inventory required).
- `NCS-FC-2026-001`: FinContinuity (candidate; codebase and AI subject inventory required).
- `NCS-RW-2026-001`: REWAIZE-AI (candidate; codebase and AI subject inventory required).
- `NCS-AIC-2026-001`: AICaffe (candidate; codebase and AI subject inventory required).

These are reserved programme identifiers, not evidence that assessments have run. Each subject must have a separate immutable run record. NCS self-conformance, Cyraduct, VeriSigilAI and all later subjects must never share a result or certificate.

### Evidence and publication

Each completed run should produce an immutable, machine-readable event record containing assessment ID, run ID, exact commit/artifact digest, model identity, test protocol and version, policy digest, native and policy-configured results, application observations, evidence completeness, failure/limitation details, timestamps and a canonical result digest.

The subject repository should mirror the same record and digest, while retaining its own implementation-side CI and test artifacts. Public status pages should read from a verified registry/event feed. Never publish "passed" from a workflow that is still queued, in progress, incomplete or failed. A mirrored record cannot claim another project was assessed unless it has its own run.

### Internal-to-external gate

Internal portfolio runs establish engineering coverage, not independent validation. Before external pilots, require NCS self-conformance, several materially different completed subjects, reviewed evidence integrity, repeatability checks and a separately conducted external review. No numeric grade or certificate is authorized by this prototype.


## NCS × VeriSigilAI Assessment Registration

Assessment ID: `NCS-VSA-VCB-2026-001`

- Subject-side assessment record: `raheem-verisigil/verisigil-website/ncs/assessments/NCS-VSA-VCB-2026-001.json`
- Temporary NCS registry mirror: `ncs_harness/assessment_registry/NCS-VSA-VCB-2026-001.json`
- Subject-side public status section: VeriSigilAI Trust / Evidence page, section `#ncs-assessment` (proposed on branch `ncs/assessment-vcb-2026-001`).
- Current status: registered; source review complete; runtime tests not started.
- Reviewed website/repository files did not establish an executable model/agent runtime or immutable model identity. Native and policy-delta tests are blocked pending runtime identification.
- Application-assurance matrix is specified but not executed.
- Grade, certificate and independent validation: not issued/completed.

Every subsequent run must append immutable evidence to the NCS registry and mirror the same assessment ID, run ID, subject commit, protocol version and result digest to the subject repository. No public pass counters until verified runs exist.


### Latest completed NCS Finance Guard Harness run

- Run: `127` (GitHub Actions run ID `41129013094`).
- Commit: `a9ee82b89a0e39a94da3a80beb7477bccb07ddb8`.
- Result: **71 passed, 0 failed** in 1.16 seconds.
- The run includes certificate lifecycle tests.
- Four dependency/framework deprecation warnings were emitted; no test failures.
- Machine-readable result is appended to `assessment_registry/NCS-CYR-FG-2026-001.json`.

This is a successful NCS harness CI run using synthetic fixtures. It does not establish a native model-provider baseline, independent certification, production readiness or external validation.


### Archived run event

The successful run is also preserved as an immutable event:
`assessment_registry/runs/NCS-CYR-FG-2026-001-CI-127.json`.

The run's 71/71 result is harness CI evidence. It is not a native AI model evaluation or an NCS certificate.


### VeriSigilAI runtime API source audit

The runtime/SDK repository is `raheem-verisigil/verisigil-api`. Static inspection of `test_conformance.js` and `conformance_vectors.json` found 16 of 80 vectors (VEC-043–VEC-058, jurisdiction resolution) falling through to a generic `assert(true)` branch. Their expected primary regime, decision and conflict fields are not asserted by the current test runner.

This is a source-level finding, not a runtime test. The 16 cases must be given explicit assertions and unknown vector types must fail rather than silently pass. The connected GitHub integration denied branch creation in the API repository, so no code change or CI execution was performed there. The finding and run record are stored in the NCS registry and mirrored to the VeriSigilAI website repository.

The actual AI model/agent workload is still unidentified. NCS has not run a Native Behavior Baseline or Policy Delta against a model.

## NCS reporting boundary

Do not issue a numeric NCS grade from this harness alone. The outputs are test observations, not a complete Native Behavior Baseline, Policy Delta Profile, Effective Conduct Profile, or independent completeness proof. Record untested/unknown dimensions as unknown; do not convert missing evidence into a pass.


## Native Capability Profile (NCP) v0.1

NCS now has a separate capability-assessment specification and initial test-pack design:
- `specifications/NCS-NATIVE-CAPABILITY-PROFILE-0.1.md`
- `testpacks/NCS-NCP-CORE-0.1.json`

NCP measures demonstrated task capability across reasoning, quantitative work, planning, coding, factual/evidence use, tool use, context integration, calibration, robustness and supported modalities. It reports a vector, not a universal intelligence/IQ score. Capability is kept separate from conduct: high capability cannot compensate for a conduct failure or prove safety. NCP is currently design-only; no portfolio model has completed this profile.

## VeriSigil jurisdiction conformance follow-up

The NCS harness now contains:
- `adapters/verisigil_jurisdiction_conformance.js`: approved local/staging adapter that checks all three expected fields for the 16 jurisdiction vectors.
- `remediation/verisigil-fail-closed-test-runner.patch`: proposed fail-closed change so unknown vector types cannot silently pass.

Neither the adapter nor patch has been executed/applied to the VeriSigil API repository. API repository write access remains blocked. No production endpoint is used by default.
