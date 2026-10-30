"""Experiment Record tests; local keys only, no provider/network calls."""
import copy
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from ncs_harness.experiment_record import (
    build_experiment_record,
    learner_data_gate,
    shareable_aggregate,
    sign_experiment_record,
    verify_experiment_record,
)

def keys():
    private = Ed25519PrivateKey.generate()
    private_pem = private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public_pem = private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem

def record(consent=False):
    return build_experiment_record(
        record_id="EXP-001", assessment_id="NCS-TEST-001",
        subject={
            "model_configuration_sha256":"a"*64,
            "model_family":"synthetic-family",
            "model_size_class":"unknown",
            "provider_type":"synthetic",
        },
        profile_features={"tool_use":{"successes":8,"trials":10}},
        policy_features={"policy_pack_sha256":"b"*64,"rule_count":4},
        outcomes={"attempt_level":{"attempts":10,"violations":2},
                  "effect_level":{"effects_observed":10,"unauthorized_effects":0}},
        uncertainty={"attempt_level_ci95":[0.08,0.45]},
        context={"suite_version":"0.1","assurance_level":"RAL-1"},
        provenance={"evidence_manifest_sha256":"c"*64,"runner_commit_sha":"d"*40},
        sharing_consent=consent,
        recorded_at="2026-10-30T00:00:00+00:00",
    )

def test_record_is_signed_and_signature_verifies():
    private, public = keys()
    envelope = sign_experiment_record(record(), private_key_pem=private, key_id="test-key")
    assert verify_experiment_record(envelope, public_key_pem=public) == (True, "verified")

def test_tampered_record_fails_signature_verification():
    private, public = keys()
    envelope = sign_experiment_record(record(), private_key_pem=private, key_id="test-key")
    changed = copy.deepcopy(envelope)
    changed["record"]["outcomes"]["attempt_level"]["violations"] = 0
    assert verify_experiment_record(changed, public_key_pem=public)[0] is False

def test_raw_prompt_and_output_fields_are_rejected():
    with pytest.raises(ValueError, match="raw content"):
        build_experiment_record(
            record_id="EXP-002", assessment_id="A",
            subject={"model_configuration_sha256":"a"*64,"model_family":"x","model_size_class":"x","provider_type":"x"},
            profile_features={}, policy_features={"prompt":"do not store"},
            outcomes={}, uncertainty={}, context={}, provenance={}
        )

def test_aggregate_sharing_requires_explicit_consent():
    private, public = keys()
    envelope = sign_experiment_record(record(), private_key_pem=private, key_id="test-key")
    with pytest.raises(PermissionError):
        shareable_aggregate([envelope], trusted_public_keys={"test-key":public})

def test_consented_aggregate_excludes_model_configuration_identity():
    private, _ = keys()
    envelopes = []
    for i in range(5):
        item = record(consent=True)
        item["record_id"] = f"EXP-{i}"
        item["subject"]["model_configuration_sha256"] = f"{i:064x}"
        envelopes.append(sign_experiment_record(item, private_key_pem=private, key_id="test-key"))
    shared = shareable_aggregate(envelopes, trusted_public_keys={"test-key":keys()[1]})
    assert shared["no_prompts_or_outputs"] is True
    assert shared["no_subject_identifiers"] is True
    assert shared["cohort_size"] == 5
    assert "model_configuration_sha256" not in str(shared)

def test_sharing_suppresses_small_cohorts_and_missing_consent():
    private, _ = keys()
    one = sign_experiment_record(record(consent=True), private_key_pem=private, key_id="test-key")
    with pytest.raises(ValueError):
        shareable_aggregate([one], trusted_public_keys={"test-key":keys()[1]})
    no_consent = sign_experiment_record(record(consent=False), private_key_pem=private, key_id="test-key")
    with pytest.raises(PermissionError):
        shareable_aggregate([one, no_consent, one, one, one], trusted_public_keys={"test-key":keys()[1]})

def test_cold_start_gate_requires_15_configs_four_families_and_temporal_validation():
    records = []
    for i in range(15):
        item = record()
        item["subject"]["model_configuration_sha256"] = f"{i:064x}"
        item["subject"]["model_family"] = f"family-{i % 4}"
        records.append({"record":item})
    assert learner_data_gate(records, temporal_validation_passed=False)["status"] == "INSUFFICIENT_DATA"
    result = learner_data_gate(records, temporal_validation_passed=True)
    assert result["status"] == "ELIGIBLE_FOR_OFFLINE_VALIDATION"
    assert result["user_facing_predictions_enabled"] is False
    assert result["grading_integration"] == "PROHIBITED"
