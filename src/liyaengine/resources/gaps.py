from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, cast
from urllib.parse import urlencode

from .._http import HttpClient

# Knowledge gaps: the questions the assistant could not answer confidently. Mirrors /v1/knowledge/gaps (see openapi.yaml),
# served by the same handlers as the dashboard's Gap queue. Secret API keys only.
#
# The loop this supports: list() the gaps, draft_article() from a topic, have a person read the draft beside its sources,
# publish it with documents.push(), then check_coverage() to see whether the questions are now answered before you mark
# anything resolved.

# A draft is a model call and a coverage check runs a retrieval per question, so both wait longer than the default and are
# never retried.
_LONG_S = 120.0


@dataclass(frozen=True)
class GapArticleDraft:
    """A draft help article from open gaps. Nothing is saved or published. Every statement cites at least one source, and every
    number in it appears in a cited source."""

    title: str
    # [{"text": str, "sources": ["S1"]}]
    statements: List[Dict[str, Any]]
    # The statements as paragraphs with no citations, ready to edit and publish.
    body_markdown: str
    # What the questions asked that no source answers. A person supplies these.
    missing: List[str]
    # [{"id", "kind": "staff_reply" | "document", "label", "excerpt"}]
    sources: List[Dict[str, Any]]
    questions: List[str]
    gap_ids: List[str]
    # Statements the model wrote that were dropped because no source supports them.
    dropped_unsupported: int
    # "NO_SOURCES" when there was nothing on record to write from: no model was called.
    reason: Optional[str]
    # {"tokens", "cost", "served_by"}, or None when no model was called.
    usage: Optional[Dict[str, Any]]

    @classmethod
    def _from_dict(cls, d: Dict[str, Any]) -> "GapArticleDraft":
        return cls(
            title=d["title"], statements=d.get("statements") or [], body_markdown=d.get("body_markdown", ""), missing=d.get("missing") or [],
            sources=d.get("sources") or [], questions=d.get("questions") or [], gap_ids=d.get("gap_ids") or [],
            dropped_unsupported=int(d.get("dropped_unsupported", 0)), reason=d.get("reason"), usage=d.get("usage"),
        )


@dataclass(frozen=True)
class GapCoverageResult:
    gap_id: str
    query: str
    # False when retrieval failed for this question: it is neither answered nor unanswered.
    checked: bool
    answered: bool
    top_similarity: Optional[float]
    top_source: Optional[str]


@dataclass(frozen=True)
class GapCoverage:
    """Whether each question now finds an answer, using the assistant's own retrieval and relevance bar (`min_similarity`).
    It does not read the passage, so it cannot tell one that answers from one that is only about the topic."""

    checked: int
    answered: int
    not_checked: int
    min_similarity: float
    results: List[GapCoverageResult]

    @classmethod
    def _from_dict(cls, d: Dict[str, Any]) -> "GapCoverage":
        return cls(
            checked=d["checked"], answered=d["answered"], not_checked=d["not_checked"], min_similarity=d["min_similarity"],
            results=[
                GapCoverageResult(gap_id=r["gap_id"], query=r["query"], checked=r["checked"], answered=r["answered"],
                                  top_similarity=r.get("top_similarity"), top_source=r.get("top_source"))
                for r in d["results"]
            ],
        )


class GapsResource:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def list(self, *, days: Optional[int] = None, resolved: Optional[bool] = None) -> Dict[str, Any]:
        """Open gaps (or closed, with resolved=True): {"total", "by_intent": [{"intent", "count", "queries"}], "items": [...]}.
        `days` is 7, 30 (default) or 90."""
        pairs: Dict[str, str] = {}
        if days is not None:
            pairs["days"] = str(days)
        if resolved is not None:
            pairs["resolved"] = "true" if resolved else "false"
        qs = f"?{urlencode(pairs)}" if pairs else ""
        return cast(Dict[str, Any], self._http.get(f"/v1/knowledge/gaps{qs}"))

    _UNSET: Any = object()

    def draft_article(self, *, gap_ids: Optional[List[str]] = None, intent: Any = _UNSET) -> GapArticleDraft:
        """Draft a help article from open gaps, written only from replies your own staff wrote in the same conversations and the
        nearest documents retrieval found. Statements with no real source, or a number no source states, are dropped. Calls a
        model and is metered; never retried, so a failure never bills twice. A person should read the draft beside `sources`
        before publishing: a statement can cite a real source and still misread it. Give `gap_ids` (up to 25) or `intent` (a
        topic; None for unclassified gaps). Raises 404 `GAPS_NOT_FOUND`, 429 `QUOTA_EXCEEDED` or 502 `DRAFT_UNAVAILABLE`."""
        body: Dict[str, Any] = {}
        if gap_ids is not None:
            body["gap_ids"] = gap_ids
        if intent is not self._UNSET:
            body["intent"] = intent
        data = self._http.post_long_running("/v1/knowledge/gaps/draft-article", body, _LONG_S)
        return GapArticleDraft._from_dict(cast(Dict[str, Any], data["draft"]))

    def check_coverage(self, gap_ids: List[str]) -> GapCoverage:
        """Whether each question now finds an answer. Run it after publishing, so a gap is closed because the knowledge base
        answers it."""
        data = self._http.post_long_running("/v1/knowledge/gaps/check-coverage", {"gap_ids": gap_ids}, _LONG_S)
        return GapCoverage._from_dict(cast(Dict[str, Any], data["coverage"]))
