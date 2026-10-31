# NCS Lifecycle & Monitoring Layer — implementation mapping v0.1

## Scope
NCS is an evidence and assurance layer that supplies verifiable outputs to an organisation's governance process. It is not a GRC platform, legal engine, shadow-AI discovery product or autonomous retirement authority.

## Provisional risk-tier inputs
Risk tier is a policy-derived classification using four separately recorded inputs:
- demonstrated capability within tested scope;
- granted authority (tools, permissions and reachable data);
- impact domain;
- exposure and affected-population context.

Tiers 0–3 are provisional pilot hypotheses. A tier is not a conduct grade and must not be inferred from model size or product label alone. The organisation's risk owner approves the tier and records rationale.

## Lifecycle event contract
Every transition records: system_id, lineage_id, prior_state, next_state, event_time, actor/role, reason, evidence_refs, policy_version and signature_status.

States: CANDIDATE, ASSESSED, REJECTED, ADMITTED, OPERATING, CHANGED, RESTRICTED, SUSPENDED, RETIRED. RETIRED is terminal. REJECTED retains the failed assessment and is never represented as deployed.

## Monitoring sequence
1. Tool-log audits where action semantics can be established without message content.
2. Scheduled canary tests, with random coverage retained.
3. Event-triggered reassessment for model, policy, context, authority, control or legal-map changes.
4. Sampled content checks only where required, with local processing, redaction and documented sampling.
5. Incident intake with severity, owner, evidence and disposition.

Attempt rate and effect rate are separate. A rising attempt rate with a stable effect rate is a warning that controls may be carrying increased load; it is not proof of model drift until confounders are examined.

## Certificate validity
VALID, VALID_WITH_WARNINGS, SUSPENDED, EXPIRED, REVOKED, RETIRED. State changes are evidence-backed events. A validity label never means universally safe or legally compliant.

## Controls
Control status: ASSERTED, TESTED, OBSERVED. ASSERTED is not evidence of enforcement. TESTED applies only to the tested environment/path. OBSERVED may be reported as operating only for the specific real execution path with trustworthy trace provenance.

## Risk tolerance
The organisation supplies versioned thresholds, severity classes, zero-tolerance rules and time-bounded risk acceptances. NCS evaluates supplied thresholds; it does not invent the organisation's appetite for risk. Statistical uncertainty and sample size must accompany rates.

## Legal obligations
NCS consumes a versioned external obligations map. Integration with SOVREN is conditional on API contract, provenance, jurisdiction coverage, update cadence and error handling being verified. Until then, legal mapping is NOT_CONNECTED / NOT_ASSESSED, not passed.

## Retirement
Retirement requires named approval, dependency review, credential/tool/endpoint revocation, a test showing shutdown calls fail, data disposition evidence and archived lineage. NCS records evidence; the organisation executes and owns the decision.

## NIST crosswalk
This design is informed by NIST AI RMF GOVERN 1.1 (legal/regulatory requirements), 1.2 (trustworthy characteristics), 1.3 (risk tolerance), 1.4 (transparent controls), 1.5 (monitoring/review), 1.6 (inventory) and 1.7 (safe decommissioning). This is an alignment map, not a claim of NIST endorsement or conformity assessment.
