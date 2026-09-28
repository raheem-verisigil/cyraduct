"""
CYRADUCT runtime execution decision layer.

This module decides whether a proposed agent action should cross the
consequence/action boundary now, using current authority, authorization
freshness, state consistency, reversibility, and measurable runtime pressure.

It is intentionally separate from the existing advisory/attested policy
engine. This first slice returns a deterministic runtime decision; the next
enforcement slice should bind that decision to a signed, consumable execution
pass enforced by the broker.
"""
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.config import CONSEQUENCE_CLASS_EXPIRY_SECONDS
from app.models import _contains_nul
from app.models import new_id


RuntimeDecisionType = Literal[
    "allow",
    "throttle",
    "hold",
    "reauthorize",
    "deny",
    "terminate",
]


class RuntimeActionRequest(BaseModel):
    agent_id: str = Field(min_length=1)
    action_type: str = Field(min_length=1)
    consequence_class: str = Field(min_length=1)
    target: str | None = None
    resource: str | None = None
    reversibility: Literal[
        "reversible", "partially_reversible", "irreversible"
    ] = "reversible"
    authority: Literal[
        "present", "delegated", "missing", "expired", "unknown"
    ] = "present"
    authorization_expires_at: str | None = None
    authorized_state_version: str | None = None
    current_state_version: str | None = None
    action_id: str | None = None
    idempotency_key: str | None = None
    policy_pack: str = "generic"
    purpose: str | None = None
    principal: str | None = None
    framework: str | None = None
    payload: dict = Field(default_factory=dict)
    runtime_state: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def reject_nul_bytes(self):
        for value in (
            self.agent_id,
            self.action_type,
            self.consequence_class,
            self.target,
            self.resource,
            self.authorization_expires_at,
            self.authorized_state_version,
            self.current_state_version,
            self.action_id,
            self.idempotency_key,
            self.policy_pack,
            self.purpose,
            self.principal,
            self.framework,
        ):
            if _contains_nul(value):
                raise ValueError("NUL byte is not permitted")
        return self


class RuntimeDecision(BaseModel):
    action_id: str
    decision: RuntimeDecisionType
    reasons: list[str]
    signals: dict[str, int | bool | str | None]
    enforcement_required: bool = True
    policy_pack: str


def _authorization_expired(value: str | None) -> bool:
    if not value:
        return False
    try:
        normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
        expiry = datetime.fromisoformat(normalized)
    except ValueError:
        return True
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) >= expiry


def _integer_signal(state: dict, key: str) -> int | None:
    value = state.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return -1
    return value


def evaluate(req: RuntimeActionRequest) -> RuntimeDecision:
    action_id = req.action_id or new_id("runtime")

    actions_last_minute = _integer_signal(req.runtime_state, "actions_last_minute")
    retries_last_minute = _integer_signal(req.runtime_state, "retries_last_minute")
    pending_side_effects = _integer_signal(
        req.runtime_state, "pending_side_effects"
    )

    authorization_expired = _authorization_expired(req.authorization_expires_at)
    state_changed = (
        req.authorized_state_version is not None
        and req.current_state_version is not None
        and req.authorized_state_version != req.current_state_version
    )

    signals = {
        "authority": req.authority,
        "reversibility": req.reversibility,
        "authorization_expired": authorization_expired,
        "state_changed": state_changed,
        "actions_last_minute": actions_last_minute,
        "retries_last_minute": retries_last_minute,
        "pending_side_effects": pending_side_effects,
    }

    if req.consequence_class not in CONSEQUENCE_CLASS_EXPIRY_SECONDS:
        return RuntimeDecision(
            action_id=action_id,
            decision="deny",
            reasons=["unknown_consequence_class"],
            signals=signals,
            policy_pack=req.policy_pack,
        )

    if actions_last_minute == -1 or retries_last_minute == -1 or pending_side_effects == -1:
        return RuntimeDecision(
            action_id=action_id,
            decision="deny",
            reasons=["malformed_runtime_signal"],
            signals=signals,
            policy_pack=req.policy_pack,
        )

    if authorization_expired or req.authority == "expired":
        return RuntimeDecision(
            action_id=action_id,
            decision="reauthorize",
            reasons=["authorization_expired"],
            signals=signals,
            policy_pack=req.policy_pack,
        )

    if state_changed:
        return RuntimeDecision(
            action_id=action_id,
            decision="reauthorize",
            reasons=["authorized_state_version_changed"],
            signals=signals,
            policy_pack=req.policy_pack,
        )

    if req.authority in {"missing", "unknown"}:
        return RuntimeDecision(
            action_id=action_id,
            decision="hold",
            reasons=["authority_missing_or_unknown"],
            signals=signals,
            policy_pack=req.policy_pack,
        )

    if req.authority == "delegated" and req.reversibility == "irreversible":
        return RuntimeDecision(
            action_id=action_id,
            decision="hold",
            reasons=["delegated_authority_cannot_execute_irreversible_action"],
            signals=signals,
            policy_pack=req.policy_pack,
        )

    pressure_reasons: list[str] = []
    if actions_last_minute is not None and actions_last_minute > 60:
        pressure_reasons.append("action_velocity_exceeded")
    if retries_last_minute is not None and retries_last_minute > 5:
        pressure_reasons.append("retry_velocity_exceeded")
    if (
        pending_side_effects is not None
        and pending_side_effects > 5
        and req.consequence_class != "low_risk"
    ):
        pressure_reasons.append("pending_side_effects_exceeded")

    if pressure_reasons:
        return RuntimeDecision(
            action_id=action_id,
            decision="throttle",
            reasons=pressure_reasons,
            signals=signals,
            policy_pack=req.policy_pack,
        )

    return RuntimeDecision(
        action_id=action_id,
        decision="allow",
        reasons=["runtime_conditions_satisfied"],
        signals=signals,
        policy_pack=req.policy_pack,
    )
