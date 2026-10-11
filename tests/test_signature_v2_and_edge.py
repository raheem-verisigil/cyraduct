"""Receipt signature v2, client-IP rate limiting, CORS origins and Railway config."""
import copy
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "examples"))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, text

import sink_guard
import verify_receipt as standalone
from app import receipts, storage
from app.rate_limit import client_key, limiter
from main import app

client = TestClient(app)
DOMAIN = "@edge-test.example"


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    limiter.reset()
    for k in ("CYRADUCT_CLIENT_IP_HEADER", "RAILWAY_ENVIRONMENT", "RAILWAY_ENVIRONMENT_NAME", "RAILWAY_PROJECT_ID"):
        monkeypatch.delenv(k, raising=False)
    yield
    limiter.reset()
    with storage._engine.begin() as conn:
        conn.execute(delete(storage.partners_table).where(storage.partners_table.c.email.like(f"%{DOMAIN}")))


def pubkey():
    return client.get("/v1/public-key").json()["public_key_b64"]


def policy_receipt(**over):
    req = dict(agent_id="test-v2", action_type="wire_transfer", consequence_class="financial_transfer",
               purpose="payroll", policy_pack="generic", payload={"amount": 75000})
    req.update(over)
    r = client.post("/v1/attested/evaluate", json=req).json()
    return client.get("/v1/receipts/" + r["receipt"]["receipt_id"]).json()   # the JSON verifiers actually get


def runtime_receipt():
    body = {"agent_id": "test-v2-runtime", "action_type": "update_customer_record", "consequence_class": "generic_tool_call",
            "target": "crm", "resource": "customer/123", "reversibility": "reversible", "authority": "present",
            "authorized_state_version": "s1", "current_state_version": "s1", "policy_pack": "generic",
            "purpose": "sync", "payload": {"field": "phone"}, "runtime_state": {}}
    r = client.post("/v1/runtime/evaluate", json=body).json()
    return client.get("/v1/receipts/" + r["authorization"]["receipt_id"]).json()


# ------------------------------------------------------------ v2 signature
def test_new_receipts_carry_both_signatures_and_verify_everywhere():
    for rc in (policy_receipt(), runtime_receipt()):
        assert rc["signature_v2"]["alg"] == "Ed25519" and rc["signature_v2"]["key_id"] == rc["signature"]["key_id"]
        ok, why = standalone.verify(rc, pubkey(), require_v2=True)
        assert ok, why
        stored = storage.get_receipt(rc["receipt_id"])
        assert receipts.verify_signature(stored)
        # independent re-implementation builds the same bytes the server signed
        assert standalone.v2_message(rc) == receipts.signature_message_v2(rc)


def test_sink_guard_accepts_a_valid_v2_receipt():
    ok = client.post("/v1/attested/evaluate", json=dict(agent_id="test-v2-ok", action_type="read_public_doc",
                     consequence_class="low_risk", policy_pack="generic", payload={})).json()["receipt"]
    sink_guard.require_receipt(ok, pubkey())


FORGERIES = {
    "decision conditional->allow": lambda r: r.update(decision="allow"),
    "agent id": lambda r: r["agent"].update(agent_id="someone-else"),
    "agent principal": lambda r: r["agent"].update(principal="org:attacker"),
    "agent framework": lambda r: r["agent"].update(framework="other"),
    "action type": lambda r: r["action"].update(type="read_public_doc"),
    "consequence class": lambda r: r["action"].update(consequence_class="low_risk"),
    "policy pack": lambda r: r["policy"].update(policy_pack="banking"),
    "policy pack version": lambda r: r["policy"].update(policy_pack_version="9.9.9"),
    "evidence assurance injected": lambda r: r.update(evidence_assurance={"standing": "independent"}),
    "issued_at": lambda r: r.update(issued_at="2020-01-01T00:00:00+00:00"),
    "prev_receipt_hash": lambda r: r.update(prev_receipt_hash="f" * 64),
    "v2 key id": lambda r: r["signature_v2"].update(key_id="other-key"),
}


@pytest.mark.parametrize("name", sorted(FORGERIES))
def test_forging_any_signed_field_is_detected_by_every_verifier(name):
    rc = policy_receipt()
    assert rc["decision"] == "conditional"
    forged = copy.deepcopy(rc); FORGERIES[name](forged)
    ok, why = standalone.verify(forged, pubkey(), require_v2=True)
    assert not ok
    if name != "prev_receipt_hash":      # that one is also covered by the legacy signature, which is checked first
        assert "v2" in why
    with pytest.raises(ValueError):
        sink_guard.require_receipt(forged, pubkey(), allow_conditional=True)


def test_forged_runtime_decision_is_detected():
    rc = runtime_receipt()
    forged = copy.deepcopy(rc); forged["runtime_decision"] = "hold"
    assert not standalone.verify(forged, pubkey(), require_v2=True)[0]


def test_decision_flip_that_the_legacy_signature_missed_is_now_caught():
    rc = policy_receipt()
    forged = copy.deepcopy(rc); forged["decision"] = "allow"
    # the legacy signature alone cannot see this change (that was the defect)
    assert standalone._check(pubkey(), forged["signature"]["value"], standalone.v1_message(forged))
    # the v2 signature can
    assert not standalone._check(pubkey(), forged["signature_v2"]["value"], standalone.v2_message(forged))
    assert standalone.verify(forged, pubkey())[0] is False


def test_stripping_v2_is_a_downgrade_and_strict_verifiers_refuse_it():
    rc = policy_receipt()
    stripped = copy.deepcopy(rc); stripped["decision"] = "allow"; del stripped["signature_v2"]
    assert standalone.verify(stripped, pubkey())[0] is True                      # legacy verifiers are blind to it
    assert standalone.verify(stripped, pubkey(), require_v2=True)[0] is False    # strict mode is not
    with pytest.raises(ValueError, match="no v2 signature"):
        sink_guard.require_receipt(stripped, pubkey(), allow_conditional=True)
    sink_guard.require_receipt(stripped, pubkey(), allow_conditional=True, allow_legacy=True)  # explicit opt-in only


def test_conditional_hold_in_the_sink_is_now_sound():
    rc = policy_receipt()
    with pytest.raises(ValueError, match="human approval"):
        sink_guard.require_receipt(rc, pubkey())
    sink_guard.require_receipt(rc, pubkey(), allow_conditional=True)


def test_receipts_stored_before_v2_still_verify_on_the_server():
    rc = policy_receipt()
    with storage._engine.begin() as conn:
        data = json.loads(conn.execute(text("select data from receipts where receipt_id=:i"), {"i": rc["receipt_id"]}).scalar())
        data.pop("signature_v2")
        conn.execute(text("update receipts set data=:d where receipt_id=:i"), {"d": json.dumps(data), "i": rc["receipt_id"]})
    legacy = storage.get_receipt(rc["receipt_id"])
    assert legacy.signature_v2 is None and receipts.verify_signature(legacy)
    v = client.get("/v1/attested/verify/" + rc["receipt_id"]).json()
    assert v["valid"] is True


def test_server_rejects_a_stored_receipt_whose_decision_was_altered():
    rc = policy_receipt()
    with storage._engine.begin() as conn:
        data = json.loads(conn.execute(text("select data from receipts where receipt_id=:i"), {"i": rc["receipt_id"]}).scalar())
        data["decision"] = "allow"
        conn.execute(text("update receipts set data=:d where receipt_id=:i"), {"d": json.dumps(data), "i": rc["receipt_id"]})
    assert client.get("/v1/attested/verify/" + rc["receipt_id"]).json()["valid"] is False


# ------------------------------------------------------- client-ip rate limit
def _post_lead(i, headers=None):
    return client.post("/api/partners", headers=headers or {}, json=dict(
        name="Ada", company="Edge Co", email=f"edge{i}{DOMAIN}", partner_type="Research",
        message="rate limit probe for the partner form."))


def test_header_is_ignored_off_railway_so_it_cannot_be_spoofed():
    codes = [_post_lead(i, {"X-Real-IP": f"203.0.113.{i}"}).status_code for i in range(7)]
    assert codes[:5] == [200] * 5 and 429 in codes[5:]


def test_on_railway_each_real_client_gets_its_own_quota(monkeypatch):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    assert all(_post_lead(i, {"X-Real-IP": f"203.0.113.{i}"}).status_code == 200 for i in range(7))
    codes = [_post_lead(100 + i, {"X-Real-IP": "198.51.100.9"}).status_code for i in range(7)]
    assert codes[:5] == [200] * 5 and 429 in codes[5:]


def test_bad_header_value_falls_back_to_the_peer(monkeypatch):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    codes = [_post_lead(200 + i, {"X-Real-IP": "not-an-ip"}).status_code for i in range(7)]
    assert 429 in codes


def test_custom_header_name_for_other_proxies(monkeypatch):
    monkeypatch.setenv("CYRADUCT_CLIENT_IP_HEADER", "CF-Connecting-IP")
    assert all(_post_lead(300 + i, {"CF-Connecting-IP": f"2001:db8::{i + 1}"}).status_code == 200 for i in range(7))


def test_client_key_unit(monkeypatch):
    class Req:
        def __init__(self, h): self.headers = h; self.client = type("C", (), {"host": "10.0.0.1"})()
    assert client_key(Req({"x-real-ip": "1.2.3.4"})) == "10.0.0.1"
    monkeypatch.setenv("RAILWAY_PROJECT_ID", "p")
    assert client_key(Req({"x-real-ip": "1.2.3.4, 9.9.9.9"})) == "1.2.3.4"
    assert client_key(Req({})) == "10.0.0.1"


# ----------------------------------------------------------------------- CORS
def _preflight(origin, **env):
    base = {k: v for k, v in os.environ.items() if not k.startswith(("CYRADUCT", "RAILWAY"))}
    base.update(env); base["CYRADUCT_DATABASE_URL"] = "sqlite:///" + os.path.join(ROOT, ".cors_probe.db")
    code = ("import warnings; warnings.filterwarnings('ignore')\n"
            "from fastapi.testclient import TestClient; import main\n"
            f"r=TestClient(main.app).options('/api/partners', headers={{'Origin': {origin!r}, 'Access-Control-Request-Method': 'POST'}})\n"
            "print(r.headers.get('access-control-allow-origin'))")
    try:
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=base, cwd=ROOT)
        return out.stdout.strip().splitlines()[-1]
    finally:
        for f in (".cors_probe.db",):
            p = os.path.join(ROOT, f)
            if os.path.exists(p): os.remove(p)


def test_cors_allows_apex_and_www_by_default_and_nothing_else():
    assert _preflight("https://cyraduct.com") == "https://cyraduct.com"
    assert _preflight("https://www.cyraduct.com") == "https://www.cyraduct.com"
    assert _preflight("https://evil.example") == "None"


def test_cors_env_overrides_and_regex():
    assert _preflight("https://staging.cyraduct.dev", CYRADUCT_ALLOWED_ORIGINS="https://staging.cyraduct.dev") == "https://staging.cyraduct.dev"
    assert _preflight("https://cyraduct.com", CYRADUCT_ALLOWED_ORIGINS="https://staging.cyraduct.dev") == "None"
    rx = r"https://preview-[a-z0-9]+\.example\.app"
    assert _preflight("https://preview-ab12.example.app", CYRADUCT_ALLOWED_ORIGIN_REGEX=rx) == "https://preview-ab12.example.app"
    assert _preflight("https://preview-ab12.example.app.evil.com", CYRADUCT_ALLOWED_ORIGIN_REGEX=rx) == "None"


# ------------------------------------------------------------- Railway config
def test_railway_start_command_matches_procfile_and_gates_deploys_on_health():
    procfile = open(os.path.join(ROOT, "Procfile")).read().strip().removeprefix("web:").strip()
    cfg = json.load(open(os.path.join(ROOT, "railway.json")))["deploy"]
    assert cfg["startCommand"] == procfile
    assert "--proxy-headers" in procfile and "--forwarded-allow-ips='*'" in procfile
    assert cfg["healthcheckPath"] == "/healthz" and cfg["healthcheckTimeout"] >= 30
    assert client.get("/healthz").status_code == 200


# ---------------------------------------------- demo verifier must not drift
def test_demo_guard_hash_and_v2_checks_match_the_server():
    sys.path.insert(0, os.path.join(ROOT, "demo", "poisoned_invoice"))
    import cyraduct_guard as guard
    req = dict(agent_id="test-guard", principal="org:demo:finance", framework="custom", action_type="wire_transfer",
               consequence_class="financial_transfer", purpose="payroll", jurisdiction="US",
               policy_pack="generic", payload={"amount": 75000, "payee": "Acme"})
    rc = client.post("/v1/attested/evaluate", json=req).json()["receipt"]
    assert rc["decision"] == "conditional"
    assert guard.action_hash(rc["action_id"], req) == rc["action_hash"]
    pk = pubkey()
    assert guard.verify_at_sink(rc, req, pk, None, human_approved=False) == (False, "conditional_receipt_requires_human_approval")
    assert guard.verify_at_sink(rc, req, pk, None, human_approved=True) == (True, "ok")
    forged = copy.deepcopy(rc); forged["decision"] = "allow"       # presenter flips the decision
    assert guard.verify_at_sink(forged, req, pk, None, human_approved=False)[0] is False
    legacy = copy.deepcopy(rc); legacy["decision"] = "allow"; del legacy["signature_v2"]
    assert guard.verify_at_sink(legacy, req, pk, None)[0] is False   # downgrade refused
