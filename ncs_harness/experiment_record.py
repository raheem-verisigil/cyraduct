"""NCS Experiment Record v0.3.

Stores aggregate experiment metadata only. It deliberately excludes prompts,
model outputs, datasets and weights. Signing uses Ed25519 from cryptography;
private-key custody remains with the caller/KMS and is never handled here.
"""
from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

SCHEMA = "ncs-experiment-record/0.1"
FORBIDDEN_KEYS = {
    "prompt", "prompt_text", "raw_prompt", "response", "raw_response",
    "output", "output_text", "raw_output", "completion", "dataset",
    "training_data", "model_weights", "weights", "input_text",
}
CAPABILITY_FEATURES = {
    "tool_use",
    "context_instruction_retention",
    "calibration_abstention",
    "robustness",
}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")


def sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _reject_raw_content(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                raise ValueError(f"raw content field is prohibited in Experiment Record: {path}.{key}")
            _reject_raw_content(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_raw_content(child, f"{path}[{index}]")


def _rate(item: dict[str, Any], name: str) -> None:
    successes = item.get("successes")
    trials = item.get("trials")
    if not isinstance(successes, int) or not isinstance(trials, int):
        raise ValueError(f"{name} requires integer successes and trials")
    if trials < 1 or successes < 0 or successes > trials:
        raise ValueError(f"{name} has invalid success/trial counts")


def build_experiment_record(
    *,
    record_id: str,
    assessment_id: str,
    subject: dict[str, Any],
    profile_features: dict[str, Any],
    policy_features: dict[str, Any],
    outcomes: dict[str, Any],
    uncertainty: dict[str, Any],
    context: dict[str, Any],
    provenance: dict[str, Any],
    sharing_consent: bool = False,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    """Validate and construct the unsigned canonical record payload."""
    if not record_id or not assessment_id:
        raise ValueError("record_id and assessment_id are required")
    required_subject = {
        "model_configuration_sha256", "model_family", "model_size_class",
        "provider_type",
    }
    if not required_subject.issubset(subject):
        raise ValueError("subject is missing exact configuration identity fields")
    config_hash = subject["model_configuration_sha256"]
    if not isinstance(config_hash, str) or len(config_hash) != 64 or any(
        c not in "0123456789abcdef" for c in config_hash
    ):
        raise ValueError("model_configuration_sha256 must be lowercase SHA-256")
    if set(profile_features) - CAPABILITY_FEATURES:
        raise ValueError("only the four pre-registered capability-lite features are allowed")
    normalized_features = {}
    for name, item in profile_features.items():
        if not isinstance(item, dict):
            raise ValueError(f"{name} must be an aggregate object")
        _rate(item, name)
        normalized_features[name] = {
            "successes": item["successes"],
            "trials": item["trials"],
            "rate": item["successes"] / item["trials"],
        }
    if not isinstance(outcomes, dict) or not isinstance(uncertainty, dict):
        raise ValueError("outcomes and uncertainty must be objects")
    if not isinstance(policy_features, dict) or not isinstance(context, dict) or not isinstance(provenance, dict):
        raise ValueError("policy_features, context and provenance must be objects")
    payload = {
        "schema": SCHEMA,
        "record_id": record_id,
        "assessment_id": assessment_id,
        "recorded_at": recorded_at or datetime.now(timezone.utc).isoformat(),
        "subject": subject,
        "profile_features": normalized_features,
        "policy_features": policy_features,
        "outcomes": outcomes,
        "uncertainty": uncertainty,
        "context": context,
        "provenance": provenance,
        "sharing": {
            "local_only_by_default": True,
            "aggregate_sharing_opt_in": bool(sharing_consent),
            "contains_prompts_or_outputs": False,
            "contains_raw_datasets_or_weights": False,
        },
    }
    _reject_raw_content(payload)
    return payload


def sign_experiment_record(
    record: dict[str, Any],
    *,
    private_key_pem: bytes,
    key_id: str,
) -> dict[str, Any]:
    """Sign canonical record bytes with caller-supplied Ed25519 PEM key."""
    if record.get("schema") != SCHEMA:
        raise ValueError("unsupported Experiment Record schema")
    if not key_id:
        raise ValueError("key_id is required")
    key = serialization.load_pem_private_key(private_key_pem, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("Experiment Record signatures require Ed25519")
    payload = canonical_bytes(record)
    signature = key.sign(payload)
    return {
        "record": record,
        "integrity": {
            "canonical_sha256": sha256_hex(payload),
            "signature": {
                "algorithm": "Ed25519",
                "key_id": key_id,
                "value_base64": base64.b64encode(signature).decode("ascii"),
            },
        },
    }


def verify_experiment_record(
    envelope: dict[str, Any],
    *,
    public_key_pem: bytes,
) -> tuple[bool, str]:
    try:
        record = envelope["record"]
        integrity = envelope["integrity"]
        payload = canonical_bytes(record)
        if record.get("schema") != SCHEMA:
            return False, "unsupported-schema"
        if sha256_hex(payload) != integrity["canonical_sha256"]:
            return False, "digest-mismatch"
        signature = integrity["signature"]
        if signature.get("algorithm") != "Ed25519":
            return False, "unsupported-signature-algorithm"
        key = serialization.load_pem_public_key(public_key_pem)
        if not isinstance(key, Ed25519PublicKey):
            return False, "invalid-public-key-type"
        key.verify(base64.b64decode(signature["value_base64"], validate=True), payload)
        return True, "verified"
    except Exception:
        return False, "signature-or-envelope-invalid"


def shareable_aggregate(envelope: dict[str, Any]) -> dict[str, Any]:
    """Return a narrow anonymized aggregate only after explicit consent."""
    record = envelope.get("record", {})
    if record.get("sharing", {}).get("aggregate_sharing_opt_in") is not True:
        raise PermissionError("aggregate sharing requires explicit opt-in consent")
    features = record.get("profile_features", {})
    return {
        "schema": "ncs-shared-experiment-aggregate/0.1",
        "model_family": record.get("subject", {}).get("model_family"),
        "profile_features": features,
        "outcomes": record.get("outcomes", {}),
        "uncertainty": record.get("uncertainty", {}),
        "context": {
            "suite_version": record.get("context", {}).get("suite_version"),
            "assurance_level": record.get("context", {}).get("assurance_level"),
        },
        "source_record_sha256": envelope.get("integrity", {}).get("canonical_sha256"),
        "no_prompts_or_outputs": True,
    }


def learner_data_gate(
    records: list[dict[str, Any]],
    *,
    temporal_validation_passed: bool,
    minimum_configurations: int = 15,
    minimum_families: int = 4,
) -> dict[str, Any]:
    """Cold-start gate; it does not train or issue predictions."""
    configurations = {
        item.get("record", {}).get("subject", {}).get("model_configuration_sha256")
        for item in records
    } - {None}
    families = {
        item.get("record", {}).get("subject", {}).get("model_family")
        for item in records
    } - {None}
    ready = (
        len(configurations) >= minimum_configurations
        and len(families) >= minimum_families
        and temporal_validation_passed is True
    )
    return {
        "status": "ELIGIBLE_FOR_OFFLINE_VALIDATION" if ready else "INSUFFICIENT_DATA",
        "distinct_configurations": len(configurations),
        "distinct_model_families": len(families),
        "temporal_validation_passed": bool(temporal_validation_passed),
        "minimum_configurations": minimum_configurations,
        "minimum_families": minimum_families,
        "user_facing_predictions_enabled": False,
        "grading_integration": "PROHIBITED",
    }
