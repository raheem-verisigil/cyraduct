from main import app
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app import storage
from app import partner_notification

client = TestClient(app)


def test_partner_submission_is_validated_and_persisted():
    payload = {
        "name": "Ada Lovelace",
        "company": "Analytical Engines",
        "email": "ada@example.com",
        "role": "CTO",
        "partner_type": "AI Platform",
        "message": "We want to evaluate action-bound receipts in our agent platform.",
        "utm_source": "linkedin",
        "utm_campaign": "hospitality_routing",
        "utm_content": "finance_angle",
        "landing_path": "/",
    }
    response = client.post("/api/partners", json=payload)
    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "message": "Partnership request received",
    }

    with storage._engine.begin() as conn:
        row = conn.execute(
            select(storage.partners_table)
            .where(storage.partners_table.c.email == payload["email"])
            .order_by(storage.partners_table.c.created_at.desc())
        ).first()
    assert row is not None
    assert row.status == "new"
    assert row.company == payload["company"]
    assert row.utm_source == payload["utm_source"]
    assert row.utm_campaign == payload["utm_campaign"]
    assert row.utm_content == payload["utm_content"]

    with storage._engine.begin() as conn:
        conn.execute(delete(storage.partners_table).where(storage.partners_table.c.email == payload["email"]))


def test_partner_submission_requires_core_fields():
    response = client.post("/api/partners", json={"name": "Missing fields"})
    assert response.status_code == 422


def test_partner_submission_rejects_invalid_email():
    payload = {
        "name": "Ada Lovelace",
        "company": "Analytical Engines",
        "email": "not-an-email",
        "role": "CTO",
        "partner_type": "Research",
        "message": "A message with a useful partnership context.",
    }
    response = client.post("/api/partners", json=payload)
    assert response.status_code == 422


def test_partner_submission_notifies_and_is_visible_to_admin(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

    calls = []
    monkeypatch.setenv("RESEND_API_KEY", "test-resend-key")
    monkeypatch.setenv("PARTNER_NOTIFICATION_FROM", "Cyraduct <test@example.com>")
    monkeypatch.setattr(
        partner_notification.httpx,
        "post",
        lambda *args, **kwargs: (calls.append(kwargs) or Response()),
    )
    payload = {
        "name": "Grace Hopper", "company": "Compilers Inc", "email": "grace@example.com",
        "role": "Platform Lead", "partner_type": "Enterprise AI",
        "message": "We need a reviewable boundary for payment actions.",
    }
    response = client.post("/api/partners", json=payload)
    assert response.status_code == 200
    assert calls and calls[0]["json"]["to"] == ["hello@cyraduct.com"]

    rows = client.get("/api/partners", headers={"X-Cyraduct-Admin-Key": "dev-insecure-admin-key"})
    assert rows.status_code == 200
    record = next(item for item in rows.json()["items"] if item["email"] == payload["email"])
    assert record["notification_status"] == "sent"

    with storage._engine.begin() as conn:
        conn.execute(delete(storage.partners_table).where(storage.partners_table.c.email == payload["email"]))
