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

## Known compatibility finding

`examples/sink_guard.py` currently verifies a pipe-delimited subset of receipt fields. The receipt issuer and `verify_receipt.py` instead sign/verify the canonical JSON representation of all immutable receipt claims, including the signature header. The compatibility regression test records that a receipt produced by the current API is rejected by the example sink helper.

This test is intentionally a **known-defect reproducer**, not a desired product behaviour. The recommended fix is to make the sink helper use the exact canonicalization contract (ideally a shared, versioned verifier module) and add positive, tamper, expiry, and action-binding tests.

## NCS reporting boundary

Do not issue a numeric NCS grade from this harness alone. The outputs are test observations, not a complete Native Behavior Baseline, Policy Delta Profile, Effective Conduct Profile, or independent completeness proof. Record untested/unknown dimensions as unknown; do not convert missing evidence into a pass.
