"""
Policy engine.

Design intent (per positioning language): Cyraduct hosts and enforces
versioned policy packs; it does not unilaterally author domain policy.
Each pack declares its own `signed_by` field so provenance is visible in
every decision — "vendor-neutral" is a checkable property, not a claim.
"""

import json
import math
import os
from typing import Dict, Any, List, Optional

from .models import ActionRequest, PolicyDecision
from .config import (
    POLICY_PACK_DIR,
    CONSEQUENCE_CLASS_EXPIRY_SECONDS,
)

_pack_cache: Dict[str, dict] = {}


def load_policy_pack(name: str) -> dict:
    if name in _pack_cache:
        return _pack_cache[name]

    path = os.path.join(POLICY_PACK_DIR, f"{name}.json")

    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Policy pack '{name}' not found at {path}"
        )

    with open(path, "r") as f:
        pack = json.load(f)

    _pack_cache[name] = pack
    return pack


def _condition_matches(
    condition: Dict[str, Any],
    req: ActionRequest,
) -> bool:
    """Evaluate a single rule's `when` block against the request.

    All keys in the condition must match (AND semantics). Supports simple
    equality, 'in' lists, and numeric payload thresholds via
    '<field>_gt' / '_lt'.
    """
    for key, expected in condition.items():
        if key == "action_type":
            if req.action_type != expected:
                return False

        elif key == "consequence_class":
            if req.consequence_class != expected:
                return False

        elif key == "jurisdiction_in":
            if req.jurisdiction not in expected:
                return False

        elif key == "jurisdiction_missing":
            jurisdiction_is_missing = not req.jurisdiction
            if jurisdiction_is_missing != expected:
                return False

        elif key == "purpose_missing":
            purpose_is_missing = not req.purpose
            if purpose_is_missing != expected:
                return False

        elif key.endswith("_gt"):
            field = key[:-3]
            val = req.payload.get(field)

            if val is None:
                return False

            try:
                if not (val > expected):
                    return False
            except (TypeError, ValueError):
                return False

        elif key.endswith("_lt"):
            field = key[:-3]
            val = req.payload.get(field)

            if val is None:
                return False

            try:
                if not (val < expected):
                    return False
            except (TypeError, ValueError):
                return False

        else:
            # Fallback: match against payload field directly
            if req.payload.get(key) != expected:
                return False

    return True


def _deny(
    req: ActionRequest,
    reason: str,
    policy_pack_version: str = "unknown",
) -> PolicyDecision:
    """Construct a deterministic deny decision for invalid policy context."""
    return PolicyDecision(
        decision="deny",
        reasons=[reason],
        policy_pack=req.policy_pack,
        policy_pack_version=policy_pack_version,
        matched_rules=[],
    )


def _validate_financial_transfer(req: ActionRequest) -> Optional[str]:
    """Validate the minimum semantic boundary for financial transfers.

    A financial transfer must carry a finite, numeric, strictly positive
    amount. Boolean values are rejected because bool is a subclass of int
    in Python.
    """
    if req.consequence_class != "financial_transfer":
        return None

    amount = req.payload.get("amount")

    if isinstance(amount, bool):
        return "financial_transfer_amount_must_be_numeric"

    if not isinstance(amount, (int, float)):
        return "financial_transfer_amount_must_be_numeric"

    try:
        if not math.isfinite(amount):
            return "financial_transfer_amount_must_be_finite"
    except OverflowError:
        return "financial_transfer_amount_must_be_finite"

    if amount <= 0:
        return "financial_transfer_amount_must_be_positive"

    return None


def evaluate(req: ActionRequest) -> PolicyDecision:
    # Unknown consequence classes must never silently enter the
    # default-allow path.
    if req.consequence_class not in CONSEQUENCE_CLASS_EXPIRY_SECONDS:
        return _deny(
            req,
            "unknown_consequence_class",
        )

    # Financial amount semantics are validated before policy rules run.
    financial_error = _validate_financial_transfer(req)

    if financial_error is not None:
        return _deny(
            req,
            financial_error,
        )

    # Unknown policy packs are an explicit deny, not a server error.
    try:
        pack = load_policy_pack(req.policy_pack)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return _deny(
            req,
            "unknown_policy_pack",
        )

    matched: List[str] = []
    reasons: List[str] = []
    final_decision = "allow"

    for rule in pack.get("rules", []):
        if _condition_matches(rule.get("when", {}), req):
            matched.append(rule["id"])
            reasons.append(rule.get("reason", rule["id"]))

            effect = rule.get("effect", "allow")

            # deny is sticky: any matched deny rule wins outright
            if effect == "deny":
                final_decision = "deny"

            elif (
                effect == "conditional"
                and final_decision != "deny"
            ):
                final_decision = "conditional"

    if not matched:
        reasons.append("no_rule_matched_default_allow")

    return PolicyDecision(
        decision=final_decision,
        reasons=reasons,
        policy_pack=pack["name"],
        policy_pack_version=pack["version"],
        matched_rules=matched,
    )
