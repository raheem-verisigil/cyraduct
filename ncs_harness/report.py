"""Summarize a verified NCS evidence JSONL ledger without issuing a grade."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from .collector import verify_hash_chain


def build_report(path: str | Path) -> dict[str, Any]:
    ledger = Path(path)
    valid, chain_result = verify_hash_chain(ledger)
    if not valid:
        raise ValueError(f"evidence ledger verification failed: {chain_result}")

    records = []
    for line in ledger.read_text(encoding="utf-8").splitlines():
        envelope = json.loads(line)
        records.append(envelope["record"])

    statuses = Counter(record.get("evidence_status", "unknown") for record in records)
    scenarios = [record.get("scenario_id") for record in records]
    return {
        "report_schema": "ncs-assessment-summary/0.1",
        "ledger_integrity": "valid",
        "ledger_head_sha256": chain_result,
        "record_count": len(records),
        "scenario_count": len(set(scenarios)),
        "evidence_status_counts": dict(sorted(statuses.items())),
        "native_behavior_baseline": "not-assessed",
        "grade_issued": False,
        "grade_eligible": False,
        "limitations": [
            "This report summarizes submitted evidence records; it does not independently reproduce the tests.",
            "A valid local hash chain is not an external transparency-log checkpoint or proof of completeness.",
            "Application-control evidence is not a Native Behavior Baseline.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", help="Path to evidence JSONL ledger")
    args = parser.parse_args()
    print(json.dumps(build_report(args.ledger), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
