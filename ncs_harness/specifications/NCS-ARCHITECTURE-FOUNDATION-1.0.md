# NCS Architecture Foundation — v1.0

**Status:** Architecture baseline for implementation planning. This is not a completed product, certification scheme, legal opinion, or patentability conclusion.

## 1. Mission

NCS is independent assessment and evidence infrastructure that helps organisations understand an AI system before deployment, prepare policies and controls, verify behaviour after configuration, and maintain defensible evidence throughout its operational life.

NCS combines two cooperating planes:
- **Governance Operations Plane:** human roles, risk gaps, policy ownership, reviews, approvals, remediation, monitoring and incident workflow.
- **Technical Assurance Plane:** exact system identity, provenance, controlled conduct assessment, policy-delta measurement, operational-effect verification, evidence integrity and change-triggered reassessment.

Neither plane substitutes for the organisation's accountable authority. NCS provides structured evidence and decision support; the organisation makes and owns deployment decisions.

## 2. Architecture principles

1. Identity before assessment.
2. Evidence before claims.
3. Native model conduct is separate from application controls.
4. Policy intent, configured policy and observed policy effect are separate states.
5. Human decisions are attributable, scoped and independently reviewable.
6. Missing, stale, untested and unverifiable evidence remains explicit.
7. Change impact is dependency-aware and certificate validity is conditional.
8. A model grade is not an organisational readiness score.
9. A deployment status is not a test result.
10. A test result is not a legal compliance certificate.
11. AI assistance is advisory; deterministic rules and authorised humans decide.
12. Customer data and raw model outputs are minimised and protected.

## 3. Logical architecture

### 3.1 Shared assurance core
- **Native Anchor:** stable identifier for an exact model/system/configuration subject; records digest algorithms, component identities and derivation links.
- **Origin Ledger:** signed, append-only provenance events for build, model, data, fine-tuning, packaging, evaluation and approval records. Completeness is reported as evidenced, declared, partial or unknown; no claim of complete provenance where upstream evidence is unavailable.
- **Evidence Weave:** references and cryptographically binds independent evidence streams without collapsing their meaning.
- **Change Impact Graph:** models dependencies between model artifact, prompt, retrieval, tools, policy, evaluator, test pack, application, sink and operating environment; determines affected evidence and retest scope.
- **Grade Compiler:** deterministic and versioned rules over eligible evidence. It never treats unobserved dimensions as zero or lets strong components mask a critical failure.
- **NCS Gate:** produces a technical fit disposition under a specified policy and evidence context. It is not the organisation's deployment approval.
- **Native Certificate:** version-bound assessment output, with issuer, scope, evidence references, limitations, validity conditions, revocation and reassessment status. No certificate issuance is enabled until trust, signing, transparency, completeness and governance requirements are implemented and reviewed.

### 3.2 Technical assurance engines
1. Model Execution Runner.
2. Native Behavior Baseline (NBB).
3. Policy Delta Profile (PDP / Conduct Delta).
4. Effective Conduct Profile (ECP).
5. Capability-lite profile (optional predictors only; never a conduct grade).
6. Application-control and sink-effect verifier.
7. Risk Intelligence Engine.
8. Organisational Readiness Engine.
9. Continuous Assurance and Incident Evidence Engine.

### 3.3 Governance Operations Workbench
- AI system register and lifecycle case.
- Risk gap assessment and risk register.
- Multidisciplinary role assignments and review queues.
- Policy and obligation register.
- Policy-to-Control-to-Evidence Compiler.
- Human decision and exception records.
- Remediation plans and deadlines.
- Deployment condition and oversight plan.
- Monitoring, change and incident workflow.
- Audit and evidence export.

Detailed design is in:
- NCS-GOVERNANCE-OPERATIONS-WORKBENCH-0.1.md
- NCS-POLICY-CONTROL-EVIDENCE-COMPILER-0.1.md
- NCS-CROSS-PROJECT-EVIDENCE-CONTRACT-0.1.md

## 4. Evidence state model

Each evidence item must have:
- subject Native Anchor and configuration digest;
- producer and provenance;
- test/control/requirement ID and version;
- observation time and environment;
- source commit and test-run ID where software-produced;
- evidence digest and protected reference;
- evaluator/oracle identity and version;
- result state and limitations;
- signature/attestation status;
- freshness and change-impact status.

Allowed result states include PASS, FAIL, PARTIAL, NOT_TESTED, NOT_VERIFIED, INDETERMINATE, NOT_APPLICABLE and STALE.

Evidence classes remain distinct:
- model/native conduct;
- policy/configuration delta;
- application control;
- sink/consequence effect;
- organisational process;
- human decision;
- formal verification;
- deployment/infrastructure health;
- incident and remediation.

## 5. Lifecycle state model

NCS supports seven governance gates:
- G0 Register
- G1 Risk discovery
- G2 Multidisciplinary review
- G3 Native assessment
- G4 Policy and control verification
- G5 Human deployment authorisation
- G6 Continuous assurance

A system may enter at any point in its real lifecycle. NCS records the entry state and evidence gaps; it must not fabricate completion of earlier gates.

A technical NCS Gate disposition and an organisation's human deployment authorisation are distinct. A system may be technically eligible but not organisationally approved; conversely, a human approval does not convert failed technical evidence into a pass.

## 6. Policy-to-Control-to-Evidence pipeline

Policy source → requirement → risk scenario → control objective → control specification → test specification → observed evidence → human disposition → remediation/retest.

The compiler proposes mappings and test cases. Policy owners approve interpretations; control owners approve operational controls; technical reviewers approve test designs; authorised humans decide deployment. Ambiguous or conflicting requirements remain disputed until resolved by qualified reviewers.

## 7. Cross-project adapters

NCS consumes external product evidence through a versioned contract. Each product retains its own repository, release process, test suite, runtime and claims registry.

Initial adapters:
- **Cyraduct:** synthetic Finance Guard application-control and sink-effect evidence. It does not establish foundation-model native conduct.
- **VeriSigilAI / VCB:** consequence-boundary evidence constrained by its current claims registry and proof report. Historic VeriSigil agent-identity test counts must not be transferred to the VCB project without repository and artifact equivalence.
- **NCS self-assessment:** tests of NCS code and protocol are separate from assessments of integrated products.

The website consumes validated result manifests; it does not accept manually typed success badges. A result must carry source commit, suite version, run ID, test counts, evidence level, report digest, timestamp and limitations. Relevant code changes mark old results stale.

## 8. Security and deployment boundary

- Tenant isolation and role-based access control are prerequisites for multi-customer use.
- Secrets never enter test fixtures, public manifests or evidence exports.
- Default testing is local or isolated staging with synthetic data.
- Production checks are read-only unless a separately approved safe test plan explicitly authorises harmless actions.
- Real financial, health or customer-data effects are excluded from default test suites.
- Audit evidence is append-only with protected external checkpoints; a local hash chain alone is not represented as immutable against an administrator who can rewrite the full ledger.
- No certificate issuer or transparency service is considered production-ready until independently reviewed.

## 9. Commercial product surfaces

### NCS Assurance Assessment
For buyers procuring or deploying AI in sensitive workflows. Delivers identity/provenance assessment, native baseline, policy delta, effective conduct, risk/control recommendations, readiness profile and evidence-backed technical disposition.

### NCS Governance Operations Workbench
For AI governance teams, risk professionals, consultants and auditors. Delivers guided lifecycle case management, role coordination, risk gaps, policy-to-control traceability, human decision records, remediation and continuous assurance.

### NCS Evidence Integration
For AI providers and runtime products. Accepts validated test evidence and exposes clear, bounded assurance records to downstream customers.

## 10. Implementation sequence

1. Stabilise existing NCS assessment harness and separate it from Cyraduct product code.
2. Build Model Execution Runner with provider adapters and exact run capture.
3. Reproducibly measure NBB, PDP and ECP.
4. Implement evidence contract and signed result manifests.
5. Implement Governance Workbench case model, role assignments, gate transitions and human decisions.
6. Implement Policy-to-Control-to-Evidence compiler with human confirmation and deterministic test oracles.
7. Add Risk Intelligence and Readiness profiles.
8. Add change impact, incident reconstruction and continuous assurance.
9. Add certificate issuance only after independent trust and governance review.
10. Deploy production workbench only after tenant isolation, authentication, authorisation, data retention, audit and security controls pass review.

## 11. Current implementation truth

At the time this foundation is authored:
- the NCS harness and its tests are experimental;
- the governance workbench and policy compiler are specifications, not implemented product modules;
- the NCS model runner has not completed a live model-provider assessment;
- Cyraduct's application tests do not constitute a model NBB;
- VeriSigilAI's website claims remain bounded by its own proof report;
- no NCS grade, certificate or independent certification is issued by this document.

The architecture must preserve these distinctions in code, reports, UI and marketing.
