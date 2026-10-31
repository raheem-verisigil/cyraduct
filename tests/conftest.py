"""Test isolation for the shared SlowAPI limiter.

The application intentionally shares one limiter across routers. Its in-memory
storage is process-global, so tests must reset that storage between test cases.
This keeps the production limits intact while preventing one test module's
synthetic traffic from exhausting another module's quota.
"""
import pytest


@pytest.fixture(autouse=True)
def reset_rate_limit_storage_between_tests():
    from app.rate_limit import limiter

    limiter._storage.reset()
    yield
    limiter._storage.reset()
