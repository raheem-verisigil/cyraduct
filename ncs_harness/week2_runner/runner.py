"""Provider-neutral NCS execution runner (local adapter contract, v0.1).

The runner invokes an explicitly supplied adapter. It has no network client,
provider credentials, hidden default model, or deployment authority. Raw inputs
and outputs are passed in memory to the adapter/oracle and are not written to
the returned evidence manifest; only output digests and outcome metadata are
retained.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Literal, Protocol

Outcome = Literal["PASS", "FAIL", "INDETERMINATE", "NOT_TESTED"]


class ModelAdapter(Protocol):
    """Minimal provider adapter contract; implementations own provider I/O."""

    @property
    def adapter_id(self) -> str: ...

    def invoke(self, *, input_text: str, system_context: str | None = None) -> str: ...


@dataclass(frozen=True)
class TestCase:
    case_id: str
    input_text: str
    oracle: Callable[[str], Outcome]
    system_context: str | None = None
    dimension: str = "unspecified"


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def run_assessment(
    *,
    adapter: ModelAdapter,
    cases: Iterable[TestCase],
    model_configuration_sha256: str,
    suite_version: str,
    assessment_mode: Literal["NATIVE_BASELINE", "POLICY_CONFIGURED", "EFFECTIVE_SYSTEM"],
    run_id: str,
    source_commit: str | None = None,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    """Execute cases and return a privacy-minimised, deterministic evidence manifest.

    This function does not assign a grade, certificate, policy-fit decision or
    deployment authorisation. Provider exceptions and malformed oracle outcomes
    become INDETERMINATE results rather than passes.
    """
    if len(model_configuration_sha256) != 64 or any(c not in "0123456789abcdef" for c in model_configuration_sha256):
        raise ValueError("model_configuration_sha256 must be lowercase SHA-256")
    if not suite_version or not run_id:
        raise ValueError("suite_version and run_id are required")
    if assessment_mode not in {"NATIVE_BASELINE", "POLICY_CONFIGURED", "EFFECTIVE_SYSTEM"}:
        raise ValueError("unsupported assessment_mode")

    seen: set[str] = set()
    results: list[dict[str, Any]] = []
    for case in cases:
        if not case.case_id or case.case_id in seen:
            raise ValueError("case_id values must be non-empty and unique")
        seen.add(case.case_id)
        if not isinstance(case.input_text, str) or not case.input_text:
            results.append({
                "case_id": case.case_id,
                "dimension": case.dimension,
                "outcome": "NOT_TESTED",
                "reason": "empty-or-invalid-input",
                "output_sha256": None,
            })
            continue
        try:
            output = adapter.invoke(input_text=case.input_text, system_context=case.system_context)
            if not isinstance(output, str):
                raise TypeError("adapter output must be text")
            output_digest = hashlib.sha256(output.encode("utf-8")).hexdigest()
            outcome = case.oracle(output)
            if outcome not in {"PASS", "FAIL", "INDETERMINATE", "NOT_TESTED"}:
                raise ValueError("oracle returned an unsupported outcome")
            results.append({
                "case_id": case.case_id,
                "dimension": case.dimension,
                "outcome": outcome,
                "reason": None,
                "output_sha256": output_digest,
            })
        except Exception as exc:
            results.append({
                "case_id": case.case_id,
                "dimension": case.dimension,
                "outcome": "INDETERMINATE",
                "reason": type(exc).__name__,
                "output_sha256": None,
            })

    counts = {name: sum(1 for item in results if item["outcome"] == name)
              for name in ("PASS", "FAIL", "INDETERMINATE", "NOT_TESTED")}
    return {
        "schema": "ncs-execution-manifest/0.1",
        "run_id": run_id,
        "recorded_at": recorded_at or datetime.now(timezone.utc).isoformat(),
        "subject": {"model_configuration_sha256": model_configuration_sha256},
        "execution": {
            "adapter_id": adapter.adapter_id,
            "assessment_mode": assessment_mode,
            "suite_version": suite_version,
            "source_commit": source_commit,
            "case_count": len(results),
        },
        "results": results,
        "summary": counts,
        "integrity": {"manifest_sha256": _canonical_digest({
            "run_id": run_id,
            "subject": {"model_configuration_sha256": model_configuration_sha256},
            "execution": {
                "adapter_id": adapter.adapter_id,
                "assessment_mode": assessment_mode,
                "suite_version": suite_version,
                "source_commit": source_commit,
                "case_count": len(results),
            },
            "results": results,
            "summary": counts,
        })},
        "limitations": [
            "No grade, certificate, policy-fit decision or deployment authorisation is issued.",
            "Raw inputs and outputs are not included in this manifest.",
            "Oracle validity and provider identity require independent validation.",
            "This run measures only the supplied adapter, configuration and test cases.",
        ],
    }
