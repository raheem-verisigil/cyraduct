#!/usr/bin/env python3
"""
Cyraduct database backup.

Dumps every table (receipts, audit_log, kill_switch, evidence,
agent_chain) to a single JSON document, encrypts it (Fernet, symmetric),
and pushes it to a SEPARATE PRIVATE repository via the GitHub contents
API — deliberately never the main `cyraduct` repo, which is public.

Why encrypted, in a private repo, rather than just "private repo is
enough": defense in depth. If the backup repo's access were ever
misconfigured to public (the same class of mistake that exposed
credentials earlier in this project's history), the backup contents
would still be unreadable without CYRADUCT_BACKUP_ENCRYPTION_KEY, which
lives only in Railway's environment variables, never in git.

Usage:
    python3 backup_postgres.py                  # real backup, pushes to GitHub
    python3 backup_postgres.py --dry-run         # does everything except the actual push;
                                                   writes the encrypted blob locally instead
    python3 backup_postgres.py --restore FILE    # decrypts a local backup file and
                                                   restores it into the database (DESTRUCTIVE —
                                                   wipes and reloads every table)

Required environment variables (real run):
    CYRADUCT_DATABASE_URL          — same one the app itself uses
    CYRADUCT_BACKUP_ENCRYPTION_KEY — from generate_backup_key.py
    GITHUB_BACKUP_TOKEN            — a fine-grained PAT scoped ONLY to the
                                      backup repo, contents:write
    GITHUB_BACKUP_REPO             — e.g. "raheem-verisigil/cyraduct-backups"
                                      (must be a PRIVATE repo)
"""
import argparse
import base64
import json
import os
import sys
from datetime import datetime, timezone

import httpx
from cryptography.fernet import Fernet
from sqlalchemy import select

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from app.storage import (
    _engine, receipts_table, audit_log_table, kill_switch_table,
    evidence_table, agent_chain_table,
)

TABLES = {
    "receipts": receipts_table,
    "audit_log": audit_log_table,
    "kill_switch": kill_switch_table,
    "evidence": evidence_table,
    "agent_chain": agent_chain_table,
}


def dump_all_tables() -> dict:
    """Reads every row from every table into a plain-dict structure."""
    dump = {
        "backed_up_at": datetime.now(timezone.utc).isoformat(),
        "tables": {},
    }
    with _engine.begin() as conn:
        for name, table in TABLES.items():
            rows = conn.execute(select(table)).mappings().all()
            dump["tables"][name] = [dict(row) for row in rows]
    return dump


def encrypt_dump(dump: dict, key: str) -> bytes:
    fernet = Fernet(key.encode())
    raw = json.dumps(dump, sort_keys=True, default=str).encode()
    return fernet.encrypt(raw)


def decrypt_dump(encrypted: bytes, key: str) -> dict:
    fernet = Fernet(key.encode())
    raw = fernet.decrypt(encrypted)
    return json.loads(raw)


def push_to_github(encrypted: bytes, token: str, repo: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    path = f"backups/cyraduct-{timestamp}.enc"
    content_b64 = base64.b64encode(encrypted).decode()

    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    resp = httpx.put(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
        json={
            "message": f"Automated backup {timestamp}",
            "content": content_b64,
        },
        timeout=30.0,
    )
    resp.raise_for_status()
    return path


def restore_from_dump(dump: dict, confirm: bool):
    """DESTRUCTIVE: wipes each table and reloads it from the dump. Only
    ever run this deliberately, against a database you intend to
    overwrite — never against a live database with newer data than the
    backup, without understanding you are discarding that newer data."""
    if not confirm:
        print("Refusing to restore without --yes-really-restore. This wipes existing table contents.")
        sys.exit(1)

    with _engine.begin() as conn:
        for name, table in TABLES.items():
            rows = dump["tables"].get(name, [])
            conn.execute(table.delete())
            if rows:
                conn.execute(table.insert(), rows)
            print(f"Restored {name}: {len(rows)} rows")


def main():
    parser = argparse.ArgumentParser(description="Cyraduct database backup")
    parser.add_argument("--dry-run", action="store_true", help="Do everything except the GitHub push")
    parser.add_argument("--restore", metavar="FILE", help="Decrypt and restore from a local backup file")
    parser.add_argument("--yes-really-restore", action="store_true", help="Required alongside --restore to actually wipe+reload tables")
    args = parser.parse_args()

    key = os.environ.get("CYRADUCT_BACKUP_ENCRYPTION_KEY")
    if not key:
        print("CYRADUCT_BACKUP_ENCRYPTION_KEY is not set. Run generate_backup_key.py once and set it.")
        sys.exit(1)

    if args.restore:
        with open(args.restore, "rb") as f:
            encrypted = f.read()
        dump = decrypt_dump(encrypted, key)
        print(f"Backup was taken at: {dump['backed_up_at']}")
        for name, rows in dump["tables"].items():
            print(f"  {name}: {len(rows)} rows in backup")
        restore_from_dump(dump, confirm=args.yes_really_restore)
        return

    print("Reading tables from database...")
    dump = dump_all_tables()
    total_rows = sum(len(rows) for rows in dump["tables"].values())
    for name, rows in dump["tables"].items():
        print(f"  {name}: {len(rows)} rows")
    print(f"Total: {total_rows} rows across {len(dump['tables'])} tables")

    print("Encrypting...")
    encrypted = encrypt_dump(dump, key)
    print(f"Encrypted size: {len(encrypted)} bytes")

    if args.dry_run:
        out_path = f"backup-dry-run-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.enc"
        with open(out_path, "wb") as f:
            f.write(encrypted)
        print(f"DRY RUN — wrote encrypted backup locally to {out_path} instead of pushing to GitHub.")
        print("To verify it round-trips correctly:")
        print(f"  python3 backup_postgres.py --restore {out_path}   (without --yes-really-restore, this only decrypts and reports row counts)")
        return

    token = os.environ.get("GITHUB_BACKUP_TOKEN")
    repo = os.environ.get("GITHUB_BACKUP_REPO")
    if not token or not repo:
        print("GITHUB_BACKUP_TOKEN and GITHUB_BACKUP_REPO must both be set for a real (non-dry-run) backup.")
        sys.exit(1)

    print(f"Pushing to {repo}...")
    path = push_to_github(encrypted, token, repo)
    print(f"Backup pushed: {path}")


if __name__ == "__main__":
    main()
