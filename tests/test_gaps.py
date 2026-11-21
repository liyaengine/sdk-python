from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx

from liyaengine import LiyaEngine, LiyaEngineAPIError

BASE_URL = "https://api.test.liyaengine.ai"

DRAFT = {
    "title": "Shipping to Canada",
    "statements": [{"text": "We ship to every Canadian province.", "sources": ["S1"]}],
    "body_markdown": "We ship to every Canadian province.",
    "missing": ["Delivery time to Toronto"],
    "sources": [{"id": "S1", "kind": "staff_reply", "label": "Staff reply, 2026-11-10", "excerpt": "Yes, we ship to every Canadian province."}],
    "questions": ["Do you ship to Canada?"],
    "gap_ids": ["g1"],
    "dropped_unsupported": 1,
    "reason": None,
    "usage": {"tokens": 900, "cost": 0.003, "served_by": "platform"},
}


@pytest.fixture
def client():
    # Retries are on, to prove the paid calls ignore them.
    with LiyaEngine(api_key="liya_test_key", base_url=BASE_URL, max_retries=2) as c:
        yield c


def _query(route):
    return {k: v[0] for k, v in parse_qs(urlparse(str(route.calls.last.request.url)).query).items()}


@respx.mock
def test_list_sends_the_window_and_resolved_flag(client):
    route = respx.get(f"{BASE_URL}/v1/knowledge/gaps").mock(return_value=httpx.Response(200, json={
        "success": True, "data": {"total": 1, "by_intent": [{"intent": "shipping", "count": 1, "queries": ["Do you ship to Canada?"]}], "items": []},
    }))
    out = client.gaps.list(days=7, resolved=False)
    assert out["total"] == 1 and out["by_intent"][0]["intent"] == "shipping"
    assert _query(route) == {"days": "7", "resolved": "false"}


@respx.mock
def test_draft_article_returns_a_typed_draft_and_sends_gap_ids(client):
    route = respx.post(f"{BASE_URL}/v1/knowledge/gaps/draft-article").mock(return_value=httpx.Response(200, json={"success": True, "data": {"draft": DRAFT}}))
    d = client.gaps.draft_article(gap_ids=["g1"])
    assert route.calls.last.request.read() == b'{"gap_ids":["g1"]}' or route.calls.last.request.content.decode().replace(" ", "") == '{"gap_ids":["g1"]}'
    assert d.title == "Shipping to Canada" and d.dropped_unsupported == 1 and d.reason is None
    assert d.statements[0]["sources"] == ["S1"] and d.usage["served_by"] == "platform"


@respx.mock
def test_draft_article_can_target_the_unclassified_topic_with_none(client):
    route = respx.post(f"{BASE_URL}/v1/knowledge/gaps/draft-article").mock(return_value=httpx.Response(200, json={"success": True, "data": {"draft": DRAFT}}))
    client.gaps.draft_article(intent=None)
    assert route.calls.last.request.content.decode().replace(" ", "") == '{"intent":null}'


@respx.mock
def test_draft_article_is_never_retried_because_each_attempt_is_a_paid_model_call(client):
    route = respx.post(f"{BASE_URL}/v1/knowledge/gaps/draft-article").mock(return_value=httpx.Response(502, json={
        "success": False, "error": {"code": "DRAFT_UNAVAILABLE", "message": "The draft could not be written. Try again."},
    }))
    with pytest.raises(LiyaEngineAPIError) as err:
        client.gaps.draft_article(gap_ids=["g1"])
    assert err.value.code == "DRAFT_UNAVAILABLE"
    assert route.call_count == 1


@respx.mock
def test_check_coverage_returns_typed_results(client):
    respx.post(f"{BASE_URL}/v1/knowledge/gaps/check-coverage").mock(return_value=httpx.Response(200, json={"success": True, "data": {"coverage": {
        "checked": 2, "answered": 1, "not_checked": 0, "min_similarity": 0.45, "results": [
            {"gap_id": "g1", "query": "Do you ship to Canada?", "checked": True, "answered": True, "top_similarity": 0.71, "top_source": "shipping.md"},
            {"gap_id": "g2", "query": "Is the sky blue?", "checked": True, "answered": False, "top_similarity": 0, "top_source": None},
        ]}}}))
    c = client.gaps.check_coverage(["g1", "g2"])
    assert (c.checked, c.answered, c.not_checked, c.min_similarity) == (2, 1, 0, 0.45)
    assert c.results[0].top_source == "shipping.md" and c.results[1].top_source is None and c.results[1].answered is False


@respx.mock
def test_memory_outcomes_reads_a_window(client):
    route = respx.get(f"{BASE_URL}/v1/memory/outcomes").mock(return_value=httpx.Response(200, json={"success": True, "data": {
        "window_days": 90, "outcome_signal": "run_finished", "runs_total": 32, "files": [{"path": "agent/a/profile.md", "verdict": "not_enough_data"}], "unopened_files": [],
    }}))
    out = client.memory.outcomes(days=90)
    assert _query(route) == {"days": "90"}
    assert out["files"][0]["verdict"] == "not_enough_data" and out["outcome_signal"] == "run_finished"


@respx.mock
def test_case_draft_from_a_trace(client):
    respx.get(f"{BASE_URL}/v1/traces/msg_xyz/eval-case-draft").mock(return_value=httpx.Response(200, json={"success": True, "data": {"draft": {
        "trace_id": "msg_xyz", "domain_key": "support", "intent_key": "resolve_ticket", "message": "Refund my plan", "input": {}, "input_available": False,
        "observed_output": "Declined.", "expected_output": None, "notes": "From trace msg_xyz.", "already_redacted": False,
        "datasets": [{"id": "ds_1", "name": "Refund set", "suites": [{"id": "su_1", "name": "Nightly"}]}],
    }}}))
    d = client.traces.case_draft("msg_xyz")
    assert (d.trace_id, d.domain_key, d.intent_key, d.input, d.input_available, d.expected_output) == ("msg_xyz", "support", "resolve_ticket", {}, False, None)
    assert d.datasets[0]["suites"][0]["name"] == "Nightly"


@respx.mock
def test_failure_clusters_reads_a_window(client):
    route = respx.get(f"{BASE_URL}/v1/traces/failure-clusters").mock(return_value=httpx.Response(200, json={"success": True, "data": {
        "window_days": 14, "runs_total": 258, "runs_failed": 26, "failure_rate": 10.1, "truncated": False, "min_cluster_runs": 3, "proposal_min_runs": 10,
        "clusters": [{"kind": "tool", "runs": 65, "runs_ended_failed": 25, "proposal_ready": True, "cause": {"kind": "tool", "label": "Tool", "rule": "A tool call inside the run failed."}, "changes": []}],
    }}))
    out = client.traces.failure_clusters(days=14)
    assert _query(route) == {"days": "14"}
    assert out["clusters"][0]["runs_ended_failed"] == 25 and out["failure_rate"] == 10.1
    respx.get(f"{BASE_URL}/v1/traces/failure-clusters").mock(return_value=httpx.Response(200, json={"success": True, "data": {"clusters": []}}))
    assert client.traces.failure_clusters()["clusters"] == []
