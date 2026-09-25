from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, cast
from urllib.parse import quote, urlencode

from .._http import HttpClient


@dataclass(frozen=True)
class DocumentChunk:
    id: str
    index: int
    text: str
    metadata: Optional[Dict[str, Any]]

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "DocumentChunk":
        return cls(
            id=data["id"],
            index=data["index"],
            text=data["text"],
            metadata=data.get("metadata"),
        )


@dataclass(frozen=True)
class Document:
    """Tenant-wide knowledge document — the pool collections REFERENCE
    rather than own (a document can be attached to zero, one, or many
    collections). Mirrors /v1/documents (see openapi.yaml).
    """

    id: str
    name: str
    category: str
    chunks: int
    size_kb: int
    embedding_model: Optional[str]
    # None on upload()'s response — a real, pre-existing API asymmetry, not
    # an SDK gap. list()/get() always include it. Call get(id) afterward if
    # you need it right after an upload.
    uploaded_by: Optional[str]
    uploaded_at: str
    collections: List[Dict[str, Any]]
    # Present only on get() — the single-document fetch.
    chunk_list: Optional[List[DocumentChunk]] = None

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "Document":
        chunk_list = data.get("chunkList")
        return cls(
            id=data["id"],
            name=data["name"],
            category=data["category"],
            chunks=data["chunks"],
            size_kb=data["sizeKb"],
            embedding_model=data.get("embeddingModel"),
            uploaded_by=data.get("uploadedBy"),
            uploaded_at=data["uploadedAt"],
            collections=data.get("collections", []),
            chunk_list=[DocumentChunk._from_dict(c) for c in chunk_list] if chunk_list is not None else None,
        )


@dataclass(frozen=True)
class IngestionJob:
    id: str
    source_type: str
    name: str
    status: str
    stage: Optional[str]
    progress: int
    result: Optional[Dict[str, Any]]
    error_message: Optional[str]
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "IngestionJob":
        return cls(
            id=data["id"],
            source_type=data["source_type"],
            name=data["name"],
            status=data["status"],
            stage=data.get("stage"),
            progress=data["progress"],
            result=data.get("result"),
            error_message=data.get("error_message"),
            created_at=data["created_at"],
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
        )


def _query(**params: Any) -> str:
    pairs = {k: v for k, v in params.items() if v is not None}
    return f"?{urlencode(pairs)}" if pairs else ""


class IngestionJobsResource:
    """Async ingestion jobs (URL crawl, file upload) — a non-blocking
    alternative to documents.upload()/push() for large files or deep
    crawls. Poll get() for status; a completed job's "entry" is the
    resulting document's summary.

    Cancellation is cooperative (checked between page fetches / chunk
    embeds), not instant — and there is no crash-recovery sweep: if the
    process running a job restarts mid-run, the job is left "running"
    indefinitely rather than automatically retried or failed. A known
    limitation, not silently promised away.
    """

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def create_url_job(
        self,
        *,
        url: str,
        depth: Optional[int] = None,
        category: Optional[str] = None,
        collection_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {"url": url}
        if depth is not None:
            body["depth"] = depth
        if category is not None:
            body["category"] = category
        if collection_ids is not None:
            body["collectionIds"] = collection_ids
        return cast(Dict[str, Any], self._http.post("/v1/documents/jobs/url", body))

    def create_file_job(
        self,
        *,
        file_base64: str,
        file_name: str,
        category: Optional[str] = None,
        collection_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {"fileBase64": file_base64, "fileName": file_name}
        if category is not None:
            body["category"] = category
        if collection_ids is not None:
            body["collectionIds"] = collection_ids
        return cast(Dict[str, Any], self._http.post("/v1/documents/jobs/file", body))

    def list(
        self, *, page: Optional[int] = None, page_size: Optional[int] = None, status: Optional[str] = None
    ) -> Dict[str, Any]:
        qs = _query(page=page, pageSize=page_size, status=status)
        data = cast(Dict[str, Any], self._http.get(f"/v1/documents/jobs{qs}"))
        return {
            "jobs": [IngestionJob._from_dict(j) for j in data["jobs"]],
            "pagination": data["pagination"],
        }

    def get(self, job_id: str) -> Dict[str, Any]:
        return cast(Dict[str, Any], self._http.get(f"/v1/documents/jobs/{quote(job_id)}"))

    def cancel(self, job_id: str) -> Dict[str, Any]:
        """Cooperative — the worker notices and stops at its next checkpoint, not instantly."""
        data = cast(Dict[str, Any], self._http.post(f"/v1/documents/jobs/{quote(job_id)}/cancel"))
        return {"job": IngestionJob._from_dict(data["job"])}


class DocumentsResource:
    def __init__(self, http: HttpClient) -> None:
        self._http = http
        self.jobs = IngestionJobsResource(http)

    def list(self) -> List[Document]:
        data = self._http.get("/v1/documents")
        return [Document._from_dict(d) for d in data["documents"]]

    def get(self, id: str) -> Document:
        """Includes the document's full chunk_list."""
        data = self._http.get(f"/v1/documents/{quote(id)}")
        return Document._from_dict(data)

    def delete(self, id: str) -> None:
        """Removes the document and its embeddings. Cascades collection attachments via FK."""
        self._http.delete(f"/v1/documents/{quote(id)}")

    def upload(
        self,
        *,
        file_base64: str,
        file_name: str,
        category: Optional[str] = None,
        collection_ids: Optional[List[str]] = None,
    ) -> Document:
        """Synchronous — the request blocks until extraction/chunking/embedding
        completes. For large files, prefer jobs.create_file_job() instead. If
        collection_ids names exactly one collection, that collection's own
        chunking/embedding defaults pre-fill this upload.

        Unlike list()/get(), the response here has no uploaded_by — a real,
        pre-existing asymmetry in the underlying API, not an SDK gap. Call
        get(id) afterward if you need it.
        """
        body: Dict[str, Any] = {"fileBase64": file_base64, "fileName": file_name}
        if category is not None:
            body["category"] = category
        if collection_ids is not None:
            body["collectionIds"] = collection_ids
        data = self._http.post("/v1/documents", body)
        return Document._from_dict(data)

    def push(
        self,
        *,
        url: Optional[str] = None,
        content: Optional[str] = None,
        title: Optional[str] = None,
        source_id: Optional[str] = None,
        category: Optional[str] = None,
        collection_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Synchronous — pushes a URL or inline content, upserting by a
        deterministic source_id. Prefer jobs.create_url_job() for a deep
        crawl (this only fetches the one URL given, no link-following).
        """
        body: Dict[str, Any] = {}
        if url is not None:
            body["url"] = url
        if content is not None:
            body["content"] = content
        if title is not None:
            body["title"] = title
        if source_id is not None:
            body["sourceId"] = source_id
        if category is not None:
            body["category"] = category
        if collection_ids is not None:
            body["collectionIds"] = collection_ids
        return cast(Dict[str, Any], self._http.post("/v1/documents/push", body))
