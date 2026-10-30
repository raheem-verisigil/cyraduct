"""Paired NCS Policy Delta comparison; no model-provider calls or aggregate score."""
from __future__ import annotations
import hashlib, json
from collections import defaultdict
from typing import Any

def _canon(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")

def digest(value: Any) -> str:
    return hashlib.sha256(_canon(value)).hexdigest()

def build_policy_observation(*, baseline_observation: dict[str, Any], policy_pack_id: str, policy_version: str, policy_digest: str, policy_prompt_sha256: str, assertions: list[dict[str, str | None]], evaluator_method: str, evaluator_id: str | None, rubric_version: str) -> dict[str, Any]:
    """Attach an independently evaluated policy run to one exact baseline run."""
    if not policy_pack_id or not policy_version or len(policy_digest) != 64 or len(policy_prompt_sha256) != 64:
        raise ValueError("policy pack, version and SHA-256 digests are required")
    if evaluator_method not in {"human-reviewed", "deterministic-check", "independent-model-assisted"} or not rubric_version:
        raise ValueError("invalid evaluator provenance")
    if baseline_observation.get("execution_context", {}).get("policy_context") != "native-unmodified":
        raise ValueError("paired baseline must be native-unmodified")
    expected = {item["assertion_id"] for item in baseline_observation["assertions"]}
    supplied = {}
    for item in assertions:
        key, result = item.get("assertion_id"), item.get("result")
        if key not in expected or key in supplied:
            raise ValueError("unknown or duplicate policy assertion")
        if result not in {"pass", "fail", "not-assessed"}:
            raise ValueError("invalid policy assertion result")
        supplied[key] = {"assertion_id": key, "result": result, "rationale": item.get("rationale")}
    for key in expected - set(supplied):
        supplied[key] = {"assertion_id": key, "result": "not-assessed", "rationale": "No policy-run evaluation supplied."}
    return {
        "schema_version": "0.1",
        "assessment_id": baseline_observation["assessment_id"],
        "probe_pack_id": baseline_observation["probe_pack_id"],
        "probe_id": baseline_observation["probe_id"],
        "dimension": baseline_observation["dimension"],
        "run_index": baseline_observation["run_index"],
        "baseline_observation_sha256": digest(baseline_observation),
        "model_identity": baseline_observation["model_identity"],
        "prompt_sha256": baseline_observation["prompt_sha256"],
        "generation_context": {"temperature": baseline_observation["execution_context"]["temperature"], "tools_enabled": False},
        "policy_context": "policy-configured",
        "policy": {"pack_id": policy_pack_id, "version": policy_version, "digest": policy_digest, "policy_prompt_sha256": policy_prompt_sha256},
        "evaluator": {"method": evaluator_method, "evaluator_id": evaluator_id, "rubric_version": rubric_version},
        "assertions": [supplied[key] for key in sorted(supplied)],
        "grade_eligible": False,
    }

def compare_policy_delta(baseline_observations: list[dict[str, Any]], policy_observations: list[dict[str, Any]]) -> dict[str, Any]:
    """Pair exact runs and classify per-assertion directional changes."""
    if not baseline_observations or not policy_observations:
        raise ValueError("both native baseline and policy observations are required")
    baseline_map = {}
    for item in baseline_observations:
        key = (item["probe_id"], item["run_index"])
        if key in baseline_map: raise ValueError("duplicate native baseline probe/run pair")
        baseline_map[key] = item
    policy_map = {}
    for item in policy_observations:
        key = (item["probe_id"], item["run_index"])
        if key in policy_map: raise ValueError("duplicate policy probe/run pair")
        policy_map[key] = item
    if set(baseline_map) != set(policy_map):
        raise ValueError("baseline and policy runs must have identical probe/run coverage")
    model_ids = { _canon(x["model_identity"]) for x in baseline_observations + policy_observations }
    if len(model_ids) != 1: raise ValueError("model identity changed; cannot attribute delta to policy")
    policy_ids = {(x["policy"]["pack_id"], x["policy"]["version"], x["policy"]["digest"]) for x in policy_observations}
    if len(policy_ids) != 1: raise ValueError("policy identity changed within comparison")
    results = []
    counts = defaultdict(int)
    for key in sorted(baseline_map):
        base, configured = baseline_map[key], policy_map[key]
        if base["execution_context"]["policy_context"] != "native-unmodified" or configured["policy_context"] != "policy-configured":
            raise ValueError("incorrect baseline or policy context")
        if base["prompt_sha256"] != configured["prompt_sha256"]:
            raise ValueError("probe prompt changed; cannot attribute delta to policy")
        if base["execution_context"]["temperature"] != configured["generation_context"]["temperature"] or configured["generation_context"]["tools_enabled"] is not False:
            raise ValueError("generation settings changed; cannot attribute delta to policy")
        if configured["baseline_observation_sha256"] != digest(base):
            raise ValueError("policy observation is not bound to supplied baseline observation")
        b_assert = {x["assertion_id"]: x["result"] for x in base["assertions"]}
        p_assert = {x["assertion_id"]: x["result"] for x in configured["assertions"]}
        if set(b_assert) != set(p_assert): raise ValueError("assertion coverage changed")
        changes = []
        for assertion_id in sorted(b_assert):
            before, after = b_assert[assertion_id], p_assert[assertion_id]
            if "not-assessed" in {before, after}: classification = "unresolved"
            elif before == after: classification = "unchanged"
            elif before == "fail" and after == "pass": classification = "improved-observed"
            elif before == "pass" and after == "fail": classification = "regressed-observed"
            else: classification = "changed-unclassified"
            counts[classification] += 1
            changes.append({"assertion_id": assertion_id, "native_result": before, "policy_result": after, "classification": classification})
        results.append({"probe_id": key[0], "run_index": key[1], "dimension": base["dimension"], "baseline_observation_sha256": digest(base), "policy_observation_sha256": digest(configured), "assertion_changes": changes})
    return {"report_schema": "ncs-policy-delta-summary/0.1", "assessment_id": baseline_observations[0]["assessment_id"], "policy": {"pack_id": next(iter(policy_ids))[0], "version": next(iter(policy_ids))[1], "digest": next(iter(policy_ids))[2]}, "paired_run_count": len(results), "change_counts": dict(sorted(counts.items())), "paired_results": results, "aggregate_score": None, "effective_conduct_grade": None, "grade_issued": False, "grade_eligible": False, "limitations": ["Observed assertion changes do not prove the policy caused the change; provider nondeterminism and context effects remain possible.", "Comparisons require matched model identity, prompt, generation settings and run indices.", "Human-reviewed or validated independent evaluation is required for reliable interpretation.", "This report is not a Native Behavior Baseline, certification or deployment authorization."]}
