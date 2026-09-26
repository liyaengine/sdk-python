import json

import httpx
import pytest
import respx

from liyaengine import LiyaEngine, LiyaEngineAPIError

BASE_URL = "https://api.test.liyaengine.ai"

FIXTURE_AGENT = {
    "id": "agent_123",
    "tenant_id": "tenant_1",
    "agent_key": "support-triage",
    "name": "Support Triage",
    "goal": "Triage incoming support tickets",
    "status": "draft",
    "description": None,
    "system_instructions": None,
    "model": None,
    "temperature": None,
    "intent_ids": [],
    "workflow_ids": [],
    "action_ids": [],
    "knowledge_domain_keys": [],
    "tools_config": None,
    "memory_config": None,
    "behavior_config": None,
    "guardrail_policy_id": None,
    "created_at": "2026-01-01T00:00:00.000Z",
    "updated_at": "2026-01-01T00:00:00.000Z",
    "effective_runtime_config": {"contract_version": 1},
}


@pytest.fixture
def client():
    with LiyaEngine(api_key="liya_test_key", base_url=BASE_URL) as c:
        yield c


@respx.mock
def test_list_returns_catalog(client):
    respx.get(f"{BASE_URL}/v1/agents").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"agents": [{"agent": "support-triage"}], "total": 1}})
    )
    agents = client.agents.list()
    assert len(agents) == 1
    assert agents[0]["agent"] == "support-triage"


@respx.mock
def test_get_returns_agent(client):
    respx.get(f"{BASE_URL}/v1/agents/support-triage").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"agent": FIXTURE_AGENT}})
    )
    agent = client.agents.get("support-triage")
    assert agent.agent_key == "support-triage"
    assert agent.status == "draft"


@respx.mock
def test_get_raises_typed_404(client):
    respx.get(f"{BASE_URL}/v1/agents/missing").mock(
        return_value=httpx.Response(404, json={"success": False, "error": {"code": "AGENT_NOT_FOUND", "message": "not found"}})
    )
    with pytest.raises(LiyaEngineAPIError) as exc_info:
        client.agents.get("missing")
    assert exc_info.value.code == "AGENT_NOT_FOUND"


@respx.mock
def test_create_returns_new_agent(client):
    respx.post(f"{BASE_URL}/v1/agents").mock(
        return_value=httpx.Response(201, json={"success": True, "data": {"agent": {**FIXTURE_AGENT, "id": "agent_new"}}})
    )
    agent = client.agents.create(agent_key="support-triage", name="Support Triage", goal="Triage tickets")
    assert agent.id == "agent_new"


@respx.mock
def test_create_raises_typed_409_on_conflict(client):
    respx.post(f"{BASE_URL}/v1/agents").mock(
        return_value=httpx.Response(409, json={"success": False, "error": {"code": "AGENT_KEY_TAKEN", "message": "taken"}})
    )
    with pytest.raises(LiyaEngineAPIError) as exc_info:
        client.agents.create(agent_key="support-triage", name="Dup", goal="x")
    assert exc_info.value.code == "AGENT_KEY_TAKEN"


@respx.mock
def test_update_patches_agent(client):
    respx.patch(f"{BASE_URL}/v1/agents/support-triage").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"agent": {**FIXTURE_AGENT, "name": "Renamed"}}})
    )
    updated = client.agents.update("support-triage", name="Renamed")
    assert updated.name == "Renamed"


@respx.mock
def test_update_rejects_direct_active_status(client):
    respx.patch(f"{BASE_URL}/v1/agents/support-triage").mock(
        return_value=httpx.Response(409, json={"success": False, "error": {"code": "DEPLOY_REQUIRED", "message": "use deploy"}})
    )
    with pytest.raises(LiyaEngineAPIError) as exc_info:
        client.agents.update("support-triage", status="active")
    assert exc_info.value.code == "DEPLOY_REQUIRED"


@respx.mock
def test_deploy_activates_agent(client):
    respx.post(f"{BASE_URL}/v1/agents/support-triage/deploy").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"agent": {**FIXTURE_AGENT, "status": "active"}}})
    )
    deployed = client.agents.deploy("support-triage")
    assert deployed.status == "active"


@respx.mock
def test_delete_does_not_raise(client):
    respx.delete(f"{BASE_URL}/v1/agents/support-triage").mock(return_value=httpx.Response(200, json={"success": True}))
    client.agents.delete("support-triage")


@respx.mock
def test_run_returns_result(client):
    respx.post(f"{BASE_URL}/v1/agents/support-triage/run").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"run_id": "run_1", "output": "hi"}})
    )
    result = client.agents.run("support-triage", input={"message": "hi"})
    assert result["run_id"] == "run_1"


@respx.mock
def test_list_runs(client):
    respx.get(f"{BASE_URL}/v1/agents/support-triage/runs").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"runs": [], "pagination": {"page": 1}}})
    )
    result = client.agents.list_runs("support-triage")
    assert result["runs"] == []


@respx.mock
def test_get_run(client):
    respx.get(f"{BASE_URL}/v1/agents/support-triage/runs/run_1").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"run": {"id": "run_1"}}})
    )
    run = client.agents.get_run("support-triage", "run_1")
    assert run["id"] == "run_1"


@respx.mock
def test_list_sessions(client):
    respx.get(f"{BASE_URL}/v1/agents/support-triage/sessions").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"sessions": [], "pagination": {"page": 1}}})
    )
    result = client.agents.list_sessions("support-triage")
    assert result["sessions"] == []


@respx.mock
def test_get_transcript(client):
    respx.get(f"{BASE_URL}/v1/agents/support-triage/sessions/ses_1/transcript").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"session": {"id": "ses_1"}, "turns": []}})
    )
    result = client.agents.get_transcript("support-triage", "ses_1")
    assert result["session"]["id"] == "ses_1"


@respx.mock
def test_run_stream_yields_step_frames_then_done(client):
    frames = [
        {"type": "step", "step": {"step_number": 1, "type": "llm_call", "model": "gpt-4o", "latency_ms": 300, "timestamp": "2026-01-01T00:00:00.000Z"}},
        {"type": "step", "step": {"step_number": 2, "type": "tool_execution", "tool_name": "lookup_order", "tool_success": True, "latency_ms": 80, "timestamp": "2026-01-01T00:00:00.000Z"}},
        {"type": "done", "run_id": "run_1", "session_id": "ses_1", "history_truncated": False, "status": "completed", "output": "Your order shipped.", "steps": 2, "total_cost": 0.002, "total_latency_ms": 500},
    ]
    sse_body = "".join(f"data: {json.dumps(f)}\n\n" for f in frames)
    respx.post(f"{BASE_URL}/v1/agents/support-triage/run/stream").mock(
        return_value=httpx.Response(200, content=sse_body, headers={"content-type": "text/event-stream"})
    )
    events = list(client.agents.run_stream("support-triage", input={"message": "Where is my order?"}))
    assert events == frames


@respx.mock
def test_run_stream_raises_for_pre_flight_rejection(client):
    respx.post(f"{BASE_URL}/v1/agents/support-triage/run/stream").mock(
        return_value=httpx.Response(400, json={"success": False, "error": {"code": "AGENT_NOT_ACTIVE", "message": "not active"}})
    )
    with pytest.raises(LiyaEngineAPIError) as exc_info:
        list(client.agents.run_stream("support-triage", input={"message": "hi"}))
    assert exc_info.value.code == "AGENT_NOT_ACTIVE"
