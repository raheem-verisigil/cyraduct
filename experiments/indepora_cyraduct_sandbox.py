#!/usr/bin/env python3
"""Synthetic INDEPORA/Cyraduct boundary experiment.

This is a contract harness, not an INDEPORA implementation. It creates a
signed Stemma-like result, verifies it in a trusted adapter, then exercises
Cyraduct's real policy, canonical hashing, signature, broker binding, and
replay controls against a local sink.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import hmac
import json
import os
import shutil
import socket
import sys
import threading
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
os.environ.update({
    "CYRADUCT_ENV": "development",
    "CYRADUCT_DATABASE_URL": "sqlite:///./indepora_cyraduct_sandbox.db",
    "CYRADUCT_SIGNING_SECRET": "sandbox-only-signing-secret",
})
DB = ROOT / "indepora_cyraduct_sandbox.db"
if DB.exists():
    DB.unlink()

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
import uvicorn  # noqa: E402

from main import app  # noqa: E402
from app import url_safety  # noqa: E402

ADAPTER_SECRET = b"synthetic-indepora-adapter-secret"
SINK_CALLS: list[dict[str, Any]] = []

# The production broker rejects loopback HTTP by design. This local-only
# harness overrides that check for the dynamically allocated test sink; the
# application code and production URL policy are not changed.
_production_webhook_validator = url_safety.validate_webhook_url


def _sandbox_webhook_validator(url: str) -> tuple[bool, str]:
    if url.startswith("http://127.0.0.1:"):
        return True, "sandbox loopback sink"
    return _production_webhook_validator(url)


url_safety.validate_webhook_url = _sandbox_webhook_validator


def canonical_result_bytes(result: dict[str, Any]) -> bytes:
    return json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sign_result(result: dict[str, Any]) -> str:
    return hmac.new(ADAPTER_SECRET, canonical_result_bytes(result), hashlib.sha256).hexdigest()


def build_stemma() -> dict[str, Any]:
    evidence = [
        {"id": "ev-001", "origin": "origin-A", "relationship": "source"},
        {"id": "ev-002", "origin": "origin-A", "relationship": "derived"},
        {"id": "ev-003", "origin": "origin-A", "relationship": "derived"},
        {"id": "ev-004", "origin": "origin-A", "relationship": "derived"},
        {"id": "ev-005", "origin": "origin-B", "relationship": "source"},
        {"id": "ev-006", "origin": "origin-B", "relationship": "derived"},
        {"id": "ev-007", "origin": "origin-A", "relationship": "republication"},
        {"id": "ev-008", "origin": None, "relationship": "unknown"},
    ]
    result = {
        "schema": "indepora.stemma.v0.synthetic",
        "result_id": "stemma-result-001",
        "experiment_id": "exp-boundary-001",
        "issued_at": "2026-10-07T08:00:00Z",
        "charter": {
            "version": "synthetic-charter-v0",
            "standing": "insufficient_for_independence_claim",
            "conclusion": "These 8 apparent pieces of evidence do not represent 8 independent origins.",
        },
        "evidence": evidence,
        "lineage": {
            "apparent_evidence_count": 8,
            "candidate_origin_count": 2,
            "verified_relationship_count": 6,
            "inferred_relationship_count": 1,
            "unknown_relationship_count": 1,
            "conflict_count": 0,
        },
        "unknowns": ["ev-008 lineage is unknown; it is not treated as independent"],
    }
    result["result_hash"] = hashlib.sha256(canonical_result_bytes(result)).hexdigest()
    result["signature"] = sign_result(result)
    return result


def verify_stemma(result: dict[str, Any]) -> tuple[bool, str]:
    supplied_signature = result.get("signature", "")
    unsigned = copy.deepcopy(result)
    unsigned.pop("signature", None)
    supplied_hash = unsigned.pop("result_hash", None)
    expected_hash = hashlib.sha256(canonical_result_bytes(unsigned)).hexdigest()
    expected_signature = hmac.new(ADAPTER_SECRET, canonical_result_bytes(result | {"signature": None}), hashlib.sha256).hexdigest()
    # The producer signs the complete result before adding signature; result_hash
    # is over the result without result_hash/signature. Reconstruct exactly.
    signed_body = copy.deepcopy(result)
    signed_body.pop("signature", None)
    signed_body.pop("result_hash", None)
    expected_hash = hashlib.sha256(canonical_result_bytes(signed_body)).hexdigest()
    expected_signature = hmac.new(ADAPTER_SECRET, canonical_result_bytes({**signed_body, "result_hash": supplied_hash}), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(str(supplied_hash), expected_hash):
        return False, "result_hash_invalid"
    if not hmac.compare_digest(str(supplied_signature), expected_signature):
        return False, "result_signature_invalid"
    return True, "ok"


def trusted_adapter(stemma: dict[str, Any], agent_claims: dict[str, Any] | None = None) -> dict[str, Any]:
    ok, reason = verify_stemma(stemma)
    if not ok:
        raise ValueError(reason)
    lineage = stemma["lineage"]
    expected = {
        "candidate_origin_count": lineage["candidate_origin_count"],
        "verified_relationship_count": lineage["verified_relationship_count"],
        "inferred_relationship_count": lineage["inferred_relationship_count"],
        "unknown_relationship_count": lineage["unknown_relationship_count"],
        "conflict_count": lineage["conflict_count"],
        "evidence_assurance_status": stemma["charter"]["standing"],
        "sandbox_only": True,
        "execution_mode": "sandbox_only",
    }
    if agent_claims:
        for key, value in agent_claims.items():
            if key in expected and value != expected[key]:
                raise ValueError(f"agent_supplied_assurance_fact_rejected:{key}")
    return {
        "indepora_result_ref": stemma["result_id"],
        "indepora_result_hash": stemma["result_hash"],
        "charter_version": stemma["charter"]["version"],
        "lineage_summary": expected,
    }


def action_request(adapter_facts: dict[str, Any], payload_mutation: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {
        "experiment_id": "exp-boundary-001",
        "decision_id": "decision-001",
        "execution_mode": "sandbox_only",
        "sandbox_only": True,
        **adapter_facts,
        "decision_parameters": {"publication_label": "synthetic-boundary-result", "amount": 1},
    }
    if payload_mutation:
        payload.update(payload_mutation)
    return {
        "protocol_version": "1.0",
        "request_id": "req-indepora-cyraduct-001",
        "agent_id": "test-indepora-agent",
        "principal": "org:synthetic:research",
        "framework": "indepora-sandbox",
        "action_type": "publish_sandbox_decision",
        "consequence_class": "generic_tool_call",
        "purpose": "synthetic evidence-lineage boundary experiment",
        "consumer": "sandbox:decision-sink",
        "jurisdiction": "TEST",
        "policy_pack": "indepora_sandbox_v1",
        "evidence_refs": [item["id"] for item in STEMMA["evidence"]],
        "payload": payload,
    }


def start_sink() -> tuple[str, threading.Thread]:
    sink = FastAPI()

    @sink.post("/sink")
    async def receive(request: Request):
        body = await request.json()
        SINK_CALLS.append(body)
        return {"accepted": True, "sink_call_number": len(SINK_CALLS)}

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    config = uvicorn.Config(sink, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return f"http://127.0.0.1:{port}/sink", thread
        except OSError:
            time.sleep(0.05)
    raise RuntimeError("sink did not start")


def record_case(client: TestClient, name: str, request: dict[str, Any], receipt_id: str | None, sink_url: str, expected: str) -> dict[str, Any]:
    if receipt_id:
        response = client.post(
            "/v1/broker/execute",
            params={"receipt_id": receipt_id, "execution_webhook": sink_url},
            json=request,
        )
    else:
        response = None
    body = response.json() if response is not None else {"adapter_rejected": True}
    return {"name": name, "request": request, "response": body, "expected": expected}


STEMMA = build_stemma()
SINK_URL, _ = start_sink()
CASES: list[dict[str, Any]] = []

with TestClient(app) as client:
    adapter_facts = trusted_adapter(STEMMA)
    original_request = action_request(adapter_facts)
    evaluate_response = client.post("/v1/attested/evaluate", json=original_request)
    evaluate_body = evaluate_response.json()
    receipt = evaluate_body["receipt"]
    receipt_id = receipt["receipt_id"]
    first_execution = client.post(
        "/v1/broker/execute",
        params={"receipt_id": receipt_id, "execution_webhook": SINK_URL},
        json=original_request,
    )

    CASES.append({
        "name": "baseline",
        "stemma": STEMMA,
        "adapter_facts": adapter_facts,
        "request": original_request,
        "evaluate_response": evaluate_body,
        "execution_response": first_execution.json(),
        "expected": "authorized and executed once in local sink",
    })

    # Fresh receipts are used for each binding mutation so replay state does not
    # mask the binding failure.
    variants = [
        ("changed_result_hash", {"indepora_result_hash": "fabricated-result-hash"}, "action_binding_mismatch"),
        ("changed_evidence_refs", {"_evidence_refs": ["ev-001", "ev-002", "ev-999"]}, "action_binding_mismatch"),
        ("changed_action_parameters", {"decision_parameters": {"publication_label": "changed", "amount": 999}}, "action_binding_mismatch"),
    ]
    for name, mutation, expected in variants:
        facts = copy.deepcopy(adapter_facts)
        req = action_request(facts)
        if "_evidence_refs" in mutation:
            req["evidence_refs"] = mutation.pop("_evidence_refs")
        req["payload"].update(mutation)
        fresh = client.post("/v1/attested/evaluate", json=original_request).json()
        fresh_id = fresh["receipt"]["receipt_id"]
        CASES.append(record_case(client, name, req, fresh_id, SINK_URL, expected))

    # Adapter catches fabricated claims before Cyraduct.
    try:
        trusted_adapter(STEMMA, {"candidate_origin_count": 8})
        agent_claim_case = {"name": "agent_claims_8_independent", "unexpected": "accepted"}
    except ValueError as exc:
        agent_claim_case = {
            "name": "agent_claims_8_independent",
            "adapter_response": {"accepted": False, "reason": str(exc)},
            "expected": "trusted adapter rejects before Cyraduct",
        }
    CASES.append(agent_claim_case)

    try:
        tampered = copy.deepcopy(STEMMA)
        tampered["lineage"]["unknown_relationship_count"] = 0
        trusted_adapter(tampered)
        unknown_case = {"name": "unknown_replaced_with_independent", "unexpected": "accepted"}
    except ValueError as exc:
        unknown_case = {
            "name": "unknown_replaced_with_independent",
            "adapter_response": {"accepted": False, "reason": str(exc)},
            "expected": "tampered Stemma rejected by integrity check",
        }
    CASES.append(unknown_case)

    # Replay is tested using the baseline receipt after its successful call.
    replay = client.post(
        "/v1/broker/execute",
        params={"receipt_id": receipt_id, "execution_webhook": SINK_URL},
        json=original_request,
    )
    CASES.append({"name": "receipt_replay", "response": replay.json(), "expected": "receipt_already_consumed"})

    second_request = action_request(adapter_facts, {"decision_parameters": {"publication_label": "second-action", "amount": 2}})
    second_eval = client.post("/v1/attested/evaluate", json=second_request).json()
    second_exec = client.post(
        "/v1/broker/execute",
        params={"receipt_id": second_eval["receipt"]["receipt_id"], "execution_webhook": SINK_URL},
        json=second_request,
    )
    CASES.append({"name": "same_evidence_different_parameters", "request": second_request, "evaluate_response": second_eval, "execution_response": second_exec.json(), "expected": "new action has a different action hash and can be authorized independently"})

report = {
    "experiment": "indepora-cyraduct-boundary-sandbox-v1",
    "scope": "synthetic local-only; no production data or external sink",
    "stemma_conclusion": STEMMA["charter"]["conclusion"],
    "stemma_lineage": STEMMA["lineage"],
    "sink_calls": SINK_CALLS,
    "cases": CASES,
}
output = ROOT / "experiments/indepora_cyraduct_sandbox_report.json"
output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
print(json.dumps({"report": str(output), "sink_calls": len(SINK_CALLS), "cases": [c["name"] for c in CASES]}, indent=2))
