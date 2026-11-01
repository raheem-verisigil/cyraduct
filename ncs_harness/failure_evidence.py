"""NCS Failure Evidence and Modification Rule Engine (experimental v0.1).

Consumes privacy-minimized observability events. It does not replace tracing,
detect failures on its own, execute containment, mutate certificates, or
authorize production return. Source telemetry is a signal until independently
adjudicated and bound to an exact model artifact.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any

HEX64 = re.compile(r"^[0-9a-f]{64}$")
CATEGORIES = {"safety", "privacy", "tool_misuse", "retrieval", "hallucination", "drift", "reliability", "policy_violation", "other"}
SEVERITIES = {"info", "low", "medium", "high", "critical"}
SIGNAL_KINDS = {"hard_error", "soft_failure", "silent_failure"}
EVENT_STATUSES = {"suspected", "observed", "confirmed", "refuted"}
SOURCE_INTEGRITY = {"unverified", "authenticated", "signed"}
CONTENT_MODES = {"none", "redacted", "reference_only"}


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _digest(value: Any, field: str) -> str:
    if not isinstance(value, str) or not HEX64.fullmatch(value):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _timestamp(value: str, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")
    return value


def normalize_observability_event(
    *, event_id: str, observed_at: str, source: dict[str, Any],
    subject: dict[str, Any], failure: dict[str, Any], evidence: dict[str, Any],
    source_integrity: str = "unverified", content_mode: str = "none",
    assessment_id: str | None = None, build_record_digest: str | None = None,
    certificate_id: str | None = None,
) -> dict[str, Any]:
    """Validate and normalize one provider-neutral failure signal.

    Raw prompts, completions, tool arguments/results and exception payloads are
    intentionally rejected. Store them only in an access-controlled evidence
    vault and reference them by digest and opaque URI.
    """
    if not isinstance(event_id, str) or not event_id.strip():
        raise ValueError("event_id is required")
    _timestamp(observed_at, "observed_at")
    if not isinstance(source, dict) or not source.get("integration") or not source.get("event_type"):
        raise ValueError("source.integration and source.event_type are required")
    if not isinstance(subject, dict):
        raise ValueError("subject is required")
    artifact_digest = _digest(subject.get("artifact_digest"), "subject.artifact_digest")
    if not isinstance(failure, dict):
        raise ValueError("failure is required")
    category, severity = failure.get("category"), failure.get("severity")
    signal_kind, status = failure.get("signal_kind"), failure.get("status", "observed")
    if category not in CATEGORIES:
        raise ValueError("failure.category is not in the NCS failure taxonomy")
    if severity not in SEVERITIES or signal_kind not in SIGNAL_KINDS or status not in EVENT_STATUSES:
        raise ValueError("invalid failure severity, signal_kind, or status")
    if not isinstance(evidence, dict):
        raise ValueError("evidence is required")
    payload_digest = _digest(evidence.get("payload_digest"), "evidence.payload_digest")
    if source_integrity not in SOURCE_INTEGRITY or content_mode not in CONTENT_MODES:
        raise ValueError("invalid source_integrity or content_mode")
    refs = evidence.get("evidence_refs", [])
    if not isinstance(refs, list) or any(not isinstance(x, dict) or not x.get("kind") or not x.get("uri") for x in refs):
        raise ValueError("evidence_refs must contain kind and opaque uri")
    for ref in refs:
        _digest(ref.get("sha256"), "evidence_refs.sha256")
    if build_record_digest is not None:
        _digest(build_record_digest, "build_record_digest")
    confidence = failure.get("confidence")
    if confidence is not None and (not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1):
        raise ValueError("failure.confidence must be between 0 and 1")

    return {
        "schema": "ncs-failure-evidence/0.1",
        "event_id": event_id.strip(),
        "observed_at": observed_at,
        "source": {
            "integration": str(source["integration"]), "event_type": str(source["event_type"]),
            "source_event_id": source.get("source_event_id"), "trace_id": source.get("trace_id"),
            "span_id": source.get("span_id"), "service_name": source.get("service_name"),
        },
        "subject": {
            "artifact_digest": artifact_digest, "provider": subject.get("provider"),
            "model_name": subject.get("model_name"), "model_version": subject.get("model_version"),
            "deployment_id": subject.get("deployment_id"), "environment": subject.get("environment"),
        },
        "failure": {
            "category": category, "severity": severity, "signal_kind": signal_kind,
            "status": status, "detector": failure.get("detector"),
            "detector_version": failure.get("detector_version"), "confidence": confidence,
            "error_type": failure.get("error_type"), "rule_or_eval_id": failure.get("rule_or_eval_id"),
            "summary_code": failure.get("summary_code"),
        },
        "evidence": {"payload_digest": payload_digest, "evidence_refs": refs, "content_mode": content_mode},
        "source_integrity": source_integrity,
        "correlation": {
            "assessment_id": assessment_id, "build_record_digest": build_record_digest,
            "certificate_id": certificate_id,
        },
        "grade_eligible": False,
    }


def normalize_otel_event(event: dict[str, Any], *, artifact_digest: str, integration: str = "opentelemetry") -> dict[str, Any]:
    """Conservative mapper for OTel GenAI exception/span events.

    OTel is the transport vocabulary. It does not establish NCS failure
    classification unless an explicit ncs.failure.category is supplied.
    """
    attrs = event.get("attributes") or {}
    name = event.get("name") or event.get("event_name") or "unknown"
    explicit_category = attrs.get("ncs.failure.category")
    error_type = attrs.get("error.type") or attrs.get("exception.type")
    span_status = str(attrs.get("otel.status_code", attrs.get("status", ""))).upper()
    is_error = bool(error_type) or "EXCEPTION" in str(name).upper() or span_status in {"ERROR", "2"}
    category = explicit_category if explicit_category in CATEGORIES else "reliability"
    signal_kind = "hard_error" if is_error else "soft_failure"
    severity = str(attrs.get("ncs.failure.severity", "medium")).lower()
    status = str(attrs.get("ncs.failure.status", "observed")).lower()
    observed_at = event.get("observed_at") or event.get("timestamp")
    if not observed_at:
        raise ValueError("observability event requires observed_at/timestamp")
    evidence_digest = attrs.get("ncs.evidence.payload_sha256") or sha256_json({
        "event_name": name, "error_type": error_type,
        "trace_id": event.get("trace_id"), "span_id": event.get("span_id"),
    })
    return normalize_observability_event(
        event_id=str(event.get("event_id") or event.get("id") or sha256_json(event)),
        observed_at=observed_at,
        source={
            "integration": integration, "event_type": name, "source_event_id": event.get("id"),
            "trace_id": event.get("trace_id"), "span_id": event.get("span_id"),
            "service_name": attrs.get("service.name"),
        },
        subject={
            "artifact_digest": artifact_digest, "provider": attrs.get("gen_ai.provider.name") or attrs.get("gen_ai.system"),
            "model_name": attrs.get("gen_ai.request.model") or attrs.get("gen_ai.response.model"),
            "model_version": attrs.get("gen_ai.response.model.version"),
            "deployment_id": attrs.get("service.instance.id"),
            "environment": attrs.get("deployment.environment.name"),
        },
        failure={
            "category": category, "severity": severity, "signal_kind": signal_kind, "status": status,
            "error_type": error_type, "detector": "opentelemetry-attribute-mapper",
            "detector_version": "0.1", "summary_code": "otel_error_signal" if is_error else "otel_observation",
        },
        evidence={"payload_digest": evidence_digest, "evidence_refs": []},
        source_integrity="unverified", content_mode="none",
    )


def evaluate_modification_rule(event: dict[str, Any]) -> dict[str, Any]:
    """Return a deterministic, non-executing response recommendation."""
    if event.get("schema") != "ncs-failure-evidence/0.1":
        raise ValueError("unsupported failure evidence schema")
    failure = event["failure"]
    category, severity, status = failure["category"], failure["severity"], failure["status"]
    integrity = event["source_integrity"]
    confirmed = status == "confirmed" and integrity in {"authenticated", "signed"}
    urgent = severity in {"high", "critical"}
    sensitive_category = category in {"safety", "privacy", "tool_misuse", "policy_violation"}
    if status == "refuted":
        rule_id, review, containment, scope = "NCS-FMR-REFUTED-001", "close-after-human-review", "none", "no-reassessment-unless-correlated-evidence"
    elif not confirmed:
        rule_id, review, containment, scope = "NCS-FMR-UNVERIFIED-001", "human-triage-required", "consider-temporary-containment", "evidence-validation-before-reassessment"
    elif urgent and sensitive_category:
        rule_id, review, containment, scope = "NCS-FMR-CONTAIN-001", "priority-human-review", "containment-recommended-not-executed", "targeted-reassessment-and-change-impact-review"
    elif urgent:
        rule_id, review, containment, scope = "NCS-FMR-REASSESS-001", "priority-human-review", "assess-operational-impact", "targeted-reassessment"
    else:
        rule_id, review, containment, scope = "NCS-FMR-OBSERVE-001", "scheduled-human-review", "none", "trend-review-and-evaluation-update"
    return {
        "schema": "ncs-modification-rule-decision/0.1", "rule_id": rule_id, "rule_version": "0.1",
        "event_id": event["event_id"], "event_digest": sha256_json(event),
        "subject_artifact_digest": event["subject"]["artifact_digest"],
        "decision_status": "recommendation-only",
        "evidence_preservation": "preserve-source-event-and-provenance",
        "notification": "notify-designated-governance-owner" if urgent else "record-in-governance-queue",
        "human_review": review, "containment": containment, "reassessment_scope": scope,
        "certificate_action": "NO_AUTOMATIC_CERTIFICATE_MUTATION",
        "return_to_production": "requires-separate-authorized-review-and-current-evidence",
        "execution_performed": False, "grade_eligible": False,
    }


def build_failure_case(event: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    """Bind one signal to its rule decision; no grade or certificate state change."""
    if decision.get("event_digest") != sha256_json(event) or decision.get("event_id") != event.get("event_id"):
        raise ValueError("decision does not bind to supplied failure event")
    case = {
        "schema": "ncs-failure-case/0.1",
        "case_id": "NCS-FC-" + sha256_json({"event_id": event["event_id"], "artifact": event["subject"]["artifact_digest"]})[:20],
        "event": event, "modification_rule": decision, "case_status": "OPEN_REVIEW",
        "certificate_status_change": "NONE", "grade_issued": False,
        "certificate_issued": False, "deployment_authorized": False,
    }
    case["case_digest"] = sha256_json(case)
    return case


def verify_failure_case(case: dict[str, Any]) -> tuple[bool, str]:
    if not isinstance(case, dict) or case.get("schema") != "ncs-failure-case/0.1":
        return False, "unsupported_case_schema"
    supplied = case.get("case_digest")
    unsigned = dict(case)
    unsigned.pop("case_digest", None)
    if supplied != sha256_json(unsigned):
        return False, "case_digest_mismatch"
    if case.get("grade_issued") is not False or case.get("certificate_issued") is not False:
        return False, "invalid_grade_or_certificate_claim"
    if case.get("certificate_status_change") != "NONE":
        return False, "automatic_certificate_mutation_not_permitted"
    return True, "valid"
