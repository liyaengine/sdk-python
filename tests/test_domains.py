import json

import httpx
import pytest
import respx

from liyaengine import LiyaEngine, LiyaEngineAPIError

BASE_URL = "https://api.test.liyaengine.ai"

FIXTURE_DOMAIN = {
    "id": "dom_123",
    "tenant_id": "tenant_1",
    "domain_key": "billing",
    "display_name": "Billing",
    "description": None,
    "icon": "◆",
    "color": "#6366f1",
    "system_prompt": None,
    "prompt_binding": None,
    "context_enrichment_webhook_url": None,
    "retrieval_scope": None,
    "status": "active",
    "is_active": True,
    "created_at": "2026-01-01T00:00:00.000Z",
    "updated_at": "2026-01-01T00:00:00.000Z",
}

FIXTURE_INTENT = {
    "id": "int_123",
    "tenant_id": "tenant_1",
    "domain_key": "billing",
    "intent_key": "refund-status",
    "display_name": "Refund Status",
    "description": "Answer refund status questions.",
    "prompt_template": "You are a billing assistant...",
    "prompt_binding": None,
    "output_schema": None,
    "input_schema": None,
    "guardrails_config": None,
    "agent_config": None,
    "execution_config": None,
    "retrieval_config": None,
    "cache_config": None,
    "is_active": True,
    "sort_order": 0,
    "created_at": "2026-01-01T00:00:00.000Z",
    "updated_at": "2026-01-01T00:00:00.000Z",
}

FIXTURE_VERSION = {
    "id": "ver_1",
    "version_number": 1,
    "changed_fields": ["prompt_template"],
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
def test_domain_crud(client):
    respx.get(f"{BASE_URL}/v1/domains").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"domains": [FIXTURE_DOMAIN]}})
    )
    domains = client.domains.list()
    assert len(domains) == 1

    respx.post(f"{BASE_URL}/v1/domains").mock(
        return_value=httpx.Response(201, json={"success": True, "data": {"domain": FIXTURE_DOMAIN}})
    )
    created = client.domains.create(domain_key="billing", display_name="Billing", status="draft")
    assert created.domain_key == "billing"

    respx.get(f"{BASE_URL}/v1/domains/billing").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"domain": {**FIXTURE_DOMAIN, "intents": [FIXTURE_INTENT], "source_types": []}}})
    )
    fetched = client.domains.get("billing")
    assert fetched.intents is not None
    assert len(fetched.intents) == 1

    respx.patch(f"{BASE_URL}/v1/domains/billing").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"updated": 1}})
    )
    updated = client.domains.update("billing", display_name="Billing Support", status="active")
    assert updated["updated"] == 1

    respx.delete(f"{BASE_URL}/v1/domains/billing").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"deleted": "billing"}})
    )
    client.domains.delete("billing")


@respx.mock
def test_domain_query(client):
    respx.post(f"{BASE_URL}/v1/domains/billing/query").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"results": [{"content": "Refunds take 5-7 days.", "score": 0.91}], "total": 1}})
    )
    result = client.domains.query("billing", query="refund timeline")
    assert result["total"] == 1
    assert "5-7 days" in result["results"][0]["content"]


@respx.mock
def test_domain_upload_document(client):
    respx.post(f"{BASE_URL}/v1/domains/billing/sources/billing-faq/docs").mock(
        return_value=httpx.Response(201, json={"success": True, "data": {"document": {"id": "doc_1", "name": "faq.txt", "chunks": 3, "sizeKb": 2, "uploadedAt": "2026-01-01T00:00:00.000Z"}}})
    )
    doc = client.domains.upload_document("billing", "billing-faq", file_base64="aGVsbG8=", file_name="faq.txt")
    assert doc["chunks"] == 3


@respx.mock
def test_domain_intents_crud(client):
    respx.get(f"{BASE_URL}/v1/domains/billing/intents").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"intents": [FIXTURE_INTENT]}})
    )
    intents = client.domains.intents.list("billing")
    assert len(intents) == 1

    respx.get(f"{BASE_URL}/v1/domains/billing/intents/refund-status").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"intent": FIXTURE_INTENT}})
    )
    fetched = client.domains.intents.get("billing", "refund-status")
    assert fetched.intent_key == "refund-status"

    respx.post(f"{BASE_URL}/v1/domains/billing/intents").mock(
        return_value=httpx.Response(201, json={"success": True, "data": {"intent": FIXTURE_INTENT}})
    )
    created = client.domains.intents.create(
        "billing", intent_key="refund-status", display_name="Refund Status",
        description="Answer refund status questions.", prompt_template="You are a billing assistant...",
    )
    assert created.intent_key == "refund-status"

    respx.patch(f"{BASE_URL}/v1/domains/billing/intents/refund-status").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"updated": 1}})
    )
    updated = client.domains.intents.update(
        "billing", "refund-status", display_name="Refund Status v2",
        agent_config={"enabled": True, "max_steps": 3}, sort_order=2,
    )
    assert updated["updated"] == 1

    respx.delete(f"{BASE_URL}/v1/domains/billing/intents/refund-status").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"deleted": "refund-status"}})
    )
    client.domains.intents.delete("billing", "refund-status")


@respx.mock
def test_domain_intent_create_with_prompt_binding(client):
    respx.post(f"{BASE_URL}/v1/domains/billing/intents").mock(
        return_value=httpx.Response(201, json={"success": True, "data": {"intent": FIXTURE_INTENT}})
    )
    created = client.domains.intents.create(
        "billing", intent_key="refund-status", display_name="Refund Status",
        description="Answer refund status questions.",
        prompt_binding={"kind": "library_version", "prompt_id": "prompt_1", "version_id": "version_2", "content_hash": "sha256:" + "a" * 64},
    )
    assert created.intent_key == "refund-status"


@respx.mock
def test_domain_intent_versions(client):
    respx.get(f"{BASE_URL}/v1/domains/billing/intents/refund-status/versions").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"versions": [FIXTURE_VERSION]}})
    )
    versions = client.domains.intents.versions.list("billing", "refund-status")
    assert len(versions) == 1
    assert versions[0].change_type == "create"

    respx.get(f"{BASE_URL}/v1/domains/billing/intents/refund-status/versions/1").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"version": FIXTURE_VERSION}})
    )
    version = client.domains.intents.versions.get("billing", "refund-status", 1)
    assert version.version_number == 1

    respx.post(f"{BASE_URL}/v1/domains/billing/intents/refund-status/versions/1/restore").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"intent": FIXTURE_INTENT}})
    )
    restored = client.domains.intents.versions.restore("billing", "refund-status", 1)
    assert restored.intent_key == "refund-status"


@respx.mock
def test_domain_sources_crud(client):
    respx.get(f"{BASE_URL}/v1/domains/billing/sources").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"sources": [{"id": "src_1", "tenant_id": "tenant_1", "domain_key": "billing", "slug": "billing-faq", "label": "Billing FAQ", "color": "#6366f1", "created_at": "2026-01-01T00:00:00.000Z"}]}})
    )
    sources = client.domains.sources.list("billing")
    assert len(sources) == 1

    respx.post(f"{BASE_URL}/v1/domains/billing/sources").mock(
        return_value=httpx.Response(201, json={"success": True, "data": {"sourceType": {"id": "src_new", "tenant_id": "tenant_1", "domain_key": "billing", "slug": "billing-faq", "label": "Billing FAQ", "color": "#6366f1", "created_at": "2026-01-01T00:00:00.000Z", "domain_keys": ["billing"]}}})
    )
    created = client.domains.sources.create("billing", slug="billing-faq", label="Billing FAQ")
    assert created.slug == "billing-faq"

    respx.delete(f"{BASE_URL}/v1/domains/billing/sources/billing-faq").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"deleted": "billing-faq"}})
    )
    client.domains.sources.delete("billing", "billing-faq")


@respx.mock
def test_intents_list_all(client):
    respx.get(f"{BASE_URL}/v1/intents").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"intents": [{
            "domain": "billing", "domainLabel": "Billing", "intent": "refund-status", "displayName": "Refund Status",
            "description": None, "endpoint": "/v1/billing/refund-status", "method": "POST", "inputSchema": {}, "outputSchema": None,
        }], "total": 1}})
    )
    catalog = client.intents.list_all()
    assert len(catalog) == 1
    assert catalog[0].domain == "billing"


@respx.mock
def test_intents_run(client):
    respx.post(f"{BASE_URL}/v1/run").mock(
        return_value=httpx.Response(200, json={
            "success": True,
            "data": {"output": {"answer": "Refunds take 5-7 days."}, "session_id": "sess_2", "message_id": "msg_1"},
            "metadata": {
                "intent": "refund-status", "domain": "billing", "model_used": "gpt-4o-mini",
                "tokens_used": 88, "cost_usd": 0.0008, "latency_ms": 301, "cached": False,
            },
            "usage": {"requests_used": 12, "tokens_used": 4908, "requests_remaining": 988, "tokens_remaining": 244870},
        })
    )
    result = client.intents.run(domain="billing", intent="refund-status", message="How long do refunds take?")
    assert result.data == {"output": {"answer": "Refunds take 5-7 days."}, "session_id": "sess_2", "message_id": "msg_1"}
    assert result.metadata is not None and result.metadata["model_used"] == "gpt-4o-mini"
    assert result.usage is not None and result.usage["requests_remaining"] == 988


@respx.mock
def test_intents_stream_yields_frames_in_order(client):
    frames = [
        {"type": "token", "delta": "Refunds "},
        {"type": "token", "delta": "take 5-7 days."},
        {
            "type": "done", "session_id": "sess_3", "latency_ms": 300,
            "input_tokens": 40, "output_tokens": 12, "cost_usd": 0.0005, "served_by": "platform",
        },
    ]
    sse_body = "".join(f"data: {json.dumps(f)}\n\n" for f in frames)
    respx.post(f"{BASE_URL}/v1/run/stream").mock(
        return_value=httpx.Response(200, content=sse_body, headers={"content-type": "text/event-stream"})
    )
    events = list(client.intents.stream(domain="chat", intent="answer_question", message="hi"))
    assert events == frames


@respx.mock
def test_intents_stream_raises_for_custom_domain_pre_flight_rejection(client):
    respx.post(f"{BASE_URL}/v1/run/stream").mock(
        return_value=httpx.Response(400, json={
            "success": False,
            "error": {"code": "STREAMING_NOT_SUPPORTED", "message": "Streaming is only supported for built-in packs today."},
        })
    )
    with pytest.raises(LiyaEngineAPIError) as exc_info:
        list(client.intents.stream(domain="legal-ops", intent="review-contract"))
    assert exc_info.value.code == "STREAMING_NOT_SUPPORTED"
    assert exc_info.value.status == 400
