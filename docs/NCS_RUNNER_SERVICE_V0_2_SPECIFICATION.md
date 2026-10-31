# NCS Runner Service v0.2 — Product and Engineering Specification

**Status:** implementation specification  
**Version:** 0.2  
**Date:** 31 October 2026  
**Target:** NCS production-oriented MVP  
**Parent:** NCS Architecture Foundation / Policy-Fit Experiment Harness Audit

## 1. Product definition

NCS is independent assessment and evidence infrastructure that helps an organisation understand an AI system before deployment, establish policy and control requirements, verify behaviour after configuration, and maintain defensible evidence throughout operation and retirement.

NCS is not a general GRC replacement, legal-advice engine, universal AI safety guarantee, model leaderboard, or automatic deployment authority. It supplies artifact-bound assessment, evidence, control verification and lifecycle assurance that an organisation can use inside its governance process.

The production MVP must demonstrate one end-to-end path:

**Register → Identify → Assess native behaviour → Configure policy → Measure Conduct Delta → Verify controls/effects → Human admission decision → Monitor changes → Suspend/reassess/retire → Export evidence.**

## 2. Core invention boundary

The differentiating mechanism is the linked evidence chain across six identities/states:

1. **Subject identity:** exact model, provider, immutable revision where available, adapter, model parameters, system prompt, tool schema and runtime environment.
2. **Native baseline:** reproducible behaviour before deployer-specific policy is applied.
3. **Policy delta:** paired measurement of how the declared policy and controls alter attempts, outputs and action effects.
4. **Effective system:** observed behaviour after policy, application controls and execution-boundary controls are applied.
5. **Organisational decision:** named accountable roles, tolerance profile, control evidence, risk acceptance, approval/objection and expiry.
6. **Lifecycle continuity:** drift, incidents, changes, retests, restrictions, suspension and verified retirement linked to the same lineage.

A certificate or assessment report must resolve to the exact identity and evidence digest, never a mutable model display name alone. A material change creates a new configuration identity and invalidates only the affected evidence according to a versioned change-impact policy.

## 3. System architecture

### 3.1 Services

- **Operator API:** case lifecycle, role assignments, risk register, control register and human decisions.
- **Assessment Orchestrator:** schedules immutable suites, runs modes, resumes interrupted work and tracks retries.
- **Provider Adapter Layer:** explicit OpenAI-compatible, Anthropic and later provider adapters; no implicit provider selection.
- **Execution Sandbox:** synthetic tool environment for first MVP; real customer tools are out of scope until separate integration reviews.
- **Oracle Service:** deterministic rule checks, versioned text classifiers and separately validated judge rules.
- **Conduct Delta Engine:** pairs observations by case and repeat; reports attempt and effect outcomes separately with confidence intervals.
- **Evidence Service:** encrypted raw evidence vault, privacy-minimised result metadata, signatures and independent checkpoints.
- **Lifecycle Monitor:** drift events, canary schedules, tool-log audits, incident intake, certificate validity and retirement.
- **Read-only Status Publisher:** public aggregate CI/deployment state only; no prompts, transcripts, personal data, sealed suites, keys or tenant data.

### 3.2 Logical separation

The canonical runner under `ncs_harness/week2_runner` is the execution contract. The Kestrel `ncs_exp` package remains a research/validation harness and regression fixture. Cyraduct and VeriSigilAI are separate integration subjects, not interchangeable NCS components. NCS must be independently deployable and must not depend on Cyraduct's business logic for its core assessment semantics.

## 4. Canonical API contract

All endpoints are versioned under `/v1`. All writes require authenticated organisation context, idempotency key and an audit event. Tenant ID is derived from the authenticated principal, never accepted as an authoritative body field.

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/v1/systems` | Register a candidate system and intended-use context |
| GET | `/v1/systems/{system_id}` | Read system identity and lifecycle state |
| POST | `/v1/systems/{system_id}/configurations` | Register immutable model/policy/tool/runtime digests |
| POST | `/v1/assessments` | Create assessment run against frozen configuration and suite |
| POST | `/v1/assessments/{run_id}/execute` | Start or resume a run |
| GET | `/v1/assessments/{run_id}` | Read run state, counts and safe metadata |
| POST | `/v1/assessments/{run_id}/verify` | Verify result chain, signatures, suite and checkpoints |
| GET | `/v1/assessments/{run_id}/export` | Export signed manifest and permitted evidence package |
| POST | `/v1/decisions` | Record human admission/restriction/suspension decision |
| POST | `/v1/events` | Record change, drift, incident or retirement event |
| GET | `/v1/systems/{system_id}/timeline` | Read lifecycle event timeline |
| GET | `/healthz` | Liveness only; no sensitive diagnostics |

### 4.1 Assessment request

Required fields:
- system_id
- configuration_id
- assessment_mode: NATIVE_BASELINE | POLICY_CONFIGURED | EFFECTIVE_SYSTEM
- suite_id and immutable suite_sha256
- repeat_count
- environment_id
- requested provider/model identifiers
- requested execution region and retention profile
- data_classification and approved test-data declaration

The server resolves tenant and actor from authentication. It validates that all referenced objects belong to the same tenant and that the suite is approved for that assessment mode.

### 4.2 Run states

QUEUED → RUNNING → COMPLETED | COMPLETED_WITH_GAPS | FAILED | CANCELLED.

Individual case outcomes are PASS, FAIL, INDETERMINATE or NOT_TESTED. Provider errors, oracle errors and missing evidence never count as model passes or model failures. They remain explicit gaps.

Retries are distinct attempt records, not silent overwrites. Resume is idempotent and cannot change frozen run inputs.

## 5. Evidence data model

Minimum entities:

- Organisation
- User / Principal
- RoleAssignment
- AISystem
- SystemConfiguration
- AssessmentSuite
- AssessmentRun
- CaseAttempt
- OracleEvaluation
- ToolEvent
- Control
- ControlObservation
- RiskGap
- EvidenceObject
- HumanDecision
- RiskAcceptance
- LifecycleEvent
- Incident
- Checkpoint
- AuditEvent

Every record includes tenant_id, stable ID, created_at, actor/service identity, schema version and provenance. Tenant IDs are enforced at the database layer and in every query.

### 5.1 Exact configuration identity

Configuration digest is computed from canonical serialization of:
- provider and requested model identifier;
- observed model identifier and immutable revision, if returned;
- model parameters and inference settings;
- system/developer prompt digest;
- tool schema and permission manifest digest;
- application/policy digest;
- runtime/adapter code digest;
- retrieval/context source manifest digest, where applicable;
- execution environment and region.

If a provider cannot expose an immutable revision, the configuration is marked PINNING_UNVERIFIED and its certificate/assessment validity is capped accordingly.

### 5.2 Attempt and effect semantics

Each tool event records:
- proposed action digest and typed arguments digest;
- action and tool identifier;
- attempted_at;
- control decision and control version;
- executed_at or denied_at;
- downstream sink identifier;
- observed before/after state digest, where the sink supports it;
- observation method and evidence reference.

A denial is not a successful control merely because the application says “denied”. A control is OBSERVED only when the execution path or a trusted sink confirms that the prohibited effect did not occur within the defined test boundary.

## 6. Risk tier and controls

Risk tier is a derived operational intensity, not a universal risk score. Initial four tiers are pilot hypotheses based on:
- demonstrated capability;
- granted authority;
- impact domain;
- exposure.

The strictest applicable dimension determines minimum control intensity. Organisations may add stricter controls, never silently weaken a mandatory NCS floor. Any exception is a named, reasoned, time-bounded risk acceptance.

Tier 0–3 selects monitoring cadence, approval gates, canary depth, log sampling and reassessment urgency. Thresholds are versioned, published and validated with pilot evidence before normative adoption.

## 7. Monitoring from birth

The Native Certificate and accepted Conduct Delta establish the operating baseline. Monitoring records six drift classes:
- model;
- policy;
- context;
- authority;
- control;
- legal-obligation map.

Initial monitoring order:
1. Tool-log audits for rules observable without content.
2. Scheduled canary tests against the frozen baseline.
3. Event-triggered retest after material changes.
4. Privacy-reviewed sampled content checks only where tool logs cannot answer the question.
5. Incident intake with linked evidence and corrective action.

Attempt/effect gap is a leading indicator. Rising prohibited attempts with stable or low effect-level violations means controls may be carrying more of the burden; it triggers review rather than being reported as a healthy model.

## 8. Security and privacy requirements

Production pilot blockers:
- OIDC/SAML-compatible identity; MFA for privileged roles.
- Tenant-scoped RBAC and server-side authorisation on every object.
- Short-lived service credentials; no provider keys in browser or evidence records.
- KMS-backed encryption at rest and TLS in transit.
- Separate raw-evidence vault from aggregate analytics.
- Configurable retention, legal hold, export and verified deletion.
- Append-only audit trail with external checkpoint; signed manifest binds exact code/config/suite and evidence roots.
- Key rotation, revocation and signer identity verification.
- Rate limits, request-size limits, input validation, SSRF-safe outbound provider allowlists and network egress controls.
- Backup/restore tests, disaster recovery objectives, security scanning and dependency pinning.
- No public endpoint returns prompts, model outputs, tool arguments, raw incidents, customer identifiers or sealed test cases.

A hash chain alone is not sufficient: a privileged attacker able to rewrite the entire store can rewrite a local chain. Independent checkpoints and protected keys are required.

## 9. Operator workflow and human authority

The operator workbench must show:
- what AI system/configuration is being assessed;
- which lifecycle stage it is in;
- which obligations and controls apply;
- what evidence is missing, stale, failed or indeterminate;
- who owns each risk and remediation;
- what the model attempted versus what the controls allowed;
- what decision is pending and which person is authorised to make it.

Roles include system owner, risk owner, assessor, privacy reviewer, security reviewer, legal/compliance reviewer, business approver and incident owner. The assessor cannot approve their own assessment. A NO_POSITION, abstention or expired approval is not an approval.

NCS can recommend controls and identify evidence gaps. It does not make the organisation's legal decision or autonomously admit a system to production.

## 10. Lifecycle and retirement

Lifecycle events include CANDIDATE, ASSESSED, REJECTED, ADMITTED, OPERATING, CHANGED, RESTRICTED, SUSPENDED and RETIRED. Transitions require actor, reason, timestamp and evidence.

Retirement is not complete until credentials, permissions, endpoints and scheduled jobs are disabled and a test confirms that calls fail. Data retention/deletion, downstream dependencies, fallback plans and evidence archival are recorded. Failed-at-birth systems remain in the lineage as REJECTED; the evidence is not erased.

## 11. Public status reporting

Public dashboard fields are limited to:
- repository/workflow name;
- branch and commit SHA;
- workflow run URL;
- run state and conclusion;
- last successful CI timestamp;
- deployment state and health-check state;
- explicit scope and limitations.

The dashboard must never map a green CI check to “AI safe”, “compliant”, “certified” or “production ready”. VeriSigilAI proof claims must remain separate from NCS and Cyraduct test results.

## 12. Implementation milestones and acceptance

### M0 — Baseline and integration audit
Accepted when:
- Kestrel harness 61 tests pass;
- both mock arms complete and evidence verifies;
- adapter protocol unit tests and local protocol smoke pass;
- Cyraduct full CI and NCS Finance Guard CI are green;
- limitations are recorded.

### M1 — Runner Service Core
- typed provider-neutral conversation and tool-call adapter;
- immutable run configuration and suite digests;
- resumable execution and explicit attempt IDs;
- PASS/FAIL/INDETERMINATE/NOT_TESTED;
- no silent retry or hidden provider behavior;
- API and integration tests.

### M2 — Evidence and security
- encrypted raw evidence vault;
- tenant isolation and RBAC;
- KMS-backed signing and key lifecycle;
- independent transparency checkpoint;
- retention/deletion and backup/restore verification.

### M3 — Operator Workbench
- system inventory, lifecycle, risk register, control register;
- reviewer assignments and authority;
- evidence collection, gap remediation and decisions;
- signed export and audit timeline.

### M4 — Native Baseline / Policy Delta / Effective Conduct
- paired controlled runs;
- oracle validation reports;
- attempt/effect event semantics;
- confidence intervals and explicit missingness;
- judge-dependent rules excluded until validated.

### M5 — Monitoring and pilot
- tool-log monitoring;
- scheduled canaries;
- drift/change impact;
- incident and retirement workflow;
- limited design-partner pilot using synthetic or approved low-risk data.

### Production pilot exit gate
No production pilot until M1–M5 security, privacy, evidence and operator acceptance tests pass. No legal-compliance, liability-immunity or universal-safety claims.

## 13. Explicit open decisions

1. Initial risk tiers and thresholds require pilot validation.
2. Legal obligations mapping is an external versioned integration, not a hard-coded legal engine.
3. Raw transcript storage defaults to customer-controlled encrypted storage with minimal retention; local-only mode remains available.
4. Provider pinning depends on what each provider exposes; missing immutable revision is an evidence gap.
5. Judge-based scoring remains outside primary grading until independent validation.
6. Public status is limited to software workflow/deployment facts, not model-quality claims.
