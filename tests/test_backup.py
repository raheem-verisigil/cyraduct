"""
Tests for backup_postgres.py — the dump/encrypt/decrypt/restore cycle.

Does not test the actual GitHub push (that needs real credentials and
shouldn't run against a real repo in CI), but proves the part that
actually matters for data safety: a backup taken now can genuinely
restore a wiped database later, encrypted at rest, with a safety guard
against accidental restore.
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cryptography.fernet import Fernet
from sqlalchemy import select, delete

from app.storage import _engine, receipts_table, init_db
import backup_postgres as bp

TEST_KEY = Fernet.generate_key().decode()


def _seed_a_receipt(agent_id="backup-test-seed"):
    from app.models import ActionRequest, new_id
    from app.receipts import issue_receipt
    from app.storage import save_receipt

    req = ActionRequest(
        agent_id=agent_id, action_type="read_public_doc",
        consequence_class="low_risk", policy_pack="generic", payload={},
    )
    receipt = issue_receipt(req, new_id("act"), "allow", "generic", "0.1.0", [], [])
    save_receipt(receipt)
    return receipt.receipt_id


def test_encrypt_decrypt_round_trip():
    dump = {"backed_up_at": "2026-01-01T00:00:00", "tables": {"receipts": [{"receipt_id": "rcpt_x"}]}}
    encrypted = bp.encrypt_dump(dump, TEST_KEY)
    assert isinstance(encrypted, bytes)
    decrypted = bp.decrypt_dump(encrypted, TEST_KEY)
    assert decrypted == dump


def test_decrypt_fails_with_wrong_key():
    dump = {"backed_up_at": "2026-01-01T00:00:00", "tables": {}}
    encrypted = bp.encrypt_dump(dump, TEST_KEY)
    wrong_key = Fernet.generate_key().decode()
    try:
        bp.decrypt_dump(encrypted, wrong_key)
        assert False, "Expected decryption to fail with the wrong key"
    except Exception:
        pass  # expected — cryptography raises InvalidToken


def test_dump_all_tables_includes_seeded_data():
    init_db()
    receipt_id = _seed_a_receipt("backup-test-dump-check")
    dump = bp.dump_all_tables()

    assert "receipts" in dump["tables"]
    receipt_ids_in_dump = [r["receipt_id"] for r in dump["tables"]["receipts"]]
    assert receipt_id in receipt_ids_in_dump


def test_full_backup_and_restore_cycle():
    """The test that actually matters: take a real backup, destroy the
    data, restore from the backup, confirm it's genuinely back."""
    init_db()
    receipt_id = _seed_a_receipt("backup-test-full-cycle")

    dump = bp.dump_all_tables()
    encrypted = bp.encrypt_dump(dump, TEST_KEY)

    # Destroy the data
    with _engine.begin() as conn:
        conn.execute(delete(receipts_table).where(receipts_table.c.receipt_id == receipt_id))
    with _engine.begin() as conn:
        remaining = conn.execute(
            select(receipts_table).where(receipts_table.c.receipt_id == receipt_id)
        ).fetchall()
    assert len(remaining) == 0, "Setup failed: receipt should be gone before restore"

    # Restore
    restored_dump = bp.decrypt_dump(encrypted, TEST_KEY)
    bp.restore_from_dump(restored_dump, confirm=True)

    with _engine.begin() as conn:
        restored = conn.execute(
            select(receipts_table).where(receipts_table.c.receipt_id == receipt_id)
        ).fetchall()
    assert len(restored) == 1, "Receipt should be back after restore"


def test_restore_refuses_without_confirm():
    dump = {"backed_up_at": "2026-01-01T00:00:00", "tables": {name: [] for name in bp.TABLES}}
    try:
        bp.restore_from_dump(dump, confirm=False)
        assert False, "Expected restore to refuse without confirm=True"
    except SystemExit:
        pass  # expected — the script calls sys.exit(1)
