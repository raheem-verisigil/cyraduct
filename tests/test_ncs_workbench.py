import hashlib
import unittest

from ncs_harness.workbench.store import Workbench


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.wb = Workbench()
        self.case = self.wb.create_case(
            org_id="org-demo", system_name="Claims Triage Assistant",
            owner="AI Office", intended_purpose="Prioritise synthetic claims for human review",
            model_config_sha256=digest("model-config-v1"), actor="tester")
        self.case_id = self.case["case_id"]

    def assign_required(self):
        for role in ("LEGAL_COMPLIANCE", "PRIVACY", "SECURITY", "DATA_SCIENCE", "BUSINESS_OWNER"):
            self.wb.assign_role(self.case_id, role=role, person_id="person-" + role,
                                scope="review this AI use case", authority_ref="delegation-" + role,
                                actor="admin")

    def approve_required(self):
        self.assign_required()
        for role in ("LEGAL_COMPLIANCE", "PRIVACY", "SECURITY", "DATA_SCIENCE", "BUSINESS_OWNER"):
            self.wb.record_decision(self.case_id, gate="G2_MULTIDISCIPLINARY_REVIEW",
                                    person_id="person-" + role, role=role,
                                    authority_ref="delegation-" + role, outcome="APPROVE",
                                    rationale="Reviewed the scoped evidence", evidence_ids=[], actor="reviewer")

    def test_create_case_records_actual_entry_gate(self):
        self.assertEqual(self.case["entry_gate"], "G0_REGISTER")
        self.assertEqual(self.case["model_config_sha256"], digest("model-config-v1"))

    def test_required_roles_and_decisions_are_not_assumed(self):
        result = self.wb.readiness(self.case_id)
        self.assertIn("REQUIRED_REVIEW_ROLES_UNASSIGNED", result["blockers"])
        self.assertIn("REQUIRED_REVIEW_DECISIONS_MISSING", result["blockers"])
        self.assertFalse(result["deployment_authorised"])

    def test_no_position_does_not_count_as_approval(self):
        self.assign_required()
        self.wb.record_decision(self.case_id, gate="G2_MULTIDISCIPLINARY_REVIEW",
                                person_id="person-PRIVACY", role="PRIVACY",
                                authority_ref="delegation-PRIVACY", outcome="NO_POSITION",
                                rationale="Awaiting evidence", evidence_ids=[], actor="reviewer")
        self.assertIn("PRIVACY", self.wb.readiness(self.case_id)["review_roles_without_approval"])

    def test_decision_requires_assigned_person_and_authority(self):
        with self.assertRaisesRegex(ValueError, "matching role assignment"):
            self.wb.record_decision(self.case_id, gate="G2_MULTIDISCIPLINARY_REVIEW",
                                    person_id="unknown", role="PRIVACY", authority_ref="delegation-PRIVACY",
                                    outcome="APPROVE", rationale="No assignment", evidence_ids=[], actor="reviewer")

    def test_critical_gap_blocks_readiness(self):
        self.wb.add_gap(self.case_id, requirement_ref="POL-17", risk_scenario="Sensitive data disclosed",
                        severity="CRITICAL", owner_person_id="privacy-lead", actor="risk-lead")
        self.assertIn("OPEN_CRITICAL_RISK_GAPS", self.wb.readiness(self.case_id)["blockers"])

    def test_gap_closure_requires_linked_passing_evidence(self):
        gap = self.wb.add_gap(self.case_id, requirement_ref="POL-17", risk_scenario="Disclosure",
                              severity="HIGH", owner_person_id="privacy-lead", actor="risk-lead")
        ev = self.wb.add_evidence(self.case_id, evidence_type="privacy", subject_sha256=digest("subject"),
                                  content_sha256=digest("evidence"), state="NOT_VERIFIED",
                                  source_type="DOCUMENT", created_by="privacy-lead")
        with self.assertRaisesRegex(ValueError, "requires linked PASS"):
            self.wb.close_gap(self.case_id, gap["gap_id"], closure_evidence_id=ev["evidence_id"], actor="risk-lead")
        passed = self.wb.add_evidence(self.case_id, evidence_type="privacy", subject_sha256=digest("subject"),
                                      content_sha256=digest("evidence-pass"), state="PASS",
                                      source_type="TEST_RESULT", created_by="privacy-lead")
        self.assertEqual(self.wb.close_gap(self.case_id, gap["gap_id"],
                                           closure_evidence_id=passed["evidence_id"], actor="risk-lead")["status"], "CLOSED")

    def test_configuration_change_marks_evidence_stale(self):
        ev = self.wb.add_evidence(self.case_id, evidence_type="security", subject_sha256=digest("old"),
                                  content_sha256=digest("test"), state="PASS",
                                  source_type="TEST_RESULT", created_by="security")
        self.wb.update_configuration(self.case_id, model_config_sha256=digest("model-config-v2"),
                                     policy_sha256=digest("policy-v2"), actor="change-manager")
        self.assertEqual(self.wb.readiness(self.case_id)["stale_evidence_count"], 1)
        exported = self.wb.export_manifest(self.case_id)
        self.assertEqual(exported["records"]["evidence"][0]["state"], "STALE")

    def test_hash_chain_verifies_and_manifest_is_digest_bound(self):
        self.assign_required()
        self.wb.add_gap(self.case_id, requirement_ref="R-1", risk_scenario="Example",
                        severity="LOW", owner_person_id="risk-owner", actor="risk-owner")
        self.assertTrue(self.wb.verify_event_chain(self.case_id)["valid"])
        manifest = self.wb.export_manifest(self.case_id)
        self.assertEqual(len(manifest["integrity"]["manifest_sha256"]), 64)
        self.assertEqual(manifest["schema"], "ncs-workbench-case-manifest/0.1")

    def test_invalid_digest_rejected(self):
        with self.assertRaises(ValueError):
            self.wb.create_case(org_id="o", system_name="s", owner="x", intended_purpose="p",
                                model_config_sha256="not-a-digest")

    def test_readiness_never_claims_deployment_authority(self):
        self.approve_required()
        result = self.wb.readiness(self.case_id)
        self.assertEqual(result["blockers"], [])
        self.assertFalse(result["deployment_authorised"])
        self.assertFalse(result["technical_or_legal_compliance_claim"])


if __name__ == "__main__":
    unittest.main()
