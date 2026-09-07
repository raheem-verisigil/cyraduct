"""
Conformance testing.

Publishing only cases where the system correctly allows something is
marketing. Publishing cases where it correctly REFUSES is what makes
conformance testing mean something to a skeptical buyer (see positioning
language). This router exposes the fixture set and a live run against it.
"""
import json
import os
from fastapi import APIRouter
from ..models import ActionRequest
from .. import policy_engine

router = APIRouter(prefix="/v1/conformance", tags=["conformance"])

_FIXTURES_PATH = os.path.join("policy_packs", "fixtures.json")


def _load_fixtures():
    with open(_FIXTURES_PATH, "r") as f:
        return json.load(f)


@router.get("/fixtures")
def list_fixtures():
    return _load_fixtures()


@router.post("/run")
def run_conformance():
    fixtures = _load_fixtures()
    results = []
    passed = 0
    for fx in fixtures:
        req = ActionRequest(**fx["request"])
        decision = policy_engine.evaluate(req)
        ok = decision.decision == fx["expected_decision"]
        passed += int(ok)
        results.append({
            "id": fx["id"],
            "type": fx["type"],
            "description": fx["description"],
            "expected": fx["expected_decision"],
            "actual": decision.decision,
            "passed": ok,
            "matched_rules": decision.matched_rules,
        })
    return {
        "total": len(fixtures),
        "passed": passed,
        "failed": len(fixtures) - passed,
        "all_passed": passed == len(fixtures),
        "results": results,
    }
