import httpx
import pytest
import respx

from liyaengine import LiyaEngine, LiyaEngineAPIError

BASE_URL = "https://api.test.liyaengine.ai"

FIXTURE_DOCUMENT = {
    "id": "doc_123",
    "name": "faq.txt",
    "category": "faq",
    "chunks": 3,
    "sizeKb": 2,
    "embeddingModel": "text-embedding-3-small",
    "uploadedBy": "user_1",
    "uploadedAt": "2026-01-01T00:00:00.000Z",
    "collections": [{"id": "col_123", "slug": "contracts", "label": "Contracts", "color": "#6366f1"}],
}

FIXTURE_DOCUMENT_DETAIL = {
    **FIXTURE_DOCUMENT,
    "chunkList": [{"id": "chk_1", "index": 0, "text": "Refunds take 5-7 days.", "metadata": None}],
}

FIXTURE_JOB = {
    "id": "job_1",
    "source_type": "_unfiled",
    "name": "faq.txt",
    "status": "pending",
    "stage": None,
    "progress": 0,
    "result": None,
    "error_message": None,
    "created_at": "2026-01-01T00:00:00.000Z",
    "started_at": None,
    "completed_at": None,
}


@pytest.fixture
def client():
    with LiyaEngine(api_key="liya_test_key", base_url=BASE_URL) as c:
        yield c


@respx.mock
def test_list_returns_documents(client):
    respx.get(f"{BASE_URL}/v1/documents").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"documents": [FIXTURE_DOCUMENT], "total": 1}})
    )
    documents = client.documents.list()
    assert len(documents) == 1
    assert documents[0].id == "doc_123"


@respx.mock
def test_get_includes_chunk_list(client):
    respx.get(f"{BASE_URL}/v1/documents/doc_123").mock(
        return_value=httpx.Response(200, json={"success": True, "data": FIXTURE_DOCUMENT_DETAIL})
    )
    detail = client.documents.get("doc_123")
    assert detail.chunk_list is not None
    assert len(detail.chunk_list) == 1


@respx.mock
def test_delete_does_not_raise(client):
    respx.delete(f"{BASE_URL}/v1/documents/doc_123").mock(return_value=httpx.Response(200, json={"success": True}))
    client.documents.delete("doc_123")  # no exception = pass


@respx.mock
def test_upload_response_has_no_uploaded_by(client):
    body = {k: v for k, v in FIXTURE_DOCUMENT.items() if k != "uploadedBy"}
    respx.post(f"{BASE_URL}/v1/documents").mock(
        return_value=httpx.Response(201, json={"success": True, "data": body})
    )
    uploaded = client.documents.upload(file_base64="ZmFrZQ==", file_name="faq.txt", category="faq")
    assert uploaded.id == "doc_123"
    assert uploaded.uploaded_by is None


@respx.mock
def test_push_returns_upserted_source_id(client):
    respx.post(f"{BASE_URL}/v1/documents/push").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"source_id": "src_1", "chunks": 3, "title": "FAQ"}})
    )
    pushed = client.documents.push(url="https://example.com/faq", title="FAQ")
    assert pushed == {"source_id": "src_1", "chunks": 3, "title": "FAQ"}


@respx.mock
def test_jobs_create_url_job(client):
    respx.post(f"{BASE_URL}/v1/documents/jobs/url").mock(
        return_value=httpx.Response(202, json={"success": True, "data": {"jobId": "job_1", "status": "pending"}})
    )
    job = client.documents.jobs.create_url_job(url="https://example.com", depth=1)
    assert job == {"jobId": "job_1", "status": "pending"}


@respx.mock
def test_jobs_create_file_job(client):
    respx.post(f"{BASE_URL}/v1/documents/jobs/file").mock(
        return_value=httpx.Response(202, json={"success": True, "data": {"jobId": "job_2", "status": "pending"}})
    )
    job = client.documents.jobs.create_file_job(file_base64="ZmFrZQ==", file_name="notes.txt")
    assert job == {"jobId": "job_2", "status": "pending"}


@respx.mock
def test_jobs_list_with_query_params(client):
    route = respx.get(f"{BASE_URL}/v1/documents/jobs").mock(
        return_value=httpx.Response(
            200,
            json={
                "success": True,
                "data": {"jobs": [FIXTURE_JOB], "pagination": {"page": 1, "pageSize": 20, "total": 1, "totalPages": 1}},
            },
        )
    )
    page = client.documents.jobs.list(status="pending")
    assert route.calls.last.request.url.params["status"] == "pending"
    assert page["jobs"][0].id == "job_1"
    assert page["pagination"]["total"] == 1


@respx.mock
def test_jobs_get_status(client):
    respx.get(f"{BASE_URL}/v1/documents/jobs/job_1").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"jobId": "job_1", "status": "pending", "stage": None, "progress": 0}})
    )
    status = client.documents.jobs.get("job_1")
    assert status["status"] == "pending"


@respx.mock
def test_jobs_cancel(client):
    respx.post(f"{BASE_URL}/v1/documents/jobs/job_1/cancel").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"job": {**FIXTURE_JOB, "status": "cancelled"}}})
    )
    result = client.documents.jobs.cancel("job_1")
    assert result["job"].status == "cancelled"


@respx.mock
def test_list_flagged_chunks(client):
    respx.get(f"{BASE_URL}/v1/documents/flagged-chunks").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"chunks": [{
            "id": "chunk_1", "source_type": "document", "source_id": "doc_123", "chunk_index": 2,
            "content_text": "stale refund policy text", "correction_count": 3,
            "flagged_at": "2026-01-02T00:00:00.000Z", "created_at": "2026-01-01T00:00:00.000Z",
        }], "total": 1}})
    )
    chunks = client.documents.list_flagged_chunks()
    assert len(chunks) == 1
    assert chunks[0].correction_count == 3


@respx.mock
def test_resolve_flagged_chunk(client):
    respx.post(f"{BASE_URL}/v1/documents/flagged-chunks/chunk_1/resolve").mock(
        return_value=httpx.Response(200, json={"success": True})
    )
    assert client.documents.resolve_flagged_chunk("chunk_1") is None


@respx.mock
def test_get_flagged_chunk_returns_the_passage_and_its_corrections():
    respx.get(f"{BASE_URL}/v1/documents/flagged-chunks/chunk_1").mock(return_value=httpx.Response(200, json={"success": True, "data": {
        "chunk": {"id": "chunk_1", "source_type": "document", "source_id": "doc_1", "chunk_index": 2, "content_text": "Refunds within 30 days.",
                  "document_name": "policy.pdf", "correction_count": 3, "flagged_at": "2026-01-02T00:00:00.000Z"},
        "corrections": [{"conversation_id": "c1", "question": "Annual plan?", "assistant_reply": "30 days.", "staff_reply": "45 days for annual plans.", "at": "2026-01-02T00:00:00.000Z"}],
    }}))
    with LiyaEngine(api_key="liya_test_key", base_url=BASE_URL, max_retries=0) as client:
        d = client.documents.get_flagged_chunk("chunk_1")
    assert d.chunk["document_name"] == "policy.pdf" and d.chunk["correction_count"] == 3
    assert d.corrections[0]["staff_reply"] == "45 days for annual plans."


@respx.mock
def test_draft_flagged_chunk_rewrite_returns_checked_edits():
    respx.post(f"{BASE_URL}/v1/documents/flagged-chunks/chunk_1/draft-rewrite").mock(return_value=httpx.Response(200, json={"success": True, "data": {"draft": {
        "chunk_id": "chunk_1", "original": "Refunds within 30 days.", "revised_text": "Refunds within 45 days.",
        "edits": [{"id": "e0", "before": "Refunds within 30 days.", "after": "Refunds within 45 days.", "sources": ["C1"], "reason": "Staff said 45", "start": 0, "end": 23}],
        "unclear": [], "dropped_unsupported": 0, "corrections": [], "reason": None, "usage": {"tokens": 900, "cost": 0.01, "served_by": "platform"},
    }}}))
    with LiyaEngine(api_key="liya_test_key", base_url=BASE_URL, max_retries=0) as client:
        d = client.documents.draft_flagged_chunk_rewrite("chunk_1")
    assert d.revised_text == "Refunds within 45 days." and d.reason is None and d.dropped_unsupported == 0
    assert d.edits[0]["before"] == "Refunds within 30 days." and d.edits[0]["sources"] == ["C1"]


@respx.mock
def test_draft_flagged_chunk_rewrite_is_never_retried_because_each_attempt_is_a_paid_model_call():
    route = respx.post(f"{BASE_URL}/v1/documents/flagged-chunks/chunk_1/draft-rewrite").mock(return_value=httpx.Response(502, json={
        "success": False, "error": {"code": "DRAFT_UNAVAILABLE", "message": "Try again."},
    }))
    with LiyaEngine(api_key="liya_test_key", base_url=BASE_URL, max_retries=2) as client:
        with pytest.raises(LiyaEngineAPIError) as err:
            client.documents.draft_flagged_chunk_rewrite("chunk_1")
    assert err.value.code == "DRAFT_UNAVAILABLE" and route.call_count == 1
