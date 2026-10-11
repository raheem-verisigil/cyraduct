#!/usr/bin/env python3
"""Pre-deploy check: will Cyraduct boot in production, and is email wired up?

Run it with the production variables in the environment, e.g. on Railway:
    railway run python scripts/check_production_env.py
Exit code 1 means the app would fail to boot or is unsafe. Warnings are advisory.
It never prints secret values.
"""
import base64
import sys
from typing import Mapping

FAIL, WARN, OK, INFO = "FAIL", "WARN", "OK  ", "INFO"
DEFAULT_ADMIN = "dev-insecure-admin-key"


def effective_environment(env: Mapping[str, str]) -> str:
    explicit = env.get("CYRADUCT_ENV", "").strip().lower()
    if explicit:
        return explicit
    if any(env.get(k) for k in ("RAILWAY_ENVIRONMENT", "RAILWAY_ENVIRONMENT_NAME", "RAILWAY_PROJECT_ID")):
        return "production"
    return "development"


def run_checks(env: Mapping[str, str]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    environment = effective_environment(env)
    out.append((INFO if environment == "production" else WARN, f"effective environment: {environment}"
                + ("" if environment == "production" else " (production safeguards are OFF)")))

    admin = env.get("CYRADUCT_ADMIN_KEY", "")
    if admin in ("", DEFAULT_ADMIN):
        out.append((FAIL, "CYRADUCT_ADMIN_KEY is missing or the default: the app will refuse to boot in production"))
    elif len(admin) < 32:
        out.append((WARN, "CYRADUCT_ADMIN_KEY is shorter than 32 characters; use a long random value"))
    else:
        out.append((OK, "CYRADUCT_ADMIN_KEY is set"))

    key = env.get("CYRADUCT_PRIVATE_KEY_B64", "")
    if not key:
        out.append((FAIL, "CYRADUCT_PRIVATE_KEY_B64 is missing: the app will refuse to boot in production "
                          "(generate one with generate_key.py)"))
    else:
        try:
            ok = len(base64.b64decode(key, validate=True)) == 32
        except Exception:
            ok = False
        out.append((OK, "CYRADUCT_PRIVATE_KEY_B64 decodes to a 32-byte Ed25519 key") if ok else
                   (FAIL, "CYRADUCT_PRIVATE_KEY_B64 is not valid base64 of a 32-byte key: boot would crash"))

    if env.get("CYRADUCT_SIGNING_SECRET"):
        out.append((INFO, "CYRADUCT_SIGNING_SECRET is set but no longer used or required"))

    db = env.get("CYRADUCT_DATABASE_URL", "")
    if not db or db.startswith("sqlite"):
        out.append((WARN, "database is SQLite: data is lost on redeploy unless a volume is attached; use Postgres"))
    else:
        out.append((OK, "database is not SQLite"))

    origins = env.get("CYRADUCT_ALLOWED_ORIGINS", "https://cyraduct.com")
    out.append((OK if "*" not in origins else FAIL, f"CORS allowed origins: {origins}"))
    if "https://www.cyraduct.com" not in origins and "CYRADUCT_ALLOWED_ORIGINS" in env:
        out.append((INFO, "https://www.cyraduct.com is not in CYRADUCT_ALLOWED_ORIGINS: pages served from www cannot call the API"))
    header = env.get("CYRADUCT_CLIENT_IP_HEADER", "").strip() or (
        "x-real-ip" if any(env.get(k) for k in ("RAILWAY_ENVIRONMENT", "RAILWAY_ENVIRONMENT_NAME", "RAILWAY_PROJECT_ID")) else "")
    out.append((INFO, f"rate limiting keys on header: {header}" if header else
                "rate limiting keys on the TCP peer: behind a proxy this is the proxy, not the visitor"))

    if env.get("RESEND_API_KEY") and env.get("PARTNER_NOTIFICATION_FROM"):
        out.append((OK, f"email configured (to {env.get('PARTNER_NOTIFICATION_TO') or 'hello@cyraduct.com'})"))
    else:
        out.append((WARN, "RESEND_API_KEY and/or PARTNER_NOTIFICATION_FROM missing: partner requests are stored but NOT emailed"))

    out.append((OK, "audit anchor URL set") if env.get("CYRADUCT_AUDIT_ANCHOR_URL") else
               (WARN, "CYRADUCT_AUDIT_ANCHOR_URL not set: no external audit anchor"))
    return out


def main() -> int:
    import os
    results = run_checks(os.environ)
    for level, message in results:
        print(f"[{level}] {message}")
    failed = any(level == FAIL for level, _ in results)
    print("\nRESULT:", "NOT SAFE TO DEPLOY" if failed else "OK to deploy (review any warnings)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
