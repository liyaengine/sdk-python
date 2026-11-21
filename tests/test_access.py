import json

import httpx
import respx

from liyaengine import LiyaEngine

BASE_URL = "https://api.test.liyaengine.ai"


def client() -> LiyaEngine:
    return LiyaEngine(api_key="liya_test_key", base_url=BASE_URL)


def sent(route) -> dict:
    return json.loads(route.calls.last.request.content)


@respx.mock
def test_run_sends_access_top_level_and_omits_it_when_not_given():
    route = respx.post(f"{BASE_URL}/v1/run").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"response": "ok"}, "meta": {}, "usage": {}})
    )
    client().intents.run(domain="hr", intent="ask", input={"user_id": "u1", "message": "hi"}, access={"groups": ["hr"]})
    body = sent(route)
    assert body["access"] == {"groups": ["hr"]}
    assert "access" not in body["input"]

    client().intents.run(domain="hr", intent="ask", input={"user_id": "u1"})
    assert "access" not in sent(route)


@respx.mock
def test_collections_query_and_agent_run_pass_access():
    q = respx.post(f"{BASE_URL}/v1/collections/query").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"results": [], "total": 0}})
    )
    client().collections.query(query="pay", access={"groups": []})
    assert sent(q)["access"] == {"groups": []}

    a = respx.post(f"{BASE_URL}/v1/agents/support/run").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"run_id": "r"}})
    )
    client().agents.run("support", input={"message": "hi"}, access={"groups": ["gold"]})
    assert sent(a)["access"] == {"groups": ["gold"]}


@respx.mock
def test_documents_label_on_upload_and_push_and_relabel():
    up = respx.post(f"{BASE_URL}/v1/documents").mock(
        return_value=httpx.Response(201, json={"success": True, "data": {
            "id": "d", "name": "pay.txt", "category": "document", "chunks": 1, "sizeKb": 1,
            "embeddingModel": "m", "uploadedAt": "2026-01-01T00:00:00.000Z", "collections": []}})
    )
    client().documents.upload(file_base64="ZmFrZQ==", file_name="pay.txt", access_groups=["hr"])
    assert sent(up)["accessGroups"] == ["hr"]

    push = respx.post(f"{BASE_URL}/v1/documents/push").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"source_id": "s", "chunks": 1, "title": "t"}})
    )
    client().documents.push(content="x")
    assert "accessGroups" not in sent(push)          # not given: keep the existing label
    client().documents.push(content="x", access_groups=None)
    assert sent(push)["accessGroups"] is None         # explicit None: unrestricted

    patch = respx.patch(f"{BASE_URL}/v1/documents/doc_1").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"id": "doc_1", "access_groups": ["hr"], "chunks_updated": 4}})
    )
    out = client().documents.set_access("doc_1", ["hr"])
    assert sent(patch) == {"accessGroups": ["hr"]}
    assert out["chunks_updated"] == 4


@respx.mock
def test_domain_update_turns_enforcement_on():
    route = respx.patch(f"{BASE_URL}/v1/domains/hr").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"updated": 1}})
    )
    client().domains.update("hr", retrieval_access="enforce")
    assert sent(route) == {"retrievalAccess": "enforce"}
