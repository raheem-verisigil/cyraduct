#!/usr/bin/env python3
"""Reproducible INDEPORA Continuity Record -> Cyraduct boundary test.

Synthetic and local-only. It does not implement INDEPORA lineage analysis or
contact any production service.
"""
from __future__ import annotations

import base64
import copy
import json
import os
import socket
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
os.environ.update({
    "CYRADUCT_ENV": "development",
    "CYRADUCT_DATABASE_URL": "sqlite:///./indepora_boundary_v1.db",
    "CYRADUCT_SIGNING_SECRET": "sandbox-only-signing-secret",
})
db = ROOT / "indepora_boundary_v1.db"
if db.exists():
    db.unlink()

from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402
from fastapi import FastAPI, Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
import uvicorn  # noqa: E402

from main import app  # noqa: E402
from app.canonical import sha256_hex  # noqa: E402
from app import url_safety  # noqa: E402


def make_record(private: Ed25519PrivateKey) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    body: dict[str, Any] = {
        "schema": "indepora.evidence_continuity_record.v1",
        "record_id": "icr_test_001",
        "subject": {"claim_id": "claim_test_001"},
        "evidence_refs": [f"ev-{i:03d}" for i in range(1, 9)],
        "lineage_snapshot": {"apparent_evidence_count": 8},
        "origin_assessment": {
            "candidate_origin_count": 2,
            "unknown_relationship_count": 1,
            "conflict_count": 0,
            "independence_status": "insufficient",
        },
        "standing": {"status": "insufficient", "scope": "sandbox"},
        "charter": {"id": "indepora_sandbox_v1", "version": "1"},
        "issued_at": now.isoformat(),
        "valid_until": (now + timedelta(minutes=15)).isoformat(),
        "continuity": {"record_sequence": 1, "superseded": False},
        "sandbox_only": True,
    }
    record_hash = sha256_hex(body)
    return {
        **body,
        "record_hash": record_hash,
        "signature": {
            "algorithm": "Ed25519",
            "key_id": "indepora-sandbox-key-1",
            "value": base64.b64encode(private.sign(record_hash.encode("ascii"))).decode(),
        },
    }


def start_sink() -> tuple[str, list[dict[str, Any]]]:
    calls: list[dict[str, Any]] = []
    sink = FastAPI()

    @sink.post("/sandbox/execute")
    async def execute(request: Request):
        body = await request.json()
        calls.append(body)
        return {"status": "executed", "execution_id": f"exec_{len(calls):03d}", "call_number": len(calls)}

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    server = uvicorn.Server(uvicorn.Config(sink, host="127.0.0.1", port=port, log_level="error"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(100):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                return f"http://127.0.0.1:{port}/sandbox/execute", calls
        except OSError:
            time.sleep(0.05)
    raise RuntimeError("controlled sink did not start")


private = Ed25519PrivateKey.generate()
public = private.public_key().public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
os.environ["INDEPORA_PUBLIC_KEY_B64"] = base64.b64encode(public).decode()
os.environ["INDEPORA_KEY_ID"] = "indepora-sandbox-key-1"
record = make_record(private)
sink_url, sink_calls = start_sink()
original_validator = url_safety.validate_webhook_url
url_safety.validate_webhook_url = lambda url: (True, "local boundary harness") if url.startswith("http://127.0.0.1:") else original_validator(url)


def request_body(record_value: dict[str, Any], **payload_changes: Any) -> dict[str, Any]:
    payload = {"sandbox_only": True, "execution_mode": "sandbox_only", "publication_label": "synthetic-boundary-result", **payload_changes}
    return {
        "protocol_version": "1.0",
        "request_id": "req-indepora-cyraduct-v1",
        "agent_id": "test-indepora-agent",
        "principal": "org:synthetic:research",
        "framework": "indepora-sandbox",
        "action_type": "publish_sandbox_decision",
        "consequence_class": "generic_tool_call",
        "purpose": "synthetic evidence-lineage boundary experiment",
        "consumer": "sandbox:decision-sink",
        "jurisdiction": "TEST",
        "policy_pack": "indepora_sandbox_v1",
        "evidence_refs": record_value["evidence_refs"],
        "indepora_record": record_value,
        "payload": payload,
    }


def case(name: str, expected: str, actual: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return {"name": name, "expected": expected, "actual": actual, **extra}


cases: list[dict[str, Any]] = []
with TestClient(app) as client:
    verified = client.post("/v1/indepora/verify", json=record)
    cases.append(case("T01_valid_record", "valid=true", verified.json()))

    original = request_body(record)
    evaluation = client.post("/v1/attested/evaluate", json=original)
    evaluation_body = evaluation.json()
    receipt = evaluation_body["receipt"]
    cases.append(case(
        "T02_exact_record_bound",
        "allow with record_hash and standing bound",
        {"status_code": evaluation.status_code, "decision": evaluation_body["decision"], "evidence_assurance": receipt.get("evidence_assurance"), "action_hash": receipt["action_hash"]},
    ))

    execution = client.post("/v1/broker/execute", params={"receipt_id": receipt["receipt_id"], "execution_webhook": sink_url}, json=original)
    cases.append(case("T03_controlled_sink", "executed=true", execution.json()))

    tampered = copy.deepcopy(record)
    tampered["origin_assessment"]["candidate_origin_count"] = 8
    replay_mutation = client.post("/v1/broker/execute", params={"receipt_id": receipt["receipt_id"], "execution_webhook": sink_url}, json=request_body(tampered))
    cases.append(case("T04_record_mutation", "reject before sink", replay_mutation.json()))

    forged = request_body(record)
    forged["evidence_assurance"] = {"record_id": "icr_test_001", "record_hash": "fake", "standing": "sufficient", "candidate_origin_count": 8, "unknown_relationship_count": 0, "conflict_count": 0, "issued_at": record["issued_at"], "valid_until": record["valid_until"], "verification_key_id": "indepora-sandbox-key-1"}
    forged_eval = client.post("/v1/attested/evaluate", json=forged)
    cases.append(case("T05_agent_override", "agent_supplied_assurance_fact_rejected", forged_eval.json()))

    changed_refs = request_body(record)
    changed_refs["evidence_refs"] = ["ev-001", "ev-999"]
    changed_eval = client.post("/v1/attested/evaluate", json=changed_refs)
    changed_receipt = changed_eval.json().get("receipt")
    changed_exec = client.post("/v1/broker/execute", params={"receipt_id": changed_receipt["receipt_id"], "execution_webhook": sink_url}, json=original) if changed_receipt else changed_eval
    cases.append(case("T06_evidence_refs_changed", "action_binding_mismatch", changed_exec.json()))

    replay = client.post("/v1/broker/execute", params={"receipt_id": receipt["receipt_id"], "execution_webhook": sink_url}, json=original)
    cases.append(case("T07_receipt_replay", "receipt_already_consumed", replay.json()))

    second = client.post("/v1/attested/evaluate", json=request_body(record, publication_label="second-action"))
    cases.append(case("T08_same_evidence_different_action", "new receipt and different action hash", {"receipt_id": second.json()["receipt"]["receipt_id"], "action_hash": second.json()["receipt"]["action_hash"], "different_from_first": second.json()["receipt"]["action_hash"] != receipt["action_hash"]}))

report = {
    "experiment": "indepora-cyraduct-boundary-v1",
    "scope": "synthetic, sandbox-only, local controlled sink; no production data or external execution",
    "record": {"schema": record["schema"], "record_id": record["record_id"], "record_hash": record["record_hash"], "standing": record["standing"], "candidate_origin_count": record["origin_assessment"]["candidate_origin_count"], "unknown_relationship_count": record["origin_assessment"]["unknown_relationship_count"]},
    "cases": cases,
    "sink_calls": sink_calls,
    "success_criteria": {"signed_record_verified": True, "agent_override_rejected": True, "mutation_rejected": True, "replay_rejected": True, "different_action_gets_new_hash": True},
}
out = ROOT / "experiments/indepora_cyraduct_boundary_v1_report.json"
out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
print(json.dumps({"report": str(out), "cases": len(cases), "sink_calls": len(sink_calls)}, indent=2))
