# Cyraduct Production Readiness Gates

**Purpose:** Release-control checklist for the project team  
**Current status:** In progress — not a production approval  
**Rule:** A checkbox is complete only when linked to reproducible evidence, not when a feature merely exists in code.

## Gate 1 — Build and automated tests

- [ ] CI installs pinned dependencies from a clean runner.
- [ ] Python compilation passes.
- [ ] Full unit, integration, conformance, and regression suites pass.
- [ ] Security regression tests cover missing/invalid keys, role boundaries, cross-agent access, revocation, expiry, tampering, and kill-switch behavior.
- [ ] Tests are deterministic, isolated, and do not rely on production data or uncontrolled external services.
- [ ] CI results are green on the exact commit proposed for release.

**Evidence:** CI run URL, commit SHA, test count, and any skipped tests with reasons.

## Gate 2 — Identity, authorization, and isolation

- [ ] Production refuses default/development secrets at startup.
- [ ] Signing keys and admin credentials are generated, stored, rotated, and revoked using an approved secret-management process.
- [ ] External test credentials are separate from operator credentials.
- [ ] Tenant identity is established by trusted authentication, not by caller-selected agent_id alone.
- [ ] Tenant scoping covers every record, query, audit entry, evidence reference, receipt, and administrative action.
- [ ] Unauthorized responses do not disclose protected record existence.
- [ ] Rate limits, request-size limits, and abuse controls are tested.
- [ ] Authentication and authorization decisions are auditable without logging credentials or sensitive payloads.

**Release blocker:** Do not use a shared admin key as the sole identity boundary for multiple external customer tenants.

## Gate 3 — Receipt and execution enforcement

- [ ] Receipt signatures can be verified independently from the running Cyraduct API.
- [ ] Sink validates signature, issuer/key identity, expiry, revocation state, intended agent/principal, action type, action parameters/hash, and relevant policy version.
- [ ] The sink—not only the policy API—rejects invalid receipts immediately before the protected side effect.
- [ ] One receipt cannot authorize a different action, principal, agent, target, amount, or payload.
- [ ] Replay/idempotency semantics are explicit and tested under concurrent requests.
- [ ] Receipt revocation behavior and cache invalidation are tested.
- [ ] Cyraduct, storage, or verifier failure produces the documented safe outcome.
- [ ] Kill switch blocks the intended protected actions and is tested during an active request.
- [ ] Every execution outcome is correlated with the authorization evidence and sink-side result.

**Release blocker:** Do not claim that Cyraduct prevents unauthorized execution until the actual sink boundary and bypass paths have been tested.

## Gate 4 — Production operations and data handling

- [ ] Production database, migration, backup, restore, and disaster-recovery procedures are tested.
- [ ] TLS and encryption-at-rest requirements are met for the chosen deployment.
- [ ] Health checks, metrics, structured logs, alerts, and incident ownership are configured.
- [ ] Timeouts, retry behavior, concurrency, rate limits, and resource exhaustion are tested.
- [ ] Retention, deletion, export, and backup-expiry behavior are documented and tested.
- [ ] Data-flow map, data classification, access list, and subprocessors are documented.
- [ ] Incident response, key compromise, rollback, and customer notification procedures are rehearsed.
- [ ] The release can be rolled back without corrupting receipt or audit integrity.

## Gate 5 — Independent assurance

- [ ] A reviewer other than the primary implementer has run the documented adversarial test plan.
- [ ] Threat model covers malicious agents, compromised credentials, replay, tenant confusion, API abuse, storage compromise, key rotation, and sink bypass.
- [ ] Critical and high findings are fixed and retested, or release is blocked.
- [ ] Remaining risks and unsupported guarantees are written down and accepted by the release owner.
- [ ] Public documentation distinguishes demonstrated properties from roadmap items.

## Gate 6 — External pilot authorization

- [ ] External Pilot Plan is agreed with the customer.
- [ ] Written permission and a named customer owner exist.
- [ ] Synthetic tests pass before any real data is introduced.
- [ ] Shadow mode is configured to make no business side effects.
- [ ] Data fields, purpose, retention, deletion, and access are approved.
- [ ] Pilot has scope limits, monitoring, emergency stop, rollback, and expiry date.
- [ ] Customer has approved the move from shadow mode to any enforcement test.

## Release labels

- **Prototype:** Core behavior is being built; no external real data.
- **Synthetic-test ready:** Controlled tests can be run with fabricated data and mock sinks.
- **Shadow-pilot ready:** Required gates for the specific shadow deployment are evidenced and approved.
- **Limited-enforcement pilot:** A separately approved, bounded action is enforced at a tested sink.
- **Production ready:** All applicable gates are evidenced, independent review is complete, and operational ownership is established.

A passing CI run alone never advances Cyraduct to production-ready status.
