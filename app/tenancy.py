"""
Tenant identification.

A tenant authenticates with an API key in the X-Cyraduct-Api-Key header.
Only a hash of the key is stored. Two dependencies:

  * optional_tenant  -- returns the tenant id if a valid key is sent, None if
    no key is sent, and 401 if a key is sent but invalid or revoked. Used on
    endpoints that also accept admin/test keys or are public by design.
  * required_tenant  -- like optional_tenant, but when
    CYRADUCT_REQUIRE_TENANT_AUTH is true a missing key is also a 401. Used on
    endpoints that create or consume authorizations.
"""
from typing import Optional
from fastapi import Header, HTTPException

from . import config, storage


def optional_tenant(x_cyraduct_api_key: Optional[str] = Header(None)) -> Optional[str]:
    if not x_cyraduct_api_key:
        return None
    tenant_id = storage.get_tenant_id_by_key(x_cyraduct_api_key)
    if tenant_id is None:
        raise HTTPException(status_code=401, detail="Invalid or revoked API key")
    return tenant_id


def required_tenant(x_cyraduct_api_key: Optional[str] = Header(None)) -> Optional[str]:
    tenant_id = optional_tenant(x_cyraduct_api_key)
    if tenant_id is None and config.REQUIRE_TENANT_AUTH:
        raise HTTPException(status_code=401, detail="API key required")
    return tenant_id
