"""
Storage layer.

Uses SQLAlchemy Core so the same code runs against SQLite (local dev,
zero setup) or Postgres (production — set CYRADUCT_DATABASE_URL to a
Railway Postgres connection string). This replaces the earlier
SQLite-only implementation; nothing in the routers changed, since every
function here keeps its exact original signature.

Why this matters: SQLite on Railway lives on ephemeral local disk — every
redeploy silently wipes receipts, evidence, and the audit log. Postgres
(via Railway's Postgres plugin, or any managed Postgres) persists across
redeploys, which is the actual requirement once anyone relies on a
receipt being retrievable later.

The audit log is hash-chained: each entry embeds the hash of the previous
entry, so any tampering with history breaks the chain and is detectable.
Receipts are additionally chained per-agent (prev_receipt_hash), and that
chain link is itself covered by the receipt's Ed25519 signature.
"""
import hashlib
import json
import os
import threading
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import (
    create_engine, MetaData, Table, Column, String, Integer, Text, select,
    insert, update, delete as sa_delete, desc, asc,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from .models import Receipt, EvidencePackage

_DATABASE_URL = os.environ.get("CYRADUCT_DATABASE_URL", "sqlite:///./cyraduct.db")

_engine = create_engine(_DATABASE_URL, future=True)
_is_sqlite = _engine.dialect.name == "sqlite"
_lock = threading.Lock()  # SQLite has no real concurrent-writer story; harmless no-op contention under Postgres

metadata = MetaData()

receipts_table = Table(
    "receipts", metadata,
    Column("receipt_id", String, primary_key=True),
    Column("agent_id", String, nullable=False, index=True),
    Column("issued_at", String, nullable=False, index=True),
    Column("consequence_class", String),
    Column("data", Text, nullable=False),
    Column("revoked", Integer, nullable=False, default=0),
)

audit_log_table = Table(
    "audit_log", metadata,
    Column("seq", Integer, primary_key=True, autoincrement=True),
    Column("timestamp", String, nullable=False),
    Column("event_type", String, nullable=False),
    Column("detail", Text, nullable=False),
    Column("prev_hash", String, nullable=False),
    Column("entry_hash", String, nullable=False),
)

kill_switch_table = Table(
    "kill_switch", metadata,
    Column("id", Integer, primary_key=True),
    Column("active", Integer, nullable=False, default=0),
    Column("reason", Text),
)

evidence_table = Table(
    "evidence", metadata,
    Column("evidence_id", String, primary_key=True),
    Column("data", Text, nullable=False),
)

agent_chain_table = Table(
    "agent_chain", metadata,
    Column("agent_id", String, primary_key=True),
    Column("last_receipt_hash", String, nullable=False),
)


def init_db():
    metadata.create_all(_engine)
    with _engine.begin() as conn:
        exists = conn.execute(
            select(kill_switch_table.c.id).where(kill_switch_table.c.id == 1)
        ).fetchone()
        if not exists:
            conn.execute(insert(kill_switch_table).values(id=1, active=0, reason=None))


def _upsert_agent_chain(conn, agent_id: str, last_hash: str):
    if _is_sqlite:
        stmt = sqlite_insert(agent_chain_table).values(agent_id=agent_id, last_receipt_hash=last_hash)
        stmt = stmt.on_conflict_do_update(
            index_elements=["agent_id"], set_={"last_receipt_hash": last_hash}
        )
    else:
        stmt = pg_insert(agent_chain_table).values(agent_id=agent_id, last_receipt_hash=last_hash)
        stmt = stmt.on_conflict_do_update(
            index_elements=["agent_id"], set_={"last_receipt_hash": last_hash}
        )
    conn.execute(stmt)


def save_receipt(receipt: Receipt):
    with _lock, _engine.begin() as conn:
        conn.execute(sa_delete(receipts_table).where(receipts_table.c.receipt_id == receipt.receipt_id))
        conn.execute(insert(receipts_table).values(
            receipt_id=receipt.receipt_id,
            agent_id=receipt.agent.agent_id,
            issued_at=receipt.issued_at,
            consequence_class=receipt.action.consequence_class,
            data=receipt.model_dump_json(),
            revoked=int(receipt.revoked),
        ))
        _upsert_agent_chain(conn, receipt.agent.agent_id, receipt.action_hash)


def get_last_receipt_hash(agent_id: str) -> Optional[str]:
    with _lock, _engine.begin() as conn:
        row = conn.execute(
            select(agent_chain_table.c.last_receipt_hash).where(agent_chain_table.c.agent_id == agent_id)
        ).fetchone()
        return row[0] if row else None


def get_receipt(receipt_id: str) -> Optional[Receipt]:
    with _lock, _engine.begin() as conn:
        row = conn.execute(
            select(receipts_table.c.data, receipts_table.c.revoked)
            .where(receipts_table.c.receipt_id == receipt_id)
        ).fetchone()
        if not row:
            return None
        r = Receipt.model_validate_json(row[0])
        r.revoked = bool(row[1])
        return r


def query_receipts(agent_id: Optional[str] = None, since: Optional[str] = None,
                    until: Optional[str] = None, limit: int = 100) -> List[Receipt]:
    stmt = select(receipts_table.c.data, receipts_table.c.revoked)
    if agent_id:
        stmt = stmt.where(receipts_table.c.agent_id == agent_id)
    if since:
        stmt = stmt.where(receipts_table.c.issued_at >= since)
    if until:
        stmt = stmt.where(receipts_table.c.issued_at <= until)
    stmt = stmt.order_by(desc(receipts_table.c.issued_at)).limit(limit)

    with _lock, _engine.begin() as conn:
        rows = conn.execute(stmt).fetchall()
        out = []
        for row in rows:
            r = Receipt.model_validate_json(row[0])
            r.revoked = bool(row[1])
            out.append(r)
        return out


def revoke_receipt(receipt_id: str) -> bool:
    with _lock, _engine.begin() as conn:
        result = conn.execute(
            update(receipts_table).where(receipts_table.c.receipt_id == receipt_id).values(revoked=1)
        )
        return result.rowcount > 0


def revoke_by_agent(agent_id: str) -> int:
    with _lock, _engine.begin() as conn:
        result = conn.execute(
            update(receipts_table)
            .where(receipts_table.c.agent_id == agent_id, receipts_table.c.revoked == 0)
            .values(revoked=1)
        )
        return result.rowcount


def save_evidence(pkg: EvidencePackage):
    with _lock, _engine.begin() as conn:
        conn.execute(sa_delete(evidence_table).where(evidence_table.c.evidence_id == pkg.evidence_id))
        conn.execute(insert(evidence_table).values(evidence_id=pkg.evidence_id, data=pkg.model_dump_json()))


def get_evidence(evidence_id: str) -> Optional[EvidencePackage]:
    with _lock, _engine.begin() as conn:
        row = conn.execute(
            select(evidence_table.c.data).where(evidence_table.c.evidence_id == evidence_id)
        ).fetchone()
        return EvidencePackage.model_validate_json(row[0]) if row else None


def _last_hash(conn) -> str:
    row = conn.execute(
        select(audit_log_table.c.entry_hash).order_by(desc(audit_log_table.c.seq)).limit(1)
    ).fetchone()
    return row[0] if row else "genesis"


def append_audit(event_type: str, detail: dict):
    with _lock, _engine.begin() as conn:
        prev_hash = _last_hash(conn)
        timestamp = datetime.now(timezone.utc).isoformat()
        payload = json.dumps({"timestamp": timestamp, "event_type": event_type, "detail": detail}, sort_keys=True)
        entry_hash = hashlib.sha256((prev_hash + payload).encode()).hexdigest()
        conn.execute(insert(audit_log_table).values(
            timestamp=timestamp, event_type=event_type, detail=json.dumps(detail),
            prev_hash=prev_hash, entry_hash=entry_hash,
        ))


def get_audit_log(limit: int = 200) -> list:
    with _lock, _engine.begin() as conn:
        rows = conn.execute(
            select(
                audit_log_table.c.seq, audit_log_table.c.timestamp, audit_log_table.c.event_type,
                audit_log_table.c.detail, audit_log_table.c.prev_hash, audit_log_table.c.entry_hash,
            ).order_by(asc(audit_log_table.c.seq)).limit(limit)
        ).fetchall()
        return [
            {"seq": r[0], "timestamp": r[1], "event_type": r[2], "detail": r[3], "prev_hash": r[4], "entry_hash": r[5]}
            for r in rows
        ]


def verify_audit_chain() -> bool:
    with _lock, _engine.begin() as conn:
        rows = conn.execute(
            select(
                audit_log_table.c.timestamp, audit_log_table.c.event_type,
                audit_log_table.c.detail, audit_log_table.c.prev_hash, audit_log_table.c.entry_hash,
            ).order_by(asc(audit_log_table.c.seq))
        ).fetchall()
    prev_hash = "genesis"
    for row in rows:
        payload = json.dumps(
            {"timestamp": row[0], "event_type": row[1], "detail": json.loads(row[2])},
            sort_keys=True,
        )
        expected = hashlib.sha256((prev_hash + payload).encode()).hexdigest()
        if expected != row[4] or row[3] != prev_hash:
            return False
        prev_hash = row[4]
    return True


def get_kill_switch() -> dict:
    with _lock, _engine.begin() as conn:
        row = conn.execute(
            select(kill_switch_table.c.active, kill_switch_table.c.reason)
            .where(kill_switch_table.c.id == 1)
        ).fetchone()
        return {"active": bool(row[0]), "reason": row[1]}


def set_kill_switch(active: bool, reason: Optional[str]):
    with _lock, _engine.begin() as conn:
        conn.execute(
            update(kill_switch_table).where(kill_switch_table.c.id == 1)
            .values(active=int(active), reason=reason)
        )
