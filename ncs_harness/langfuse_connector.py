"""Langfuse v4 read connector for NCS failure-evidence ingestion.

Polls the supported Observations API v2. It never treats Langfuse API
authentication as proof of model artifact identity or event authorship.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterator
from urllib.parse import urlparse

import httpx

from ncs_harness.failure_evidence import normalize_observability_event, sha256_json

HEX64 = re.compile(r"^[0-9a-f]{64}$")
LEVELS = ("ERROR", "WARNING")


@dataclass(frozen=True)
class LangfuseConfig:
    base_url: str
    public_key: str
    secret_key: str
    timeout_seconds: float = 20.0
    page_limit: int = 500
    artifact_metadata_key: str = "ncs.artifact.sha256"
    category_metadata_key: str = "ncs.failure.category"
    severity_metadata_key: str = "ncs.failure.severity"
    status_metadata_key: str = "ncs.failure.status"

    @classmethod
    def from_env(cls) -> "LangfuseConfig":
        return cls(
            base_url=os.environ.get("LANGFUSE_BASE_URL", "https://cloud.langfuse.com"),
            public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
            secret_key=os.environ["LANGFUSE_SECRET_KEY"],
            timeout_seconds=float(os.environ.get("NCS_LANGFUSE_TIMEOUT", "20")),
            page_limit=int(os.environ.get("NCS_LANGFUSE_PAGE_LIMIT", "500")),
        )

    def validate(self) -> None:
        parsed = urlparse(self.base_url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("LANGFUSE_BASE_URL must be an HTTPS origin without embedded credentials")
        if not self.public_key or not self.secret_key:
            raise ValueError("Langfuse public and secret keys are required")
        if not 1 <= self.page_limit <= 1000:
            raise ValueError("page_limit must be between 1 and 1000")


class LangfuseConnectorError(RuntimeError):
    pass


class LangfuseNCSConnector:
    """Bounded, read-only Langfuse observation poller."""

    def __init__(self, config: LangfuseConfig, *, client: httpx.Client | None = None):
        config.validate()
        self.config = config
        self._owns_client = client is None
        self.client = client or httpx.Client(
            base_url=config.base_url.rstrip("/"),
            auth=(config.public_key, config.secret_key),
            timeout=config.timeout_seconds,
            headers={"Accept": "application/json", "User-Agent": "NCS-Langfuse-Connector/0.1"},
        )

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    @staticmethod
    def _validate_window(from_start_time: str, to_start_time: str) -> None:
        def parse(value: str) -> datetime:
            try:
                result = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except (TypeError, ValueError) as exc:
                raise ValueError("time bounds must be ISO-8601 timestamps") from exc
            if result.tzinfo is None:
                raise ValueError("time bounds must include a timezone")
            return result
        if parse(from_start_time) >= parse(to_start_time):
            raise ValueError("from_start_time must be earlier than to_start_time")

    def iter_observations(self, *, from_start_time: str, to_start_time: str) -> Iterator[dict[str, Any]]:
        """Yield only ERROR/WARNING observations; all requests have a fixed time window."""
        self._validate_window(from_start_time, to_start_time)
        for level in LEVELS:
            cursor = None
            while True:
                params: dict[str, Any] = {
                    "fromStartTime": from_start_time,
                    "toStartTime": to_start_time,
                    "level": level,
                    "fields": "core,basic,metadata,model,trace_context",
                    "limit": self.config.page_limit,
                }
                if cursor:
                    params["cursor"] = cursor
                try:
                    response = self.client.get(self.config.base_url.rstrip("/") + "/api/public/v2/observations", params=params)
                    response.raise_for_status()
                    body = response.json()
                except httpx.HTTPStatusError as exc:
                    status = exc.response.status_code
                    if status in (401, 403):
                        raise LangfuseConnectorError("Langfuse authentication/permission failure; check read access to traces") from exc
                    if status == 429:
                        raise LangfuseConnectorError("Langfuse API rate limit reached; retry later with a smaller polling window") from exc
                    raise LangfuseConnectorError(f"Langfuse observations API returned HTTP {status}") from exc
                except (httpx.HTTPError, ValueError) as exc:
                    raise LangfuseConnectorError("Langfuse observations request failed or returned invalid JSON") from exc
                rows = body.get("data")
                if not isinstance(rows, list):
                    raise LangfuseConnectorError("Langfuse response missing observations data array")
                for row in rows:
                    if isinstance(row, dict):
                        yield row
                meta = body.get("meta") or {}
                cursor = meta.get("cursor") if isinstance(meta, dict) else None
                if not cursor:
                    break

    def normalize_observation(self, row: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
        """Return a normalized, unverified signal or a quarantine reason.

        Artifact digest must be explicitly attached by the instrumented workload
        under the configured metadata key. No model-name or release-name fallback.
        """
        metadata = row.get("metadata") or {}
        if not isinstance(metadata, dict):
            return None, "metadata_not_object"
        artifact_digest = metadata.get(self.config.artifact_metadata_key)
        if not isinstance(artifact_digest, str) or not HEX64.fullmatch(artifact_digest):
            return None, "missing_or_invalid_artifact_digest"
        level = str(row.get("level") or "").upper()
        if level not in LEVELS:
            return None, "not_a_failure_level"
        observed_at = row.get("startTime")
        if not isinstance(observed_at, str):
            return None, "missing_observation_timestamp"
        status_message = row.get("statusMessage")
        # Only retain a bounded error-type token, never raw exception text.
        error_type = None
        if isinstance(status_message, str) and status_message:
            # Retain only a likely exception class token, never its message.
            match = re.match(r"^([A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception))(?::|$)", status_message.strip())
            if match:
                error_type = match.group(1)[:96]
        category = metadata.get(self.config.category_metadata_key, "reliability")
        severity = metadata.get(self.config.severity_metadata_key, "high" if level == "ERROR" else "medium")
        status = metadata.get(self.config.status_metadata_key, "observed")
        identity = {
            "id": row.get("id"), "traceId": row.get("traceId"), "type": row.get("type"),
            "name": row.get("name"), "level": level, "startTime": observed_at,
            "statusMessage": status_message, "version": row.get("version"),
            "model": row.get("model"), "metadata": {
                self.config.artifact_metadata_key: artifact_digest,
                self.config.category_metadata_key: category,
                self.config.severity_metadata_key: severity,
                self.config.status_metadata_key: status,
            },
        }
        payload_digest = sha256_json(identity)
        try:
            event = normalize_observability_event(
                event_id=f"langfuse:{row.get('id') or payload_digest}",
                observed_at=observed_at,
                source={
                    "integration": "langfuse",
                    "event_type": f"observation.{level.lower()}",
                    "source_event_id": str(row.get("id") or ""),
                    "trace_id": row.get("traceId"),
                    "span_id": row.get("id"),
                    "service_name": metadata.get("service.name"),
                },
                subject={
                    "artifact_digest": artifact_digest,
                    "provider": metadata.get("gen_ai.provider.name"),
                    "model_name": row.get("model"),
                    "model_version": metadata.get("gen_ai.response.model.version"),
                    "deployment_id": metadata.get("service.instance.id"),
                    "environment": row.get("environment"),
                },
                failure={
                    "category": category, "severity": severity,
                    "signal_kind": "hard_error" if level == "ERROR" else "soft_failure",
                    "status": status, "error_type": error_type,
                    "detector": "langfuse-observation-level", "detector_version": "0.1",
                    "summary_code": f"langfuse_{level.lower()}",
                },
                evidence={"payload_digest": payload_digest, "evidence_refs": []},
                content_mode="none",
            )
        except (ValueError, TypeError) as exc:
            return None, f"invalid_ncs_metadata:{str(exc)}"
        return event, None


    def iter_scores(self, *, from_timestamp: str, to_timestamp: str) -> Iterator[dict[str, Any]]:
        """Yield evaluation scores from Scores API v3 within a fixed window."""
        self._validate_window(from_timestamp, to_timestamp)
        cursor = None
        while True:
            params: dict[str, Any] = {
                "fromTimestamp": from_timestamp,
                "toTimestamp": to_timestamp,
                "source": "EVAL",
                "fields": "details,subject",
                "limit": self.config.page_limit,
            }
            if cursor:
                params["cursor"] = cursor
            try:
                response = self.client.get(self.config.base_url.rstrip("/") + "/api/public/v3/scores", params=params)
                response.raise_for_status()
                body = response.json()
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status in (401, 403):
                    raise LangfuseConnectorError("Langfuse authentication/permission failure reading evaluation scores") from exc
                if status == 429:
                    raise LangfuseConnectorError("Langfuse API rate limit reached while reading evaluation scores") from exc
                raise LangfuseConnectorError(f"Langfuse scores API returned HTTP {status}") from exc
            except (httpx.HTTPError, ValueError) as exc:
                raise LangfuseConnectorError("Langfuse scores request failed or returned invalid JSON") from exc
            rows = body.get("data")
            if not isinstance(rows, list):
                raise LangfuseConnectorError("Langfuse scores response missing data array")
            for row in rows:
                if isinstance(row, dict):
                    yield row
            meta = body.get("meta") or {}
            cursor = meta.get("cursor") if isinstance(meta, dict) else None
            if not cursor:
                break

    def normalize_score(self, row: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
        """Map only explicit failed eval outcomes; scores are not model-authenticity proofs."""
        details = row.get("metadata") or (row.get("details") or {}).get("metadata") or {}
        if not isinstance(details, dict):
            return None, "score_metadata_not_object"
        artifact_digest = details.get(self.config.artifact_metadata_key)
        if not isinstance(artifact_digest, str) or not HEX64.fullmatch(artifact_digest):
            return None, "score_missing_or_invalid_artifact_digest"
        data_type = str(row.get("dataType") or "").upper()
        value = row.get("value")
        explicit_failure = details.get("ncs.failure.is_failure")
        failed = explicit_failure is True
        if data_type == "BOOLEAN" and value is False:
            failed = True
        elif data_type == "CATEGORICAL" and isinstance(value, str) and value.strip().lower() in {
            "fail", "failed", "failure", "error", "incorrect", "unsafe", "false"
        }:
            failed = True
        if not failed:
            return None, "evaluation_score_not_explicitly_failed"
        subject = row.get("subject") or {}
        if not isinstance(subject, dict):
            return None, "score_subject_not_object"
        timestamp = row.get("timestamp")
        if not isinstance(timestamp, str):
            return None, "score_missing_timestamp"
        category = details.get(self.config.category_metadata_key, "reliability")
        severity = details.get(self.config.severity_metadata_key, "medium")
        status = details.get(self.config.status_metadata_key, "observed")
        score_identity = {
            "id": row.get("id"), "name": row.get("name"), "value": value,
            "dataType": data_type, "source": row.get("source"), "timestamp": timestamp,
            "subject": subject, "artifact_digest": artifact_digest,
            "failure_category": category, "failure_severity": severity,
        }
        digest = sha256_json(score_identity)
        try:
            event = normalize_observability_event(
                event_id=f"langfuse-score:{row.get('id') or digest}",
                observed_at=timestamp,
                source={
                    "integration": "langfuse", "event_type": f"evaluation.score.{row.get('name') or 'unnamed'}",
                    "source_event_id": str(row.get("id") or ""),
                    "trace_id": subject.get("traceId"),
                    "span_id": subject.get("id") if subject.get("kind") == "observation" else None,
                    "service_name": details.get("service.name"),
                },
                subject={
                    "artifact_digest": artifact_digest,
                    "provider": details.get("gen_ai.provider.name"),
                    "model_name": details.get("gen_ai.request.model"),
                    "model_version": details.get("gen_ai.response.model.version"),
                    "deployment_id": details.get("service.instance.id"),
                    "environment": row.get("environment"),
                },
                failure={
                    "category": category, "severity": severity, "signal_kind": "soft_failure",
                    "status": status, "detector": "langfuse-evaluation-score-v3",
                    "detector_version": "0.1", "rule_or_eval_id": str(row.get("name") or ""),
                    "summary_code": "langfuse_eval_score_failed",
                },
                evidence={"payload_digest": digest, "evidence_refs": []},
                content_mode="none",
            )
        except (ValueError, TypeError) as exc:
            return None, f"invalid_ncs_score_metadata:{str(exc)}"
        return event, None

    def poll(self, *, from_start_time: str, to_start_time: str) -> dict[str, Any]:
        """Read a bounded window and return normalized events plus quarantine counters."""
        events: list[dict[str, Any]] = []
        quarantined: dict[str, int] = {}
        fetched = 0
        scores_fetched = 0
        for row in self.iter_observations(from_start_time=from_start_time, to_start_time=to_start_time):
            fetched += 1
            event, reason = self.normalize_observation(row)
            if event is not None:
                events.append(event)
            elif reason:
                quarantined[reason] = quarantined.get(reason, 0) + 1
        for row in self.iter_scores(from_timestamp=from_start_time, to_timestamp=to_start_time):
            scores_fetched += 1
            event, reason = self.normalize_score(row)
            if event is not None:
                events.append(event)
            elif reason:
                quarantined[reason] = quarantined.get(reason, 0) + 1
        return {
            "schema": "ncs-langfuse-poll/0.1",
            "source": "langfuse-observations-api-v2+scores-api-v3",
            "from_start_time": from_start_time,
            "to_start_time": to_start_time,
            "observations_fetched": fetched,
            "evaluation_scores_fetched": scores_fetched,
            "events_emitted": len(events),
            "quarantined": quarantined,
            "events": events,
            "grade_eligible": False,
        }


def poll_from_environment(*, from_start_time: str, to_start_time: str) -> dict[str, Any]:
    connector = LangfuseNCSConnector(LangfuseConfig.from_env())
    try:
        return connector.poll(from_start_time=from_start_time, to_start_time=to_start_time)
    finally:
        connector.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Read-only Langfuse to NCS failure evidence poller")
    parser.add_argument("--from", dest="from_start_time", required=True, help="ISO-8601 inclusive start time")
    parser.add_argument("--to", dest="to_start_time", required=True, help="ISO-8601 exclusive end time")
    args = parser.parse_args()
    print(json.dumps(poll_from_environment(
        from_start_time=args.from_start_time,
        to_start_time=args.to_start_time,
    ), indent=2, sort_keys=True))
