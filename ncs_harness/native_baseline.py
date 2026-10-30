"""NCS Native Behavior Baseline v0.1 — protocol and observation utilities.

This module does not call a model provider. It prepares exact probes, records
externally obtained raw-response digests plus independent evaluator assertions,
and summarizes repeatability without issuing a score or certificate.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PACK_PATH = Path(__file__).with_name("native-baseline-pack-0.1.json")
MIN_REPEATS = 3


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_probe_pack(path: str | Path = PACK_PATH) -> dict[str, Any]:
    pack = json.loads(Path(path).read_text(encoding="utf-8"))
    if pack.get("schema") != "ncs-native-behavior-probe-pack/0.1":
        raise ValueError("unsupported native baseline probe pack schema")
    ids = [probe["id"] for probe in pack.get("probes", [])]
    if len(ids) != len(set(ids)):
        raise ValueError("probe IDs must be unique")
    return pack


def get_probe(probe_id: str, pack: dict[str, Any] | None = None) -> dict[str, Any]:
    pack = pack or load_probe_pack()
    for probe in pack["probes"]:
        if probe["id"] == probe_id:
            return probe
    raise KeyError(f"unknown NCS native baseline probe: {probe_id}")


def build_observation(
    *,
    assessment_id: str,
    probe_id: str,
    run_index: int,
    raw_response: str,
    model_identity: dict[str, str | None],
    system_prompt_sha256: str | None,
    temperature: float | None,
    tools_enabled: bool,
    evaluator_method: str,
    evaluator_id: str | None,
    rubric_version: str,
    assertions: list[dict[str, str | None]],
    raw_response_ref: str | None = None,
    provider_request_id: str | None = None,
    pack: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create one observation. Raw response is hashed, never embedded."""
    if not assessment_id or run_index < 1 or not raw_response:
        raise ValueError("assessment_id, positive run_index and raw_response are required")
    if tools_enabled:
        raise ValueError("v0.1 native baseline probes require tools_enabled=False")
    if evaluator_method not in {"human-reviewed", "deterministic-check", "independent-model-assisted"}:
        raise ValueError("unsupported evaluator method")
    if not rubric_version:
        raise ValueError("rubric_version is required")

    probe = get_probe(probe_id, pack)
    required = set(probe["required_assertions"])
    received = set()
    normalized = []
    for assertion in assertions:
        assertion_id = assertion.get("assertion_id")
        result = assertion.get("result")
        if assertion_id not in required:
            raise ValueError(f"unknown assertion for {probe_id}: {assertion_id}")
        if assertion_id in received:
            raise ValueError(f"duplicate assertion: {assertion_id}")
        if result not in {"pass", "fail", "not-assessed"}:
            raise ValueError("assertion result must be pass, fail, or not-assessed")
        received.add(assertion_id)
        normalized.append({
            "assertion_id": assertion_id,
            "result": result,
            "rationale": assertion.get("rationale"),
        })

    missing = required - received
    for assertion_id in sorted(missing):
        normalized.append({
            "assertion_id": assertion_id,
            "result": "not-assessed",
            "rationale": "No evaluator observation supplied.",
        })

    results = [item["result"] for item in normalized]
    if all(result in {"pass", "fail"} for result in results):
        status = "observed"
    elif any(result in {"pass", "fail"} for result in results):
        status = "partially-observed"
    else:
        status = "not-assessed"

    identity = {
        "provider": model_identity.get("provider"),
        "model_name": model_identity.get("model_name"),
        "model_version": model_identity.get("model_version"),
        "artifact_digest": model_identity.get("artifact_digest"),
    }
    return {
        "schema_version": "0.1",
        "assessment_id": assessment_id,
        "probe_pack_id": (pack or load_probe_pack())["pack_id"],
        "probe_id": probe_id,
        "dimension": probe["dimension"],
        "run_index": run_index,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "model_identity": identity,
        "execution_context": {
            "system_prompt_sha256": system_prompt_sha256,
            "temperature": temperature,
            "tools_enabled": False,
            "policy_context": "native-unmodified",
            "provider_request_id": provider_request_id,
        },
        "prompt_sha256": sha256_text(probe["prompt"]),
        "response_sha256": sha256_text(raw_response),
        "raw_response_ref": raw_response_ref,
        "evaluator": {
            "method": evaluator_method,
            "evaluator_id": evaluator_id,
            "rubric_version": rubric_version,
        },
        "assertions": normalized,
        "observation_status": status,
        "limitations": [
            "A single observation is not a complete Native Behavior Baseline.",
            "The evaluator's assertions require independent review and versioned rubric governance.",
            "The response digest proves identity of supplied bytes only; it does not prove provider origin.",
            "This probe pack is experimental and does not establish universal safety or deployment fitness.",
        ],
        "grade_eligible": False,
    }


def summarize_baseline(
    observations: list[dict[str, Any]],
    pack: dict[str, Any] | None = None,
    minimum_repeats: int = MIN_REPEATS,
) -> dict[str, Any]:
    """Summarize per-probe repeatability; never compute an aggregate grade."""
    pack = pack or load_probe_pack()
    if minimum_repeats < 2:
        raise ValueError("minimum_repeats must be at least 2")
    if not observations:
        raise ValueError("at least one observation is required")

    assessment_ids = {item["assessment_id"] for item in observations}
    model_identities = {canonical_bytes(item["model_identity"]) for item in observations}
    contexts = {
        canonical_bytes({
            "system_prompt_sha256": item["execution_context"]["system_prompt_sha256"],
            "temperature": item["execution_context"]["temperature"],
            "tools_enabled": item["execution_context"]["tools_enabled"],
            "policy_context": item["execution_context"]["policy_context"],
        })
        for item in observations
    }
    if len(assessment_ids) != 1:
        raise ValueError("observations must belong to exactly one assessment")
    if len(model_identities) != 1:
        raise ValueError("model identity changed within assessment; split into separate assessments")
    if len(contexts) != 1:
        raise ValueError("execution context changed within assessment; split into separate assessments")

    by_probe: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in observations:
        probe = get_probe(item["probe_id"], pack)
        if item["probe_pack_id"] != pack["pack_id"] or item["dimension"] != probe["dimension"]:
            raise ValueError("observation does not match the selected probe pack")
        by_probe[item["probe_id"]].append(item)

    per_probe = []
    for probe in pack["probes"]:
        runs = by_probe.get(probe["id"], [])
        run_indices = [run["run_index"] for run in runs]
        if len(run_indices) != len(set(run_indices)):
            raise ValueError(f"duplicate run_index for {probe['id']}")
        assertion_runs: dict[str, list[str]] = defaultdict(list)
        for run in runs:
            for assertion in run["assertions"]:
                assertion_runs[assertion["assertion_id"]].append(assertion["result"])

        assertions = []
        for assertion_id in probe["required_assertions"]:
            results = assertion_runs.get(assertion_id, [])
            decisive = [result for result in results if result in {"pass", "fail"}]
            if len(runs) < minimum_repeats or len(decisive) < minimum_repeats:
                stability = "insufficient-repeats"
            elif len(set(decisive)) > 1:
                stability = "variable"
            elif decisive[0] == "pass":
                stability = "consistently-observed-pass"
            else:
                stability = "consistently-observed-fail"
            assertions.append({"assertion_id": assertion_id, "runs_observed": len(results), "stability": stability})

        per_probe.append({
            "probe_id": probe["id"],
            "dimension": probe["dimension"],
            "run_count": len(runs),
            "assertions": assertions,
            "probe_status": (
                "not-run" if not runs
                else "insufficient-repeats" if len(runs) < minimum_repeats
                else "variable" if any(a["stability"] == "variable" for a in assertions)
                else "repeatable-observations"
            ),
        })

    return {
        "report_schema": "ncs-native-baseline-summary/0.1",
        "assessment_id": next(iter(assessment_ids)),
        "probe_pack_id": pack["pack_id"],
        "model_identity": json.loads(next(iter(model_identities)).decode("utf-8")),
        "execution_context": json.loads(next(iter(contexts)).decode("utf-8")),
        "minimum_repeats": minimum_repeats,
        "probe_results": per_probe,
        "native_behavior_baseline": "experimental-observations-only",
        "aggregate_score": None,
        "grade_issued": False,
        "grade_eligible": False,
        "limitations": [
            "Only the listed probe dimensions and supplied observations are represented.",
            "Repeatability is not correctness, safety, robustness or deployment fitness.",
            "No deployer-specific policy delta is evaluated in this baseline summary.",
            "Missing or insufficient evidence is not a pass.",
        ],
    }
