"""
Rate limiting tests.

The rest of the suite proves the decorators don't break normal usage
(41 other tests all stay well under any limit). This file specifically
proves a limit actually fires — slowapi decorator misconfiguration is a
known failure mode where the app runs fine but silently never limits
anything, which would defeat the entire point of adding this.
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_advisory_evaluate_rate_limit_fires():
    """Limit is 60/minute. Hammer it well past that from the same
    (test-client-simulated) source and confirm a 429 eventually appears."""
    saw_429 = False
    for _ in range(80):
        r = client.post("/v1/advisory/evaluate", json={
            "agent_id": "rate-limit-test-agent", "action_type": "read_public_doc",
            "consequence_class": "low_risk", "policy_pack": "generic", "payload": {}
        })
        if r.status_code == 429:
            saw_429 = True
            break
    assert saw_429, "Expected a 429 after exceeding 60/minute on /v1/advisory/evaluate — rate limiting is not firing"


def test_broker_execute_rate_limit_is_tighter_than_advisory():
    """Broker is limited to 20/minute (tighter, since each call can
    trigger a real outbound HTTP request) — confirm it fires well before
    advisory's 60/minute would."""
    # Issue one real receipt first so we have a valid receipt_id to hammer with.
    ev = client.post("/v1/attested/evaluate", json={
        "agent_id": "rate-limit-broker-agent", "action_type": "read_public_doc",
        "consequence_class": "low_risk", "policy_pack": "generic", "payload": {}
    }).json()
    receipt_id = ev["receipt"]["receipt_id"]

    saw_429 = False
    for _ in range(35):
        r = client.post("/v1/broker/execute", params={
            "receipt_id": receipt_id,
            "execution_webhook": "https://example.com/",
        }, json={
            "agent_id": "rate-limit-broker-agent", "action_type": "read_public_doc",
            "consequence_class": "low_risk", "policy_pack": "generic", "payload": {}
        })
        if r.status_code == 429:
            saw_429 = True
            break
    assert saw_429, "Expected a 429 after exceeding 20/minute on /v1/broker/execute"
