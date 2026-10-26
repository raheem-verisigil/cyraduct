# Cyraduct Production Deployment Checklist

**Status:** Deployment guide; not a declaration that the current service is production-ready.

## Required production configuration

Set these as deployment secrets/environment variables. Do not commit real values or paste them into issues, pull requests, logs, or chat.

| Variable | Requirement |
|---|---|
| `CYRADUCT_ENV` | `production` |
| `CYRADUCT_DATABASE_URL` | PostgreSQL URL; local SQLite is rejected in production |
| `CYRADUCT_ADMIN_KEY` | Unique random secret, at least 32 characters |
| `CYRADUCT_BROKER_API_KEY` | Separate unique random secret, at least 32 characters; required on every broker execution request |
| `CYRADUCT_SIGNING_SECRET` | Unique random secret, at least 32 characters (legacy compatibility setting; do not reuse another key) |
| `CYRADUCT_PRIVATE_KEY_B64` | Base64 encoding of a 32-byte raw Ed25519 private key |
| `CYRADUCT_KEY_ID` | Explicit non-development key identifier, for example `cyraduct-prod-2026-01` |
| `CYRADUCT_ALLOWED_ORIGINS` | Exact trusted browser origins; avoid wildcards |
| `CYRADUCT_TEST_ADMIN_KEY` | Optional; only if a separate test capability is required, at least 32 characters and distinct from the admin key |

The application fails at startup when production settings contain default credentials, an invalid signing key, a development key ID, or a non-PostgreSQL database URL.

## Generate the signing key

Run `python generate_key.py` in a trusted environment. Store the printed private key only in the deployment secret store as `CYRADUCT_PRIVATE_KEY_B64`. Keep the corresponding public key and key ID in the operator's key inventory. Never commit the private key.

Generate independent random values for the admin, broker, and signing secrets using an approved password/secret manager. Do not reuse the signing private key as an API credential.

## Broker integration requirements

The broker execution endpoint requires `X-Cyraduct-Broker-Key`. This is a coarse single-integration credential, **not** multi-tenant authentication. Do not give it to unrelated customers or an untrusted external tester. A real multi-customer deployment needs per-tenant/per-integration credentials, revocation, scoped sink allowlists, and auditable ownership.

The sink must independently verify the signed receipt and enforce the authorized action immediately before the side effect. The API's broker key is not a substitute for receipt verification, action binding, or sink-side authorization.

## Database and recovery

- Use a managed PostgreSQL service with TLS and restricted network access.
- Confirm backup retention, restoration, migration, and recovery time before accepting records that must survive.
- Test restart/redeploy behavior and confirm signing identity remains stable.
- Confirm audit and receipt records remain available after a restore.
- Configure network-level outbound egress restrictions for the broker. URL validation alone cannot fully eliminate DNS rebinding/SSRF risks.

## Release procedure

1. Deploy a candidate build to a separate staging service with separate database and keys.
2. Run CI and the synthetic conformance suite against the exact commit.
3. Test missing/invalid broker key, tampered/expired/revoked/mismatched receipt, duplicate execution, kill switch, storage failure, and outbound URL restrictions.
4. Verify no external real-world side effect can occur in the test environment.
5. Run backup/restore and rollback exercises.
6. Obtain an independent security review and close critical/high findings.
7. Obtain written pilot scope and data-handling approval before shadow mode. Do not begin with real transfers or irreversible actions.

**Current architectural limitation:** a single broker key authenticates access to the broker but does not establish customer tenant identity or enforce per-customer sink ownership. Treat the current implementation as a controlled single-integration pilot candidate until that model is implemented and independently tested.
