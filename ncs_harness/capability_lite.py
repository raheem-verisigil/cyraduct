"""NCS capability-lite predictor features; no general intelligence score."""
from __future__ import annotations

import math
from typing import Any

FEATURES = (
    "tool_use",
    "context_instruction_retention",
    "calibration_abstention",
    "robustness",
)


def wilson_interval(successes: int, trials: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if trials < 1 or successes < 0 or successes > trials:
        raise ValueError("invalid binomial counts")
    p = successes / trials
    denominator = 1 + z * z / trials
    centre = (p + z * z / (2 * trials)) / denominator
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * trials)) / trials) / denominator
    return max(0.0, centre - margin), min(1.0, centre + margin)


def build_capability_lite_profile(observations: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize only pre-registered predictors; absent dimensions stay NOT_TESTED."""
    totals = {name: {"successes": 0, "trials": 0} for name in FEATURES}
    for item in observations:
        feature = item.get("feature")
        if feature not in totals:
            raise ValueError(f"unsupported capability-lite feature: {feature}")
        successes = item.get("successes")
        trials = item.get("trials")
        if not isinstance(successes, int) or not isinstance(trials, int):
            raise ValueError("successes and trials must be integers")
        if trials < 1 or successes < 0 or successes > trials:
            raise ValueError("invalid capability observation counts")
        totals[feature]["successes"] += successes
        totals[feature]["trials"] += trials

    results = {}
    for name, counts in totals.items():
        n = counts["trials"]
        if n == 0:
            results[name] = {"status": "NOT_TESTED", "successes": 0, "trials": 0, "rate": None, "ci95": None}
        else:
            low, high = wilson_interval(counts["successes"], n)
            results[name] = {
                "status": "OBSERVED",
                **counts,
                "rate": counts["successes"] / n,
                "ci95": [low, high],
            }
    return {
        "schema": "ncs-capability-lite-profile/0.1",
        "features": results,
        "aggregate_intelligence_score": None,
        "grade_effect": "NONE",
        "limitations": [
            "Predictor features only; not a general intelligence benchmark.",
            "Rates describe tested tasks and conditions, not universal capability.",
            "Capability cannot raise or repair a conduct grade.",
        ],
    }
