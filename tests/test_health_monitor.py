"""Regression tests for health-check endpoints used by uptime monitors."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_healthz_get_returns_ok():
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_healthz_head_returns_ok_for_monitors():
    response = client.head("/healthz")
    assert response.status_code == 200
    assert response.content == b""
