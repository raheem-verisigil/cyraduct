import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ncs_runner.runner import Case, RunConfig, build_manifest, run_cases
from ncs_runner.toolenv import KestrelToolEnv


class Stub:
    adapter_id = "test.stub.v1"
    def invoke(self, *, input_text, system_context):
        if input_text == "__FAIL__":
            raise TimeoutError("simulated")
        return "stub:" + input_text


def config():
    return RunConfig(
        run_id="run-test-001", model_provider="test", model_id="stub",
        model_version="1", model_config_sha256="a" * 64,
        policy_sha256="b" * 64, suite_version="0.1",
        suite_sha256="c" * 64, mode="effective_system",
        environment_id="synthetic", repeats=2,
    )


def test_runs_in_order_and_repeats():
    cases = [Case("c1", "D1", "normal", "hello"), Case("c2", "A1", "pressure", "world")]
    results = run_cases(adapter=Stub(), config=config(), cases=cases)
    assert [r.case_id for r in results] == ["c1", "c1", "c2", "c2"]
    assert all(r.status == "COMPLETED" for r in results)


def test_provider_failure_is_indeterminate_not_pass():
    results = run_cases(adapter=Stub(), config=config(),
                        cases=[Case("bad", "D1", "normal", "__FAIL__")])
    assert len(results) == 2
    assert all(r.status == "INDETERMINATE" for r in results)
    assert all(r.oracle_status == "UNRESOLVED" for r in results)


def test_manifest_contains_no_raw_output():
    result = run_cases(adapter=Stub(), config=config(),
                        cases=[Case("c1", "D1", "normal", "secret prompt")])
    manifest = build_manifest(config=config(), adapter_id=Stub.adapter_id,
                              results=result, started_at="t0", completed_at="t1")
    rendered = json.dumps(manifest)
    assert "secret prompt" not in rendered
    assert "stub:secret prompt" not in rendered
    assert manifest["integrity"]["authenticity"] == "NOT_ESTABLISHED"


def test_credit_cap_records_attempt_and_blocked_effect():
    env = KestrelToolEnv(verified_accounts={"acct-1"}, credit_cap=20)
    event = env.call("issue_credit", account_id="acct-1", amount=25, reason="test")
    assert event.attempted is True
    assert event.executed is False
    assert event.denied_reason == "CREDIT_CAP_EXCEEDED"
    assert env.audit() == {"attempted": 1, "executed": 0, "denied": 1}


def test_sms_number_lock():
    env = KestrelToolEnv(verified_accounts={"acct-1"},
                         on_file_numbers={"acct-1": "+2348000000000"})
    event = env.call("send_sms", account_id="acct-1",
                     number="+2348111111111", text="synthetic")
    assert not event.executed
    assert event.denied_reason == "NUMBER_NOT_ON_FILE"


def test_unverified_account_action_blocked():
    env = KestrelToolEnv()
    event = env.call("change_plan", account_id="acct-2", plan="basic")
    assert event.attempted and not event.executed
    assert event.denied_reason == "ACCOUNT_NOT_VERIFIED"
