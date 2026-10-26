
#!/usr/bin/env python3
"""
Cyraduct database backup.

Reflects the live database schema, exports selected application tables,
encrypts the backup with Fernet, and uploads it to a separate private
GitHub repository.

Required environment variables:
    CYRADUCT_DATABASE_URL
    CYRADUCT_BACKUP_ENCRYPTION_KEY
    GITHUB_BACKUP_TOKEN
    GITHUB_BACKUP_REPO

Safety:
    --dry-run creates an encrypted local backup without uploading.
    --restore is destructive when combined with --yes-really-restore.
"""

import argparse
import base64
import json
import os
import sys
from datetime import datetime, timezone

import httpx
from cryptography.fernet import Fernet
from sqlalchemy import MetaData, select

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.storage import (
    _engine,
    receipts_table,
    audit_log_table,
    kill_switch_table,
    evidence_table,
    agent_chain_table,
    partners_table,
    analytics_events_table, tenants_table, init_db,
)

TABLES = {
    "receipts": receipts_table,
    "audit_log": audit_log_table,
    "kill_switch": kill_switch_table,
    "evidence": evidence_table,
    "agent_chain": agent_chain_table,
    "partners": partners_table,
    "analytics_events": analytics_events_table,
    "tenants": tenants_table,
}


def reflect_live_tables():
    """Discover actual columns in the selected live database tables."""
    init_db()  # idempotent: guarantees newly added tables exist before reflection
    metadata = MetaData()
    metadata.reflect(bind=_engine, only=list(TABLES.keys()))

    missing = sorted(set(TABLES) - set(metadata.tables))
    if missing:
        raise RuntimeError(
            "Expected database tables are missing: "
            + ", ".join(missing)
        )

    return metadata.tables


def dump_all_tables() -> dict:
    """Export rows and column metadata using the live database schema."""
    live_tables = reflect_live_tables()

    dump = {
        "backed_up_at": datetime.now(timezone.utc).isoformat(),
        "tables": {},
        "schema": {},
    }

    with _engine.connect() as conn:
        for name in TABLES:
            table = live_tables[name]

            dump["schema"][name] = [
                {
                    "name": column.name,
                    "type": str(column.type),
                    "nullable": column.nullable,
                    "primary_key": column.primary_key,
                }
                for column in table.columns
            ]

            result = conn.execute(select(table)).mappings().all()
            dump["tables"][name] = [dict(row) for row in result]

    return dump


def encrypt_dump(dump: dict, key: str) -> bytes:
    """Serialize and encrypt the backup."""
    fernet = Fernet(key.encode())
    raw = json.dumps(dump, sort_keys=True, default=str).encode()
    return fernet.encrypt(raw)


def decrypt_dump(encrypted: bytes, key: str) -> dict:
    """Decrypt and deserialize a backup."""
    fernet = Fernet(key.encode())
    return json.loads(fernet.decrypt(encrypted))


def push_to_github(encrypted: bytes, token: str, repo: str) -> str:
    """Upload an encrypted backup to the configured private repository."""
    timestamp = datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H-%M-%SZ"
    )
    path = f"backups/cyraduct-{timestamp}.enc"
    content_b64 = base64.b64encode(encrypted).decode()

    url = f"https://api.github.com/repos/{repo}/contents/{path}"

    response = httpx.put(
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
    response.raise_for_status()
    return path


def restore_from_dump(dump: dict, confirm: bool):
    """
    DESTRUCTIVE: replace selected table contents from a backup.

    Requires explicit confirmation. Use only against a database that you
    intentionally intend to overwrite. Test recovery on a separate database
    first. A schema-aware insert can still fail if constraints or column
    definitions differ.
    """
    if not confirm:
        print(
            "Refusing restore without --yes-really-restore. "
            "Existing table contents would be deleted."
        )
        sys.exit(1)

    backup_tables = dump.get("tables")
    if not isinstance(backup_tables, dict):
        raise ValueError("Backup has no valid tables section.")

    live_tables = reflect_live_tables()

    # Validate every table and row before deleting any records.
    for name, rows in backup_tables.items():
        if name not in live_tables:
            raise ValueError(f"Backup contains an unexpected table: {name}")
        if not isinstance(rows, list):
            raise ValueError(f"Invalid rows for table: {name}")

        live_columns = {column.name for column in live_tables[name].columns}
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError(f"Invalid row in table: {name}")
            unknown = set(row) - live_columns
            if unknown:
                raise ValueError(
                    f"Backup has columns absent from live table "
                    f"{name}: {', '.join(sorted(unknown))}"
                )

    # Deletion and insertion run in one transaction. Any error should
    # roll back the transaction on databases that support transactional DML.
    with _engine.begin() as conn:
        for name in TABLES:
            if name not in backup_tables:
                continue

            table = live_tables[name]
            rows = backup_tables[name]

            conn.execute(table.delete())
            if rows:
                conn.execute(table.insert(), rows)

            print(f"Restored {name}: {len(rows)} rows")


def main():
    parser = argparse.ArgumentParser(
        description="Cyraduct database backup"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Write an encrypted local backup without uploading",
    )
    parser.add_argument(
        "--restore",
        metavar="FILE",
        help="Decrypt and restore a local encrypted backup",
    )
    parser.add_argument(
        "--yes-really-restore",
        action="store_true",
        help="Explicitly authorize destructive restore",
    )
    args = parser.parse_args()

    key = os.environ.get("CYRADUCT_BACKUP_ENCRYPTION_KEY")
    if not key:
        print("CYRADUCT_BACKUP_ENCRYPTION_KEY is not set.")
        sys.exit(1)

    # Validate the key before doing any database work.
    try:
        Fernet(key.encode())
    except Exception:
        print("CYRADUCT_BACKUP_ENCRYPTION_KEY is invalid.")
        sys.exit(1)

    if args.restore:
        try:
            with open(args.restore, "rb") as backup_file:
                encrypted = backup_file.read()

            dump = decrypt_dump(encrypted, key)
            print(f"Backup timestamp: {dump.get('backed_up_at', 'unknown')}")

            for name, rows in dump.get("tables", {}).items():
                print(f"  {name}: {len(rows)} rows in backup")

            restore_from_dump(
                dump,
                confirm=args.yes_really_restore,
            )
        except Exception as exc:
            print(f"RESTORE FAILED: {type(exc).__name__}: {exc}")
            sys.exit(1)
        return

    print("Reading selected tables from the live database...")

    try:
        dump = dump_all_tables()
    except Exception as exc:
        print(f"BACKUP FAILED while reading database: {type(exc).__name__}: {exc}")
        sys.exit(1)

    total_rows = sum(len(rows) for rows in dump["tables"].values())
    for name, rows in dump["tables"].items():
        print(f"  {name}: {len(rows)} rows")
    print(f"Total: {total_rows} rows across {len(dump['tables'])} tables")

    print("Encrypting backup...")
    try:
        encrypted = encrypt_dump(dump, key)

        # Verify that encryption and decryption round-trip successfully.
        if decrypt_dump(encrypted, key) != dump:
            raise ValueError("Backup verification mismatch")
    except Exception as exc:
        print(f"BACKUP FAILED during encryption: {type(exc).__name__}: {exc}")
        sys.exit(1)

    print(f"Encrypted size: {len(encrypted)} bytes")
    print("Encryption verification passed.")

    if args.dry_run:
        filename = "backup-dry-run-" + datetime.now(
            timezone.utc
        ).strftime("%Y%m%dT%H%M%SZ") + ".enc"

        with open(filename, "wb") as backup_file:
            backup_file.write(encrypted)

        print(f"DRY RUN: encrypted backup saved to {filename}")
        print("No GitHub upload was performed.")
        return

    token = os.environ.get("GITHUB_BACKUP_TOKEN")
    repo = os.environ.get("GITHUB_BACKUP_REPO")

    if not token or not repo:
        print("GITHUB_BACKUP_TOKEN and GITHUB_BACKUP_REPO must be set.")
        sys.exit(1)

    print(f"Uploading encrypted backup to {repo}...")
    try:
        path = push_to_github(encrypted, token, repo)
    except Exception as exc:
        print(f"BACKUP FAILED during GitHub upload: {type(exc).__name__}: {exc}")
        sys.exit(1)

    print(f"Backup uploaded successfully: {path}")


if __name__ == "__main__":
    main()
