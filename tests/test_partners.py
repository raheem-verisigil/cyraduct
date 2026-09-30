from main import app
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app import storage

client = TestClient(app)


def test_partner_submission_is_validated_and_persisted():
    payload = {
        "name": "Ada Lovelace",
        "company": "Analytical Engines",
        "email": "ada@example.com",
        "role": "CTO",
        "partner_type": "AI Platform",
        "message": "We want to evaluate action-bound receipts in our agent platform.",
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
