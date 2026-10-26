"""
Scoped authentication for admin-gated and service-to-service endpoints.
"""
from typing import Optional
import hmac
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
    """Returns which admin tier, if any, the provided key matches."""
    if not provided_key:
        return AuthResult(False, False)
    if config.ADMIN_API_KEY and hmac.compare_digest(provided_key, config.ADMIN_API_KEY):
        return AuthResult(True, False)
    if config.TEST_ADMIN_KEY and hmac.compare_digest(provided_key, config.TEST_ADMIN_KEY):
        return AuthResult(False, True)
    return AuthResult(False, False)


def require_service_key(provided_key: Optional[str], configured_key: str, setting_name: str) -> None:
    """Protect a service endpoint with its own key.

    In production, missing configuration fails closed with 503. When a key is
    configured, every environment requires a match. For local development only,
    an unset key leaves the endpoint usable so the reference app remains easy
    to run; production startup must configure the dedicated key.
    """
    if not configured_key:
        if config.ENVIRONMENT == "production":
            raise HTTPException(status_code=503, detail=f"{setting_name.lower()}_not_configured")
        return
    if not provided_key or not hmac.compare_digest(provided_key, configured_key):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


def require_full_admin(provided_key: Optional[str]):
    """Require the full admin key; a scoped test key is never sufficient."""
    result = check_admin_or_test_key(provided_key)
    if not result.authenticated:
        raise HTTPException(status_code=401, detail="Invalid or missing admin key")
    if not result.is_full_admin:
        raise HTTPException(status_code=403, detail="This operation requires the full admin key; a test key is not sufficient")


def is_test_namespace(agent_id: str) -> bool:
    return agent_id.startswith(config.TEST_AGENT_PREFIX)


def require_admin_or_scoped_test(provided_key: Optional[str], target_agent_id: str):
    """Full admin can act on any agent; test key is restricted to test namespace."""
    result = check_admin_or_test_key(provided_key)
    if not result.authenticated:
        raise HTTPException(status_code=401, detail="Invalid or missing admin/test key")
    if result.is_full_admin:
        return
    if not is_test_namespace(target_agent_id):
        raise HTTPException(
            status_code=403,
            detail=f"Test key may only act on agents prefixed '{config.TEST_AGENT_PREFIX}' — "
                   f"'{target_agent_id}' is outside the test namespace",
        )
