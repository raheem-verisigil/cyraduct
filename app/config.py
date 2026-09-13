"""
Cyraduct configuration.

Consequence-class expiry policy is a first-class, documented property of the
system (see positioning language: "staleness is a bounded property, not a
gap"). Do not let receipts default to indefinite validity.
"""
import os

# Signing secret for receipts. In production this MUST come from a secrets
# manager / environment variable, never committed to source.
SIGNING_SECRET = os.environ.get("CYRADUCT_SIGNING_SECRET", "dev-insecure-secret-change-me")

# Consequence classes and their receipt expiry, in seconds.
# Higher-consequence actions get shorter-lived receipts by default.
CONSEQUENCE_CLASS_EXPIRY_SECONDS = {
    "financial_transfer": 120,          # 2 minutes
    "infra_change": 3600,               # 1 hour
    "health_record_access": 900,        # 15 minutes
    "generic_tool_call": 1800,          # 30 minutes
    "low_risk": 86400,                  # 24 hours
}

DEFAULT_EXPIRY_SECONDS = 600  # fallback if consequence class is unrecognized

# Storage backend. Defaults to local SQLite; override with DATABASE_URL for
# a real deployment (e.g. Railway Postgres plugin).
DATABASE_URL = os.environ.get("CYRADUCT_DATABASE_URL", "sqlite:///./cyraduct.db")

# Admin API key required to operate the kill switch. Must be overridden in
# any real deployment.
ADMIN_API_KEY = os.environ.get("CYRADUCT_ADMIN_KEY", "dev-insecure-admin-key")

# Scoped test key: grants LIMITED admin-like capabilities, restricted to
# receipts/agents in the test namespace only (see TEST_AGENT_PREFIX below).
# This key can NEVER touch the kill switch and can NEVER see or act on
# real (non-test-namespaced) receipts or audit entries. Since Cyraduct has
# no separate staging environment, this is what makes it safe to hand to
# an external adversarial test harness without giving it control over the
# live service that real callers depend on. Unset by default — must be
# explicitly configured to enable test-key access at all.
TEST_ADMIN_KEY = os.environ.get("CYRADUCT_TEST_ADMIN_KEY", "")

# Any agent_id starting with this prefix is considered "test namespace."
# A test key may only act on receipts/agents within this namespace.
TEST_AGENT_PREFIX = os.environ.get("CYRADUCT_TEST_AGENT_PREFIX", "test-")

POLICY_PACK_DIR = os.environ.get("CYRADUCT_POLICY_DIR", "policy_packs")
