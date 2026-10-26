"""Regression tests for dedicated service credentials."""
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from main import app
from app import auth, config

client = TestClient(app)


def test_service_key_rejects_missing_key_when_configured(monkeypatch):
    monkeypatch.setattr(config, "RUNTIME_API_KEY", "test-runtime-secret")
    response = client.post(
        "/v1/runtime/evaluate",
        json={
            "agent_id": "service-auth-test",
            "action_type": "read_public_doc",
            "consequence_class": "low_risk",
            "target": "docs",
            "resource": "public",
            "reversibility": "reversible",
            "authority": "present",
            "policy_pack": "generic",
            "payload": {},
            "runtime_state": {},
        },
    )
    assert response.status_code == 401


def test_service_key_rejects_wrong_key_when_configured(monkeypatch):
    monkeypatch.setattr(config, "RUNTIME_API_KEY", "test-runtime-secret")
    response = client.post(
        "/v1/runtime/evaluate",
        headers={"X-Cyraduct-Runtime-Key": "wrong-key"},
        json={
            "agent_id": "service-auth-test",
            "action_type": "read_public_doc",
            "consequence_class": "low_risk",
            "target": "docs",
            "resource": "public",
            "reversibility": "reversible",
            "authority": "present",
            "policy_pack": "generic",
            "payload": {},
            "runtime_state": {},
        },
    )
    assert response.status_code == 401


def test_service_key_accepts_matching_key(monkeypatch):
    monkeypatch.setattr(config, "RUNTIME_API_KEY", "test-runtime-secret")
    response = client.post(
        "/v1/runtime/evaluate",
        headers={"X-Cyraduct-Runtime-Key": "test-runtime-secret"},
        json={
            "agent_id": "service-auth-test",
            "action_type": "read_public_doc",
            "consequence_class": "low_risk",
            "target": "docs",
            "resource": "public",
            "reversibility": "reversible",
            "authority": "present",
            "policy_pack": "generic",
            "payload": {},
            "runtime_state": {},
        },
    )
    assert response.status_code == 200


def test_missing_service_key_fails_closed_in_production(monkeypatch):
    monkeypatch.setattr(config, "ENVIRONMENT", "production")
    with pytest.raises(HTTPException) as exc:
        auth.require_service_key(None, "", "CYRADUCT_RUNTIME_API_KEY")
    assert exc.value.status_code == 503
    assert exc.value.detail == "cyraduct_runtime_api_key_not_configured"


def test_broker_requires_its_own_key_before_processing(monkeypatch):
    monkeypatch.setattr(config, "BROKER_API_KEY", "test-broker-secret")
    response = client.post(
        "/v1/broker/execute?receipt_id=not-a-real-receipt&execution_webhook=https%3A%2F%2Fexample.com%2Fhook",
        json={
            "agent_id": "service-auth-test",
            "action_type": "read_public_doc",
            "consequence_class": "low_risk",
            "target": "docs",
            "resource": "public",
            "reversibility": "reversible",
            "authority": "present",
            "policy_pack": "generic",
            "payload": {},
            "runtime_state": {},
        },
    )
    assert response.status_code == 401
