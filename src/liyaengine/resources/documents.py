from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, cast
from urllib.parse import quote, urlencode

from .._http import HttpClient

# Distinguishes "not given" from an explicit None (None means unrestricted).
_UNSET: Any = object()


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


@dataclass(frozen=True)
class FlaggedChunkDetail:
    """A flagged passage in full, with the corrections behind it. Only a count is stored per passage, so the corrections are
    rebuilt from the conversations that retrieved it: there can be fewer than `correction_count`. A flag is a suspicion, not
    proof, because a correction counts against every passage retrieved for that reply."""

    # {"id", "source_type", "source_id", "chunk_index", "content_text", "document_name", "correction_count", "flagged_at"}
    chunk: Dict[str, Any]
    # [{"conversation_id", "question", "assistant_reply", "staff_reply", "at"}], newest first, personal details removed.
    corrections: List[Dict[str, Any]]

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "FlaggedChunkDetail":
        return cls(chunk=data["chunk"], corrections=data.get("corrections") or [])


@dataclass(frozen=True)
class ChunkRewriteDraft:
    """Checked edits that make a flagged passage agree with what staff said. Each edit quotes the passage word for word and is kept
    only if a staff reply it cites says it. Nothing is saved: a passage cannot be edited in place, so apply `revised_text` in the
    source document, then resolve the flag."""

    chunk_id: str
    original: str
    # The passage with every kept edit applied.
    revised_text: str
    # [{"id", "before" (exact quote, None for text added at the end), "after", "sources": ["C1"], "reason", "start", "end"}]
    edits: List[Dict[str, Any]]
    # Why no edit was made, or what the staff replies leave open.
    unclear: List[str]
    # Edits the model proposed that were dropped: not an exact quote, or citing a reply that does not say it.
    dropped_unsupported: int
    corrections: List[Dict[str, Any]]
    # "NO_CORRECTIONS": no staff reply could be found, no model was called. "NO_CHANGE": the replies show no error in this passage.
    reason: Optional[str]
    usage: Optional[Dict[str, Any]]

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "ChunkRewriteDraft":
        return cls(
            chunk_id=data["chunk_id"], original=data["original"], revised_text=data["revised_text"], edits=data.get("edits") or [],
            unclear=data.get("unclear") or [], dropped_unsupported=int(data.get("dropped_unsupported", 0)),
            corrections=data.get("corrections") or [], reason=data.get("reason"), usage=data.get("usage"),
        )


@dataclass(frozen=True)
class FlaggedChunk:
    """One chunk from the tenant-wide embedding store that accumulated enough human corrections to be flagged for review."""

    id: str
    # What kind of content this chunk came from (document, article, etc.).
    source_type: str
    source_id: str
    chunk_index: int
    content_text: str
    correction_count: int
    flagged_at: Optional[str]
    created_at: str

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "FlaggedChunk":
        return cls(
            id=data["id"], source_type=data["source_type"], source_id=data["source_id"],
            chunk_index=data["chunk_index"], content_text=data["content_text"],
            correction_count=data["correction_count"], flagged_at=data.get("flagged_at"),
            created_at=data["created_at"],
        )


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
        access_groups: Any = _UNSET,
    ) -> Document:
        """Synchronous — the request blocks until extraction/chunking/embedding
        completes. For large files, prefer jobs.create_file_job() instead. If
        collection_ids names exactly one collection, that collection's own
        chunking/embedding defaults pre-fill this upload.

        Unlike list()/get(), the response here has no uploaded_by — a real,
        pre-existing asymmetry in the underlying API, not an SDK gap. Call
        get(id) afterward if you need it.

        `access_groups` restricts the document to those groups (visible only to end
        users holding at least one). Leave it out, or pass None, for unrestricted.
        An empty list is rejected.
        """
        body: Dict[str, Any] = {"fileBase64": file_base64, "fileName": file_name}
        if category is not None:
            body["category"] = category
        if collection_ids is not None:
            body["collectionIds"] = collection_ids
        if access_groups is not _UNSET:
            body["accessGroups"] = access_groups
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
        access_groups: Any = _UNSET,
    ) -> Dict[str, Any]:
        """Synchronous — pushes a URL or inline content, upserting by a
        deterministic source_id. Prefer jobs.create_url_job() for a deep
        crawl (this only fetches the one URL given, no link-following).

        Leave `access_groups` out to keep the label a re-pushed document already
        has (a re-sync never makes a restricted document public); pass None to make
        it unrestricted, or a list of groups to restrict it.
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
        if access_groups is not _UNSET:
            body["accessGroups"] = access_groups
        return cast(Dict[str, Any], self._http.post("/v1/documents/push", body))

    def set_access(self, id: str, access_groups: Optional[List[str]]) -> Dict[str, Any]:
        """Change who can see a document without re-embedding it. None makes it
        unrestricted; otherwise a list of groups. Applies to every chunk at once.
        Returns {"id", "access_groups", "chunks_updated"}."""
        return cast(Dict[str, Any], self._http.patch(f"/v1/documents/{quote(id)}", {"accessGroups": access_groups}))

    def list_flagged_chunks(self) -> List[FlaggedChunk]:
        """Read/resolve only — what actually flags a chunk (repeated human corrections on a support ticket or
        conversation) is product-internal logic with no SDK surface. This is the generic, tenant-wide half: any
        domain's content can end up flagged, regardless of what flagged it."""
        data = self._http.get("/v1/documents/flagged-chunks")
        return [FlaggedChunk._from_dict(c) for c in data["chunks"]]

    def get_flagged_chunk(self, id: str) -> FlaggedChunkDetail:
        """A flagged passage in full, with what the customer asked, what the assistant said and what a person said after.
        Raises a 404 `FLAGGED_CHUNK_NOT_FOUND` when it is not flagged."""
        data = self._http.get(f"/v1/documents/flagged-chunks/{quote(id)}")
        return FlaggedChunkDetail._from_dict(cast(Dict[str, Any], data))

    def draft_flagged_chunk_rewrite(self, id: str) -> ChunkRewriteDraft:
        """Checked edits that make the passage agree with what staff said. Numbers must come from a cited staff reply or the text
        replaced. Calls a model and is metered, so it is never retried. Nothing is saved: apply `revised_text` in the source
        document, then `resolve_flagged_chunk`. Raises 429 `QUOTA_EXCEEDED` or 502 `DRAFT_UNAVAILABLE`."""
        data = self._http.post_long_running(f"/v1/documents/flagged-chunks/{quote(id)}/draft-rewrite", {}, 120.0)
        return ChunkRewriteDraft._from_dict(cast(Dict[str, Any], data["draft"]))

    def resolve_flagged_chunk(self, id: str) -> None:
        """Clears the flag and resets the correction count to 0. Does not edit or delete the chunk's content —
        resolving is an acknowledgement, not a fix."""
        self._http.post(f"/v1/documents/flagged-chunks/{quote(id)}/resolve")
