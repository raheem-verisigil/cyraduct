"""Create provenance-bound NCS evidence records for isolated assessments.

This module records observed application behaviour. It does not evaluate model
native conduct, issue grades, or assert that an unobserved consequence did not
occur. Raw request/response bodies are never written to the evidence record.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def _require_commit(commit_sha: str) -> str:
    if not isinstance(commit_sha, str) or len(commit_sha) != 40:
        raise ValueError("commit_sha must be an exact 40-character Git commit SHA")
    if any(c not in "0123456789abcdef" for c in commit_sha):
        raise ValueError("commit_sha must be lowercase hexadecimal")
    return commit_sha


def _decision(value: Any) -> str:
    if value not in {"allow", "deny", "conditional", "error", "not-observed"}:
        return "not-observed"
    return value


def build_evidence_record(
    *,
    assessment_id: str,
    scenario_id: str,
    repository: str,
    commit_sha: str,
    component: str,
    input_payload: Any,
    application_decision: str | None,
    expected_decision: str,
    assertions: list[dict[str, Any]],
    environment_mode: str = "local-isolated",
    external_side_effects: str = "disabled",
    synthetic_data: bool = True,
    policy_pack: str | None = None,
    policy_version: str | None = None,
    policy_digest: str | None = None,
    receipt_id: str | None = None,
    receipt_signature_valid: bool | None = None,
    receipt_action_binding_valid: bool | None = None,
    sink_invoked: bool | None = None,
    sink_state_before: Any = None,
    sink_state_after: Any = None,
    evidence_refs: list[dict[str, str]] | None = None,
    limitations: list[str] | None = None,
    agent_under_test: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one evidence record using explicit, caller-supplied observations.

    The caller must pass None for any property that was not actually observed.
    In particular, sink_invoked=None means unknown, not False.
    """
    if not assessment_id or not scenario_id or not component:
        raise ValueError("assessment_id, scenario_id, and component are required")
    if not repository.startswith("https://"):
        raise ValueError("repository must be an HTTPS repository URL")
    commit_sha = _require_commit(commit_sha)
    if synthetic_data is not True:
        raise ValueError("NCS pilot collector requires synthetic_data=True")
    if environment_mode not in {"local-isolated", "disposable-test", "staging-approved"}:
        raise ValueError("unsupported assessment environment")
    if external_side_effects not in {"disabled", "mocked", "explicitly-approved"}:
        raise ValueError("unsupported external_side_effects value")
    if expected_decision not in {"allow", "deny", "conditional", "not-defined"}:
        raise ValueError("unsupported expected_decision")

    observed = _decision(application_decision)
    normalized_assertions = []
    for assertion in assertions:
        result = assertion.get("result")
        if result not in {"pass", "fail", "not-run", "not-observable"}:
            raise ValueError("assertion result must be explicit")
        if not assertion.get("assertion_id"):
            raise ValueError("assertion_id is required")
        normalized_assertions.append({
            "assertion_id": str(assertion["assertion_id"]),
            "result": result,
            "detail": assertion.get("detail"),
        })

    results = [a["result"] for a in normalized_assertions]
    if not results or all(r == "not-run" for r in results):
        status = "not-run"
    elif "fail" in results:
        status = "failed"
    elif "not-observable" in results or observed == "not-observed":
        status = "partially-verified"
    elif all(r == "pass" for r in results):
        status = "verified"
    else:
        status = "partially-verified"

    policy_delta = None
    if policy_pack is not None:
        policy_delta = {
            "policy_pack": policy_pack,
            "policy_version": policy_version,
            "policy_digest": policy_digest,
            "policy_source": "Cyraduct policy pack",
        }

    record = {
        "schema_version": "0.1",
        "assessment_id": assessment_id,
        "scenario_id": scenario_id,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "target": {
            "product": "Cyraduct Finance Guard",
            "repository": repository,
            "commit_sha": commit_sha,
            "component": component,
        },
        "agent_under_test": agent_under_test,
        "environment": {
            "mode": environment_mode,
            "synthetic_data": True,
            "external_side_effects": external_side_effects,
            "runtime": os.environ.get("PYTHON_VERSION"),
            "dependency_lock_digest": None,
        },
        "policy_delta": policy_delta,
        "input": {"sha256": sha256_json(input_payload), "redacted_excerpt": None},
        "observation": {
            "application_decision": observed,
            "expected_decision": expected_decision,
            "receipt_id": receipt_id,
            "receipt_signature_valid": receipt_signature_valid,
            "receipt_action_binding_valid": receipt_action_binding_valid,
            "sink_invoked": sink_invoked,
            "sink_state_before_sha256": sha256_json(sink_state_before) if sink_state_before is not None else None,
            "sink_state_after_sha256": sha256_json(sink_state_after) if sink_state_after is not None else None,
            "assertions": normalized_assertions,
        },
        "evidence_status": status,
        "evidence_refs": evidence_refs or [],
        "limitations": limitations or [
            "Application-control evidence only; Native Behavior Baseline not assessed.",
            "No NCS grade or certificate is produced by this collector.",
        ],
        "native_behavior_baseline": "not-assessed",
        "grade_eligible": False,
    }
    return record


def append_hash_chained_record(path: str | Path, record: dict[str, Any]) -> dict[str, Any]:
    """Append an envelope to a JSONL ledger, chaining to the prior envelope.

    This is tamper-evident only relative to a protected prior hash/checkpoint.
    A local writable JSONL file alone is not an independently trusted
    transparency log or proof of completeness.
    """
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    previous_hash = None
    if destination.exists() and destination.stat().st_size:
        last_line = destination.read_text(encoding="utf-8").splitlines()[-1]
        previous = json.loads(last_line)
        previous_hash = previous["record_hash"]

    envelope = {
        "previous_record_hash": previous_hash,
        "record": record,
    }
    envelope["record_hash"] = sha256_json(envelope)
    with destination.open("a", encoding="utf-8") as stream:
        stream.write(canonical_json_bytes(envelope).decode("utf-8") + "\n")
    return envelope


def verify_hash_chain(path: str | Path) -> tuple[bool, str]:
    """Verify local envelope hashes and previous-hash links."""
    previous_hash = None
    destination = Path(path)
    if not destination.exists():
        return False, "ledger_not_found"
    for line_number, line in enumerate(destination.read_text(encoding="utf-8").splitlines(), 1):
        try:
            envelope = json.loads(line)
            claimed_hash = envelope.pop("record_hash")
            if envelope.get("previous_record_hash") != previous_hash:
                return False, f"previous_hash_mismatch_at_line_{line_number}"
            actual_hash = sha256_json(envelope)
            if actual_hash != claimed_hash:
                return False, f"record_hash_mismatch_at_line_{line_number}"
            previous_hash = claimed_hash
        except (ValueError, KeyError, TypeError):
            return False, f"malformed_record_at_line_{line_number}"
    return True, previous_hash or "empty_ledger"
