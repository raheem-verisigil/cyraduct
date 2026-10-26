# Cyraduct hardening sprint 001 — deployment handoff

## Included

- Canonical Ed25519 signature over immutable receipt claims.
- Independent verifier updated to use the same canonical representation.
- Adversarial regression tests for decision, agent, action, policy metadata, evidence references, expiry, chain link and signing-key identifier mutation.
- GitHub Actions workflow to install pinned project dependencies, compile the application and run the test suite on pushes and pull requests.

## Validation performed in this environment

Command:

```bash
PYTHONPATH=. pytest -q tests/test_field_binding_fix.py tests/test_canonical.py tests/test_receipt_integrity_adversarial.py
```

Result: **18 passed**.

Python compile check also passed:

```bash
python -m compileall -q app main.py verify_receipt.py
```

The full test suite has not been run here. The local environment lacks `slowapi`, which is listed in `requirements.txt`; network access was unavailable for dependency installation. The GitHub Actions workflow is intended to run the full suite once the change is pushed.

## Deployment status

This archive has **not** been pushed to GitHub and has **not** been deployed to Railway. The connected GitHub integration returned HTTP 403 `Resource not accessible by integration` for branch and file writes. Do not represent this sprint as live.

The known Railway production service is `Cyraduct tech` / service `web`, connected to `raheem-verisigil/cyraduct` branch `main`, with custom domain `api.cyraduct.com` and port 8080. Its last observed successful deployment was commit `3972c8f8f6af2e76129422e611c5a857be396f7a` from 2026-10-10. Production was not changed.

## Before production deployment

1. Push this reviewed archive as a new hardening branch or apply the diff in a local checkout.
2. Run the complete CI suite and resolve every failure.
3. Add a broker-level test proving a mutated stored receipt is rejected before the execution sink is called.
4. Validate compatibility with existing receipts and clients.
5. Deploy to an isolated Railway staging service first, then run smoke and adversarial tests.
6. Promote to production only after staging is green and the owner approves the production release.

This sprint is not a security audit, penetration test, or production-readiness certification.
