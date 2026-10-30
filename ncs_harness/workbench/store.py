"""NCS Governance Operations Workbench local prototype (v0.1).

This module is a workflow/domain prototype, not a production multi-tenant service.
It uses SQLite and a hash-chained event log. External checkpointing/signatures,
authentication, authorisation and protected object storage are not implemented.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GATES = ("G0_REGISTER", "G1_RISK_DISCOVERY", "G2_MULTIDISCIPLINARY_REVIEW",
         "G3_NATIVE_ASSESSMENT", "G4_POLICY_CONTROL_VERIFICATION",
         "G5_DEPLOYMENT_AUTHORISATION", "G6_CONTINUOUS_ASSURANCE")
GATE_STATES = {"NOT_STARTED", "IN_PROGRESS", "BLOCKED", "READY_FOR_REVIEW",
               "APPROVED_WITH_CONDITIONS", "APPROVED", "REJECTED",
               "NOT_APPLICABLE", "REOPENED"}
REVIEW_OUTCOMES = {"APPROVE", "APPROVE_WITH_CONDITIONS", "OBJECT",
                   "REQUEST_MORE_EVIDENCE", "NOT_APPLICABLE", "NO_POSITION"}
EVIDENCE_STATES = {"DECLARED", "PENDING", "PASS", "FAIL", "PARTIAL",
                   "NOT_TESTED", "NOT_VERIFIED", "INDETERMINATE",
                   "NOT_APPLICABLE", "STALE", "UNRESOLVED"}
ROLES = {"ACCOUNTABLE_OWNER", "BUSINESS_OWNER", "AI_GOVERNANCE",
         "LEGAL_COMPLIANCE", "PRIVACY", "SECURITY", "DATA_SCIENCE",
         "ENGINEERING", "PROCUREMENT", "INTERNAL_AUDIT", "HUMAN_OVERSIGHT"}
REQUIRED_REVIEW_ROLES = {"LEGAL_COMPLIANCE", "PRIVACY", "SECURITY",
                         "DATA_SCIENCE", "BUSINESS_OWNER"}
DOMAINS = {"ownership", "policy", "data", "security", "human_oversight",
           "operations", "incident_response", "monitoring"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _require_sha(value: str, field: str) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")


class Workbench:
    """SQLite-backed case workflow with explicit human decisions and evidence states."""

    def __init__(self, database: str | Path = ":memory:"):
        self.database = str(database)
        self._init()

    def _connect(self):
        db = sqlite3.connect(self.database)
        db.row_factory = sqlite3.Row
        return db

    def _init(self):
        with self._connect() as db:
            db.executescript("""
            PRAGMA foreign_keys=ON;
            CREATE TABLE IF NOT EXISTS cases(
              case_id TEXT PRIMARY KEY, org_id TEXT NOT NULL, system_name TEXT NOT NULL,
              owner TEXT NOT NULL, intended_purpose TEXT NOT NULL,
              model_config_sha256 TEXT NOT NULL, policy_sha256 TEXT,
              entry_gate TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS assignments(
              assignment_id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
              role TEXT NOT NULL, person_id TEXT NOT NULL, scope TEXT NOT NULL,
              authority_ref TEXT, due_at TEXT, created_at TEXT NOT NULL,
              UNIQUE(case_id, role, person_id)
            );
            CREATE TABLE IF NOT EXISTS gaps(
              gap_id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
              requirement_ref TEXT NOT NULL, risk_scenario TEXT NOT NULL,
              severity TEXT NOT NULL, status TEXT NOT NULL, owner_person_id TEXT NOT NULL,
              due_at TEXT, remediation TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS evidence(
              evidence_id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
              evidence_type TEXT NOT NULL, subject_sha256 TEXT NOT NULL,
              content_sha256 TEXT NOT NULL, protected_ref TEXT,
              state TEXT NOT NULL, source_type TEXT NOT NULL,
              created_by TEXT NOT NULL, created_at TEXT NOT NULL, stale_reason TEXT
            );
            CREATE TABLE IF NOT EXISTS decisions(
              decision_id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
              gate TEXT NOT NULL, person_id TEXT NOT NULL, role TEXT NOT NULL,
              authority_ref TEXT NOT NULL, outcome TEXT NOT NULL, rationale TEXT NOT NULL,
              evidence_ids_json TEXT NOT NULL, policy_sha256 TEXT, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events(
              seq INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT NOT NULL,
              event_type TEXT NOT NULL, actor TEXT NOT NULL, payload_json TEXT NOT NULL,
              occurred_at TEXT NOT NULL, previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL
            );
            """)

    def _event(self, db, case_id: str, event_type: str, actor: str, payload: dict):
        previous = db.execute(
            "SELECT event_hash FROM events WHERE case_id=? ORDER BY seq DESC LIMIT 1",
            (case_id,)).fetchone()
        previous_hash = previous["event_hash"] if previous else "0" * 64
        body = {"case_id": case_id, "event_type": event_type, "actor": actor,
                "payload": payload, "occurred_at": _now(), "previous_hash": previous_hash}
        event_hash = _sha(_canonical(body))
        db.execute("""INSERT INTO events(case_id,event_type,actor,payload_json,occurred_at,previous_hash,event_hash)
                      VALUES(?,?,?,?,?,?,?)""",
                   (case_id, event_type, actor, _canonical(payload), body["occurred_at"],
                    previous_hash, event_hash))

    def create_case(self, *, org_id: str, system_name: str, owner: str,
                    intended_purpose: str, model_config_sha256: str,
                    entry_gate: str = "G0_REGISTER", actor: str = "system") -> dict:
        _require_sha(model_config_sha256, "model_config_sha256")
        if entry_gate not in GATES:
            raise ValueError("entry_gate must be a known NCS lifecycle gate")
        for name, value in (("org_id", org_id), ("system_name", system_name),
                            ("owner", owner), ("intended_purpose", intended_purpose)):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is required")
        case_id, now = "ncs_" + uuid.uuid4().hex, _now()
        with self._connect() as db:
            db.execute("""INSERT INTO cases VALUES(?,?,?,?,?,?,?,?,?,?)""",
                       (case_id, org_id, system_name, owner, intended_purpose,
                        model_config_sha256, None, entry_gate, now, now))
            self._event(db, case_id, "CASE_REGISTERED", actor,
                        {"system_name": system_name, "model_config_sha256": model_config_sha256,
                         "entry_gate": entry_gate})
        return self.get_case(case_id)

    def get_case(self, case_id: str) -> dict:
        with self._connect() as db:
            row = db.execute("SELECT * FROM cases WHERE case_id=?", (case_id,)).fetchone()
            if not row:
                raise KeyError(case_id)
            result = dict(row)
            result["gate_states"] = {gate: ("IN_PROGRESS" if gate == result["entry_gate"] else "NOT_STARTED")
                                     for gate in GATES}
            return result

    def assign_role(self, case_id: str, *, role: str, person_id: str, scope: str,
                    authority_ref: str | None = None, due_at: str | None = None,
                    actor: str) -> dict:
        if role not in ROLES:
            raise ValueError("unsupported role")
        if not person_id.strip() or not scope.strip() or not actor.strip():
            raise ValueError("person_id, scope and actor are required")
        assignment_id = "as_" + uuid.uuid4().hex
        with self._connect() as db:
            self._case_exists(db, case_id)
            db.execute("INSERT INTO assignments VALUES(?,?,?,?,?,?,?,?)",
                       (assignment_id, case_id, role, person_id, scope, authority_ref, due_at, _now()))
            self._event(db, case_id, "ROLE_ASSIGNED", actor,
                        {"assignment_id": assignment_id, "role": role, "person_id": person_id,
                         "scope": scope, "authority_ref": authority_ref})
        return {"assignment_id": assignment_id, "case_id": case_id, "role": role, "person_id": person_id}

    def add_gap(self, case_id: str, *, requirement_ref: str, risk_scenario: str,
                severity: str, owner_person_id: str, due_at: str | None = None,
                remediation: str | None = None, actor: str) -> dict:
        if severity not in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}:
            raise ValueError("severity must be CRITICAL, HIGH, MEDIUM or LOW")
        if not all(isinstance(v, str) and v.strip() for v in (requirement_ref, risk_scenario, owner_person_id, actor)):
            raise ValueError("requirement_ref, risk_scenario, owner_person_id and actor are required")
        gap_id, now = "gap_" + uuid.uuid4().hex, _now()
        with self._connect() as db:
            self._case_exists(db, case_id)
            db.execute("INSERT INTO gaps VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                       (gap_id, case_id, requirement_ref, risk_scenario, severity, "OPEN",
                        owner_person_id, due_at, remediation, now, now))
            self._event(db, case_id, "RISK_GAP_OPENED", actor,
                        {"gap_id": gap_id, "requirement_ref": requirement_ref,
                         "severity": severity, "owner_person_id": owner_person_id})
        return {"gap_id": gap_id, "status": "OPEN", "severity": severity}

    def close_gap(self, case_id: str, gap_id: str, *, closure_evidence_id: str,
                  actor: str) -> dict:
        with self._connect() as db:
            self._case_exists(db, case_id)
            evidence = db.execute("SELECT state FROM evidence WHERE evidence_id=? AND case_id=?",
                                  (closure_evidence_id, case_id)).fetchone()
            if not evidence or evidence["state"] not in {"PASS", "NOT_APPLICABLE"}:
                raise ValueError("gap closure requires linked PASS or approved NOT_APPLICABLE evidence")
            changed = db.execute("UPDATE gaps SET status='CLOSED',updated_at=? WHERE gap_id=? AND case_id=? AND status='OPEN'",
                                 (_now(), gap_id, case_id)).rowcount
            if not changed:
                raise ValueError("gap not found or not open")
            self._event(db, case_id, "RISK_GAP_CLOSED", actor,
                        {"gap_id": gap_id, "closure_evidence_id": closure_evidence_id})
        return {"gap_id": gap_id, "status": "CLOSED"}

    def add_evidence(self, case_id: str, *, evidence_type: str, subject_sha256: str,
                     content_sha256: str, state: str, source_type: str,
                     created_by: str, protected_ref: str | None = None) -> dict:
        _require_sha(subject_sha256, "subject_sha256")
        _require_sha(content_sha256, "content_sha256")
        if state not in EVIDENCE_STATES:
            raise ValueError("unsupported evidence state")
        if source_type not in {"HUMAN_DECLARATION", "SYSTEM_OBSERVATION", "THIRD_PARTY",
                               "AI_SUGGESTION", "TEST_RESULT", "DOCUMENT"}:
            raise ValueError("unsupported source_type")
        if not evidence_type.strip() or not created_by.strip():
            raise ValueError("evidence_type and created_by are required")
        evidence_id, now = "ev_" + uuid.uuid4().hex, _now()
        with self._connect() as db:
            self._case_exists(db, case_id)
            db.execute("INSERT INTO evidence VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                       (evidence_id, case_id, evidence_type, subject_sha256, content_sha256,
                        protected_ref, state, source_type, created_by, now, None))
            self._event(db, case_id, "EVIDENCE_RECORDED", created_by,
                        {"evidence_id": evidence_id, "evidence_type": evidence_type,
                         "state": state, "source_type": source_type,
                         "subject_sha256": subject_sha256, "content_sha256": content_sha256})
        return {"evidence_id": evidence_id, "state": state}

    def record_decision(self, case_id: str, *, gate: str, person_id: str, role: str,
                        authority_ref: str, outcome: str, rationale: str,
                        evidence_ids: list[str], actor: str) -> dict:
        if gate not in GATES or outcome not in REVIEW_OUTCOMES:
            raise ValueError("unknown gate or review outcome")
        if not all(isinstance(v, str) and v.strip() for v in (person_id, role, authority_ref, rationale, actor)):
            raise ValueError("human identity, role, authority, rationale and actor are required")
        decision_id, now = "dec_" + uuid.uuid4().hex, _now()
        with self._connect() as db:
            self._case_exists(db, case_id)
            assigned = db.execute("""SELECT 1 FROM assignments WHERE case_id=? AND role=? AND person_id=?
                                     AND authority_ref=?""",
                                  (case_id, role, person_id, authority_ref)).fetchone()
            if not assigned:
                raise ValueError("decision-maker must have a matching role assignment and authority reference")
            for evidence_id in evidence_ids:
                if not db.execute("SELECT 1 FROM evidence WHERE evidence_id=? AND case_id=?",
                                  (evidence_id, case_id)).fetchone():
                    raise ValueError("decision evidence must belong to this case")
            policy = db.execute("SELECT policy_sha256 FROM cases WHERE case_id=?", (case_id,)).fetchone()["policy_sha256"]
            db.execute("INSERT INTO decisions VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                       (decision_id, case_id, gate, person_id, role, authority_ref, outcome,
                        rationale, _canonical(evidence_ids), policy, now))
            self._event(db, case_id, "HUMAN_DECISION_RECORDED", actor,
                        {"decision_id": decision_id, "gate": gate, "person_id": person_id,
                         "role": role, "outcome": outcome, "evidence_ids": evidence_ids})
        return {"decision_id": decision_id, "outcome": outcome, "gate": gate}

    def update_configuration(self, case_id: str, *, model_config_sha256: str,
                             policy_sha256: str | None, actor: str) -> dict:
        _require_sha(model_config_sha256, "model_config_sha256")
        if policy_sha256 is not None:
            _require_sha(policy_sha256, "policy_sha256")
        with self._connect() as db:
            row = self._case_exists(db, case_id)
            changed = row["model_config_sha256"] != model_config_sha256 or row["policy_sha256"] != policy_sha256
            if changed:
                db.execute("UPDATE cases SET model_config_sha256=?,policy_sha256=?,updated_at=? WHERE case_id=?",
                           (model_config_sha256, policy_sha256, _now(), case_id))
                db.execute("UPDATE evidence SET state='STALE',stale_reason='subject configuration or policy changed' WHERE case_id=? AND state IN ('PASS','FAIL','PARTIAL','DECLARED','NOT_VERIFIED','INDETERMINATE')",
                           (case_id,))
                self._event(db, case_id, "CONFIGURATION_CHANGED", actor,
                            {"model_config_sha256": model_config_sha256, "policy_sha256": policy_sha256,
                             "stale_evidence_marked": True})
        return {"case_id": case_id, "changed": changed, "model_config_sha256": model_config_sha256}

    def readiness(self, case_id: str) -> dict:
        with self._connect() as db:
            case = self._case_exists(db, case_id)
            assignments = db.execute("SELECT role,person_id FROM assignments WHERE case_id=?", (case_id,)).fetchall()
            gaps = db.execute("SELECT * FROM gaps WHERE case_id=?", (case_id,)).fetchall()
            evidence = db.execute("SELECT * FROM evidence WHERE case_id=?", (case_id,)).fetchall()
            decisions = db.execute("SELECT * FROM decisions WHERE case_id=?", (case_id,)).fetchall()
        assigned_roles = {r["role"] for r in assignments}
        open_critical = [dict(g) for g in gaps if g["severity"] == "CRITICAL" and g["status"] == "OPEN"]
        review_roles = {r["role"] for r in decisions if r["outcome"] in {"APPROVE", "APPROVE_WITH_CONDITIONS", "NOT_APPLICABLE"}}
        review_roles = {role for role in review_roles if role in REQUIRED_REVIEW_ROLES}
        stale = [dict(e) for e in evidence if e["state"] == "STALE"]
        missing_roles = sorted(REQUIRED_REVIEW_ROLES - assigned_roles)
        no_review = sorted(REQUIRED_REVIEW_ROLES - review_roles)
        blockers = []
        if open_critical:
            blockers.append("OPEN_CRITICAL_RISK_GAPS")
        if missing_roles:
            blockers.append("REQUIRED_REVIEW_ROLES_UNASSIGNED")
        if no_review:
            blockers.append("REQUIRED_REVIEW_DECISIONS_MISSING")
        if stale:
            blockers.append("STALE_EVIDENCE_REQUIRES_REASSESSMENT")
        domains = {d: "NOT_ASSESSED" for d in sorted(DOMAINS)}
        for e in evidence:
            domain = e["evidence_type"].lower()
            if domain in domains and e["state"] == "PASS":
                domains[domain] = "EVIDENCED"
            elif domain in domains and e["state"] not in {"NOT_APPLICABLE"}:
                domains[domain] = "GAP_OR_UNVERIFIED"
        return {"case_id": case_id, "lifecycle_entry_gate": case["entry_gate"],
                "model_config_sha256": case["model_config_sha256"],
                "assigned_roles": sorted(assigned_roles), "missing_required_roles": missing_roles,
                "review_roles_without_approval": no_review, "open_critical_gaps": open_critical,
                "stale_evidence_count": len(stale), "domain_profile": domains,
                "blockers": blockers, "technical_or_legal_compliance_claim": False,
                "deployment_authorised": False,
                "note": "This readiness snapshot is workflow evidence only; it is not a legal compliance conclusion or deployment approval."}

    def export_manifest(self, case_id: str) -> dict:
        with self._connect() as db:
            case = self._case_exists(db, case_id)
            tables = {}
            for table in ("assignments", "gaps", "evidence", "decisions", "events"):
                rows = db.execute(f"SELECT * FROM {table} WHERE case_id=? ORDER BY rowid", (case_id,)).fetchall()
                tables[table] = [dict(r) for r in rows]
        body = {"schema": "ncs-workbench-case-manifest/0.1", "case": dict(case),
                "records": tables, "readiness": self.readiness(case_id)}
        body["integrity"] = {"manifest_sha256": _sha(_canonical(body))}
        return body

    def verify_event_chain(self, case_id: str) -> dict:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM events WHERE case_id=? ORDER BY seq", (case_id,)).fetchall()
        previous = "0" * 64
        for row in rows:
            body = {"case_id": row["case_id"], "event_type": row["event_type"],
                    "actor": row["actor"], "payload": json.loads(row["payload_json"]),
                    "occurred_at": row["occurred_at"], "previous_hash": previous}
            expected = _sha(_canonical(body))
            if row["previous_hash"] != previous or row["event_hash"] != expected:
                return {"valid": False, "events_checked": len(rows), "failed_seq": row["seq"]}
            previous = row["event_hash"]
        return {"valid": True, "events_checked": len(rows), "head_hash": previous}

    @staticmethod
    def _case_exists(db, case_id):
        row = db.execute("SELECT * FROM cases WHERE case_id=?", (case_id,)).fetchone()
        if not row:
            raise KeyError(case_id)
        return row
