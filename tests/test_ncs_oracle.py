import pytest
from ncs_harness.case_generator import generate_cases, load_scenarios
from ncs_harness.oracle import evaluate_case

def cases(): return generate_cases(seed="oracle-test", pack=load_scenarios())

def test_oracle_passes_matching_declared_decision_and_receipt():
    case=next(x for x in cases() if x["source_scenario_id"]=="NCS-CYR-FG-001")
    result=evaluate_case(case,{"application_decision":"allow","receipt_issued":True})
    assert result["status"]=="passed" and result["grade_authority"] is False

def test_oracle_fails_wrong_decision():
    case=next(x for x in cases() if x["source_scenario_id"]=="NCS-CYR-FG-002")
    assert evaluate_case(case,{"application_decision":"allow","receipt_issued":False})["status"]=="failed"

def test_oracle_keeps_unobserved_effect_unknown():
    case=next(x for x in cases() if x["source_scenario_id"]=="NCS-CYR-FG-001")
    result=evaluate_case(case,{"application_decision":"allow","receipt_issued":None})
    assert result["status"]=="not-observed" and result["checks"][1]["result"]=="not-observable"

def test_oracle_rejects_non_synthetic_cases():
    case=cases()[0]; case["synthetic_only"]=False
    with pytest.raises(ValueError): evaluate_case(case,{"application_decision":"allow","receipt_issued":True})
