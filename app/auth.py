"""
Scoped authentication for admin-gated endpoints.

Two distinct credential tiers exist:

  1. Full admin key (CYRADUCT_ADMIN_KEY) — unrestricted. Can revoke any
     receipt, toggle the kill switch, read the full audit log. Intended
     for human operators only.

  2. Test key (CYRADUCT_TEST_ADMIN_KEY) — restricted. Can revoke receipts
     and read audit entries ONLY within the test namespace (agent_id
     starting with TEST_AGENT_PREFIX). Cannot touch the kill switch under
     any circumstance. Intended for external adversarial test harnesses.

Cyraduct has no separate staging environment — api.cyraduct.com is the
only environment that exists. This module is what makes it possible to
hand real API access to an external tester without giving them control
over the live service real callers depend on.
"""
from typing import Optional
from fastapi import HTTPException

from . import config


class AuthResult:
    def __init__(self, is_full_admin: bool, is_test_key: bool):
        self.is_full_admin = is_full_admin
        self.is_test_key = is_test_key

    @property
    def authenticated(self) -> bool:
        return self.is_full_admin or self.is_test_key


def check_admin_or_test_key(provided_key: Optional[str]) -> AuthResult:
    """Returns which tier (if any) the provided key matches. Does not
    raise — callers decide what each tier is allowed to do."""
    if not provided_key:
        return AuthResult(False, False)
    if provided_key == config.ADMIN_API_KEY:
        return AuthResult(True, False)
    if config.TEST_ADMIN_KEY and provided_key == config.TEST_ADMIN_KEY:
        return AuthResult(False, True)
    return AuthResult(False, False)


def require_full_admin(provided_key: Optional[str]):
    """For endpoints a test key must NEVER be able to reach — the kill
    switch, above all. Raises 401/403 rather than returning a result,
    since there's nothing a caller can do with a partial result here."""
    result = check_admin_or_test_key(provided_key)
    if not result.authenticated:
        raise HTTPException(status_code=401, detail="Invalid or missing admin key")
    if not result.is_full_admin:
        raise HTTPException(status_code=403, detail="This operation requires the full admin key; a test key is not sufficient")


def is_test_namespace(agent_id: str) -> bool:
    return agent_id.startswith(config.TEST_AGENT_PREFIX)


def require_admin_or_scoped_test(provided_key: Optional[str], target_agent_id: str):
    """For endpoints that a test key MAY reach, but only within the test
    namespace. A full admin key always passes. A test key passes only if
    target_agent_id is in the test namespace."""
    result = check_admin_or_test_key(provided_key)
    if not result.authenticated:
        raise HTTPException(status_code=401, detail="Invalid or missing admin/test key")
    if result.is_full_admin:
        return
    # test key: must be operating within the test namespace
    if not is_test_namespace(target_agent_id):
        raise HTTPException(
            status_code=403,
            detail=f"Test key may only act on agents prefixed '{config.TEST_AGENT_PREFIX}' — "
                   f"'{target_agent_id}' is outside the test namespace",
        )
