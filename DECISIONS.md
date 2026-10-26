# Architecture Decisions

This file exists to prevent re-litigating settled scope decisions every time
a new proposal arrives.

## Decision: Cyraduct is the live three-tier receipt protocol.

Status: Final, as of 2026-09-08.

Cyraduct is:
- Advisory / Attested / Broker-Enforced tiers
- Ed25519-signed, expiring, revocable receipts
- Policy packs with a public conformance suite (positive and negative cases)
- Everything currently live at api.cyraduct.com, tested, and documented in README.md

This is the product. It is not a placeholder for something larger.

## Out of scope until further notice

Proposals for "Operational State," "Pressure Vectors," "Adaptive Control
Engines," "Authority Leases," multi-agent delegation chains, intent-binding
layers, or any full-rewrite architecture spec are not approved for
implementation right now, regardless of how complete the proposal is.
This is about sequencing, not merit.

## Conditions under which this could change

1. The live receipt system has been stable and trusted in production for a
   meaningful track record.
2. There is concrete design-partner demand for the specific capability.
3. There is a committed plan to staff and maintain the new surface area.

## How new work should land, if it ever does

- Small and additive — reads from and modulates the existing receipt
  issuer, never a rewrite of it.
- Isolated — deletable without breaking the three-tier system underneath.
- Reviewed line-by-line before deployment, same discipline as the SSRF fix.

## Scope additions since 2026-09-08 (recorded 2026-10-26, awaiting owner confirmation)

The repository now also contains: a Runtime tier (`/v1/runtime`), INDEPORA
integration, a canonical action envelope, partner intake and privacy-safe
analytics endpoints, tenant isolation (`/v1/admin/tenants`), a security posture
report, and request-size / rate-limit hardening. Most were added after the scope
lock above without an entry here. This section records that they exist; it does
not approve them. The owner should confirm or remove each, per the "How new work
should land" rules (small, additive, isolated, reviewed line by line).
