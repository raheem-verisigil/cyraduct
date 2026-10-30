"""NCS Certificate Lifecycle and Change Impact prototype v0.1.

This module prepares a non-issuable certificate candidate and calculates
reassessment scope after a declared change. It does not sign, issue, revoke,
or publish certificates. A production implementation requires authenticated
Build Records, a governed issuer, signing-key custody, trusted time and a
public transparency/revocation mechanism.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .evidence_weave import sha256_json, verify_evidence_weave

HEX = set("0123456789abcdef")

# Changes are classified by what evidence they can invalidate. These are
# conservative v0.1 defaults; a governed NCS change taxonomy must supersede
# them before production certification.
CHANGE_RULES: dict[str, dict[str, Any]] = {
    "model_weights": {"streams": ["native-behavior-baseline", "policy-delta"], "dimensions": ["all"], "scope": "full-native-and-derived-reassessment"},
    "base_model": {"streams": ["native-behavior-baseline", "policy-delta"], "dimensions": ["all"], "scope": "full-native-and-derived-reassessment"},
    "adapter_or_lora": {"streams": ["native-behavior-baseline", "policy-delta"], "dimensions": ["all"], "scope": "full-native-and-derived-reassessment"},
    "tokenizer": {"streams": ["native-behavior-baseline", "policy-delta"], "dimensions": ["all"], "scope": "full-native-and-derived-reassessment"},
    "quantization": {"streams": ["native-behavior-baseline", "policy-delta"], "dimensions": ["all"], "scope": "full-native-and-derived-reassessment"},
    "model_version": {"streams": ["native-behavior-baseline", "policy-delta"], "dimensions": ["all"], "scope": "full-native-and-derived-reassessment"},
    "system_prompt": {"streams": ["native-behavior-baseline", "policy-delta"], "dimensions": ["all"], "scope": "native-context-and-derived-reassessment"},
    "inference_runtime": {"streams": ["native-behavior-baseline", "policy-delta"], "dimensions": ["all"], "scope": "native-runtime-and-derived-reassessment"},
    "generation_configuration": {"streams": ["native-behavior-baseline", "policy-delta"], "dimensions": ["all"], "scope": "native-configuration-and-derived-reassessment"},
    "policy_pack": {"streams": ["policy-delta"], "dimensions": ["policy-defined"], "scope": "policy-delta-and-fit-reassessment"},
    "policy_prompt": {"streams": ["policy-delta"], "dimensions": ["policy-defined"], "scope": "policy-delta-and-fit-reassessment"},
    "policy_requirements": {"streams": ["policy-delta"], "dimensions": ["policy-defined"], "scope": "policy-fit-reassessment"},
    "tool_permissions": {"streams": ["application-control-and-consequence"], "dimensions": ["application-defined"], "scope": "application-integration-reassessment"},
    "connector_code": {"streams": ["application-control-and-consequence"], "dimensions": ["application-defined"], "scope": "application-integration-reassessment"},
    "sink_adapter": {"streams": ["application-control-and-consequence"], "dimensions": ["application-defined"], "scope": "application-consequence-reassessment"},
    "evaluator_rubric": {"streams": ["native-behavior-baseline", "policy-delta"], "dimensions": ["affected-assertions"], "scope": "re-evaluation-required"},
    "probe_pack": {"streams": ["native-behavior-baseline", "policy-delta"], "dimensions": ["all"], "scope": "probe-pack-reassessment"},
    "build_record": {"streams": ["native-behavior-baseline", "policy-delta"], "dimensions": ["all"], "scope": "provenance-review-and-reassessment"},
}


def _sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def _valid_digest(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in HEX for ch in value)


def build_certificate_candidate(
    *,
    evidence_weave: dict[str, Any],
    capability_profile: dict[str, Any],
    build_record: dict[str, Any] | None,
    requested_validity_days: int = 90,
) -> dict[str, Any]:
    """Create a certificate candidate envelope; issuance remains disabled."""
    if requested_validity_days < 1 or requested_validity_days > 365:
        raise ValueError("requested validity must be between 1 and 365 days")
    blockers: list[str] = []
    if capability_profile.get("assessment_id") != evidence_weave.get("assessment_id"):
        raise ValueError("capability profile and evidence weave assessment IDs differ")
    valid_weave, weave_reason = verify_evidence_weave(evidence_weave)
    if not valid_weave:
        blockers.append("evidence_weave_invalid:" + weave_reason)
    if evidence_weave.get("weave_status") != "assembled-needs-review":
        blockers.append("evidence_weave_incomplete")
    if capability_profile.get("grade_issued") is not False or capability_profile.get("certificate_issued") is not False:
        blockers.append("capability_profile_must_not_claim_grade_or_certificate")
    if capability_profile.get("global_evidence_ceiling") != "EXPERIMENTAL_NOT_GRADEABLE":
        blockers.append("experimental_grade_ceiling_missing")

    model_identity = capability_profile.get("model_identity") or {}
    artifact_digest = model_identity.get("artifact_digest")
    if not _valid_digest(artifact_digest):
        blockers.append("exact_model_artifact_digest_missing_or_unverified")

    build_record_digest = None
    if not isinstance(build_record, dict):
        blockers.append("build_record_missing")
    else:
        build_record_digest = build_record.get("record_digest")
        if not _valid_digest(build_record_digest):
            blockers.append("build_record_digest_missing_or_invalid")
        if build_record.get("artifact_digest") != artifact_digest or not _valid_digest(artifact_digest):
            blockers.append("build_record_artifact_binding_mismatch")
        if build_record.get("signature_status") != "verified":
            blockers.append("build_record_signature_not_verified")
        if build_record.get("completeness_status") != "verified":
            blockers.append("build_record_completeness_not_verified")

    blockers.extend([
        "issuer_signing_and_key_custody_not_implemented",
        "trusted_time_and_expiry_service_not_implemented",
        "external_transparency_log_and_revocation_service_not_implemented",
        "NCS_probe_construct_validity_and_grade_thresholds_not_independently_validated",
        "independent_assessor_review_not_recorded",
    ])

    candidate = {
        "schema_version": "0.1",
        "record_type": "ncs-certificate-candidate",
        "certificate_status": "NOT_ISSUED",
        "certificate_id": None,
        "assessment_id": evidence_weave["assessment_id"],
        "subject": {
            "provider": model_identity.get("provider"),
            "model_name": model_identity.get("model_name"),
            "model_version": model_identity.get("model_version"),
            "artifact_digest": artifact_digest if _valid_digest(artifact_digest) else None,
        },
        "build_record_digest": build_record_digest if _valid_digest(build_record_digest) else None,
        "evidence": {
            "evidence_weave_sha256": _sha256(evidence_weave),
            "capability_profile_sha256": _sha256(capability_profile),
        },
        "requested_validity_days": requested_validity_days,
        "issued_at": None,
        "expires_at": None,
        "blockers": sorted(set(blockers)),
        "issuance_eligible": False,
        "signature": None,
        "transparency_log_entry": None,
        "revocation_status": "NOT_APPLICABLE_NOT_ISSUED",
    }
    candidate["candidate_sha256"] = _sha256(candidate)
    return candidate


def assess_change_impact(
    *,
    certificate_record: dict[str, Any],
    change_event: dict[str, Any],
) -> dict[str, Any]:
    """Calculate conservative reassessment scope for one declared change."""
    change_type = change_event.get("change_type")
    if change_type not in CHANGE_RULES:
        raise ValueError("unknown change type; classify and review before proceeding")
    old_digest = change_event.get("old_digest")
    new_digest = change_event.get("new_digest")
    if not _valid_digest(old_digest) or not _valid_digest(new_digest):
        raise ValueError("change event requires valid old_digest and new_digest")
    if old_digest == new_digest:
        raise ValueError("change event digests are identical; no material change demonstrated")
    if not change_event.get("event_id") or not change_event.get("occurred_at"):
        raise ValueError("change event_id and occurred_at are required")

    rule = CHANGE_RULES[change_type]
    cert_status = certificate_record.get("certificate_status", "UNKNOWN")
    if cert_status == "ISSUED":
        action = "SUSPEND_OR_REVOKE_PENDING_REASSESSMENT"
    elif cert_status == "NOT_ISSUED":
        action = "NO_ACTIVE_CERTIFICATE; CANDIDATE_REASSESSMENT_REQUIRED"
    else:
        action = "CERTIFICATE_STATUS_UNRESOLVED; MANUAL_REVIEW_REQUIRED"

    result = {
        "schema_version": "0.1",
        "record_type": "ncs-change-impact-assessment",
        "event_id": change_event["event_id"],
        "occurred_at": change_event["occurred_at"],
        "change_type": change_type,
        "old_digest": old_digest,
        "new_digest": new_digest,
        "affected_evidence_streams": rule["streams"],
        "affected_dimensions": rule["dimensions"],
        "reassessment_scope": rule["scope"],
        "certificate_action_recommendation": action,
        "certificate_mutated": False,
        "automated_revocation_performed": False,
        "requires_assessor_review": True,
        "change_event_source": change_event.get("source"),
        "limitations": [
            "Impact rules are conservative experimental defaults, not a finalized normative NCS change taxonomy.",
            "The engine does not establish that the supplied change event is authentic.",
            "No certificate is automatically suspended, revoked, reissued or renewed.",
            "Unknown changes are rejected for manual classification rather than assumed harmless.",
        ],
    }
    result["impact_sha256"] = _sha256(result)
    return result


def verify_change_impact(record: dict[str, Any]) -> tuple[bool, str]:
    claimed = record.get("impact_sha256")
    if not _valid_digest(claimed):
        return False, "missing_or_malformed_impact_digest"
    unsigned = dict(record)
    unsigned.pop("impact_sha256", None)
    actual = _sha256(unsigned)
    return (True, actual) if actual == claimed else (False, "impact_digest_mismatch")
