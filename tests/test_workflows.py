import json

import httpx
import pytest
import respx

from liyaengine import LiyaEngine, LiyaEngineAPIError

BASE_URL = "https://api.test.liyaengine.ai"

FIXTURE_WORKFLOW = {
    "id": "wf_123",
    "tenant_id": "tenant_1",
    "name": "Lead Intake",
    "workflow_key": "lead-intake",
    "description": None,
    "is_active": False,
    "status": "draft",
    "trigger_type": "webhook",
    "trigger_config": None,
    "created_at": "2026-01-01T00:00:00.000Z",
    "updated_at": "2026-01-01T00:00:00.000Z",
    "steps": [],
}


@pytest.fixture
def client():
    with LiyaEngine(api_key="liya_test_key", base_url=BASE_URL) as c:
        yield c


@respx.mock
def test_list_returns_deployed_workflows(client):
    respx.get(f"{BASE_URL}/v1/workflows").mock(
        return_value=httpx.Response(200, json={"success": True, "data": [{**FIXTURE_WORKFLOW, "status": "active", "is_active": True}]})
    )
    workflows = client.workflows.list()
    assert len(workflows) == 1
    assert workflows[0].workflow_key == "lead-intake"


@respx.mock
def test_get_returns_workflow(client):
    respx.get(f"{BASE_URL}/v1/workflows/lead-intake").mock(
        return_value=httpx.Response(200, json={"success": True, "data": FIXTURE_WORKFLOW})
    )
    workflow = client.workflows.get("lead-intake")
    assert workflow.id == "wf_123"


@respx.mock
def test_get_raises_typed_404(client):
    respx.get(f"{BASE_URL}/v1/workflows/missing").mock(
        return_value=httpx.Response(404, json={"success": False, "error": {"code": "WORKFLOW_NOT_FOUND", "message": "not found"}})
    )
    with pytest.raises(LiyaEngineAPIError) as exc_info:
        client.workflows.get("missing")
    assert exc_info.value.code == "WORKFLOW_NOT_FOUND"


@respx.mock
def test_create_returns_draft_workflow(client):
    respx.post(f"{BASE_URL}/v1/workflows").mock(
        return_value=httpx.Response(201, json={"success": True, "data": {"workflow": {**FIXTURE_WORKFLOW, "id": "wf_new"}}})
    )
    workflow = client.workflows.create(name="Lead Intake")
    assert workflow.id == "wf_new"
    assert workflow.status == "draft"


@respx.mock
def test_update_patches_workflow(client):
    respx.patch(f"{BASE_URL}/v1/workflows/lead-intake").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"workflow": {**FIXTURE_WORKFLOW, "name": "Renamed"}}})
    )
    updated = client.workflows.update("lead-intake", name="Renamed")
    assert updated.name == "Renamed"


@respx.mock
def test_toggle_flips_is_active(client):
    respx.patch(f"{BASE_URL}/v1/workflows/lead-intake/toggle").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"workflow": {**FIXTURE_WORKFLOW, "status": "active", "is_active": True}}})
    )
    toggled = client.workflows.toggle("lead-intake")
    assert toggled.is_active is True


@respx.mock
def test_toggle_raises_typed_409_when_draft(client):
    respx.patch(f"{BASE_URL}/v1/workflows/draft-wf/toggle").mock(
        return_value=httpx.Response(409, json={"success": False, "error": {"code": "DEPLOY_REQUIRED", "message": "deploy first"}})
    )
    with pytest.raises(LiyaEngineAPIError) as exc_info:
        client.workflows.toggle("draft-wf")
    assert exc_info.value.code == "DEPLOY_REQUIRED"


@respx.mock
def test_deploy_returns_one_time_webhook_secret(client):
    respx.post(f"{BASE_URL}/v1/workflows/lead-intake/deploy").mock(
        return_value=httpx.Response(200, json={
            "success": True,
            "data": {
                "workflow": {**FIXTURE_WORKFLOW, "status": "active", "is_active": True},
                "webhook_url": "https://api.test.liyaengine.ai/webhooks/workflows/abc123",
                "webhook_secret": "plaintext-secret-shown-once",
            },
        })
    )
    result = client.workflows.deploy("lead-intake")
    assert result["workflow"]["status"] == "active"
    assert result["webhook_secret"] == "plaintext-secret-shown-once"


@respx.mock
def test_rotate_webhook_secret_returns_new_secret(client):
    respx.post(f"{BASE_URL}/v1/workflows/lead-intake/webhook-secret/rotate").mock(
        return_value=httpx.Response(200, json={
            "success": True,
            "data": {
                "webhook_url": "https://api.test.liyaengine.ai/webhooks/workflows/abc123",
                "webhook_secret": "new-plaintext-secret",
                "previous_secret_valid_until": "2026-01-01T00:05:00.000Z",
            },
        })
    )
    result = client.workflows.rotate_webhook_secret("lead-intake", grace_period_seconds=300)
    assert result["webhook_secret"] == "new-plaintext-secret"
    assert result["previous_secret_valid_until"] == "2026-01-01T00:05:00.000Z"


@respx.mock
def test_delete_does_not_raise(client):
    respx.delete(f"{BASE_URL}/v1/workflows/lead-intake").mock(return_value=httpx.Response(200, json={"success": True}))
    client.workflows.delete("lead-intake")


@respx.mock
def test_run_returns_result(client):
    respx.post(f"{BASE_URL}/v1/workflows/lead-intake/run").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"run_id": "run_1", "conversation_id": "convo_1", "status": "completed", "trace": []}})
    )
    result = client.workflows.run("lead-intake", input={"name": "Ada"})
    assert result["run_id"] == "run_1"
    assert result["status"] == "completed"


@respx.mock
def test_list_runs(client):
    respx.get(f"{BASE_URL}/v1/workflows/lead-intake/runs").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"runs": [], "pagination": {"page": 1}}})
    )
    result = client.workflows.list_runs("lead-intake")
    assert result["runs"] == []


@respx.mock
def test_get_run(client):
    respx.get(f"{BASE_URL}/v1/workflows/lead-intake/runs/run_1").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"run": {"id": "run_1"}}})
    )
    run = client.workflows.get_run("lead-intake", "run_1")
    assert run["id"] == "run_1"


@respx.mock
def test_run_stream_yields_step_frames_then_done(client):
    frames = [
        {"type": "step", "step": {"stepId": "s1", "stepType": "ai_intent", "name": "Classify", "success": True, "response": {"confidence": 0.9}, "durationMs": 120}},
        {"type": "step", "step": {"stepId": "s2", "stepType": "condition", "name": "Confidence check", "success": True, "durationMs": 5}},
        {"type": "done", "run_id": "run_1", "conversation_id": "convo_1", "status": "completed", "trace": []},
    ]
    sse_body = "".join(f"data: {json.dumps(f)}\n\n" for f in frames)
    respx.post(f"{BASE_URL}/v1/workflows/lead-intake/run/stream").mock(
        return_value=httpx.Response(200, content=sse_body, headers={"content-type": "text/event-stream"})
    )
    events = list(client.workflows.run_stream("lead-intake", input={"foo": "bar"}))
    assert events == frames


@respx.mock
def test_run_stream_raises_for_pre_flight_rejection(client):
    respx.post(f"{BASE_URL}/v1/workflows/ghost-wf/run/stream").mock(
        return_value=httpx.Response(404, json={"success": False, "error": {"code": "WORKFLOW_NOT_FOUND", "message": "not found"}})
    )
    with pytest.raises(LiyaEngineAPIError) as exc_info:
        list(client.workflows.run_stream("ghost-wf"))
    assert exc_info.value.code == "WORKFLOW_NOT_FOUND"
