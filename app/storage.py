"""
Storage layer.

Uses SQLite by default (fine for a pilot/MVP; swap CYRADUCT_DATABASE_URL
for Postgres in a real deployment).

The audit log is hash-chained: each entry embeds the hash of the previous
entry, so any tampering with history breaks the chain and is detectable.
Receipts are additionally chained per-agent (prev_receipt_hash), and that
chain link is itself covered by the receipt's Ed25519 signature.
"""
import sqlite3
import json
import hashlib
import threading
from datetime import datetime, timezone
from typing import Optional, List

from .models import Receipt, EvidencePackage

_DB_PATH = "cyraduct.db"
_lock = threading.Lock()


def _conn():
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _lock, _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS receipts (
                receipt_id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                issued_at TEXT NOT NULL,
                consequence_class TEXT,
                data TEXT NOT NULL,
                revoked INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_receipts_agent ON receipts (agent_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_receipts_issued ON receipts (issued_at)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                detail TEXT NOT NULL,
                prev_hash TEXT NOT NULL,
                entry_hash TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS kill_switch (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                active INTEGER NOT NULL DEFAULT 0,
                reason TEXT
            )
        """)
        conn.execute("INSERT OR IGNORE INTO kill_switch (id, active, reason) VALUES (1, 0, NULL)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS evidence (
                evidence_id TEXT PRIMARY KEY,
                data TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_chain (
                agent_id TEXT PRIMARY KEY,
                last_receipt_hash TEXT NOT NULL
            )
        """)
        conn.commit()


def save_receipt(receipt: Receipt):
    with _lock, _conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO receipts (receipt_id, agent_id, issued_at, consequence_class, data, revoked) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (receipt.receipt_id, receipt.agent.agent_id, receipt.issued_at,
             receipt.action.consequence_class, receipt.model_dump_json(), int(receipt.revoked)),
        )
        # Chain: this receipt's own signature covers prev_receipt_hash, so
        # what we store as "last hash" for the next receipt is this
        # receipt's action_hash (a stable, content-derived value).
        conn.execute(
            "INSERT INTO agent_chain (agent_id, last_receipt_hash) VALUES (?, ?) "
            "ON CONFLICT(agent_id) DO UPDATE SET last_receipt_hash = excluded.last_receipt_hash",
            (receipt.agent.agent_id, receipt.action_hash),
        )
        conn.commit()


def get_last_receipt_hash(agent_id: str) -> Optional[str]:
    with _lock, _conn() as conn:
        row = conn.execute("SELECT last_receipt_hash FROM agent_chain WHERE agent_id = ?", (agent_id,)).fetchone()
        return row["last_receipt_hash"] if row else None


def get_receipt(receipt_id: str) -> Optional[Receipt]:
    with _lock, _conn() as conn:
        row = conn.execute("SELECT data, revoked FROM receipts WHERE receipt_id = ?", (receipt_id,)).fetchone()
        if not row:
            return None
        r = Receipt.model_validate_json(row["data"])
        r.revoked = bool(row["revoked"])
        return r


def query_receipts(agent_id: Optional[str] = None, since: Optional[str] = None,
                    until: Optional[str] = None, limit: int = 100) -> List[Receipt]:
    clauses, params = [], []
    if agent_id:
        clauses.append("agent_id = ?")
        params.append(agent_id)
    if since:
        clauses.append("issued_at >= ?")
        params.append(since)
    if until:
        clauses.append("issued_at <= ?")
        params.append(until)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with _lock, _conn() as conn:
        rows = conn.execute(
            f"SELECT data, revoked FROM receipts {where} ORDER BY issued_at DESC LIMIT ?",
            (*params, limit),
        ).fetchall()
        out = []
        for row in rows:
            r = Receipt.model_validate_json(row["data"])
            r.revoked = bool(row["revoked"])
            out.append(r)
        return out


def revoke_receipt(receipt_id: str) -> bool:
    with _lock, _conn() as conn:
        cur = conn.execute("UPDATE receipts SET revoked = 1 WHERE receipt_id = ?", (receipt_id,))
        conn.commit()
        return cur.rowcount > 0


def revoke_by_agent(agent_id: str) -> int:
    """Revoke all currently-unrevoked receipts for an agent — the
    fleet/agent-scoped 'kill this agent now' operation."""
    with _lock, _conn() as conn:
        cur = conn.execute(
            "UPDATE receipts SET revoked = 1 WHERE agent_id = ? AND revoked = 0", (agent_id,)
        )
        conn.commit()
        return cur.rowcount


def save_evidence(pkg: EvidencePackage):
    with _lock, _conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO evidence (evidence_id, data) VALUES (?, ?)",
            (pkg.evidence_id, pkg.model_dump_json()),
        )
        conn.commit()


def get_evidence(evidence_id: str) -> Optional[EvidencePackage]:
    with _lock, _conn() as conn:
        row = conn.execute("SELECT data FROM evidence WHERE evidence_id = ?", (evidence_id,)).fetchone()
        return EvidencePackage.model_validate_json(row["data"]) if row else None


def _last_hash(conn) -> str:
    row = conn.execute("SELECT entry_hash FROM audit_log ORDER BY seq DESC LIMIT 1").fetchone()
    return row["entry_hash"] if row else "genesis"


def append_audit(event_type: str, detail: dict):
    with _lock, _conn() as conn:
        prev_hash = _last_hash(conn)
        timestamp = datetime.now(timezone.utc).isoformat()
        payload = json.dumps({"timestamp": timestamp, "event_type": event_type, "detail": detail}, sort_keys=True)
        entry_hash = hashlib.sha256((prev_hash + payload).encode()).hexdigest()
        conn.execute(
            "INSERT INTO audit_log (timestamp, event_type, detail, prev_hash, entry_hash) VALUES (?, ?, ?, ?, ?)",
            (timestamp, event_type, json.dumps(detail), prev_hash, entry_hash),
        )
        conn.commit()


def get_audit_log(limit: int = 200) -> list:
    with _lock, _conn() as conn:
        rows = conn.execute(
            "SELECT seq, timestamp, event_type, detail, prev_hash, entry_hash FROM audit_log ORDER BY seq ASC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def verify_audit_chain() -> bool:
    with _lock, _conn() as conn:
        rows = conn.execute(
            "SELECT timestamp, event_type, detail, prev_hash, entry_hash FROM audit_log ORDER BY seq ASC"
        ).fetchall()
    prev_hash = "genesis"
    for row in rows:
        payload = json.dumps(
            {"timestamp": row["timestamp"], "event_type": row["event_type"], "detail": json.loads(row["detail"])},
            sort_keys=True,
        )
        expected = hashlib.sha256((prev_hash + payload).encode()).hexdigest()
        if expected != row["entry_hash"] or row["prev_hash"] != prev_hash:
            return False
        prev_hash = row["entry_hash"]
    return True


def get_kill_switch() -> dict:
    with _lock, _conn() as conn:
        row = conn.execute("SELECT active, reason FROM kill_switch WHERE id = 1").fetchone()
        return {"active": bool(row["active"]), "reason": row["reason"]}


def set_kill_switch(active: bool, reason: Optional[str]):
    with _lock, _conn() as conn:
        conn.execute("UPDATE kill_switch SET active = ?, reason = ? WHERE id = 1", (int(active), reason))
        conn.commit()
