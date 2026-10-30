"""Deterministic synthetic case generator for NCS Week 1 harness."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

DEFAULT_PACK = Path(__file__).with_name("scenarios.json")


def load_scenarios(path: str | Path = DEFAULT_PACK) -> dict[str, Any]:
    pack = json.loads(Path(path).read_text(encoding="utf-8"))
    if pack.get("schema") != "ncs-assessment-scenarios/0.1":
        raise ValueError("unsupported scenario pack schema")
    ids = [item.get("id") for item in pack.get("scenarios", [])]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("scenario IDs must be present and unique")
    return pack


def generate_cases(*, seed: str, pack: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Generate stable case IDs without changing oracle inputs or expected outcomes."""
    if not seed:
        raise ValueError("seed is required")
    pack = pack or load_scenarios()
    generated = []
    for scenario in pack["scenarios"]:
        source = copy.deepcopy(scenario)
        canonical = json.dumps(source, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        digest = hashlib.sha256((seed + "\n" + canonical).encode("utf-8")).hexdigest()
        generated.append({
            "schema": "ncs-generated-case/0.1",
            "case_id": f"{scenario['id']}-{digest[:12]}",
            "source_scenario_id": scenario["id"],
            "seed_digest": hashlib.sha256(seed.encode("utf-8")).hexdigest(),
            "input": source["input"],
            "oracle": source["expected"],
            "evidence_requirements": source.get("evidence", []),
            "source_pack_sha256": hashlib.sha256(
                json.dumps(pack, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            ).hexdigest(),
            "synthetic_only": True,
            "external_side_effects": "disabled-or-mocked",
        })
    return generated
