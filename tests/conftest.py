"""Shared test fixtures for deterministic, isolated API rate-limit tests.

FastAPI TestClient requests share the same simulated remote address. SlowAPI
therefore sees requests from separate tests as one client unless its storage is
reset between tests. Reset only the limiter's test-process storage; production
rate-limit behaviour and the dedicated per-test limit assertions remain intact.
"""
from pathlib import Path
import sys

# Make the repository root importable when pytest loads this conftest before
# individual test modules have adjusted sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app.rate_limit import limiter


@pytest.fixture(autouse=True)
def isolate_rate_limit_storage():
    """Prevent one test's request budget from leaking into another test."""
    limiter._storage.reset()
    yield
    limiter._storage.reset()
