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


def test_small_chunked_body_is_accepted():
    """Chunked uploads (no Content-Length) within the cap must still work."""
    import json
    payload = json.dumps({
        "agent_id": "test-chunked-ok", "action_type": "read_public_doc",
        "consequence_class": "low_risk", "policy_pack": "generic", "payload": {},
    }).encode()

    def gen():
        yield payload[:20]
        yield payload[20:]
    r = client.post("/v1/advisory/evaluate", content=gen(),
                    headers={"content-type": "application/json"})
    assert r.status_code == 200


def test_oversized_chunked_body_is_cut_off_with_413():
    """No Content-Length to inspect: the cap must still fire on bytes received."""
    chunk = b"x" * 65536

    def gen():
        for _ in range((MAX_REQUEST_BYTES // len(chunk)) + 3):
            yield chunk
    r = client.post("/v1/advisory/evaluate", content=gen(),
                    headers={"content-type": "application/json"})
    assert r.status_code == 413


def test_understated_content_length_cannot_bypass_cap():
    """Header says small, body is large: must not be accepted."""
    import httpx  # noqa: F401
    big = b'{"agent_id":"test-lie","payload":{"b":"' + b"x" * (MAX_REQUEST_BYTES + 5000) + b'"}}'
    r = client.post("/v1/advisory/evaluate", content=big,
                    headers={"content-type": "application/json", "content-length": "50"})
    assert r.status_code in (400, 413)


def test_invalid_content_length_is_400():
    r = client.post("/v1/advisory/evaluate", content=b"{}",
                    headers={"content-type": "application/json", "content-length": "abc"})
    assert r.status_code in (400, 422)


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
