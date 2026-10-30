# NCS Model Execution Runner v0.1

This package introduces a provider-neutral execution contract. A provider adapter is supplied explicitly by the caller; this package does not silently call a model, infer a provider, load credentials, or access the network.

## Scope

- Execute a fixed, versioned set of cases against one exact configuration identity.
- Distinguish native baseline, policy-configured and effective-system assessment modes.
- Preserve per-case outcome, dimension, output digest and limited error class.
- Keep raw input/output text out of the returned evidence manifest.
- Mark provider/oracle errors as INDETERMINATE; never convert them to PASS.
- Issue no grade, certificate, policy-fit result or deployment authorisation.

## Adapter contract

Implement `adapter_id` and `invoke(input_text=..., system_context=...)`. Provider-specific network calls, credential custody, retries, rate limits, data residency and safety controls belong in a separately reviewed adapter. Use synthetic data until a provider-specific test plan is approved.

## Evidence boundary

The manifest digest covers the complete manifest excluding its integrity field. It detects accidental changes but does not provide authenticity or tamper resistance. A future signing/attestation service must bind it to a trusted identity and append-only transparency checkpoint.

## Run the contract tests

```bash
pytest -q tests/test_ncs_model_runner.py
```

The test adapter is a deterministic stub. Passing these tests does not constitute a live model assessment.
