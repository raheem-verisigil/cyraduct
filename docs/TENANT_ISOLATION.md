# Tenant isolation — operator guide

Status: implemented, **off by default**. Turn it on only after tenants hold keys.

## What it guarantees (and the tests that prove it)

`tests/test_tenant_isolation.py`:

- A receipt issued to tenant A cannot be verified, executed, read, listed or
  revoked by tenant B or by an unauthenticated caller. Every cross-tenant
  attempt looks exactly like "receipt not found", so ids are not an existence
  oracle.
- Per-agent hash chains are namespaced by tenant: two tenants using the same
  `agent_id` do not share or read each other's chain.
- API keys are shown once and stored only as SHA-256 hashes.
- Revoking a tenant disables its key and revokes all of its receipts.
- With `CYRADUCT_REQUIRE_TENANT_AUTH=true`, advisory / attested / runtime
  evaluate and broker execute return 401 without a valid key. Admin access is
  unaffected.

Receipts are **not** changed: tenant ownership is stored beside the receipt,
outside the signed claims, so existing receipts and `verify_receipt.py` keep
working and independent verification still needs only the public key.

## What it does not do (yet)

- The audit log is one global hash chain. Tenant calls carry `tenant_id` in
  the entry detail, but tenants cannot read the audit log; only a full admin can.
- Evidence registration is admin-only and not tenant-scoped.
- Policy packs are shared, unsigned and global.
- Rate limits are per client IP, not per tenant.
- No self-service key rotation; rotate by creating a new tenant key and revoking the old tenant.

## Rollout

1. Deploy with the flag off (default). Nothing changes for current callers.
2. Create a tenant per design partner (full admin key):
   `curl -s -X POST https://api.cyraduct.com/v1/admin/tenants -H "X-Cyraduct-Admin-Key: $KEY" -H "Content-Type: application/json" -d '{"name":"Partner name"}'`
   The `api_key` in the response is shown once. Send it over a secure channel.
3. The partner sends `X-Cyraduct-Api-Key: <key>` on every call.
4. When every real caller has a key, set `CYRADUCT_REQUIRE_TENANT_AUTH=true` on
   the `web` service. Existing key-less receipts remain verifiable by key-less
   callers but cannot be executed by tenants.
5. Check `GET /v1/admin/posture` (full admin key).

## Client IP behind Railway

Rate limits key on the socket address by default. If Railway's proxy is the
socket peer for every request, all callers share one bucket. To check:

`curl -s https://api.cyraduct.com/v1/admin/posture -H "X-Cyraduct-Admin-Key: $KEY"`

Look at `socket_peer`, `client_ip_seen_by_rate_limiter` and
`forwarded_headers_present`. If `socket_peer` is a Railway-internal address and
`x-real-ip` is present, set `CYRADUCT_CLIENT_IP_HEADER=x-real-ip`, then repeat
the call from two networks and confirm `client_ip_seen_by_rate_limiter`
differs. Only name a header the edge overwrites on every request; a header a
client can send itself lets that client pick its own rate-limit bucket.
