"""
Policy engine.

Design intent (per positioning language): Cyraduct hosts and enforces
versioned policy packs; it does not unilaterally author domain policy.
Each pack declares its own `signed_by` field so provenance is visible in
every decision — "vendor-neutral" is a checkable property, not a claim.
"""
import json
import os
from typing import Dict, Any, List
from .models import ActionRequest, PolicyDecision
from .config import POLICY_PACK_DIR

_pack_cache: Dict[str, dict] = {}


def load_policy_pack(name: str) -> dict:
    if name in _pack_cache:
        return _pack_cache[name]
    path = os.path.join(POLICY_PACK_DIR, f"{name}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Policy pack '{name}' not found at {path}")
    with open(path, "r") as f:
        pack = json.load(f)
    _pack_cache[name] = pack
    return pack


def _condition_matches(condition: Dict[str, Any], req: ActionRequest) -> bool:
    """Evaluate a single rule's `when` block against the request. All keys
    in the condition must match (AND semantics). Supports simple equality,
    'in' lists, and numeric payload thresholds via '<field>_gt' / '_lt'."""
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
            if val is None or not (val > expected):
                return False
        elif key.endswith("_lt"):
            field = key[:-3]
            val = req.payload.get(field)
            if val is None or not (val < expected):
                return False
        else:
            # Fallback: match against payload field directly
            if req.payload.get(key) != expected:
                return False
    return True


def evaluate(req: ActionRequest) -> PolicyDecision:
    pack = load_policy_pack(req.policy_pack)
    matched: List[str] = []
    reasons: List[str] = []
    final_decision = "allow"  # default-allow unless a rule says otherwise

    for rule in pack.get("rules", []):
        if _condition_matches(rule.get("when", {}), req):
            matched.append(rule["id"])
            reasons.append(rule.get("reason", rule["id"]))
            effect = rule.get("effect", "allow")
            # deny is sticky: any matched deny rule wins outright
            if effect == "deny":
                final_decision = "deny"
            elif effect == "conditional" and final_decision != "deny":
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
