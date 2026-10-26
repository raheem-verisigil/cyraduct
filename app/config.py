"""
Cyraduct configuration.

Production startup validation is intentionally fail-closed: a service must
not boot with development credentials, an ephemeral signing identity, or a
local SQLite database that may lose authorization records on redeploy.
"""
import base64
import binascii
import os

ENVIRONMENT = os.environ.get("CYRADUCT_ENV", "development").lower()

SIGNING_SECRET = os.environ.get("CYRADUCT_SIGNING_SECRET", "dev-insecure-secret-change-me")

CONSEQUENCE_CLASS_EXPIRY_SECONDS = {
    "financial_transfer": 120,
    "infra_change": 3600,
    "health_record_access": 900,
    "generic_tool_call": 1800,
    "vendor_master_change": 900,
    "low_risk": 86400,
}
DEFAULT_EXPIRY_SECONDS = 600

DATABASE_URL = os.environ.get("CYRADUCT_DATABASE_URL", "sqlite:///./cyraduct.db")
ADMIN_API_KEY = os.environ.get("CYRADUCT_ADMIN_KEY", "dev-insecure-admin-key")
BROKER_API_KEY = os.environ.get("CYRADUCT_BROKER_API_KEY", "")
BROKER_ALLOWED_HOSTS = {host.strip().lower() for host in os.environ.get("CYRADUCT_BROKER_ALLOWED_HOSTS", "").split(",") if host.strip()}
TEST_ADMIN_KEY = os.environ.get("CYRADUCT_TEST_ADMIN_KEY", "")
TEST_AGENT_PREFIX = os.environ.get("CYRADUCT_TEST_AGENT_PREFIX", "test-")
POLICY_PACK_DIR = os.environ.get("CYRADUCT_POLICY_DIR", "policy_packs")


def validate_startup() -> None:
    """Reject unsafe production configuration before serving requests.

    The Ed25519 private key must be a base64-encoded 32-byte raw private key.
    Production must use PostgreSQL (or a compatible PostgreSQL SQLAlchemy URL)
    so authorization records survive restarts and redeploys.
    """
    if ENVIRONMENT != "production":
        return

    if ADMIN_API_KEY in {"", "dev-insecure-admin-key"} or len(ADMIN_API_KEY) < 32:
        raise RuntimeError("CYRADUCT_ADMIN_KEY must be a unique secret of at least 32 characters in production")

    if SIGNING_SECRET in {"", "dev-insecure-secret-change-me"} or len(SIGNING_SECRET) < 32:
        raise RuntimeError("CYRADUCT_SIGNING_SECRET must be a unique secret of at least 32 characters in production")

    if BROKER_API_KEY in {"", "dev-insecure-broker-key"} or len(BROKER_API_KEY) < 32:
        raise RuntimeError("CYRADUCT_BROKER_API_KEY must be a unique secret of at least 32 characters in production")
    if BROKER_API_KEY in {ADMIN_API_KEY, SIGNING_SECRET}:
        raise RuntimeError("CYRADUCT_BROKER_API_KEY must differ from admin and signing secrets")
    if not BROKER_ALLOWED_HOSTS:
        raise RuntimeError("CYRADUCT_BROKER_ALLOWED_HOSTS must list exact approved sink hostnames in production")

    if TEST_ADMIN_KEY:
        if len(TEST_ADMIN_KEY) < 32:
            raise RuntimeError("CYRADUCT_TEST_ADMIN_KEY must be at least 32 characters when configured in production")
        if TEST_ADMIN_KEY == ADMIN_API_KEY:
            raise RuntimeError("CYRADUCT_TEST_ADMIN_KEY must differ from CYRADUCT_ADMIN_KEY")

    if not DATABASE_URL.startswith(("postgresql://", "postgresql+psycopg2://")):
        raise RuntimeError("CYRADUCT_DATABASE_URL must point to PostgreSQL in production")

    private_key_b64 = os.environ.get("CYRADUCT_PRIVATE_KEY_B64", "")
    try:
        private_key = base64.b64decode(private_key_b64, validate=True)
    except (binascii.Error, ValueError):
        raise RuntimeError("CYRADUCT_PRIVATE_KEY_B64 must be valid base64 for a 32-byte Ed25519 private key") from None
    if len(private_key) != 32:
        raise RuntimeError("CYRADUCT_PRIVATE_KEY_B64 must decode to exactly 32 bytes")

    key_id = os.environ.get("CYRADUCT_KEY_ID", "")
    if not key_id or key_id == "cyraduct-dev-key-1":
        raise RuntimeError("CYRADUCT_KEY_ID must be explicitly set to a production key identifier")
