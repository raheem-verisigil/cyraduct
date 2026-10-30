import json
from ncs_harness.case_generator import generate_cases, load_scenarios

def test_case_generator_is_deterministic_and_preserves_oracles():
    pack = load_scenarios()
    first = generate_cases(seed="ncs-week1-2026", pack=pack)
    second = generate_cases(seed="ncs-week1-2026", pack=pack)
    assert first == second
    assert len(first) == len(pack["scenarios"])
    source = {item["id"]: item for item in pack["scenarios"]}
    for case in first:
        original = source[case["source_scenario_id"]]
        assert case["input"] == original["input"]
        assert case["oracle"] == original["expected"]
        assert case["synthetic_only"] is True
        assert case["external_side_effects"] == "disabled-or-mocked"

def test_different_seed_changes_case_ids_not_expected_outcomes():
    pack = load_scenarios()
    a = generate_cases(seed="alpha", pack=pack)
    b = generate_cases(seed="beta", pack=pack)
    assert [x["case_id"] for x in a] != [x["case_id"] for x in b]
    assert [x["oracle"] for x in a] == [x["oracle"] for x in b]

def test_unknown_scenario_schema_is_rejected():
    import pytest
    with pytest.raises(ValueError):
        load_scenarios_from_bad = {"schema":"wrong","scenarios":[]}
        generate_cases(seed="x", pack=load_scenarios_from_bad)
