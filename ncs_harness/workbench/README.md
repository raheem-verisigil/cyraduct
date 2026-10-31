# NCS Governance Operations Workbench — executable prototype v0.1

This is the first local domain/service slice of the NCS operator workbench. It is intentionally separate from Cyraduct's production request path.

## Implemented in this prototype
- Register an AI assurance case against an exact model-configuration SHA-256 and actual lifecycle entry gate.
- Assign accountable multidisciplinary roles and authority references.
- Create risk gaps with severity, owner, due date and remediation.
- Record explicit evidence provenance and outcome states.
- Record human review decisions; a decision-maker must have a matching case assignment and authority reference.
- Treat NO_POSITION as non-approval.
- Require linked PASS or NOT_APPLICABLE evidence before a gap can close.
- Mark prior evidence STALE when model configuration or policy digest changes.
- Produce a machine-readable case manifest.
- Verify a per-case SHA-256 hash-chained event history.

## Run tests
From repository root:

```bash
python -m unittest tests.test_ncs_workbench -v
```

## Minimal use
```python
import hashlib
from ncs_harness.workbench import Workbench

sha = lambda s: hashlib.sha256(s.encode()).hexdigest()
wb = Workbench("ncs-workbench.sqlite3")
case = wb.create_case(
    org_id="org-demo",
    system_name="Claims Triage Assistant",
    owner="AI Office",
    intended_purpose="Prioritise synthetic claims for human review",
    model_config_sha256=sha("frozen-model-config-v1"),
    actor="operator-001",
)
print(wb.readiness(case["case_id"]))
print(wb.export_manifest(case["case_id"]))
```

## Important limitations
- Local SQLite prototype only; no production authentication, tenant isolation, RBAC enforcement, API, UI, encrypted evidence vault, object storage, retention controls or disaster recovery.
- Role assignments and decision authority are recorded and checked for matching references, but identity proof and delegated-authority verification are not implemented.
- The hash chain detects local record tampering only if its trusted head/checkpoint is held outside the database. There is no signature, external transparency log or independently operated checkpoint yet.
- A PASS is accepted only as a recorded evidence state from a source type. Production use needs evidence verification adapters and reviewer controls.
- The prototype does not interpret law, determine legal compliance, issue NCS grades/certificates or authorise deployment.
- Readiness output is a workflow snapshot, not a percentage score or assurance conclusion.
