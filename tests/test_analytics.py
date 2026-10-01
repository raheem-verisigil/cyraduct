from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app import storage
from main import app

client = TestClient(app)


def test_analytics_event_accepts_allowlisted_properties():
    response = client.post(
        "/api/analytics/events",
        json={
            "event": "audience_route_click",
            "properties": {
                "audience": "finance_ap",
                "destination": "finance",
                "utm_campaign": "hospitality_routing",
            },
        },
    )
    assert response.status_code == 202
    assert response.json() == {"accepted": True}

    with storage._engine.begin() as conn:
        row = conn.execute(
            select(storage.analytics_events_table)
            .where(storage.analytics_events_table.c.event == "audience_route_click")
            .order_by(storage.analytics_events_table.c.created_at.desc())
        ).first()
        assert row is not None
        conn.execute(delete(storage.analytics_events_table).where(storage.analytics_events_table.c.id == row.id))


def test_analytics_event_rejects_unknown_properties():
    response = client.post(
        "/api/analytics/events",
        json={"event": "audience_route_click", "properties": {"email": "should-not-be-stored"}},
    )
    assert response.status_code == 422


def test_analytics_event_rejects_unknown_event():
    response = client.post(
        "/api/analytics/events",
        json={"event": "page_view", "properties": {}},
    )
    assert response.status_code == 422
