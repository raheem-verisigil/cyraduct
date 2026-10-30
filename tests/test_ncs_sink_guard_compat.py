"""Known-defect reproducer: current receipts and example sink guard disagree.

The test is intentionally expected to pass only while it observes the documented
compatibility defect. After the sink helper is fixed, replace this assertion with
a positive verification test plus tamper/expiry/action-binding tests.
"""
import pytest
from fastapi.testclient import TestClient

from main import app
from examples.sink_guard import require_receipt

client = TestClient(app)


def test_current_api_receipt_is_rejected_by_legacy_example_sink_guard():
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

    # The current server-side canonical verifier accepts the same receipt.
    server_verification = client.get(
        f"/v1/attested/verify/{receipt['receipt_id']}"
    )
    assert server_verification.json()["valid"] is True

    # The example helper uses a different message format and rejects it.
    with pytest.raises(ValueError, match="receipt signature is invalid"):
        require_receipt(receipt, public_key)
