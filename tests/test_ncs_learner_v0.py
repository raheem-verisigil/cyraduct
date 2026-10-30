import pytest
from ncs_harness.learner_v0 import fit_logistic_regression,predict_probability,brier_score,roc_auc,temporal_split,learner_release_gate

def rows():
    return [{"subject_id":f"m{i}","recorded_at":f"2026-10-{i+1:02d}T00:00:00Z","label":i%2,
             "features":{"tool_use":i/10,"context":(10-i)/10}} for i in range(10)]

def test_learner_is_interpretable_advisory_artifact():
    model=fit_logistic_regression(rows()[:8],["tool_use","context"],iterations=300)
    assert 0<=predict_probability(model,{"tool_use":0.7,"context":0.3})<=1
    assert model["grade_authority"] is False and model["user_facing_predictions_enabled"] is False

def test_validation_metrics_report_auc_and_brier():
    assert roc_auc([0,0,1,1],[0.1,0.2,0.8,0.9])==1.0
    assert brier_score([0,1],[0.1,0.9])==pytest.approx(0.01)

def test_temporal_split_requires_both_sides():
    train,test=temporal_split(rows(),"2026-10-06T00:00:00Z"); assert train and test
    with pytest.raises(ValueError): temporal_split(rows(),"2030-01-01")

def test_learner_release_gate_stays_closed_until_all_conditions_pass():
    assert learner_release_gate(distinct_configurations=14,distinct_families=4,temporal_validation_passed=True)["status"]=="INSUFFICIENT_DATA"
    ready=learner_release_gate(distinct_configurations=15,distinct_families=4,temporal_validation_passed=True)
    assert ready["status"]=="ELIGIBLE_FOR_OFFLINE_VALIDATION" and ready["user_facing_predictions_enabled"] is False
