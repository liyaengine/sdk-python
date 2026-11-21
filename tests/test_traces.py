from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx

from liyaengine import LiyaEngine, LiyaEngineAPIError

BASE_URL = "https://api.test.liyaengine.ai"

FIXTURE_SUMMARY = {
    "kind": "request",
    "traceId": "msg_xyz",
    "name": "custom_support_resolve_ticket",
    "status": None,
    "parent": None,
    "sessionId": "ses_abc",
    "requestId": "req_1",
    "userId": "usr_123",
    "intent": "custom_support_resolve_ticket",
    "domain": "custom:support",
    "modelUsed": "claude-sonnet-5",
    "inputTokens": 820,
    "outputTokens": 420,
    "totalTokens": 1240,
    "costUsd": "0.002100",
    "latencyMs": 340,
    "ttftMs": None,
    "flagged": True,
    "flagReason": "PII_EMAIL_REDACTED",
    "piiDetected": True,
    "issueCategories": ["safety"],
    "captureMode": "full",
    "commentCount": 0,
    "qaScore": 91,
    "qaBreakdown": None,
    "timestamp": "2026-10-01T10:00:00.000Z",
}

FIXTURE_TRACE = {
    "traceId": "msg_xyz",
    "sessionId": "ses_abc",
    "requestId": "req_1",
    "userId": "usr_123",
    "domain": "custom:support",
    "contentAccess": "full",
    "captureMode": "full",
    "intent": "custom_support_resolve_ticket",
    "userRequest": "Where is my refund?",
    "content": "Refunds are processed within 5-7 days.",
    "modelUsed": "claude-sonnet-5",
    "inputTokens": 820,
    "outputTokens": 420,
    "totalTokens": 1240,
    "costUsd": "0.002100",
    "latencyMs": 340,
    "ttftMs": None,
    "flagged": False,
    "flagReason": None,
    "issues": [],
    "piiDetected": False,
    "fromCache": False,
    "qaScore": 91,
    "retrievedContext": [{"sourceId": "src_01", "sourceType": "policy", "score": 0.94, "snippet": "Refunds are processed within..."}],
    "observations": [],
    "timestamp": "2026-10-01T10:00:00.000Z",
}

FIXTURE_STATS = {
    "window": {"from": "2026-09-01T00:00:00.000Z", "to": "2026-10-01T00:00:00.000Z"},
    "total": 412,
    "flagged": 9,
    "piiDetected": 30,
    "fromCache": 12,
    "inputTokens": 100000,
    "outputTokens": 40000,
    "costUsd": "12.340000",
    "latencyMs": {"avg": 350, "p50": 300, "p95": 900, "p99": 1500},
    "ttftMs": {"p50": 120, "p95": 400},
    "qaScore": {"avg": 88, "scored": 200},
    "issuesByCategory": {"safety": 5, "validation": 2, "grounding": 1, "other": 1},
    "byIntent": [],
}


@pytest.fixture
def client():
    with LiyaEngine(api_key="liya_test_key", base_url=BASE_URL, max_retries=0) as c:
        yield c


def _query(route):
    return {k: v[0] for k, v in parse_qs(urlparse(str(route.calls.last.request.url)).query).items()}


@respx.mock
def test_list_keeps_the_pagination_and_sort_beside_data(client):
    respx.get(f"{BASE_URL}/v1/traces").mock(return_value=httpx.Response(200, json={
        "success": True,
        "data": {"traces": [FIXTURE_SUMMARY]},
        "pagination": {"total": 412, "limit": 25, "offset": 0},
        "sort": {"key": "time", "dir": "desc"},
    }))
    page = client.traces.list()
    assert len(page.traces) == 1
    assert page.traces[0].trace_id == "msg_xyz"
    assert page.traces[0].issue_categories == ["safety"]
    assert page.pagination == {"total": 412, "limit": 25, "offset": 0}
    assert page.sort == {"key": "time", "dir": "desc"}


@respx.mock
def test_list_sends_every_filter_as_the_query_parameter_the_api_reads(client):
    route = respx.get(f"{BASE_URL}/v1/traces").mock(return_value=httpx.Response(200, json={
        "success": True, "data": {"traces": []}, "pagination": {"total": 0, "limit": 10, "offset": 20}, "sort": {"key": "cost", "dir": "asc"},
    }))
    client.traces.list(
        limit=10, offset=20, domain="support", intent="resolve_ticket", flagged=True, issue="safety",
        from_=datetime(2026, 9, 1, tzinfo=timezone.utc), to="2026-10-01T00:00:00.000Z",
        user_id="usr_123", session_id="ses_abc", model="claude-sonnet-5", min_latency_ms=500, from_cache=False,
        capture="full", q="refund", sort="cost", order="asc", scope="traces", kind="agent", nested=True,
    )
    assert _query(route) == {
        "limit": "10", "offset": "20", "domain": "support", "intent": "resolve_ticket", "flagged": "true", "issue": "safety",
        "from": "2026-09-01T00:00:00+00:00", "to": "2026-10-01T00:00:00.000Z",
        "userId": "usr_123", "sessionId": "ses_abc", "model": "claude-sonnet-5", "minLatencyMs": "500", "fromCache": "false",
        "capture": "full", "q": "refund", "sort": "cost", "order": "asc", "scope": "traces", "kind": "agent", "nested": "true",
    }


@respx.mock
def test_list_omits_filters_that_are_none(client):
    route = respx.get(f"{BASE_URL}/v1/traces").mock(return_value=httpx.Response(200, json={
        "success": True, "data": {"traces": []}, "pagination": {"total": 0, "limit": 25, "offset": 0}, "sort": {"key": "time", "dir": "desc"},
    }))
    client.traces.list(domain="support", intent=None)
    assert _query(route) == {"domain": "support"}


@respx.mock
def test_get_returns_the_trace(client):
    respx.get(f"{BASE_URL}/v1/traces/msg_xyz").mock(return_value=httpx.Response(200, json={"success": True, "data": {"trace": FIXTURE_TRACE}}))
    trace = client.traces.get("msg_xyz")
    assert trace.trace_id == "msg_xyz"
    assert trace.content_access == "full"
    assert trace.retrieved_context[0]["score"] == 0.94
    assert trace.raw["costUsd"] == "0.002100"


@respx.mock
def test_get_raises_a_typed_error_for_a_missing_trace(client):
    respx.get(f"{BASE_URL}/v1/traces/msg_missing").mock(return_value=httpx.Response(404, json={
        "success": False, "error": {"code": "TRACE_NOT_FOUND", "message": "Trace not found"},
    }))
    with pytest.raises(LiyaEngineAPIError) as exc:
        client.traces.get("msg_missing")
    assert exc.value.code == "TRACE_NOT_FOUND"
    assert exc.value.status == 404


@respx.mock
def test_get_run_reads_an_agent_run_trace(client):
    respx.get(f"{BASE_URL}/v1/traces/runs/agent/run_1").mock(return_value=httpx.Response(200, json={
        "success": True, "data": {"trace": {**FIXTURE_TRACE, "kind": "agent_run", "traceId": "run_1"}},
    }))
    trace = client.traces.get_run("agent", "run_1")
    assert trace.kind == "agent_run"
    assert trace.trace_id == "run_1"


@respx.mock
def test_embed_token_refusal_is_a_typed_error(client):
    respx.get(f"{BASE_URL}/v1/traces/runs/workflow/run_1").mock(return_value=httpx.Response(403, json={
        "success": False, "error": {"code": "EMBED_TOKEN_NOT_ALLOWED", "message": "Use a secret API key to read traces."},
    }))
    with pytest.raises(LiyaEngineAPIError) as exc:
        client.traces.get_run("workflow", "run_1")
    assert exc.value.code == "EMBED_TOKEN_NOT_ALLOWED"
    assert exc.value.status == 403


@respx.mock
def test_stats_returns_totals_and_passes_the_same_filters(client):
    route = respx.get(f"{BASE_URL}/v1/traces/stats").mock(return_value=httpx.Response(200, json={"success": True, "data": FIXTURE_STATS}))
    stats = client.traces.stats(domain="support", from_="2026-09-01T00:00:00.000Z", flagged=True)
    assert stats.total == 412
    assert stats.latency_ms["p95"] == 900
    assert stats.issues_by_category["safety"] == 5
    assert _query(route) == {"domain": "support", "from": "2026-09-01T00:00:00.000Z", "flagged": "true"}


@respx.mock
def test_ids_are_url_encoded(client):
    respx.get(f"{BASE_URL}/v1/traces/a%2Fb").mock(return_value=httpx.Response(200, json={"success": True, "data": {"trace": FIXTURE_TRACE}}))
    assert client.traces.get("a/b").trace_id == "msg_xyz"
