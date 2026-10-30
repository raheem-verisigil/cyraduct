"""NCS Native Behavior Baseline protocol tests; no model provider is called."""
import pytest

from ncs_harness.native_baseline import (
    build_observation,
    get_probe,
    load_probe_pack,
    summarize_baseline,
)


PACK = load_probe_pack()
IDENTITY = {
    "provider": "synthetic-provider",
    "model_name": "synthetic-model",
    "model_version": "test-version-1",
    "artifact_digest": None,
}
PROBE = get_probe("NBB-001", PACK)


def make_observation(run_index=1, results=None, **overrides):
    results = results or {item: "pass" for item in PROBE["required_assertions"]}
    assertions = [
        {"assertion_id": assertion_id, "result": result, "rationale": "test rubric"}
        for assertion_id, result in results.items()
    ]
    args = {
        "assessment_id": "NCS-NBB-TEST-001",
        "probe_id": "NBB-001",
        "run_index": run_index,
        "raw_response": "Synthetic model response: three factual bullets.",
        "model_identity": IDENTITY,
        "system_prompt_sha256": "a" * 64,
        "temperature": 0,
        "tools_enabled": False,
        "evaluator_method": "human-reviewed",
        "evaluator_id": "reviewer-test-01",
        "rubric_version": "NBB-RUBRIC-0.1",
        "assertions": assertions,
        "pack": PACK,
    }
    args.update(overrides)
    return build_observation(**args)


def test_probe_pack_has_six_unique_dimensions_and_ids():
    assert len(PACK["probes"]) == 6
    assert len({probe["id"] for probe in PACK["probes"]}) == 6
    assert len({probe["dimension"] for probe in PACK["probes"]}) == 6


def test_observation_hashes_response_and_does_not_store_raw_text():
    raw = "private raw output example"
    record = make_observation(raw_response=raw)
    assert record["response_sha256"]
    assert raw not in str(record)
    assert record["grade_eligible"] is False
    assert record["execution_context"]["policy_context"] == "native-unmodified"


def test_missing_assertions_become_not_assessed_not_pass():
    record = make_observation(results={PROBE["required_assertions"][0]: "pass"})
    assert record["observation_status"] == "partially-observed"
    missing = [
        item for item in record["assertions"]
        if item["result"] == "not-assessed"
    ]
    assert missing


def test_failed_assertion_is_observed_failure():
    results = {item: "pass" for item in PROBE["required_assertions"]}
    results[PROBE["required_assertions"][0]] = "fail"
    record = make_observation(results=results)
    assert record["observation_status"] == "observed"
    assert any(item["result"] == "fail" for item in record["assertions"])


def test_v01_refuses_tool_enabled_runs():
    with pytest.raises(ValueError, match="tools_enabled=False"):
        make_observation(tools_enabled=True)


def test_unknown_assertions_are_rejected():
    with pytest.raises(ValueError, match="unknown assertion"):
        make_observation(results={"made_up_assertion": "pass"})


def test_duplicate_run_index_is_rejected():
    one = make_observation(run_index=1)
    two = make_observation(run_index=1)
    with pytest.raises(ValueError, match="duplicate run_index"):
        summarize_baseline([one, two], PACK)


def test_model_identity_change_requires_separate_assessment():
    one = make_observation(run_index=1)
    changed = dict(IDENTITY, model_version="test-version-2")
    two = make_observation(run_index=2, model_identity=changed)
    with pytest.raises(ValueError, match="model identity changed"):
        summarize_baseline([one, two], PACK)


def test_three_repeats_produce_repeatability_not_a_grade():
    runs = [make_observation(run_index=i) for i in (1, 2, 3)]
    summary = summarize_baseline(runs, PACK)
    first = next(item for item in summary["probe_results"] if item["probe_id"] == "NBB-001")
    assert first["probe_status"] == "repeatable-observations"
    assert first["assertions"][0]["stability"] == "consistently-observed-pass"
    assert summary["aggregate_score"] is None
    assert summary["grade_issued"] is False


def test_mixed_repeat_results_are_marked_variable():
    runs = []
    for index, result in enumerate(("pass", "fail", "pass"), start=1):
        results = {item: "pass" for item in PROBE["required_assertions"]}
        results[PROBE["required_assertions"][0]] = result
        runs.append(make_observation(run_index=index, results=results))
    summary = summarize_baseline(runs, PACK)
    first = next(item for item in summary["probe_results"] if item["probe_id"] == "NBB-001")
    assert first["probe_status"] == "variable"
    assert first["assertions"][0]["stability"] == "variable"


def test_missing_probe_is_not_reported_as_pass():
    summary = summarize_baseline([make_observation()], PACK)
    missing = next(item for item in summary["probe_results"] if item["probe_id"] == "NBB-002")
    assert missing["probe_status"] == "not-run"
    assert all(assertion["stability"] == "insufficient-repeats" for assertion in missing["assertions"])
