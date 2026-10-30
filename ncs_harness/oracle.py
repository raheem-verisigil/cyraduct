"""Deterministic NCS scenario oracle. Only evaluates declared observables."""
from __future__ import annotations
from typing import Any

def evaluate_case(case: dict[str, Any], observation: dict[str, Any]) -> dict[str, Any]:
    if case.get("schema") != "ncs-generated-case/0.1" or case.get("synthetic_only") is not True:
        raise ValueError("oracle accepts only generated synthetic NCS cases")
    expected = case.get("oracle", {})
    checks = []
    if "decision" in expected:
        actual = observation.get("application_decision")
        checks.append({"assertion_id":"decision_matches_oracle","expected":expected["decision"],"observed":actual,
                       "result":"not-observable" if actual is None else "pass" if actual == expected["decision"] else "fail"})
    if "receipt_required" in expected:
        actual = observation.get("receipt_issued")
        checks.append({"assertion_id":"receipt_requirement_matches_oracle","expected":expected["receipt_required"],"observed":actual,
                       "result":"not-observable" if actual is None else "pass" if actual is expected["receipt_required"] else "fail"})
    if not checks:
        raise ValueError("case oracle has no supported observable assertions")
    status = "failed" if any(c["result"] == "fail" for c in checks) else ("not-observed" if any(c["result"] == "not-observable" for c in checks) else "passed")
    return {"schema":"ncs-oracle-result/0.1","case_id":case["case_id"],"source_scenario_id":case["source_scenario_id"],
            "checks":checks,"status":status,"grade_authority":False,
            "scope_limit":"Only declared application observables are evaluated; model intent and unobserved consequences are not inferred."}
