"""Rate limit on the runtime tier and the request-size cap."""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from fastapi.testclient import TestClient
from main import app
from app.request_limits import MAX_REQUEST_BYTES

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_limiter():
    """The limiter is process-wide; clear it before and after each test so
    exhausting a bucket here cannot make other test files see 429s."""
    app.state.limiter.reset()
    yield
    app.state.limiter.reset()


def test_oversized_body_is_rejected_with_413():
    big = "x" * (MAX_REQUEST_BYTES + 1024)
    r = client.post("/v1/advisory/evaluate", json={
        "agent_id": "test-size-cap", "action_type": "read_public_doc",
        "consequence_class": "low_risk", "policy_pack": "generic",
        "payload": {"blob": big},
    })
    assert r.status_code == 413
    assert r.json()["detail"] == "request_too_large"


def test_normal_body_is_still_accepted():
    r = client.post("/v1/advisory/evaluate", json={
        "agent_id": "test-size-ok", "action_type": "read_public_doc",
        "consequence_class": "low_risk", "policy_pack": "generic", "payload": {},
    })
    assert r.status_code == 200


def test_chunked_body_without_length_is_rejected_with_411():
    def gen():
        yield b'{"agent_id":"test-chunked"}'
    r = client.post("/v1/advisory/evaluate", content=gen(),
                    headers={"content-type": "application/json"})
    assert r.status_code == 411


def test_runtime_evaluate_rate_limit_fires():
    """Runtime evaluate writes a receipt + audit row per allowed call, so
    it must be limited like the other evaluate endpoints (60/minute)."""
    saw_429 = False
    for _ in range(80):
        r = client.post("/v1/runtime/evaluate", json={
            "agent_id": "test-runtime-rate-limit", "action_type": "read_public_doc",
            "consequence_class": "low_risk", "payload": {},
        })
        if r.status_code == 429:
            saw_429 = True
            break
    assert saw_429, "Expected 429 on /v1/runtime/evaluate after 60/minute"
