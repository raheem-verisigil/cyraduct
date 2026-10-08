"""INDEPORA Continuity Record verification boundary.

Cyraduct does not decide evidence independence. It verifies a signed,
versioned INDEPORA result and consumes only a bounded set of facts for policy
and action binding.
"""
from __future__ import annotations

import base64
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import BaseModel, ConfigDict, Field, model_serializer

from .canonical import canonical_json_bytes, sha256_hex

INDEPORA_SCHEMA = "indepora.evidence_continuity_record.v1"
INDEPORA_PUBLIC_KEY_ENV = "INDEPORA_PUBLIC_KEY_B64"
INDEPORA_KEY_ID_ENV = "INDEPORA_KEY_ID"


class IndeporaVerificationError(ValueError):
    """Raised when a Continuity Record cannot be safely consumed."""


class EvidenceAssuranceBinding(BaseModel):
    """Allowlisted facts derived from a verified INDEPORA record."""

    model_config = ConfigDict(populate_by_name=True)

    provider: str = "indepora"
    record_id: str = Field(..., max_length=256)
    record_hash: str = Field(..., max_length=128)
    schema_name: str = Field(INDEPORA_SCHEMA, alias="schema")
    standing: str = Field(..., max_length=80)
    candidate_origin_count: int = Field(..., ge=0)
    unknown_relationship_count: int = Field(..., ge=0)
    conflict_count: int = Field(..., ge=0)
    issued_at: str
    valid_until: str
    verification_key_id: str = Field(..., max_length=256)
    not_superseded: bool = True
    sandbox_only: bool = False

    @model_serializer
    def serialize_public(self) -> dict[str, Any]:
        data = self.__dict__.copy()
        data["schema"] = data.pop("schema_name")
        return data


def _parse_time(value: str) -> datetime:
    try:
        normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
        parsed = datetime.fromisoformat(normalized)
    except (TypeError, ValueError) as exc:
        raise IndeporaVerificationError("indepora_valid_until_invalid") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _record_payload(record: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(record)
    payload.pop("record_hash", None)
    payload.pop("signature", None)
    return payload


def _verify_signature(record_hash: str, signature: Dict[str, Any], public_key_b64: str) -> None:
    if signature.get("algorithm") != "Ed25519":
        raise IndeporaVerificationError("indepora_signature_algorithm_invalid")
    if not public_key_b64:
        raise IndeporaVerificationError("indepora_verifier_not_configured")
    try:
        public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64))
        public_key.verify(base64.b64decode(signature["value"]), record_hash.encode("ascii"))
    except Exception as exc:
        raise IndeporaVerificationError("indepora_signature_invalid") from exc


def verify_and_bind(
    record: Dict[str, Any],
    *,
    public_key_b64: Optional[str] = None,
    expected_key_id: Optional[str] = None,
) -> EvidenceAssuranceBinding:
    """Verify a signed record and return only trusted policy facts.

    The signed record is deliberately not copied into a Cyraduct receipt.
    The receipt binds the record hash and the derived facts instead.
    """
    if record.get("schema") != INDEPORA_SCHEMA:
        raise IndeporaVerificationError("indepora_schema_unsupported")

    record_id = record.get("record_id")
    record_hash = record.get("record_hash")
    signature = record.get("signature") or {}
    if not record_id or not record_hash or not signature:
        raise IndeporaVerificationError("indepora_record_incomplete")

    expected_hash = sha256_hex(_record_payload(record))
    if record_hash != expected_hash:
        raise IndeporaVerificationError("indepora_record_hash_mismatch")

    key_id = signature.get("key_id")
    configured_key_id = expected_key_id or os.getenv(INDEPORA_KEY_ID_ENV, "")
    if configured_key_id and key_id != configured_key_id:
        raise IndeporaVerificationError("indepora_key_id_mismatch")
    _verify_signature(
        record_hash,
        signature,
        public_key_b64 or os.getenv(INDEPORA_PUBLIC_KEY_ENV, ""),
    )

    valid_until = record.get("valid_until")
    issued_at = record.get("issued_at")
    if not issued_at:
        raise IndeporaVerificationError("indepora_issued_at_missing")
    if not valid_until or _parse_time(valid_until) <= datetime.now(timezone.utc):
        raise IndeporaVerificationError("indepora_record_expired")

    continuity = record.get("continuity") or {}
    if continuity.get("superseded") is True:
        raise IndeporaVerificationError("indepora_record_superseded")

    assessment = record.get("origin_assessment") or {}
    standing = record.get("standing") or {}
    status = standing.get("status") or assessment.get("independence_status")
    if not status:
        raise IndeporaVerificationError("indepora_standing_missing")

    try:
        binding = EvidenceAssuranceBinding(
            record_id=record_id,
            record_hash=record_hash,
            schema=record["schema"],
            standing=status,
            candidate_origin_count=int(assessment["candidate_origin_count"]),
            unknown_relationship_count=int(assessment.get("unknown_relationship_count", 0)),
            conflict_count=int(assessment.get("conflict_count", 0)),
            issued_at=issued_at,
            valid_until=valid_until,
            verification_key_id=key_id,
            not_superseded=True,
            sandbox_only=bool(record.get("sandbox_only", (standing.get("scope") == "sandbox"))),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise IndeporaVerificationError("indepora_assessment_incomplete") from exc
    return binding


def verify_record_response(record: Dict[str, Any]) -> dict[str, Any]:
    binding = verify_and_bind(record)
    return {"valid": True, "binding": binding.model_dump(by_alias=True)}
