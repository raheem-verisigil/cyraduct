"""
Consequence scoring.

Deliberately a transparent, rule-based heuristic — not a machine-learned
risk model. A number that nobody can inspect or dispute is worse than no
number at all in a governance product; the scoring logic here is meant to
be readable in one pass and arguable with, the same way the policy packs
are.

Score is 0.0 (trivial) to 1.0 (maximal consequence). It informs display
and default review bands; it does NOT itself allow or deny — the policy
engine's explicit rules remain the actual enforcement logic.
"""
from typing import Dict, Any

_BASE_SCORE_BY_CLASS = {
    "low_risk": 0.05,
    "generic_tool_call": 0.15,
    "health_record_access": 0.55,
    "infra_change": 0.6,
    "financial_transfer": 0.5,
}

_IRREVERSIBLE_ACTION_TYPES = {
    "delete_vm", "wire_transfer", "bulk_record_export", "delete_database",
    "revoke_access_all", "record_transfer",
}


def score(consequence_class: str, action_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    base = _BASE_SCORE_BY_CLASS.get(consequence_class, 0.3)

    reversibility_penalty = 0.25 if action_type in _IRREVERSIBLE_ACTION_TYPES else 0.0

    # Scale up financial actions by amount, in bands rather than a raw
    # linear formula so the reasoning stays legible.
    amount_penalty = 0.0
    amount = payload.get("amount")
    if isinstance(amount, (int, float)):
        if amount > 1_000_000:
            amount_penalty = 0.35
        elif amount > 50_000:
            amount_penalty = 0.2
        elif amount > 5_000:
            amount_penalty = 0.1

    total = min(1.0, base + reversibility_penalty + amount_penalty)

    factors = [f"base_class:{consequence_class}={base}"]
    if reversibility_penalty:
        factors.append(f"irreversible_action_type=+{reversibility_penalty}")
    if amount_penalty:
        factors.append(f"amount_band=+{amount_penalty}")

    return {"consequence_score": round(total, 2), "factors": factors}
