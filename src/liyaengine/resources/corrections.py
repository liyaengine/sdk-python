from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, cast
from urllib.parse import quote

from .._http import HttpClient

# Corrections: your application telling LiyaEngine that an answer was wrong and what it should have said. Mirrors
# POST /v1/corrections (see openapi.yaml).
#
# For a workspace that serves traffic through the API, with no support inbox or widget handover, this is how a passage of
# the knowledge base gets flagged: the top two passages the answer was built from are counted against, and three corrections flag a
# passage for review under Self-healing, Findings, Passages. Call it from your backend when a user marks an answer wrong or
# edits it. A runtime-scoped key may call it.


@dataclass(frozen=True)
class ReportedPassage:
    document_id: Optional[str]
    file_name: Optional[str]
    # Where the trace ranked this passage for the answer, 1 being the best. None when it was not recorded.
    rank: Optional[int]
    # "passage": tied to one stored passage. "document_only": the trace named the document but no single passage could be
    # tied to, so nothing was counted. "lower_ranked": below the top two passages, so not looked at and not counted.
    attribution: str
    # True when this correction was counted against the passage. False for a document-only or lower-ranked passage, or when
    # this conversation had already counted against it.
    counted: bool
    # True when the passage is flagged for review now.
    flagged: bool


@dataclass(frozen=True)
class CorrectionResult:
    correction_id: str
    # True when this answer had already been reported: the correction text was updated and nothing was counted again.
    already_recorded: bool
    passages: List[ReportedPassage]
    # Why nothing was counted, when that is the case.
    note: Optional[str]

    @classmethod
    def _from_dict(cls, d: Dict[str, Any]) -> "CorrectionResult":
        return cls(
            correction_id=d["correction_id"], already_recorded=bool(d.get("already_recorded")), note=d.get("note"),
            passages=[
                ReportedPassage(
                    document_id=p.get("document_id"), file_name=p.get("file_name"), rank=p.get("rank"), attribution=p["attribution"],
                    counted=bool(p.get("counted")), flagged=bool(p.get("flagged")),
                )
                for p in (d.get("passages") or [])
            ],
        )


class CorrectionsResource:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def report(
        self,
        *,
        correct_answer: str,
        message_id: Optional[str] = None,
        run_id: Optional[str] = None,
        note: Optional[str] = None,
        end_user_id: Optional[str] = None,
    ) -> CorrectionResult:
        """Report that an answer was wrong. Name the answer with exactly one of `message_id` (the one an intent call
        returned, `data.message_id`) or `run_id` (the one an agent run returned, `data.run_id`; the run must have
        finished, and the passages of its last knowledge search are counted against). `correct_answer` is what it should
        have said (at most 4000 characters, personal details removed). Reporting the same answer again updates it and
        counts nothing a second time, and a conversation counts once against a passage however many of its answers are
        reported, so retrying is safe. Raises a 404 `MESSAGE_NOT_FOUND` or `RUN_NOT_FOUND` for an id that is not in this
        workspace, a 409 `RUN_NOT_FINISHED` for a run still going, and a 400 `INVALID_CORRECTION` for a missing or
        oversized field."""
        if (message_id is None) == (run_id is None):
            raise ValueError("Pass exactly one of message_id or run_id.")
        body: Dict[str, Any] = {"correct_answer": correct_answer}
        if message_id is not None:
            body["message_id"] = message_id
        if run_id is not None:
            body["run_id"] = run_id
        if note is not None:
            body["note"] = note
        if end_user_id is not None:
            body["end_user_id"] = end_user_id
        return CorrectionResult._from_dict(cast(Dict[str, Any], self._http.post("/v1/corrections", body)))

    def delete(self, correction_id: str) -> Dict[str, Any]:
        """Erase what a correction says (question, reply, correct answer, note, end user id). Needs a full-access key. It does
        NOT lower any passage's count, and an answer whose correction was deleted cannot be reported again (409
        `CORRECTION_DELETED`). Deleting twice is safe. Returns `{"deleted": True, "already_deleted": bool}`."""
        return cast(Dict[str, Any], self._http.delete(f"/v1/corrections/{quote(correction_id, safe='')}"))
