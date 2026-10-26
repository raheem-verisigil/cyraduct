"""
Cyraduct configuration.

Consequence-class expiry policy is a first-class, documented property of the
system (see positioning language: "staleness is a bounded property, not a
gap"). Do not let receipts default to indefinite validity.
"""
import os

ENVIRONMENT = os.environ.get("CYRADUCT_ENV", "development").lower()

# Signing secret for receipts. In production this MUST come from a secrets
# manager / environment variable, never committed to source.
SIGNING_SECRET = os.environ.get("CYRADUCT_SIGNING_SECRET", "dev-insecure-secret-change-me")

# Consequence classes and their receipt expiry, in seconds.
# Higher-consequence actions get shorter-lived receipts by default.
CONSEQUENCE_CLASS_EXPIRY_SECONDS = {
    "financial_transfer": 120,
    "infra_change": 3600,
    "health_record_access": 900,
    "generic_tool_call": 1800,
    "vendor_master_change": 900,
    "low_risk": 86400,
}

DEFAULT_EXPIRY_SECONDS = 600

# Storage backend. Defaults to local SQLite; override with DATABASE_URL for
# a real deployment (e.g. Railway Postgres plugin).
DATABASE_URL = os.environ.get("CYRADUCT_DATABASE_URL", "sqlite:///./cyraduct.db")

# Admin API key required to operate the kill switch. Must be overridden in
# any real deployment.
ADMIN_API_KEY = os.environ.get("CYRADUCT_ADMIN_KEY", "dev-insecure-admin-key")

# Separate credentials for endpoints that can mint runtime authorizations or
# trigger outbound execution webhooks. In production these endpoints fail
# closed until their dedicated keys are configured.
RUNTIME_API_KEY = os.environ.get("CYRADUCT_RUNTIME_API_KEY", "")
BROKER_API_KEY = os.environ.get("CYRADUCT_BROKER_API_KEY", "")

# Scoped test key: grants LIMITED admin-like capabilities, restricted to
# receipts/agents in the test namespace only (see TEST_AGENT_PREFIX below).
TEST_ADMIN_KEY = os.environ.get("CYRADUCT_TEST_ADMIN_KEY", "")
TEST_AGENT_PREFIX = os.environ.get("CYRADUCT_TEST_AGENT_PREFIX", "test-")

POLICY_PACK_DIR = os.environ.get("CYRADUCT_POLICY_DIR", "policy_packs")


def validate_startup() -> None:
    """Fail closed when a production process is using development secrets."""
    if ENVIRONMENT != "production":
        return
    if ADMIN_API_KEY in {"", "dev-insecure-admin-key"}:
        raise RuntimeError("CYRADUCT_ADMIN_KEY must be set to a non-default value in production")
    if SIGNING_SECRET in {"", "dev-insecure-secret-change-me"}:
        raise RuntimeError("CYRADUCT_SIGNING_SECRET must be set to a non-default value in production")
    if not os.environ.get("CYRADUCT_PRIVATE_KEY_B64"):
        raise RuntimeError("CYRADUCT_PRIVATE_KEY_B64 must be set in production")
