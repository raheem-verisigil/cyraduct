# Cyraduct External Pilot Plan

**Status:** Draft — controlled evaluation only  
**Release posture:** Not approved for unrestricted production use  
**Initial use case:** Vendor-master / bank-detail change validation in shadow mode  
**Data posture:** Synthetic data first; real data only after written authorization and a documented data-handling review

## 1. Purpose

This plan defines a safe, evidence-led route for an external organization to evaluate Cyraduct's authorization decisions and receipt-verification workflow. A successful pilot demonstrates the tested properties and known limits; it does not by itself establish general production readiness or independent security certification.

## 2. Pilot stages

### Stage A — Synthetic conformance

- Use fabricated organizations, agents, vendor records, amounts, and action payloads.
- Exercise allow, deny, conditional, expired, revoked, malformed, mismatched-agent, altered-signature, replay, and unavailable-service scenarios.
- Use a mock sink that never connects to payment rails, production databases, or customer infrastructure.
- Preserve a test report containing case ID, expected result, observed result, build/commit, and evidence reference.
- Exit only when all required cases pass and critical/high-severity defects are closed or explicitly block the pilot.

### Stage B — Customer-controlled shadow mode

- Obtain written authorization from the data/system owner and name a customer pilot owner.
- Agree the purpose, data categories, fields, retention period, subprocessors, access list, incident channel, and deletion date before any transfer.
- Minimize or pseudonymize inputs. Prefer proposed-action metadata over complete vendor records.
- Cyraduct evaluates actions and records what it would allow or deny; it must not execute or trigger the underlying business action.
- Compare decisions with the customer's existing controls and manually review disagreements.
- Exit only after the customer approves the results and no unresolved critical/high-severity issue remains.

### Stage C — Narrow enforcement test

This stage is separate approval, not an automatic extension of shadow mode.

- Use a customer-approved sandbox or dedicated low-risk reversible action.
- Confirm the sink independently verifies the receipt and checks expiry, revocation, action/agent binding, and replay/duplicate behavior immediately before execution.
- Apply least privilege, strict action allowlists, transaction/volume limits, human ownership, monitoring, and a tested stop/rollback procedure.
- Do not start with real transfers, destructive infrastructure actions, health-record writes, or irreversible customer-impacting operations.
- Stop the test immediately if authorization and execution outcomes diverge or logs/evidence are incomplete.

## 3. Required test cases

| ID | Scenario | Required result |
|---|---|---|
| CP-001 | Valid receipt for the intended agent/action | Sink accepts only the bound action |
| CP-002 | Missing or invalid credential on private API | Request rejected |
| CP-003 | Test key attempts to access a non-test agent/receipt | Denied without sensitive disclosure |
| CP-004 | Expired receipt | Sink rejects execution |
| CP-005 | Revoked receipt | Sink rejects execution |
| CP-006 | Altered receipt/signature | Independent verification fails |
| CP-007 | Receipt presented for a different action or agent | Sink rejects execution |
| CP-008 | Duplicate/replayed request | No unintended duplicate side effect |
| CP-009 | Cyraduct or verifier unavailable | Fail closed for protected actions |
| CP-010 | Kill switch active | Protected action blocked and event recorded |
| CP-011 | Audit evidence is incomplete or inconsistent | Alert and stop/hold the pilot |
| CP-012 | Rate limit or malformed oversized request | Controlled rejection; service remains stable |

A case is not passed merely because the API returns HTTP 200. The tester must verify the sink's actual behavior and whether any side effect occurred.

## 4. Data protection and access rules

Before Stage B, document and approve:

- Data owner, controller/processor roles as applicable, lawful authority, purpose, and permitted fields.
- Data-flow diagram, storage locations, encryption in transit/at rest, and all people/services with access.
- Retention and deletion timeline, including logs, backups, exports, and test artifacts.
- Incident notification contacts and response expectations.
- Whether data may contain personal, financial, health, credential, or other regulated information. Exclude sensitive categories unless a separate assessment explicitly approves them.
- A prohibition on production credentials, private keys, payment secrets, passwords, access tokens, and unredacted customer payloads in test submissions or tickets.

## 5. Roles

- **Customer pilot owner:** Approves scope, data access, business acceptance, and stop/resume decisions.
- **Cyraduct technical owner:** Supplies versioned build, configuration, API documentation, and technical incident response.
- **Independent tester:** Runs the cases, records evidence, challenges assumptions, and reports defects.
- **Sink/system owner:** Confirms that enforcement is performed at the actual execution boundary and that bypass paths are not available.

One person may hold multiple roles in a small pilot, but the test report must disclose this and should not describe self-testing as independent validation.

## 6. Stop conditions

Stop the pilot and disable the integration if any of the following occurs:

- An unauthorized action reaches execution.
- A test identity can read or change data outside its assigned scope.
- Receipt verification accepts a tampered, expired, revoked, or mismatched receipt.
- A replay causes an unintended repeated side effect.
- The kill switch or emergency stop does not work as documented.
- Audit evidence is missing, unexpectedly mutable, or materially inconsistent.
- Customer data is exposed outside the approved scope.
- A critical/high-severity security defect is discovered.

Resume only after root-cause analysis, remediation, retesting, and approval by the named customer owner.

## 7. Pilot success measures

Agree numeric thresholds with the customer before testing. Report at minimum:

- Required scenarios passed / total.
- Unauthorized execution attempts blocked.
- False approvals and false denials, reviewed by severity.
- Receipt verification success and failure behavior.
- Median and p95 evaluation/verification latency under the agreed load.
- Audit completeness and ability to independently verify receipt signatures.
- Recovery and stop/rollback test results.
- Open defects, severity, owner, and disposition.

Do not publish or market success percentages until they are supported by the recorded test results and disclosed test conditions.

## 8. Evidence package

For every run, record:

- Pilot ID, date, environment, Cyraduct commit/release, configuration version, and tester.
- Test case ID, sanitized request, expected result, observed result, and sink-side side-effect check.
- Receipt ID or a safe reference, signature-verification result, relevant audit correlation ID, and timestamps.
- Defect ID and retest outcome.
- Customer acceptance, exclusions, known limitations, and sign-off.

Never put secrets or unnecessary raw customer data into the evidence package.

## 9. Go / no-go decision

**No-go** if required tests fail, critical/high issues remain unresolved, tenant isolation is unproven, a safe stop/rollback cannot be demonstrated, or data handling is not approved.

**Limited pilot approval** requires passing the agreed tests, a documented risk acceptance by the customer, a named operational owner, monitoring, a stop procedure, and an explicit scope and expiry date.

**Production readiness is a separate decision.** It requires deployment hardening, operational recovery evidence, appropriate independent security review, and validation of the actual sink integration—not just a successful shadow-mode exercise.
