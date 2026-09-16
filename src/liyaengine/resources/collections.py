from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .._http import HttpClient


@dataclass(frozen=True)
class Collection:
    id: str
    slug: str
    label: str
    color: str
    created_at: str
    domain_keys: List[str]
    tags: List[str]
    visibility: str
    last_synced_at: Optional[str]
    retrieval_config: Optional[Dict[str, Any]]
    default_embedding_model: Optional[str]
    default_chunking_strategy: Optional[str]
    default_chunk_size: Optional[int]
    default_chunk_overlap: Optional[int]

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "Collection":
        return cls(
            id=data["id"],
            slug=data["slug"],
            label=data["label"],
            color=data["color"],
            created_at=data["created_at"],
            domain_keys=data.get("domain_keys", []),
            tags=data.get("tags", []),
            visibility=data.get("visibility", "workspace"),
            last_synced_at=data.get("last_synced_at"),
            retrieval_config=data.get("retrieval_config"),
            default_embedding_model=data.get("default_embedding_model"),
            default_chunking_strategy=data.get("default_chunking_strategy"),
            default_chunk_size=data.get("default_chunk_size"),
            default_chunk_overlap=data.get("default_chunk_overlap"),
        )


class CollectionsResource:
    """Tenant-wide knowledge collections — organize documents, scope
    retrieval, attach to one or many domains. Mirrors GET/POST
    /v1/collections and GET/PATCH/DELETE /v1/collections/{id} exactly
    (see liyaengine-api's openapi.yaml).
    """

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def list(self) -> List[Collection]:
        data = self._http.get("/v1/collections")
        return [Collection._from_dict(c) for c in data["collections"]]

    def get(self, id: str) -> Collection:
        data = self._http.get(f"/v1/collections/{id}")
        return Collection._from_dict(data["collection"])

    def create(
        self,
        *,
        slug: str,
        label: str,
        domain_keys: List[str],
        color: Optional[str] = None,
        default_embedding_model: Optional[str] = None,
        default_chunking_strategy: Optional[str] = None,
        default_chunk_size: Optional[int] = None,
        default_chunk_overlap: Optional[int] = None,
    ) -> Collection:
        body: Dict[str, Any] = {"slug": slug, "label": label, "domain_keys": domain_keys}
        if color is not None:
            body["color"] = color
        if default_embedding_model is not None:
            body["default_embedding_model"] = default_embedding_model
        if default_chunking_strategy is not None:
            body["default_chunking_strategy"] = default_chunking_strategy
        if default_chunk_size is not None:
            body["default_chunk_size"] = default_chunk_size
        if default_chunk_overlap is not None:
            body["default_chunk_overlap"] = default_chunk_overlap

        data = self._http.post("/v1/collections", body)
        return Collection._from_dict(data["collection"])

    def update(
        self,
        id: str,
        *,
        label: Optional[str] = None,
        color: Optional[str] = None,
        tags: Optional[List[str]] = None,
        visibility: Optional[str] = None,
        retrieval_config: Optional[Dict[str, Any]] = None,
        default_embedding_model: Optional[str] = None,
        default_chunking_strategy: Optional[str] = None,
        default_chunk_size: Optional[int] = None,
        default_chunk_overlap: Optional[int] = None,
    ) -> Collection:
        body: Dict[str, Any] = {}
        if label is not None:
            body["label"] = label
        if color is not None:
            body["color"] = color
        if tags is not None:
            body["tags"] = tags
        if visibility is not None:
            body["visibility"] = visibility
        if retrieval_config is not None:
            body["retrieval_config"] = retrieval_config
        if default_embedding_model is not None:
            body["default_embedding_model"] = default_embedding_model
        if default_chunking_strategy is not None:
            body["default_chunking_strategy"] = default_chunking_strategy
        if default_chunk_size is not None:
            body["default_chunk_size"] = default_chunk_size
        if default_chunk_overlap is not None:
            body["default_chunk_overlap"] = default_chunk_overlap

        data = self._http.patch(f"/v1/collections/{id}", body)
        return Collection._from_dict(data["collection"])

    def delete(self, id: str) -> None:
        self._http.delete(f"/v1/collections/{id}")
