"""Rate limit on the runtime tier and the request-size cap."""
import asyncio
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from fastapi.testclient import TestClient
from main import app
from app.request_limits import MAX_REQUEST_BYTES, RequestSizeLimitMiddleware

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


def test_chunked_body_without_length_is_accepted_when_under_limit():
    def gen():
        yield b'{"agent_id":"test-chunked","action_type":"read_public_doc","consequence_class":"low_risk","policy_pack":"generic","payload":{}}'
    r = client.post("/v1/advisory/evaluate", content=gen(),
                    headers={"content-type": "application/json"})
    assert r.status_code == 200


def test_chunked_body_without_length_is_rejected_when_over_limit():
    def gen():
        yield b"x" * (MAX_REQUEST_BYTES + 1)
    r = client.post("/v1/advisory/evaluate", content=gen(),
                    headers={"content-type": "application/octet-stream"})
    assert r.status_code == 413
    assert r.json()["detail"] == "request_too_large"


def _run_middleware(body: bytes, headers: list[tuple[bytes, bytes]]):
    """Exercise raw ASGI framing cases that high-level clients normalize."""
    response = []
    app_called = False
    messages = iter([
        {"type": "http.request", "body": body, "more_body": False},
    ])

    async def receive():
        try:
            return next(messages)
        except StopIteration:
            return {"type": "http.disconnect"}

    async def send(message):
        response.append(message)

    async def downstream(scope, receive, send):
        nonlocal app_called
        app_called = True
        received = await receive()
        assert received["body"] == body
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/test",
        "headers": headers,
    }
    asyncio.run(RequestSizeLimitMiddleware(downstream, max_bytes=8)(scope, receive, send))
    status = next(m["status"] for m in response if m["type"] == "http.response.start")
    return status, app_called


def test_body_without_content_length_is_checked_by_actual_bytes():
    status, app_called = _run_middleware(b"123456789", [])
    assert status == 413
    assert not app_called


def test_underreported_content_length_is_rejected_before_application():
    status, app_called = _run_middleware(
        b"123456789", [(b"content-length", b"1")]
    )
    assert status == 413
    assert not app_called


def test_content_length_mismatch_is_rejected():
    status, app_called = _run_middleware(
        b"1234", [(b"content-length", b"3")]
    )
    assert status == 400
    assert not app_called


def test_ambiguous_content_length_and_transfer_encoding_is_rejected():
    status, app_called = _run_middleware(
        b"1234",
        [(b"content-length", b"4"), (b"transfer-encoding", b"chunked")],
    )
    assert status == 400
    assert not app_called


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
