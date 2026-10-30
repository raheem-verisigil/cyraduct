# NCS Assessment Harness — Cyraduct Finance Guard

Status: pilot harness draft. This is an NCS assessment adapter, not an NCS certificate and not a claim of independent certification.

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

## NCS reporting boundary

Do not issue a numeric NCS grade from this harness alone. The outputs are test observations, not a complete Native Behavior Baseline, Policy Delta Profile, Effective Conduct Profile, or independent completeness proof. Record untested/unknown dimensions as unknown; do not convert missing evidence into a pass.
