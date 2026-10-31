from ncs_harness.week2_runner.runner import TestCase, run_assessment


class StubAdapter:
    adapter_id = "test-stub/1"

    def invoke(self, *, input_text, system_context=None):
        if input_text == "explode":
            raise RuntimeError("provider failure with secret-like content")
        return "safe-answer:" + input_text


def test_runner_records_outcomes_without_raw_inputs_or_outputs():
    adapter = StubAdapter()
    cases = [
        TestCase("case-1", "hello", lambda output: "PASS" if output.endswith("hello") else "FAIL", dimension="privacy"),
        TestCase("case-2", "explode", lambda output: "PASS", dimension="tool-use"),
        TestCase("case-3", "", lambda output: "PASS", dimension="scope"),
    ]
    manifest = run_assessment(
        adapter=adapter,
        cases=cases,
        model_configuration_sha256="a" * 64,
        suite_version="ncs-testpack/0.1",
        assessment_mode="NATIVE_BASELINE",
        run_id="run-001",
        source_commit="b" * 40,
        recorded_at="2026-10-31T00:00:00Z",
    )
    assert manifest["summary"] == {"PASS": 1, "FAIL": 0, "INDETERMINATE": 1, "NOT_TESTED": 1}
    rendered = str(manifest)
    assert "hello" not in rendered
    assert "safe-answer" not in rendered
    assert "secret-like" not in rendered
    assert len(manifest["results"][0]["output_sha256"]) == 64
    assert manifest["results"][1]["reason"] == "RuntimeError"


def test_runner_rejects_bad_identity_and_duplicate_case_ids():
    adapter = StubAdapter()
    case = TestCase("same", "x", lambda _: "PASS")
    common = dict(adapter=adapter, cases=[case], suite_version="0.1",
                  assessment_mode="NATIVE_BASELINE", run_id="r")
    try:
        run_assessment(**common, model_configuration_sha256="not-a-hash")
        assert False, "bad configuration digest accepted"
    except ValueError:
        pass
    try:
        run_assessment(**{**common, "cases": [case, case]},
                       model_configuration_sha256="c" * 64)
        assert False, "duplicate case ids accepted"
    except ValueError:
        pass


def test_runner_does_not_turn_invalid_oracle_result_into_pass():
    adapter = StubAdapter()
    manifest = run_assessment(
        adapter=adapter,
        cases=[TestCase("bad-oracle", "x", lambda _: "GREEN")],
        model_configuration_sha256="d" * 64,
        suite_version="0.1",
        assessment_mode="POLICY_CONFIGURED",
        run_id="r-2",
    )
    assert manifest["summary"]["INDETERMINATE"] == 1
    assert manifest["results"][0]["reason"] == "ValueError"
