"""Receipt querying with full-admin and test-namespace access controls."""
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from .. import storage, auth
from ..tenancy import optional_tenant

router = APIRouter(prefix="/v1/receipts", tags=["receipts"])


def _authenticated_scope(provided_key: Optional[str]):
    result = auth.check_admin_or_test_key(provided_key)
    if not result.authenticated:
        raise HTTPException(status_code=401, detail="Invalid or missing admin/test key")
    return result


@router.get("")
def query_receipts(
    agent_id: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    x_cyraduct_admin_key: Optional[str] = Header(None),
    tenant: Optional[str] = Depends(optional_tenant),
):
    if tenant and not x_cyraduct_admin_key:
        results = storage.query_receipts(agent_id=agent_id, since=since, until=until, limit=limit, tenant_id=tenant)
        return {"count": len(results), "receipts": [r.model_dump() for r in results]}
    scope = _authenticated_scope(x_cyraduct_admin_key)

    if scope.is_test_key:
        if not agent_id:
            raise HTTPException(status_code=403, detail="Test key must query a specific test-namespace agent")
        if not auth.is_test_namespace(agent_id):
            raise HTTPException(status_code=403, detail="Test key may only query the test namespace")

    results = storage.query_receipts(agent_id=agent_id, since=since, until=until, limit=limit)
    if scope.is_test_key:
        results = [r for r in results if auth.is_test_namespace(r.agent.agent_id)]
    return {"count": len(results), "receipts": [r.model_dump() for r in results]}


@router.get("/{receipt_id}")
def get_receipt(receipt_id: str, x_cyraduct_admin_key: Optional[str] = Header(None),
                tenant: Optional[str] = Depends(optional_tenant)):
    if tenant and not x_cyraduct_admin_key:
        r = storage.get_receipt(receipt_id)
        if not r or storage.get_receipt_tenant(receipt_id) != tenant:
            raise HTTPException(status_code=404, detail="Receipt not found")
        return r.model_dump()
    scope = _authenticated_scope(x_cyraduct_admin_key)
    r = storage.get_receipt(receipt_id)
    if not r:
        return {"error": "receipt_not_found"}

    if scope.is_test_key and not auth.is_test_namespace(r.agent.agent_id):
        # Do not disclose whether a non-test receipt exists to scoped testers.
        raise HTTPException(status_code=404, detail="Receipt not found")
    return r.model_dump()
