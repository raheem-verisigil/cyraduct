"""NCS sink-guard contract tests.

All receipts are generated locally with synthetic requests. No external sink
or live payment endpoint is contacted.
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import copy
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from main import app
from examples.sink_guard import require_receipt

client = TestClient(app)


def issue_test_receipt():
    public_key_response = client.get("/v1/public-key")
    assert public_key_response.status_code == 200
    public_key = public_key_response.json()["public_key_b64"]

    evaluated = client.post("/v1/attested/evaluate", json={
        "agent_id": "test-ncs-sink-compat",
        "action_type": "read_public_doc",
        "consequence_class": "low_risk",
        "purpose": "synthetic compatibility test",
        "policy_pack": "generic",
        "payload": {},
    })
    assert evaluated.status_code == 200
    receipt = evaluated.json()["receipt"]
    assert receipt is not None
    return receipt, public_key


def test_current_api_receipt_is_accepted_by_sink_guard():
    receipt, public_key = issue_test_receipt()
    require_receipt(receipt, public_key)


def test_sink_guard_rejects_tampered_signed_claim():
    receipt, public_key = issue_test_receipt()
    tampered = copy.deepcopy(receipt)
    tampered["policy"]["policy_pack"] = "attacker-substituted-pack"
    with pytest.raises(ValueError, match="receipt signature is invalid"):
        require_receipt(tampered, public_key)


def test_sink_guard_rejects_wrong_expected_action_hash():
    receipt, public_key = issue_test_receipt()
    with pytest.raises(ValueError, match="action hash does not match"):
        require_receipt(receipt, public_key, expected_action_hash="0" * 64)


def test_sink_guard_rejects_expired_receipt():
    receipt, public_key = issue_test_receipt()
    receipt["expires_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    with pytest.raises(ValueError, match="receipt is expired"):
        require_receipt(receipt, public_key)
