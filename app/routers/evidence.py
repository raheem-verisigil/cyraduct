"""
Evidence registration.

Registers a reference to external assurance material (a SOC2 report, a
model card, a human approval record) by its content hash. Cyraduct never
stores or sees the underlying document — only a hash and a label — which
is what lets a receipt cite "soc2_type2 evidence hash X" without Cyraduct
becoming a repository of sensitive compliance documents itself.

This is intentionally a thin registry, not the "evidence -> reliance
limit" binding logic described in the roadmap doc. That binding (evidence
package -> automatically-derived policy limits) is a real Phase 2 item,
not built here — registering evidence today lets a receipt reference it;
it does not yet automatically change what a policy pack allows.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from ..models import EvidenceRegisterRequest, EvidencePackage, new_id
from .. import storage

router = APIRouter(prefix="/v1/evidence", tags=["evidence"])


@router.post("", response_model=EvidencePackage)
def register_evidence(req: EvidenceRegisterRequest):
    pkg = EvidencePackage(
        evidence_id=new_id("ev"),
        label=req.label,
        content_hash=req.content_hash,
        registered_at=datetime.now(timezone.utc).isoformat(),
        registered_by=req.registered_by,
    )
    storage.save_evidence(pkg)
    storage.append_audit("evidence_registered", {"evidence_id": pkg.evidence_id, "label": pkg.label})
    return pkg


@router.get("/{evidence_id}", response_model=EvidencePackage)
def get_evidence(evidence_id: str):
    pkg = storage.get_evidence(evidence_id)
    if not pkg:
        raise HTTPException(status_code=404, detail="Evidence package not found")
    return pkg
