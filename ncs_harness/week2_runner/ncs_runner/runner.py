"""Deterministic orchestration contract for NCS model assessments.

The runner deliberately does not assign grades, infer safety, or certify deployment.
Provider adapters are injected by the caller and must be independently reviewed.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol


class Adapter(Protocol):
    adapter_id: str

    def invoke(self, *, input_text: str, system_context: str) -> str: ...


@dataclass(frozen=True)
class Case:
    case_id: str
    rule_id: str
    condition: str
    input_text: str
    system_context: str = ""
    oracle_id: str = "manual"
    expected: str | None = None


@dataclass(frozen=True)
class RunConfig:
    run_id: str
    model_provider: str
    model_id: str
    model_version: str
    model_config_sha256: str
    policy_sha256: str
    suite_version: str
    suite_sha256: str
    mode: str  # native_baseline | policy_configured | effective_system
    environment_id: str
    repeats: int = 1

    def __post_init__(self) -> None:
        if self.mode not in {"native_baseline", "policy_configured", "effective_system"}:
            raise ValueError("unsupported assessment mode")
        if self.repeats < 1:
            raise ValueError("repeats must be >= 1")
        for name in ("model_config_sha256", "policy_sha256", "suite_sha256"):
            value = getattr(self, name)
            if value and (len(value) != 64 or any(c not in "0123456789abcdef" for c in value.lower())):
                raise ValueError(f"{name} must be a 64-character SHA-256 hex digest")


@dataclass
class CaseResult:
    case_id: str
    rule_id: str
    condition: str
    repeat_index: int
    status: str  # COMPLETED | INDETERMINATE
    output_sha256: str | None
    output_chars: int | None
    error_class: str | None = None
    oracle_status: str = "UNRESOLVED"
    attempt_outcome: str = "NOT_ASSESSED"
    effect_outcome: str = "NOT_ASSESSED"
    evidence_refs: list[str] = field(default_factory=list)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def run_cases(
    *,
    adapter: Adapter,
    config: RunConfig,
    cases: Iterable[Case],
    on_result: Callable[[CaseResult, str | None], None] | None = None,
) -> list[CaseResult]:
    """Run in supplied order. Raw outputs are passed only to optional local callback.

    No retries are implicit: retries change exposure and must be explicit in the
    calling orchestration layer and recorded as separate attempts.
    """
    results: list[CaseResult] = []
    for case in cases:
        for repeat in range(config.repeats):
            try:
                output = adapter.invoke(
                    input_text=case.input_text,
                    system_context=case.system_context,
                )
                if not isinstance(output, str):
                    raise TypeError("adapter output must be str")
                result = CaseResult(
                    case_id=case.case_id,
                    rule_id=case.rule_id,
                    condition=case.condition,
                    repeat_index=repeat,
                    status="COMPLETED",
                    output_sha256=sha256_text(output),
                    output_chars=len(output),
                )
            except Exception as exc:  # preserve failure; never convert to PASS
                output = None
                result = CaseResult(
                    case_id=case.case_id,
                    rule_id=case.rule_id,
                    condition=case.condition,
                    repeat_index=repeat,
                    status="INDETERMINATE",
                    output_sha256=None,
                    output_chars=None,
                    error_class=type(exc).__name__,
                )
            results.append(result)
            if on_result:
                on_result(result, output)
    return results


def build_manifest(*, config: RunConfig, adapter_id: str,
                   results: list[CaseResult], started_at: str,
                   completed_at: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema": "ncs.experiment-run.v0.1",
        "run": asdict(config),
        "adapter_id": adapter_id,
        "started_at": started_at,
        "completed_at": completed_at,
        "result_count": len(results),
        "completed_count": sum(r.status == "COMPLETED" for r in results),
        "indeterminate_count": sum(r.status == "INDETERMINATE" for r in results),
        "results": [asdict(r) for r in results],
        "limitations": [
            "Output digests do not prove output truth or oracle correctness.",
            "No grade, certificate, policy-fit decision or deployment authorisation is produced.",
            "Provider-native instructions and safeguards must be recorded by the adapter.",
            "A caller-supplied adapter may have external side effects; use synthetic data first.",
        ],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    payload["integrity"] = {
        "algorithm": "sha256",
        "manifest_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "authenticity": "NOT_ESTABLISHED",
        "append_only_anchor": "NOT_ESTABLISHED",
    }
    return payload


def write_manifest(manifest: dict[str, Any], path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
