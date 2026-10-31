# NCS Policy-to-Control-to-Evidence Compiler — v0.1

**Status:** Proposed specification; implementation not yet present.

## 1. Core transformation

The compiler creates a traceable chain:

Policy source → requirement → risk scenario → control objective → control specification → test specification → observed evidence → human disposition.

The compiler does not decide that a policy is legally correct. It does not silently convert ambiguous prose into binding rules. A qualified policy owner must approve the interpreted requirement and control.

## 2. Input contract

Each policy source must include:
- policy ID, title, owner and approving authority;
- version, effective date, review date and jurisdiction/scope;
- immutable source digest and protected source reference;
- source type: INTERNAL_POLICY, CONTRACT, LAW, STANDARD or GUIDANCE;
- authoritative source URL or citation where applicable;
- clause/section locator and original text excerpt, subject to rights and data minimisation.

Each extracted requirement must include:
- stable requirement ID;
- exact source locator and digest;
- normative strength: MUST, SHOULD, MAY or INTERNAL;
- applicability conditions;
- interpretation status: DRAFT, HUMAN_CONFIRMED, DISPUTED or NOT_APPLICABLE;
- approving reviewer and timestamp.

## 3. Control specification

A control is an operational mechanism with:
- control ID, version and owner;
- linked requirement IDs and risk scenario IDs;
- control objective and scope;
- control type: PREVENTIVE, DETECTIVE, CORRECTIVE or GOVERNANCE;
- enforcement location: MODEL, PROMPT, RETRIEVAL, AGENT, APPLICATION, TOOL, SINK or HUMAN_PROCESS;
- trigger and decision conditions;
- expected result and prohibited result;
- failure behaviour and escalation;
- evidence source and retention requirement;
- test coverage and acceptance criteria;
- control operator and independent reviewer, where required.

The control record must say whether it is a model-behaviour expectation or an external application/process control. These are never conflated.

## 4. Test specification generation

The compiler may propose tests from a control, but generated tests remain DRAFT until reviewed. A test definition includes:
- test ID, version and linked control;
- preconditions and frozen configuration identity;
- synthetic input/fixture references;
- expected behaviour and expected sink effect;
- negative, boundary, replay, expiry and change cases as appropriate;
- oracle type: DETERMINISTIC, TOOL_LOG, HUMAN_REVIEW or MODEL_ASSISTED;
- pass/fail/indeterminate rules;
- repeat count and sampling method;
- environment and isolation requirements.

Tests must be safe by default. Production endpoints, real financial sinks and personal data are prohibited unless a separately authorised production assurance protocol exists.

## 5. Evidence outcome states

Use explicit outcome states:
- PASS
- FAIL
- PARTIAL
- NOT_TESTED
- NOT_VERIFIED
- INDETERMINATE
- NOT_APPLICABLE
- STALE

No outcome may be converted into PASS by missing data, an AI-generated summary or a caller-supplied status field. The evidence collector independently evaluates observed fields against the approved test specification.

## 6. Compiler pipeline

1. Ingest and hash the policy source.
2. Extract candidate requirements with exact locators.
3. Human review confirms interpretation, scope and normative strength.
4. Link requirements to risk scenarios and accountable owners.
5. Generate candidate controls and assign enforcement locations.
6. Human control owner approves control design.
7. Generate candidate tests and fixtures.
8. Technical reviewer approves the test/oracle and safety conditions.
9. Execute in an isolated environment.
10. Verify evidence integrity and compare observations with expected outcomes.
11. Route failures and indeterminate results to remediation.
12. Re-test after control or configuration change.
13. Publish an evidence-linked control status; never publish a generic compliance percentage as a substitute.

## 7. Policy delta linkage

Where a control changes model/agent instructions or configuration, the test must pair native and configured runs under matched identity and conditions. The compiler must not attribute changes to policy when model identity, prompt, generation settings, tool access or other controlled variables differ.

Where the control operates outside the model (for example, sink-side approval), the result belongs to application-control/effect evidence, not Native Behaviour Baseline or Policy Delta.

## 8. Requirement precedence

For conflicts, preserve source and authority metadata. The compiler must not invent a universal precedence between law, regulation, contract, organisational policy and technical standards. The organisation's legal/compliance reviewer determines applicability and conflict treatment. The NCS Gate may enforce the stricter of applicable approved operational constraints, but it must not represent this as a legal interpretation.

## 9. Acceptance criteria

A v0.1 implementation must demonstrate:
- policy source digest and version retention;
- stable requirement/control/test IDs;
- traceability in both directions;
- mandatory human confirmation of extracted requirements;
- clear separation of model, application, tool, sink and human controls;
- deterministic outcome validation;
- explicit indeterminate and not-tested states;
- evidence staleness when policy, control or configuration changes;
- exportable machine-readable traceability graph;
- no automated compliance certification or deployment approval.
