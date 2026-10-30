import pytest
from ncs_harness.capability_lite import build_capability_lite_profile, wilson_interval

def test_capability_lite_reports_rates_and_confidence_intervals():
    profile = build_capability_lite_profile([
        {"feature":"tool_use","successes":8,"trials":10},
        {"feature":"tool_use","successes":7,"trials":10},
    ])
    item = profile["features"]["tool_use"]
    assert item["status"] == "OBSERVED"
    assert item["successes"] == 15
    assert item["trials"] == 20
    assert item["rate"] == 0.75
    assert item["ci95"][0] < item["rate"] < item["ci95"][1]
    assert profile["aggregate_intelligence_score"] is None
    assert profile["grade_effect"] == "NONE"

def test_untested_capability_dimension_is_not_zero():
    profile = build_capability_lite_profile([])
    assert profile["features"]["robustness"]["status"] == "NOT_TESTED"
    assert profile["features"]["robustness"]["rate"] is None

def test_unknown_capability_dimension_rejected():
    with pytest.raises(ValueError):
        build_capability_lite_profile([{"feature":"general_iq","successes":1,"trials":1}])

def test_wilson_interval_rejects_invalid_counts():
    with pytest.raises(ValueError):
        wilson_interval(4, 3)
