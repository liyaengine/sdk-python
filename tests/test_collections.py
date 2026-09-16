import httpx
import pytest
import respx

from liyaengine import LiyaEngine, LiyaEngineAPIError

BASE_URL = "https://api.test.liyaengine.ai"

FIXTURE_COLLECTION = {
    "id": "col_123",
    "slug": "contracts",
    "label": "Contracts",
    "color": "#6366f1",
    "created_at": "2026-01-01T00:00:00.000Z",
    "domain_keys": ["legal-ops"],
    "tags": [],
    "visibility": "workspace",
    "last_synced_at": None,
    "retrieval_config": None,
    "default_embedding_model": None,
    "default_chunking_strategy": None,
    "default_chunk_size": None,
    "default_chunk_overlap": None,
}


@pytest.fixture
def client():
    with LiyaEngine(api_key="liya_test_key", base_url=BASE_URL) as c:
        yield c


def test_constructor_requires_api_key():
    with pytest.raises(ValueError, match="api_key is required"):
        LiyaEngine(api_key="")


@respx.mock
def test_list_unwraps_envelope(client):
    respx.get(f"{BASE_URL}/v1/collections").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"collections": [FIXTURE_COLLECTION]}})
    )
    collections = client.collections.list()
    assert len(collections) == 1
    assert collections[0].slug == "contracts"


@respx.mock
def test_get_returns_single_collection(client):
    respx.get(f"{BASE_URL}/v1/collections/col_123").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"collection": FIXTURE_COLLECTION}})
    )
    collection = client.collections.get("col_123")
    assert collection.id == "col_123"


@respx.mock
def test_get_raises_typed_error_on_404(client):
    respx.get(f"{BASE_URL}/v1/collections/missing").mock(
        return_value=httpx.Response(
            404, json={"success": False, "error": {"code": "NOT_FOUND", "message": "Collection not found."}}
        )
    )
    with pytest.raises(LiyaEngineAPIError) as exc_info:
        client.collections.get("missing")
    assert exc_info.value.code == "NOT_FOUND"
    assert exc_info.value.status == 404


@respx.mock
def test_create_returns_new_collection(client):
    respx.post(f"{BASE_URL}/v1/collections").mock(
        return_value=httpx.Response(
            201, json={"success": True, "data": {"collection": {**FIXTURE_COLLECTION, "id": "col_new"}}}
        )
    )
    collection = client.collections.create(slug="contracts", label="Contracts", domain_keys=["legal-ops"])
    assert collection.id == "col_new"


@respx.mock
def test_create_raises_typed_409_on_conflict(client):
    respx.post(f"{BASE_URL}/v1/collections").mock(
        return_value=httpx.Response(
            409,
            json={
                "success": False,
                "error": {"code": "SLUG_CONFLICT", "message": "A collection named 'contracts' already exists."},
            },
        )
    )
    with pytest.raises(LiyaEngineAPIError) as exc_info:
        client.collections.create(slug="contracts", label="Contracts", domain_keys=["legal-ops"])
    assert exc_info.value.code == "SLUG_CONFLICT"
    assert exc_info.value.status == 409


@respx.mock
def test_update_patches_collection(client):
    respx.patch(f"{BASE_URL}/v1/collections/col_123").mock(
        return_value=httpx.Response(
            200, json={"success": True, "data": {"collection": {**FIXTURE_COLLECTION, "label": "Renamed"}}}
        )
    )
    updated = client.collections.update("col_123", label="Renamed")
    assert updated.label == "Renamed"


@respx.mock
def test_delete_does_not_raise(client):
    respx.delete(f"{BASE_URL}/v1/collections/col_123").mock(
        return_value=httpx.Response(200, json={"success": True})
    )
    client.collections.delete("col_123")  # no exception = pass
