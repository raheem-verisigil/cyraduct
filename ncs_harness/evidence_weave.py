"""NCS Evidence Weave v0.1: bind evidence streams without blending their meaning."""
from __future__ import annotations
import hashlib, json
from typing import Any

def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")

def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()

def _assessment_id(item: dict[str, Any], stream: str) -> str:
    value = item.get("assessment_id")
    if not isinstance(value, str) or not value:
        raise ValueError(f"{stream} evidence must carry an assessment_id")
    return value

def _native_coverage(summary: dict[str, Any]) -> dict[str, Any]:
    probes = summary.get("probe_results")
    if not isinstance(probes, list) or not probes:
        return {"status": "not-observed", "probe_count": 0, "repeatable_probe_count": 0, "insufficient_probe_ids": []}
    repeatable = [p for p in probes if p.get("probe_status") == "repeatable-observations"]
    missing = [p.get("probe_id", "unknown") for p in probes if p.get("probe_status") != "repeatable-observations"]
    return {
        "status": "repeatable-for-declared-pack" if not missing else "partial-or-insufficient",
        "probe_count": len(probes),
        "repeatable_probe_count": len(repeatable),
        "insufficient_probe_ids": missing,
    }

def _policy_coverage(report: dict[str, Any]) -> dict[str, Any]:
    paired = report.get("paired_results")
    if not isinstance(paired, list) or not paired:
        return {"status": "not-observed", "paired_run_count": 0, "unresolved_assertion_count": None}
    unresolved = sum(
        1 for run in paired for change in run.get("assertion_changes", [])
        if change.get("classification") == "unresolved"
    )
    return {
        "status": "paired-observations-with-unresolved" if unresolved else "paired-observations-no-unresolved-assertions",
        "paired_run_count": len(paired),
        "unresolved_assertion_count": unresolved,
    }

def _application_coverage(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        return {"status": "not-observed", "record_count": 0, "consequence_observed_count": 0, "failed_record_count": 0, "partial_record_count": 0}
    consequence_count = 0
    failed_count = 0
    partial_count = 0
    for record in records:
        observation = record.get("observation") or {}
        consequence_observed = (
            observation.get("sink_invoked") is not None
            and observation.get("sink_state_before_sha256") is not None
            and observation.get("sink_state_after_sha256") is not None
        )
        consequence_count += int(consequence_observed)
        failed_count += int(record.get("evidence_status") == "failed")
        partial_count += int(record.get("evidence_status") in {"partially-verified", "not-observable", "not-run"})
    status = "observed-with-failures" if failed_count else "observed-with-gaps" if partial_count or consequence_count < len(records) else "observed-for-supplied-records"
    return {"status": status, "record_count": len(records), "consequence_observed_count": consequence_count, "failed_record_count": failed_count, "partial_record_count": partial_count}

def build_evidence_weave(*, assessment_id: str, native_baseline: dict[str, Any] | None, policy_delta: dict[str, Any] | None, application_records: list[dict[str, Any]] | None = None, declared_scope: dict[str, Any] | None = None) -> dict[str, Any]:
    """Bind evidence streams by digest and report coverage; never issue a grade."""
    if not assessment_id:
        raise ValueError("assessment_id is required")
    application_records = application_records or []
    components = []
    if native_baseline is not None:
        if _assessment_id(native_baseline, "native baseline") != assessment_id:
            raise ValueError("native baseline assessment_id mismatch")
        if native_baseline.get("report_schema") != "ncs-native-baseline-summary/0.1":
            raise ValueError("unsupported native baseline summary schema")
        if native_baseline.get("grade_issued") is not False:
            raise ValueError("native baseline summary must not issue a grade")
        components.append({"stream": "native-behavior-baseline", "sha256": sha256_json(native_baseline), "coverage": _native_coverage(native_baseline)})
    else:
        components.append({"stream": "native-behavior-baseline", "sha256": None, "coverage": {"status": "not-supplied"}})
    if policy_delta is not None:
        if _assessment_id(policy_delta, "policy delta") != assessment_id:
            raise ValueError("policy delta assessment_id mismatch")
        if policy_delta.get("report_schema") != "ncs-policy-delta-summary/0.1":
            raise ValueError("unsupported policy delta summary schema")
        if policy_delta.get("grade_issued") is not False:
            raise ValueError("policy delta summary must not issue a grade")
        components.append({"stream": "policy-delta", "sha256": sha256_json(policy_delta), "coverage": _policy_coverage(policy_delta)})
    else:
        components.append({"stream": "policy-delta", "sha256": None, "coverage": {"status": "not-supplied"}})
    for record in application_records:
        if _assessment_id(record, "application") != assessment_id:
            raise ValueError("application evidence assessment_id mismatch")
        if record.get("grade_eligible") is not False:
            raise ValueError("application evidence must not be marked grade eligible")
    app_coverage = _application_coverage(application_records)
    components.append({"stream": "application-control-and-consequence", "sha256": sha256_json(application_records) if application_records else None, "coverage": app_coverage})
    supplied_count = sum(1 for component in components if component["sha256"] is not None)
    missing_streams = [component["stream"] for component in components if component["sha256"] is None]
    weave = {
        "report_schema": "ncs-evidence-weave/0.1",
        "assessment_id": assessment_id,
        "created_for": "evidence-integrity-and-coverage-only",
        "declared_scope": declared_scope or {},
        "components": components,
        "stream_count": len(components),
        "supplied_stream_count": supplied_count,
        "missing_streams": missing_streams,
        "weave_status": "incomplete" if missing_streams else "assembled-needs-review",
        "cross_stream_binding": "assessment-id-and-content-digest",
        "grade_compiler_input": False,
        "grade_issued": False,
        "grade_eligible": False,
        "limitations": [
            "A digest binds supplied content but does not authenticate the source that produced it.",
            "Assessment ID equality does not prove that model, policy and application runs occurred in one controlled environment.",
            "Application-control evidence is not a substitute for Native Behavior Baseline evidence.",
            "Repeatable observations are not proof of correctness, safety or deployment fitness.",
            "Completeness is limited to the supplied declared scope; this weave is not a proof of global evidence completeness.",
            "No NCS grade, certificate or deployment authorization is produced.",
        ],
    }
    weave["weave_sha256"] = sha256_json(weave)
    return weave

def verify_evidence_weave(weave: dict[str, Any]) -> tuple[bool, str]:
    """Verify the weave envelope digest; this does not authenticate source evidence."""
    claimed = weave.get("weave_sha256")
    if not isinstance(claimed, str) or len(claimed) != 64:
        return False, "missing_or_malformed_weave_digest"
    unsigned = dict(weave)
    unsigned.pop("weave_sha256", None)
    actual = sha256_json(unsigned)
    if actual != claimed:
        return False, "weave_digest_mismatch"
    return True, actual

