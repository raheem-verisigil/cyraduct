"""Offline contract tests for the read-only Langfuse connector."""
import base64
import json
import httpx
import pytest
from ncs_harness.langfuse_connector import LangfuseConfig, LangfuseNCSConnector, LangfuseConnectorError

D = "a" * 64

def cfg():
    return LangfuseConfig("https://cloud.langfuse.com", "pk-test", "sk-test")

def test_normalizes_error_observation_only_with_explicit_artifact_digest():
    connector = LangfuseNCSConnector(cfg(), client=httpx.Client(base_url="https://cloud.langfuse.com", transport=httpx.MockTransport(lambda r: httpx.Response(200,json={}))))
    row = {
        "id":"obs-1","traceId":"trace-1","type":"GENERATION","level":"ERROR",
        "startTime":"2026-11-01T10:00:00Z","statusMessage":"TimeoutError: upstream timeout",
        "model":"fixture-model","environment":"test",
        "metadata":{"ncs.artifact.sha256":D}
    }
    event, reason = connector.normalize_observation(row)
    assert reason is None
    assert event["source"]["integration"] == "langfuse"
    assert event["subject"]["artifact_digest"] == D
    assert event["source_integrity"] == "unverified"
    assert event["grade_eligible"] is False
    assert event["failure"]["error_type"] == "TimeoutError"
    assert "upstream timeout" not in str(event)

def test_quarantines_observation_without_artifact_binding():
    connector = LangfuseNCSConnector(cfg(), client=httpx.Client(base_url="https://cloud.langfuse.com", transport=httpx.MockTransport(lambda r: httpx.Response(200,json={}))))
    event, reason = connector.normalize_observation({
        "id":"obs-2","level":"ERROR","startTime":"2026-11-01T10:00:00Z","model":"gpt-x"
    })
    assert event is None
    assert reason == "missing_or_invalid_artifact_digest"

def test_paginates_bounded_error_and_warning_queries():
    calls = []
    def handler(request):
        calls.append(dict(request.url.params))
        if request.url.params.get("cursor") == "next":
            return httpx.Response(200,json={"data":[{"id":"obs-2"}],"meta":{}})
        if request.url.params.get("level") == "ERROR":
            return httpx.Response(200,json={"data":[{"id":"obs-1"}],"meta":{"cursor":"next"}})
        return httpx.Response(200,json={"data":[],"meta":{}})
    client = httpx.Client(base_url="https://cloud.langfuse.com", transport=httpx.MockTransport(handler))
    connector = LangfuseNCSConnector(cfg(),client=client)
    rows = list(connector.iter_observations(from_start_time="2026-11-01T00:00:00Z",to_start_time="2026-11-02T00:00:00Z"))
    assert [x["id"] for x in rows] == ["obs-1","obs-2"]
    assert calls[0]["fromStartTime"] == "2026-11-01T00:00:00Z"
    assert calls[0]["toStartTime"] == "2026-11-02T00:00:00Z"
    assert calls[1]["cursor"] == "next"
    assert calls[-1]["level"] == "WARNING"

def test_rejects_unbounded_or_timezone_free_polling_windows():
    connector = LangfuseNCSConnector(cfg(),client=httpx.Client(base_url="https://cloud.langfuse.com", transport=httpx.MockTransport(lambda r: httpx.Response(200,json={}))))
    with pytest.raises(ValueError,match="timezone"):
        list(connector.iter_observations(from_start_time="2026-11-01T00:00:00",to_start_time="2026-11-02T00:00:00Z"))
    with pytest.raises(ValueError,match="earlier"):
        list(connector.iter_observations(from_start_time="2026-11-02T00:00:00Z",to_start_time="2026-11-01T00:00:00Z"))

def test_authentication_errors_are_sanitized():
    def handler(request):
        return httpx.Response(401,json={"message":"secret should not leak"})
    connector = LangfuseNCSConnector(cfg(),client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(LangfuseConnectorError,match="authentication/permission"):
        list(connector.iter_observations(from_start_time="2026-11-01T00:00:00Z",to_start_time="2026-11-02T00:00:00Z"))


def test_maps_explicit_failed_boolean_eval_score_with_artifact_digest():
    connector = LangfuseNCSConnector(cfg(), client=httpx.Client(
        base_url="https://cloud.langfuse.com",
        transport=httpx.MockTransport(lambda r: httpx.Response(200,json={}))
    ))
    event, reason = connector.normalize_score({
        "id":"score-1","name":"groundedness","value":False,"dataType":"BOOLEAN",
        "source":"EVAL","timestamp":"2026-11-01T10:00:00Z","environment":"test",
        "subject":{"kind":"observation","id":"obs-1","traceId":"trace-1"},
        "details":{"metadata":{"ncs.artifact.sha256":D,"ncs.failure.category":"hallucination"}}
    })
    assert reason is None
    assert event["source"]["event_type"] == "evaluation.score.groundedness"
    assert event["source"]["trace_id"] == "trace-1"
    assert event["failure"]["category"] == "hallucination"
    assert event["source_integrity"] == "unverified"
    assert event["grade_eligible"] is False


def test_ignores_non_failed_eval_score_and_quarantines_missing_artifact():
    connector = LangfuseNCSConnector(cfg(), client=httpx.Client(
        base_url="https://cloud.langfuse.com",
        transport=httpx.MockTransport(lambda r: httpx.Response(200,json={}))
    ))
    row = {"id":"s1","value":True,"dataType":"BOOLEAN","timestamp":"2026-11-01T10:00:00Z",
           "details":{"metadata":{"ncs.artifact.sha256":D}}}
    event, reason = connector.normalize_score(row)
    assert event is None and reason == "evaluation_score_not_explicitly_failed"
    row["value"] = False
    row["details"]["metadata"] = {}
    event, reason = connector.normalize_score(row)
    assert event is None and reason == "score_missing_or_invalid_artifact_digest"


def test_paginates_scores_v3_and_uses_evaluation_source():
    calls = []
    def handler(request):
        calls.append(dict(request.url.params))
        return httpx.Response(200,json={"data":[{"id":"score-1"}],"meta":{}})
    connector = LangfuseNCSConnector(cfg(),client=httpx.Client(
        base_url="https://cloud.langfuse.com",transport=httpx.MockTransport(handler)
    ))
    rows = list(connector.iter_scores(
        from_timestamp="2026-11-01T00:00:00Z",to_timestamp="2026-11-02T00:00:00Z"
    ))
    assert len(rows) == 1
    assert calls[0]["source"] == "EVAL"
    assert calls[0]["fields"] == "details,subject"
    assert calls[0]["fromTimestamp"] == "2026-11-01T00:00:00Z"
