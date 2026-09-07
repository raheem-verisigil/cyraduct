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

POLICY_PACK_DIR = os.environ.get("CYRADUCT_POLICY_DIR", "policy_packs")
