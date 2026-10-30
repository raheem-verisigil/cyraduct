# NCS Governance Operations Workbench — v0.1

**Status:** Proposed specification; not implemented or certified.

## 1. Product definition

The NCS Governance Operations Workbench (GOW) is a guided, evidence-aware workspace for organisations to register AI systems, assess risk gaps, coordinate multidisciplinary reviews, assign accountable owners, translate policy into testable controls, record human decisions, and maintain lifecycle assurance.

GOW is not a substitute for legal advice, an organisation's management system, independent audit, a regulator, or the accountable deployment authority. It provides structured workflows and evidence; the organisation retains decision responsibility.

## 2. Design invariants

1. **One system identity:** every case is bound to a Native Anchor and an immutable configuration identity.
2. **Evidence before assertion:** every material status is supported by evidence or explicitly marked declared, pending, not tested, not verified, not applicable, or unresolved.
3. **Human authority is explicit:** approval requires an identified person, role, authority scope, decision, timestamp, rationale and evidence references.
4. **Separation of duties:** authors, control operators, reviewers and final approvers are distinguishable; high-consequence cases can require independent review.
5. **No silent green status:** missing evidence never becomes pass; an unresolved critical gap cannot be hidden by an aggregate percentage.
6. **Lifecycle continuity:** an existing deployed AI system may enter at any stage; NCS records the actual entry state and does not fabricate completed earlier gates.
7. **Change invalidates selectively:** material changes trigger the Change Impact Graph; affected evidence is invalidated or marked for reassessment with dependency rationale.
8. **Least data collection:** store hashes, structured observations and protected evidence references by default; do not collect prompts, outputs, personal data or customer records unless necessary and authorised.
9. **Framework mapping is not certification:** mappings to laws and standards identify relevant evidence and obligations; they do not assert legal compliance.
10. **Auditable automation:** AI-generated summaries, mappings and recommendations are labelled suggestions and cannot approve, close or waive a mandatory control.

## 3. Lifecycle case model

An AI Assurance Case contains:
- case ID and organisation scope;
- Native Anchor, model/system identity and configuration digest;
- provider, developer, deployer and business owner identities;
- intended purpose, users, affected parties and operating context;
- jurisdiction and selected framework mappings;
- risk classification and impact rationale;
- lifecycle gate state and task assignments;
- policy versions and control specifications;
- Native Baseline, Policy Delta and Effective Conduct evidence references;
- human approvals, exceptions, incidents, remediation and change history;
- current certificate state and reassessment triggers.

A case can contain multiple deployments or derived configurations. A derived configuration must not inherit a parent's certificate as if it were unchanged.

## 4. Seven lifecycle gates

| Gate | Name | Required outputs | Gate condition |
|---|---|---|---|
| G0 | Register | system identity, owner, intended purpose, lifecycle entry point | minimum identity and accountability fields complete |
| G1 | Risk discovery | use context, impact analysis, initial risk register, evidence-gap list | critical unknowns assigned and triaged |
| G2 | Multidisciplinary review | legal, privacy, security, data, engineering, operations and business reviews as applicable | required reviewers record a position or explicit non-applicability |
| G3 | Native assessment | provenance status, NBB and capability profile, limitations | required native tests completed or explicitly excepted by authorised authority |
| G4 | Policy/control verification | PDP, ECP, control tests, residual risks | mandatory controls pass at their defined evidence tier |
| G5 | Deployment authorisation | deployment conditions, human oversight plan, approval record | accountable human approval and all blocking conditions resolved |
| G6 | Continuous assurance | monitoring, incident handling, change assessment, reassessment history | recurring obligations assigned and operational evidence route active |

Gate state values: NOT_STARTED, IN_PROGRESS, BLOCKED, READY_FOR_REVIEW, APPROVED_WITH_CONDITIONS, APPROVED, REJECTED, NOT_APPLICABLE, REOPENED.

APPROVED is a human organisational decision, not an NCS technical grade. A technical NCS Gate result and organisational approval are separate fields.

## 5. Risk gap assessment

Each gap record must contain:
- requirement/control reference and source/version;
- risk scenario, affected asset/process/person and consequence;
- inherent risk rationale and uncertainty;
- existing control and owner;
- evidence required and evidence received;
- control design status and operating-effectiveness status;
- residual risk rationale;
- remediation action, accountable owner and due date;
- reviewer and closure evidence.

Risk dimensions should be configurable to the organisation's approved methodology. NCS must not impose an unvalidated universal risk formula. Any calculated risk score must expose inputs, method version and uncertainty.

Criticality is determined by explicit rules and context, not averaging. A critical unresolved item remains visible even if other items pass.

## 6. Multidisciplinary collaboration

Role templates:
- executive/accountable AI owner;
- business/process owner;
- AI governance or risk lead;
- legal/compliance;
- privacy/data protection;
- information security;
- data science/model engineering;
- application/platform engineering;
- procurement/vendor management;
- HR/workforce or affected-people representative, where relevant;
- internal audit/independent assessor;
- human overseer/operator.

Roles are templates, not assumptions that every organisation has these job titles. An organisation may map equivalent responsibilities. Each assignment includes scope, decision rights, due date, evidence request and escalation path.

A reviewer may record APPROVE, APPROVE_WITH_CONDITIONS, OBJECT, REQUEST_MORE_EVIDENCE, NOT_APPLICABLE or NO_POSITION. NO_POSITION does not count as approval.

## 7. Human decision record

Required fields:
- decision ID and case/configuration ID;
- decision-maker identity and role;
- delegated authority reference and scope;
- decision type and outcome;
- rationale and material considerations;
- evidence references and policy versions considered;
- conditions, expiry and review date;
- timestamp and signature/attestation;
- any dissent, exception or conflict-of-interest declaration.

NCS automation may prepare a decision brief but may not sign, impersonate or infer a human decision.

## 8. Readiness profile

Organisational readiness is separate from model grade:
- L0_UNPREPARED
- L1_DOCUMENTED
- L2_IMPLEMENTED
- L3_VERIFIED
- L4_CONTINUOUSLY_ASSURED

L3 requires evidence that relevant controls operate as intended. L4 requires repeated evidence over time and effective change/incident handling. A policy document alone cannot establish L2 or above.

Readiness is reported by domain (ownership, policy, data, security, human oversight, operations, incident response, monitoring) rather than hidden in a single average.

## 9. Operator experience

The default user journey is task-led:
1. show current lifecycle stage and case identity;
2. show the next required action and responsible role;
3. explain why the action is required;
4. state acceptable evidence and examples;
5. allow secure upload or connector-based evidence reference;
6. validate completeness and provenance;
7. route to reviewer;
8. record human outcome and rationale;
9. update gate state and downstream retest requirements.

The interface must distinguish verified evidence, human declaration, third-party assertion, AI-generated suggestion, inferred mapping, and missing or stale evidence.

## 10. AI assistant boundaries

The assistant may draft gap assessments, map policy text to candidate controls, explain failed tests, prepare reviewer briefs and suggest remediation. It must cite the exact source requirement and version, disclose uncertainty, request human confirmation for mappings, never close a critical gap or approve deployment, retain model/version and prompt-template digest for material recommendations, and preserve human-approved policy and decisions separately from generated drafts.

## 11. Data and security requirements

Tenant isolation is mandatory before multi-customer use. Role-based access control must be combined with case-level permissions and separation-of-duties rules. Sensitive evidence should be stored in protected object storage with access logs; the ledger stores content digests and references. Secrets must never be written to evidence records. Retention, deletion, legal hold and residency rules must be configurable by jurisdiction and contract.

## 12. Acceptance criteria for v0.1

A prototype is acceptable only when it can:
- create an AI assurance case with explicit lifecycle entry point;
- assign at least five distinct role types;
- create and track risk gaps with owners and evidence requests;
- record review decisions without conflating no-response with approval;
- represent all seven gates and block progression on configured critical gaps;
- link each decision to exact policy/configuration/evidence versions;
- mark evidence stale after a material change;
- export a machine-readable case manifest and human-readable review report;
- preserve NOT_TESTED, NOT_VERIFIED, NOT_APPLICABLE and UNRESOLVED as distinct states.

No production-readiness claim is implied by this specification.
