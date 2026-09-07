"""
Receipt querying — the "single source of truth" surface for an auditor,
insurer, or internal risk team asking "what did this agent do, and under
what authorization."
"""
from typing import Optional
from fastapi import APIRouter
from .. import storage

router = APIRouter(prefix="/v1/receipts", tags=["receipts"])


@router.get("")
def query_receipts(agent_id: Optional[str] = None, since: Optional[str] = None,
                    until: Optional[str] = None, limit: int = 100):
    results = storage.query_receipts(agent_id=agent_id, since=since, until=until, limit=limit)
    return {"count": len(results), "receipts": [r.model_dump() for r in results]}


@router.get("/{receipt_id}")
def get_receipt(receipt_id: str):
    r = storage.get_receipt(receipt_id)
    if not r:
        return {"error": "receipt_not_found"}
    return r.model_dump()
