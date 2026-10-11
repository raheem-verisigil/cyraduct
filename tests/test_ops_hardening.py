"""Production boot safety, partner email delivery, conditional-receipt hold, audit-head
truncation detection, backups, sink guard and the pre-deploy checker."""
import base64
import os
import sqlite3
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "examples"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

import backup_postgres as bp
import check_production_env as cpe
import sink_guard
from app import config, partner_notification as pn, storage
from app.rate_limit import limiter
from main import app

client = TestClient(app)
ADMIN = {"X-Cyraduct-Admin-Key": "dev-insecure-admin-key"}
DOMAIN = "@ops-test.example"


class Resp:
    def __init__(self, code=200): self.status_code = code
    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=httpx.Request("POST", pn.RESEND_URL), response=httpx.Response(self.status_code))


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    limiter.reset()
    for k in ("RESEND_API_KEY", "PARTNER_NOTIFICATION_FROM", "PARTNER_NOTIFICATION_TO"):
        monkeypatch.delenv(k, raising=False)
    yield
    with storage._engine.begin() as conn:
        conn.execute(delete(storage.partners_table).where(storage.partners_table.c.email.like(f"%{DOMAIN}")))


def lead(n="a", **over):
    d = dict(name="Ada Lovelace", company="Analytical Engines", email=f"{n}{DOMAIN}", role="CTO",
             partner_type="AI Platform", message="We want to evaluate action-bound receipts in our platform.")
    d.update(over); return d


def row(n):
    with storage._engine.begin() as conn:
        return conn.execute(select(storage.partners_table).where(storage.partners_table.c.email == f"{n}{DOMAIN}")).mappings().first()


def configure(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test"); monkeypatch.setenv("PARTNER_NOTIFICATION_FROM", "Cyraduct <notifications@cyraduct.com>")


# ------------------------------------------------------------ production boot
def _boot(tmp_path, **env):
    base = {k: v for k, v in os.environ.items() if not k.startswith(("CYRADUCT", "RAILWAY", "RESEND", "PARTNER"))}
    base.update(env); base["CYRADUCT_DATABASE_URL"] = f"sqlite:///{tmp_path / 'boot.db'}"
    base["CYRADUCT_PRIVATE_KEY_PATH"] = str(tmp_path / "k.pem")
    p = subprocess.run([sys.executable, "-W", "ignore", "-c", "import main"], capture_output=True, text=True, env=base, cwd=ROOT)
    return p.returncode, p.stderr


def _real_key():
    raw = Ed25519PrivateKey.generate().private_bytes(
        serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    return base64.b64encode(raw).decode()


def test_production_boots_without_the_unused_signing_secret(tmp_path):
    rc, err = _boot(tmp_path, CYRADUCT_ENV="production", CYRADUCT_ADMIN_KEY="a" * 40, CYRADUCT_PRIVATE_KEY_B64=_real_key())
    assert rc == 0, err[-400:]


def test_production_still_refuses_default_admin_key_and_missing_private_key(tmp_path):
    rc, err = _boot(tmp_path, CYRADUCT_ENV="production")
    assert rc != 0 and "CYRADUCT_ADMIN_KEY" in err
    rc, err = _boot(tmp_path, CYRADUCT_ENV="production", CYRADUCT_ADMIN_KEY="a" * 40)
    assert rc != 0 and "CYRADUCT_PRIVATE_KEY_B64" in err


def test_railway_is_production_even_without_cyraduct_env(tmp_path):
    rc, err = _boot(tmp_path, RAILWAY_ENVIRONMENT="production")
    assert rc != 0 and "CYRADUCT_ADMIN_KEY" in err
    rc, err = _boot(tmp_path, RAILWAY_ENVIRONMENT="production", CYRADUCT_ADMIN_KEY="a" * 40, CYRADUCT_PRIVATE_KEY_B64=_real_key())
    assert rc == 0, err[-400:]


def test_explicit_environment_overrides_railway_detection(tmp_path):
    rc, err = _boot(tmp_path, RAILWAY_ENVIRONMENT="pr-123", CYRADUCT_ENV="development")
    assert rc == 0, err[-400:]


def test_environment_detection_function(monkeypatch):
    for k in ("CYRADUCT_ENV", "RAILWAY_ENVIRONMENT", "RAILWAY_ENVIRONMENT_NAME", "RAILWAY_PROJECT_ID"):
        monkeypatch.delenv(k, raising=False)
    assert config._detect_environment() == "development"
    monkeypatch.setenv("RAILWAY_PROJECT_ID", "p"); assert config._detect_environment() == "production"
    monkeypatch.setenv("CYRADUCT_ENV", "Staging"); assert config._detect_environment() == "staging"


# ------------------------------------------------------------ partner emails
def test_unconfigured_provider_stores_lead_and_marks_pending():
    assert client.post("/api/partners", json=lead("u")).status_code == 200
    r = row("u"); assert r["notification_status"] == "pending" and r["notification_error"] == "notification_provider_not_configured"


def test_delivery_to_hello_with_reply_to_in_background(monkeypatch):
    configure(monkeypatch)
    with patch("app.partner_notification.httpx.post", return_value=Resp(200)) as post:
        assert client.post("/api/partners", json=lead("s")).status_code == 200
    j = post.call_args.kwargs["json"]
    assert j["to"] == ["hello@cyraduct.com"] and j["reply_to"] == [f"s{DOMAIN}"]
    assert "Analytical Engines" in j["subject"] and "action-bound receipts" in j["text"]
    r = row("s"); assert r["notification_status"] == "sent" and r["notified_at"] and r["notification_error"] is None


def test_recipient_is_configurable(monkeypatch):
    configure(monkeypatch); monkeypatch.setenv("PARTNER_NOTIFICATION_TO", "founder@cyraduct.com")
    with patch("app.partner_notification.httpx.post", return_value=Resp(200)) as post:
        client.post("/api/partners", json=lead("c"))
    assert post.call_args.kwargs["json"]["to"] == ["founder@cyraduct.com"]


def test_header_injection_cannot_add_recipients_or_headers(monkeypatch):
    configure(monkeypatch)
    with patch("app.partner_notification.httpx.post", return_value=Resp(200)) as post:
        client.post("/api/partners", json=lead("i", company="Evil\r\nBcc: x@evil.test", partner_type="R\nSubject: pwned"))
    j = post.call_args.kwargs["json"]
    assert "\n" not in j["subject"] and "\r" not in j["subject"]
    assert j["to"] == ["hello@cyraduct.com"] and "bcc" not in j and "cc" not in j


def test_bad_reply_to_is_dropped(monkeypatch):
    configure(monkeypatch)
    with patch("app.partner_notification.httpx.post", return_value=Resp(200)) as post:
        assert pn.send_email("s", "b", reply_to="a@b.test, c@d.test")[0] == "sent"
    assert "reply_to" not in post.call_args.kwargs["json"]


def test_provider_failure_never_fails_visitor_and_is_marked_failed(monkeypatch):
    configure(monkeypatch)
    with patch("app.partner_notification.httpx.post", return_value=Resp(500)):
        assert client.post("/api/partners", json=lead("f")).status_code == 200
    r = row("f"); assert r["notification_status"] == "failed" and "HTTPStatusError" in r["notification_error"]
    with patch("app.partner_notification.httpx.post", side_effect=httpx.ConnectError("boom")):
        assert client.post("/api/partners", json=lead("g")).status_code == 200
    assert row("g")["notification_status"] == "failed"


def test_failed_and_pending_leads_can_be_retried_by_admin(monkeypatch):
    client.post("/api/partners", json=lead("p"))                       # pending (not configured)
    configure(monkeypatch)
    with patch("app.partner_notification.httpx.post", return_value=Resp(500)):
        client.post("/api/partners", json=lead("q"))                   # failed
    assert client.post("/api/partners/retry-notifications").status_code == 401
    with patch("app.partner_notification.httpx.post", return_value=Resp(200)):
        for _ in range(6):
            client.post("/api/partners/retry-notifications", headers=ADMIN)
            if row("p")["notification_status"] == row("q")["notification_status"] == "sent":
                break
    assert row("p")["notification_status"] == "sent" and row("q")["notification_status"] == "sent"


def test_admin_endpoints_require_the_full_admin_key(monkeypatch):
    monkeypatch.setattr(config, "TEST_ADMIN_KEY", "scoped-test-key")
    scoped = {"X-Cyraduct-Admin-Key": "scoped-test-key"}
    for method, path in (("get", "/api/partners/notifications"), ("post", "/api/partners/notifications/test"),
                         ("post", "/api/partners/retry-notifications"), ("get", "/api/partners")):
        assert getattr(client, method)(path).status_code == 401
        assert getattr(client, method)(path, headers=scoped).status_code == 403


def test_test_email_and_health_report(monkeypatch):
    r = client.post("/api/partners/notifications/test", headers=ADMIN).json()
    assert r["status"] == "pending" and r["notify_to"] == "hello@cyraduct.com"
    configure(monkeypatch)
    with patch("app.partner_notification.httpx.post", return_value=Resp(200)):
        assert client.post("/api/partners/notifications/test", headers=ADMIN).json()["status"] == "sent"
    h = client.get("/api/partners/notifications", headers=ADMIN).json()
    assert h["configured"] is True and h["notify_to"] == "hello@cyraduct.com" and "re_test" not in str(h)


def test_kill_switch_change_sends_alert(monkeypatch):
    seen = []
    monkeypatch.setattr(pn, "send_email", lambda subject, body, reply_to=None: seen.append(subject) or ("sent", None))
    try:
        assert client.post("/v1/admin/kill-switch", headers=ADMIN, json={"active": True, "reason": "drill"}).status_code == 200
        assert any("Kill switch ACTIVATED" in s for s in seen)
    finally:
        client.post("/v1/admin/kill-switch", headers=ADMIN, json={"active": False, "reason": "drill over"})


# ------------------------------------------------- conditional receipts + sink
def _conditional():
    req = dict(agent_id="test-cond", action_type="wire_transfer", consequence_class="financial_transfer",
               purpose="payroll", policy_pack="generic", payload={"amount": 75000})
    r = client.post("/v1/attested/evaluate", json=req).json()
    assert r["decision"]["decision"] == "conditional"
    return req, r["receipt"]


def test_broker_refuses_conditional_without_burning_receipt():
    req, rc = _conditional()
    with patch("app.routers.broker.httpx.AsyncClient") as sink:
        sink.return_value.__aenter__ = AsyncMock()
        b = client.post("/v1/broker/execute", json=req,
                        params={"receipt_id": rc["receipt_id"], "execution_webhook": "https://example.com/sink"}).json()
        sink.assert_not_called()
    assert b["executed"] is False and b["reason"] == "conditional_receipt_requires_human_approval"
    assert storage.get_receipt(rc["receipt_id"]).consumed_at is None
    log = client.get("/v1/admin/audit-log", headers=ADMIN, params={"limit": 1000000}).json()["entries"]
    assert any(e["event_type"] == "broker_blocked_conditional_requires_human" for e in log)


def test_sink_guard_conditional_hold():
    _, cond = _conditional()
    pk = client.get("/v1/public-key").json()["public_key_b64"]
    with pytest.raises(ValueError, match="human approval"):
        sink_guard.require_receipt(cond, pk)
    sink_guard.require_receipt(cond, pk, allow_conditional=True)
    ok = client.post("/v1/attested/evaluate", json=dict(agent_id="test-ok", action_type="read_public_doc",
                     consequence_class="low_risk", policy_pack="generic", payload={})).json()["receipt"]
    sink_guard.require_receipt(ok, pk)


# --------------------------------------------------------- audit tail deletion
def _db_path():
    return storage._engine.url.database


def test_deleting_newest_audit_entries_is_detected():
    for i in range(3): storage.append_audit("ops_test", {"agent_id": f"a{i}"})
    assert storage.verify_audit_chain() is True
    con = sqlite3.connect(_db_path()); cur = con.cursor()
    seqs = [r[0] for r in cur.execute("select seq from audit_log order by seq desc limit 2")]
    saved = [cur.execute("select * from audit_log where seq=?", (s,)).fetchone() for s in seqs]
    cur.executemany("delete from audit_log where seq=?", [(s,) for s in seqs]); con.commit()
    try:
        assert storage.verify_audit_chain() is False       # chain alone would still say True
    finally:
        cur.executemany("insert into audit_log values (?,?,?,?,?,?)", saved); con.commit(); con.close()
    assert storage.verify_audit_chain() is True


def test_audit_head_adopts_existing_log_and_follows_new_appends():
    con = sqlite3.connect(_db_path()); con.execute("delete from audit_head"); con.commit(); con.close()
    assert storage.verify_audit_chain() is True            # no head yet: not flagged
    storage.init_db()                                       # startup adopts the current last row
    con = sqlite3.connect(_db_path())
    assert con.execute("select count(*) from audit_head").fetchone()[0] == 1; con.close()
    storage.append_audit("ops_test", {"agent_id": "z"})
    assert storage.verify_audit_chain() is True


def test_backup_carries_leads_and_audit_head_together():
    client.post("/api/partners", json=lead("b"))
    dump = bp.dump_all_tables()
    assert any(p["email"] == f"b{DOMAIN}" for p in dump["tables"]["partners"])
    assert dump["tables"]["audit_head"], "audit_head must be backed up with audit_log"


# ------------------------------------------------------------------ checker
GOOD = {"CYRADUCT_ENV": "production", "CYRADUCT_ADMIN_KEY": "k" * 40, "CYRADUCT_PRIVATE_KEY_B64": base64.b64encode(b"\x01" * 32).decode(),
        "CYRADUCT_DATABASE_URL": "postgresql://u:p@h/db", "RESEND_API_KEY": "re_x",
        "PARTNER_NOTIFICATION_FROM": "Cyraduct <notifications@cyraduct.com>", "CYRADUCT_AUDIT_ANCHOR_URL": "https://a.example"}


def levels(env): return [lv for lv, _ in cpe.run_checks(env)]


def test_checker_passes_a_complete_production_config():
    out = cpe.run_checks(GOOD)
    assert "FAIL" not in levels(GOOD) and "WARN" not in levels(GOOD)
    assert "k" * 40 not in str(out) and "re_x" not in str(out)


def test_checker_flags_what_would_break_boot():
    assert "FAIL" in levels({**GOOD, "CYRADUCT_ADMIN_KEY": "dev-insecure-admin-key"})
    assert "FAIL" in levels({k: v for k, v in GOOD.items() if k != "CYRADUCT_PRIVATE_KEY_B64"})
    assert "FAIL" in levels({**GOOD, "CYRADUCT_PRIVATE_KEY_B64": "not base64!!"})
    assert "FAIL" in levels({**GOOD, "CYRADUCT_PRIVATE_KEY_B64": base64.b64encode(b"short").decode()})
    assert "FAIL" in levels({**GOOD, "CYRADUCT_ALLOWED_ORIGINS": "*"})


def test_checker_warns_but_does_not_fail_for_email_db_anchor():
    weak = {k: v for k, v in GOOD.items() if k not in ("RESEND_API_KEY", "CYRADUCT_AUDIT_ANCHOR_URL", "CYRADUCT_DATABASE_URL")}
    lv = levels(weak); assert "FAIL" not in lv and lv.count("WARN") == 3


def test_checker_does_not_require_signing_secret():
    assert "FAIL" not in levels(GOOD) and "CYRADUCT_SIGNING_SECRET" not in str(cpe.run_checks(GOOD))
