import httpx
import pytest
import respx

from liyaengine import LiyaEngine

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
