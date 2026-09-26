import json

import httpx
import pytest
import respx

from liyaengine import LiyaEngine, LiyaEngineAPIError

BASE_URL = "https://api.test.liyaengine.ai"

FIXTURE_POLICY = {
    "id": "policy_1",
    "name": "Default Policy",
    "description": None,
    "is_default": True,
    "is_active": True,
    "config": {"pre_llm": {"pii": {"enabled": True, "mode": "redact"}}},
    "created_at": "2026-01-01T00:00:00.000Z",
    "updated_at": "2026-01-01T00:00:00.000Z",
}

FIXTURE_VERSION = {
    "id": "ver_1",
    "version_number": 1,
    "changed_fields": ["config"],
    "change_type": "create",
    "restored_from_version": None,
    "created_by": None,
    "actorName": None,
    "created_at": "2026-01-01T00:00:00.000Z",
}


@pytest.fixture
def client():
    with LiyaEngine(api_key="liya_test_key", base_url=BASE_URL) as c:
        yield c


@respx.mock
def test_list_policies_with_attached_count(client):
    respx.get(f"{BASE_URL}/v1/guardrail-policies").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"policies": [{**FIXTURE_POLICY, "attached_count": 2}]}})
    )
    policies = client.guardrail_policies.list()
    assert policies[0].attached_count == 2


@respx.mock
def test_get_policy(client):
    respx.get(f"{BASE_URL}/v1/guardrail-policies/policy_1").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"policy": FIXTURE_POLICY}})
    )
    policy = client.guardrail_policies.get("policy_1")
    assert policy.name == "Default Policy"


@respx.mock
def test_get_policy_not_found_raises_typed_error(client):
    respx.get(f"{BASE_URL}/v1/guardrail-policies/ghost").mock(
        return_value=httpx.Response(404, json={"success": False, "error": {"code": "NOT_FOUND", "message": "Guardrail policy not found."}})
    )
    with pytest.raises(LiyaEngineAPIError) as exc_info:
        client.guardrail_policies.get("ghost")
    assert exc_info.value.code == "NOT_FOUND"
    assert exc_info.value.status == 404


@respx.mock
def test_create_policy(client):
    respx.post(f"{BASE_URL}/v1/guardrail-policies").mock(
        return_value=httpx.Response(201, json={"success": True, "data": {"policy": {**FIXTURE_POLICY, "id": "policy_new", "name": "Strict"}}})
    )
    policy = client.guardrail_policies.create(name="Strict", is_default=False)
    assert policy.name == "Strict"


@respx.mock
def test_update_rejects_deactivating_default(client):
    respx.patch(f"{BASE_URL}/v1/guardrail-policies/policy_1").mock(
        return_value=httpx.Response(400, json={"success": False, "error": {
            "code": "CANNOT_DEACTIVATE_DEFAULT",
            "message": "This is the tenant default policy — set a different policy as default before deactivating this one.",
        }})
    )
    with pytest.raises(LiyaEngineAPIError) as exc_info:
        client.guardrail_policies.update("policy_1", is_active=False)
    assert exc_info.value.code == "CANNOT_DEACTIVATE_DEFAULT"


@respx.mock
def test_delete_rejects_current_default(client):
    respx.delete(f"{BASE_URL}/v1/guardrail-policies/policy_1").mock(
        return_value=httpx.Response(400, json={"success": False, "error": {
            "code": "CANNOT_DELETE_DEFAULT",
            "message": "This is the tenant default policy — set a different policy as default before deleting this one.",
        }})
    )
    with pytest.raises(LiyaEngineAPIError) as exc_info:
        client.guardrail_policies.delete("policy_1")
    assert exc_info.value.code == "CANNOT_DELETE_DEFAULT"


@respx.mock
def test_delete_non_default_policy(client):
    respx.delete(f"{BASE_URL}/v1/guardrail-policies/policy_2").mock(return_value=httpx.Response(200, json={"success": True}))
    assert client.guardrail_policies.delete("policy_2") is None


@respx.mock
def test_set_default(client):
    respx.post(f"{BASE_URL}/v1/guardrail-policies/policy_2/set-default").mock(return_value=httpx.Response(200, json={"success": True}))
    assert client.guardrail_policies.set_default("policy_2") is None


@respx.mock
def test_attach_to_agent(client):
    route = respx.post(f"{BASE_URL}/v1/guardrail-policies/policy_1/attach").mock(
        return_value=httpx.Response(201, json={"success": True})
    )
    client.guardrail_policies.attach("policy_1", "agent", "agent_1")
    sent_body = json.loads(route.calls.last.request.content)
    assert sent_body == {"consumer_type": "agent", "consumer_id": "agent_1"}


@respx.mock
def test_attach_raises_consumer_not_found(client):
    respx.post(f"{BASE_URL}/v1/guardrail-policies/policy_1/attach").mock(
        return_value=httpx.Response(404, json={"success": False, "error": {"code": "CONSUMER_NOT_FOUND", "message": "agent 'ghost-agent' not found."}})
    )
    with pytest.raises(LiyaEngineAPIError) as exc_info:
        client.guardrail_policies.attach("policy_1", "agent", "ghost-agent")
    assert exc_info.value.code == "CONSUMER_NOT_FOUND"
    assert exc_info.value.status == 404


@respx.mock
def test_detach(client):
    respx.post(f"{BASE_URL}/v1/guardrail-policies/policy_1/detach").mock(return_value=httpx.Response(200, json={"success": True}))
    assert client.guardrail_policies.detach("policy_1", "domain", "dom_1") is None


@respx.mock
def test_connections(client):
    respx.get(f"{BASE_URL}/v1/guardrail-policies/policy_1/connections").mock(
        return_value=httpx.Response(200, json={
            "success": True,
            "data": {"domains": [], "intents": [], "agents": [{"id": "agent_1", "name": "Support Copilot"}], "actions": []},
        })
    )
    connections = client.guardrail_policies.connections("policy_1")
    assert connections.agents == [{"id": "agent_1", "name": "Support Copilot"}]


@respx.mock
def test_analytics_with_custom_days(client):
    route = respx.get(f"{BASE_URL}/v1/guardrail-policies/policy_1/analytics?days=7").mock(
        return_value=httpx.Response(200, json={
            "success": True,
            "data": {"window_days": 7, "total_checks": 10, "blocked_checks": 2, "pass_rate": 0.8, "top_issue_codes": [], "trend": []},
        })
    )
    analytics = client.guardrail_policies.analytics("policy_1", days=7)
    assert analytics.window_days == 7
    assert analytics.pass_rate == 0.8
    assert route.called


@respx.mock
def test_test_policy_against_unsaved_draft_config(client):
    respx.post(f"{BASE_URL}/v1/guardrail-policies/test").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"passed": True, "content": "hello world", "issues": []}})
    )
    result = client.guardrail_policies.test(stage="pre_llm", content="hello world", config={})
    assert result.passed is True
    assert result.content == "hello world"


@respx.mock
def test_test_policy_rejects_missing_stage(client):
    respx.post(f"{BASE_URL}/v1/guardrail-policies/test").mock(
        return_value=httpx.Response(400, json={"success": False, "error": {"code": "INVALID_INPUT", "message": "stage and content are required."}})
    )
    with pytest.raises(LiyaEngineAPIError) as exc_info:
        client.guardrail_policies.test(stage="pre_llm", content="x")
    assert exc_info.value.code == "INVALID_INPUT"


@respx.mock
def test_versions_list_get_restore(client):
    respx.get(f"{BASE_URL}/v1/guardrail-policies/policy_1/versions").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"versions": [FIXTURE_VERSION]}})
    )
    versions = client.guardrail_policies.versions.list("policy_1")
    assert versions[0].version_number == 1

    respx.get(f"{BASE_URL}/v1/guardrail-policies/policy_1/versions/1").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"version": FIXTURE_VERSION}})
    )
    version = client.guardrail_policies.versions.get("policy_1", 1)
    assert version.change_type == "create"

    respx.post(f"{BASE_URL}/v1/guardrail-policies/policy_1/versions/1/restore").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"policy": FIXTURE_POLICY}})
    )
    restored = client.guardrail_policies.versions.restore("policy_1", 1)
    assert restored.id == "policy_1"
