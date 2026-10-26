# Cyraduct Security Hardening — Sprint 001

**Scope:** receipt signature integrity and adversarial regression tests.

## Finding addressed

The previous policy receipt signature covered only a small tuple (receipt ID, action hash, expiry, and previous receipt hash). The broker also read `decision` and policy metadata from the stored receipt. A storage-layer mutation of `decision` from `conditional` to `allow` could therefore leave the signature verifiable while changing the approval behavior.

## Change

Receipt signatures now cover a canonical JSON representation of all immutable receipt claims, including:

- decision;
- agent identity and action metadata;
- policy pack, version, matched rules, and reasons;
- evidence references and evidence assurance;
- issue/expiry timestamps;
- action hash and prior receipt-chain link;
- authorization type and runtime decision;
- signature algorithm and key identifier.

Mutable lifecycle fields (`revoked`, `consumed_at`) are excluded from the immutable signature payload because enforcement evaluates them as current state. The standalone verifier uses the same canonicalization rules.

## Focused validation performed

- `tests/test_field_binding_fix.py`
- `tests/test_canonical.py`
- `tests/test_receipt_integrity_adversarial.py`
- Python compile check for application and updated verifier

Focused result: **18 passed**.

Adversarial cases include conditional-to-allow mutation, agent/action substitution, policy-version and matched-rule changes, evidence-reference changes, expiry extension, chain-link substitution, key-ID substitution, independent public-key verification, and the intentional separation of lifecycle state from immutable signature integrity.

## Validation limitation

The full application suite could not be collected in this environment because `slowapi` is absent. Package installation was unavailable due to network/DNS restrictions. This sprint therefore does **not** claim the full suite passes, nor is it a penetration test, independent audit, production-readiness certification, or proof of security against all attacks.

## Next required hardening

1. Run the complete test suite in CI with pinned dependencies.
2. Add broker-level regression proving a tampered `conditional` receipt never reaches the execution sink.
3. Review atomic receipt consumption under concurrent requests and crash/retry ambiguity at the downstream sink.
4. Implement tenant isolation and per-tenant authorization before shared multi-customer deployment.
5. Sign and verify policy-pack provenance/version, rather than trusting unsigned policy-pack placeholders.
6. Add a separate signed execution-outcome receipt and independent ledger checkpoint/anti-truncation mechanism.
7. Complete threat modelling and independent security review before any production financial integration.
