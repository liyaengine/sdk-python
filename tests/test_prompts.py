import httpx
import pytest
import respx

from liyaengine import LiyaEngine, LiyaEngineAPIError

BASE_URL = "https://api.test.liyaengine.ai"

FIXTURE_VERSION = {
    "id": "version_1",
    "prompt_id": "prompt_1",
    "version_number": 1,
    "content": "Answer {{question}} using only approved policy.",
    "variables": [{"name": "question", "type": "string", "required": True}],
    "output_schema": None,
    "model_hints": None,
    "provenance": {"kind": "prompt_studio"},
    "content_hash": "sha256:abc",
    "change_note": None,
    "created_by": None,
    "created_at": "2026-01-01T00:00:00.000Z",
}

FIXTURE_PROMPT = {
    "id": "prompt_1",
    "prompt_key": "support-answer",
    "name": "Support answer",
    "description": None,
    "role": "system",
    "tags": ["support"],
    "status": "draft",
    "created_by": None,
    "updated_by": None,
    "created_at": "2026-01-01T00:00:00.000Z",
    "updated_at": "2026-01-01T00:00:00.000Z",
    "versions": [FIXTURE_VERSION],
    "deployments": [],
}


@pytest.fixture
def client():
    with LiyaEngine(api_key="liya_test_key", base_url=BASE_URL) as c:
        yield c


@respx.mock
def test_list_prompts(client):
    respx.get(f"{BASE_URL}/v1/prompts").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"prompts": [FIXTURE_PROMPT]}})
    )
    prompts = client.prompts.list()
    assert prompts[0].prompt_key == "support-answer"


@respx.mock
def test_get_prompt(client):
    respx.get(f"{BASE_URL}/v1/prompts/prompt_1").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"prompt": FIXTURE_PROMPT}})
    )
    prompt = client.prompts.get("prompt_1")
    assert prompt.name == "Support answer"


@respx.mock
def test_get_prompt_not_found_raises_typed_error(client):
    respx.get(f"{BASE_URL}/v1/prompts/ghost").mock(
        return_value=httpx.Response(404, json={"success": False, "error": {"code": "PROMPT_NOT_FOUND", "message": "Prompt not found."}})
    )
    with pytest.raises(LiyaEngineAPIError) as exc_info:
        client.prompts.get("ghost")
    assert exc_info.value.code == "PROMPT_NOT_FOUND"
    assert exc_info.value.status == 404


@respx.mock
def test_create_prompt_creates_version_1_too(client):
    respx.post(f"{BASE_URL}/v1/prompts").mock(
        return_value=httpx.Response(201, json={"success": True, "data": {"prompt": {**FIXTURE_PROMPT, "id": "prompt_new", "prompt_key": "refund-policy"}}})
    )
    prompt = client.prompts.create(
        prompt_key="refund-policy", name="Refund Policy",
        content="Report the refund status for {{order_id}}.",
        variables=[{"name": "order_id", "type": "string", "required": True}],
    )
    assert prompt.prompt_key == "refund-policy"


@respx.mock
def test_create_prompt_raises_for_duplicate_key(client):
    respx.post(f"{BASE_URL}/v1/prompts").mock(
        return_value=httpx.Response(409, json={"success": False, "error": {"code": "PROMPT_KEY_EXISTS", "message": "taken"}})
    )
    with pytest.raises(LiyaEngineAPIError) as exc_info:
        client.prompts.create(prompt_key="support-answer", name="Dup", content="x")
    assert exc_info.value.code == "PROMPT_KEY_EXISTS"


@respx.mock
def test_versions_list(client):
    respx.get(f"{BASE_URL}/v1/prompts/prompt_1/versions").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"versions": [FIXTURE_VERSION]}})
    )
    versions = client.prompts.versions.list("prompt_1")
    assert versions[0].version_number == 1


@respx.mock
def test_versions_create(client):
    respx.post(f"{BASE_URL}/v1/prompts/prompt_1/versions").mock(
        return_value=httpx.Response(201, json={"success": True, "data": {"version": {**FIXTURE_VERSION, "id": "version_2", "version_number": 2}}})
    )
    version = client.prompts.versions.create("prompt_1", content="Updated content")
    assert version.version_number == 2


@respx.mock
def test_versions_create_raises_for_no_op_save(client):
    respx.post(f"{BASE_URL}/v1/prompts/prompt_1/versions").mock(
        return_value=httpx.Response(409, json={"success": False, "error": {"code": "PROMPT_VERSION_UNCHANGED", "message": "Prompt configuration matches version 1."}})
    )
    with pytest.raises(LiyaEngineAPIError) as exc_info:
        client.prompts.versions.create("prompt_1", content="Same content")
    assert exc_info.value.code == "PROMPT_VERSION_UNCHANGED"


@respx.mock
def test_publish(client):
    respx.post(f"{BASE_URL}/v1/prompts/prompt_1/publish").mock(
        return_value=httpx.Response(200, json={
            "success": True,
            "data": {
                "deployment": {"id": "deployment_1", "environment": "production", "version_id": "version_1", "deployed_by": None, "deployment_note": None, "deployed_at": "2026-01-01T00:00:00.000Z"},
                "unchanged": False,
            },
        })
    )
    result = client.prompts.publish("prompt_1", version_id="version_1")
    assert result.deployment["version_id"] == "version_1"
    assert result.unchanged is False


@respx.mock
def test_publish_raises_for_unknown_version(client):
    respx.post(f"{BASE_URL}/v1/prompts/prompt_1/publish").mock(
        return_value=httpx.Response(404, json={"success": False, "error": {"code": "PROMPT_VERSION_NOT_FOUND", "message": "Prompt or version not found."}})
    )
    with pytest.raises(LiyaEngineAPIError) as exc_info:
        client.prompts.publish("prompt_1", version_id="ghost-version")
    assert exc_info.value.code == "PROMPT_VERSION_NOT_FOUND"
