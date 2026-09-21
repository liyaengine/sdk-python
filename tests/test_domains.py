import httpx
import pytest
import respx

from liyaengine import LiyaEngine

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
    "context_enrichment_webhook_url": None,
    "retrieval_scope": None,
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
    "output_schema": None,
    "input_schema": None,
    "guardrails_config": None,
    "is_active": True,
    "sort_order": 0,
    "created_at": "2026-01-01T00:00:00.000Z",
    "updated_at": "2026-01-01T00:00:00.000Z",
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
    created = client.domains.create(domain_key="billing", display_name="Billing")
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
    updated = client.domains.update("billing", display_name="Billing Support")
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

    respx.post(f"{BASE_URL}/v1/domains/billing/intents").mock(
        return_value=httpx.Response(201, json={"success": True, "data": {"intent": FIXTURE_INTENT}})
    )
    created = client.domains.intents.create(
        "billing", intent_key="refund-status", display_name="Refund Status", prompt_template="You are a billing assistant...",
    )
    assert created.intent_key == "refund-status"

    respx.patch(f"{BASE_URL}/v1/domains/billing/intents/refund-status").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"updated": 1}})
    )
    updated = client.domains.intents.update("billing", "refund-status", display_name="Refund Status v2")
    assert updated["updated"] == 1

    respx.delete(f"{BASE_URL}/v1/domains/billing/intents/refund-status").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"deleted": "refund-status"}})
    )
    client.domains.intents.delete("billing", "refund-status")


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
