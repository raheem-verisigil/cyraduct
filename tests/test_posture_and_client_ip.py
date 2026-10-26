"""Security posture report and the opt-in client-IP header for rate limiting."""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from fastapi.testclient import TestClient

from main import app
from app import config

client = TestClient(app)
ADMIN = {"X-Cyraduct-Admin-Key": config.ADMIN_API_KEY}


@pytest.fixture(autouse=True)
def _reset_limiter():
    app.state.limiter.reset()
    yield
    app.state.limiter.reset()


def test_posture_requires_full_admin():
    assert client.get("/v1/admin/posture").status_code == 401
    if config.TEST_ADMIN_KEY:
        r = client.get("/v1/admin/posture", headers={"X-Cyraduct-Admin-Key": config.TEST_ADMIN_KEY})
        assert r.status_code == 403


def test_posture_reports_without_leaking_secrets():
    r = client.get("/v1/admin/posture", headers=ADMIN)
    assert r.status_code == 200
    text = r.text
    assert config.ADMIN_API_KEY not in text
    assert config.SIGNING_SECRET not in text
    body = r.json()
    assert body["ready_for_production"] is False  # test environment is not production
    assert any("CYRADUCT_ENV" in f for f in body["findings"])
    assert "signing_key_source" in body and "client_ip_seen_by_rate_limiter" in body


def test_client_ip_header_is_ignored_by_default():
    r = client.get("/v1/admin/posture", headers={**ADMIN, "X-Real-IP": "203.0.113.9"})
    assert r.json()["client_ip_seen_by_rate_limiter"] != "203.0.113.9"


def test_configured_client_ip_header_separates_rate_limit_buckets(monkeypatch):
    monkeypatch.setattr(config, "CLIENT_IP_HEADER", "x-real-ip")
    body = {"agent_id": "test-ip-bucket", "action_type": "read_public_doc",
            "consequence_class": "low_risk", "policy_pack": "generic", "payload": {}}
    saw_429 = False
    for _ in range(70):
        if client.post("/v1/advisory/evaluate", json=body, headers={"X-Real-IP": "198.51.100.1"}).status_code == 429:
            saw_429 = True
            break
    assert saw_429
    # A different client behind the same proxy is not affected.
    assert client.post("/v1/advisory/evaluate", json=body, headers={"X-Real-IP": "198.51.100.2"}).status_code == 200
