from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, cast
from urllib.parse import quote, urlencode

from .._http import HttpClient

# Execution traces — read-only. Mirrors /v1/traces (see openapi.yaml), served by the same handlers as the
# dashboard's Trace Explorer, so a filter or field that works there works here. Secret API keys only: a trace
# holds prompts and responses, so a public embed token is refused (EMBED_TOKEN_NOT_ALLOWED). Comments,
# bookmarks and replay stay in the dashboard.


@dataclass(frozen=True)
class TraceSummary:
    """One row of `traces.list()`. Agent and workflow rows carry the same fields, with the request-only ones None."""

    kind: str  # "request" | "agent" | "workflow"
    # For a request, the `message_id` that run() returned.
    trace_id: str
    name: Optional[str]
    # The run's status for an agent or workflow trace; None for a request.
    status: Optional[str]
    # The agent or workflow run that made this call, when it was made as part of one.
    parent: Optional[Dict[str, Any]]
    session_id: Optional[str]
    request_id: Optional[str]
    user_id: Optional[str]
    intent: Optional[str]
    domain: Optional[str]
    model_used: Optional[str]
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    total_tokens: Optional[int]
    # Decimal string in USD, e.g. "0.002100".
    cost_usd: Optional[str]
    latency_ms: Optional[int]
    ttft_ms: Optional[int]
    flagged: bool
    flag_reason: Optional[str]
    pii_detected: bool
    issue_categories: List[str]
    capture_mode: str
    comment_count: int
    qa_score: Optional[float]
    qa_breakdown: Optional[Dict[str, Any]]
    timestamp: str

    @classmethod
    def _from_dict(cls, d: Dict[str, Any]) -> "TraceSummary":
        return cls(
            kind=d["kind"],
            trace_id=d["traceId"],
            name=d.get("name"),
            status=d.get("status"),
            parent=d.get("parent"),
            session_id=d.get("sessionId"),
            request_id=d.get("requestId"),
            user_id=d.get("userId"),
            intent=d.get("intent"),
            domain=d.get("domain"),
            model_used=d.get("modelUsed"),
            input_tokens=d.get("inputTokens"),
            output_tokens=d.get("outputTokens"),
            total_tokens=d.get("totalTokens"),
            cost_usd=d.get("costUsd"),
            latency_ms=d.get("latencyMs"),
            ttft_ms=d.get("ttftMs"),
            flagged=d["flagged"],
            flag_reason=d.get("flagReason"),
            pii_detected=d["piiDetected"],
            issue_categories=list(d.get("issueCategories") or []),
            capture_mode=d.get("captureMode", "full"),
            comment_count=d.get("commentCount", 0),
            qa_score=d.get("qaScore"),
            qa_breakdown=d.get("qaBreakdown"),
            timestamp=d["timestamp"],
        )


@dataclass(frozen=True)
class TracesPage:
    traces: List[TraceSummary]
    # {"total": int, "limit": int, "offset": int}
    pagination: Dict[str, int]
    # {"key": "time" | "latency" | "ttft" | "cost", "dir": "asc" | "desc"}
    sort: Dict[str, str]


@dataclass(frozen=True)
class Trace:
    """The full trace of one request (`traces.get`), or of an agent or workflow run (`traces.get_run`)."""

    trace_id: str
    session_id: str
    request_id: Optional[str]
    user_id: Optional[str]
    domain: Optional[str]
    # What this caller may see of request and response text: "full" | "restricted_by_role" | "not_stored".
    # Secret keys read with full access.
    content_access: str
    capture_mode: str
    intent: Optional[str]
    user_request: Optional[str]
    content: Optional[str]
    model_used: Optional[str]
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    total_tokens: Optional[int]
    cost_usd: Optional[str]
    latency_ms: Optional[int]
    ttft_ms: Optional[int]
    flagged: bool
    flag_reason: Optional[str]
    issues: List[Dict[str, Any]]
    pii_detected: bool
    from_cache: bool
    qa_score: Optional[float]
    timestamp: Optional[str]
    # "agent_run" | "workflow_run" for a run trace; None for a request.
    kind: Optional[str] = None
    # Every retrieved chunk with its source and similarity score. `snippet` is None when the key may not see content.
    retrieved_context: List[Dict[str, Any]] = field(default_factory=list)
    # What was searched and how: method, top-k, threshold, whether a boost or fallback fired.
    retrieval_meta: Optional[Dict[str, Any]] = None
    # Agent reasoning and tool-call steps, for an agent-mode call.
    agentic_steps: List[Dict[str, Any]] = field(default_factory=list)
    # The trace as a tree of steps with timing, as the Trace Explorer shows it.
    observations: List[Dict[str, Any]] = field(default_factory=list)
    billing: Optional[Dict[str, Any]] = None
    session: Optional[Dict[str, Any]] = None
    # The response exactly as returned by the API, for any field not modelled above.
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def _from_dict(cls, d: Dict[str, Any]) -> "Trace":
        return cls(
            kind=d.get("kind"),
            trace_id=d["traceId"],
            session_id=d.get("sessionId") or "",
            request_id=d.get("requestId"),
            user_id=d.get("userId"),
            domain=d.get("domain"),
            content_access=d.get("contentAccess", "full"),
            capture_mode=d.get("captureMode", "full"),
            intent=d.get("intent"),
            user_request=d.get("userRequest"),
            content=d.get("content"),
            model_used=d.get("modelUsed"),
            input_tokens=d.get("inputTokens"),
            output_tokens=d.get("outputTokens"),
            total_tokens=d.get("totalTokens"),
            cost_usd=d.get("costUsd"),
            latency_ms=d.get("latencyMs"),
            ttft_ms=d.get("ttftMs"),
            flagged=d["flagged"],
            flag_reason=d.get("flagReason"),
            issues=list(d.get("issues") or []),
            pii_detected=d.get("piiDetected", False),
            from_cache=d.get("fromCache", False),
            qa_score=d.get("qaScore"),
            timestamp=d.get("timestamp"),
            retrieved_context=list(d.get("retrievedContext") or []),
            retrieval_meta=d.get("retrievalMeta"),
            agentic_steps=list(d.get("agenticSteps") or []),
            observations=list(d.get("observations") or []),
            billing=d.get("billing"),
            session=d.get("session"),
            raw=d,
        )


@dataclass(frozen=True)
class TraceStats:
    """Totals for every trace matching the filters (not just a page). Defaults to the last 30 days."""

    window: Dict[str, str]
    total: int
    flagged: int
    pii_detected: int
    from_cache: int
    input_tokens: int
    output_tokens: int
    cost_usd: str
    # {"avg", "p50", "p95", "p99"}, each Optional[int]
    latency_ms: Dict[str, Optional[int]]
    # {"p50", "p95"}
    ttft_ms: Dict[str, Optional[int]]
    # {"avg": Optional[int], "scored": int}
    qa_score: Dict[str, Any]
    # {"safety", "validation", "grounding", "other"} -> count
    issues_by_category: Dict[str, int]
    by_intent: List[Dict[str, Any]]
    # Present with scope="traces".
    by_kind: Optional[Dict[str, int]] = None
    failed_runs: Optional[int] = None

    @classmethod
    def _from_dict(cls, d: Dict[str, Any]) -> "TraceStats":
        return cls(
            window=d["window"],
            total=d["total"],
            flagged=d["flagged"],
            pii_detected=d.get("piiDetected", 0),
            from_cache=d.get("fromCache", 0),
            input_tokens=d.get("inputTokens", 0),
            output_tokens=d.get("outputTokens", 0),
            cost_usd=d["costUsd"],
            latency_ms=d["latencyMs"],
            ttft_ms=d["ttftMs"],
            qa_score=d["qaScore"],
            issues_by_category=d["issuesByCategory"],
            by_intent=list(d.get("byIntent") or []),
            by_kind=d.get("byKind"),
            failed_runs=d.get("failedRuns"),
        )


@dataclass(frozen=True)
class TraceCaseDraft:
    """A redacted draft evaluation case from a request trace (`traces.case_draft`). Nothing is saved: once a person has written
    the expected output, create the case with `evaluations`. A request trace keeps the user's message and the intent's answer,
    not the intent's structured input, so `input` is empty and `input_available` is False. `observed_output` is context for the
    person, never a suggested expected output."""

    trace_id: str
    domain_key: str
    intent_key: str
    # What the user said, with personal details removed.
    message: Optional[str]
    input: Dict[str, Any]
    input_available: bool
    observed_output: Optional[str]
    expected_output: None
    notes: str
    already_redacted: bool
    # Datasets of suites that test this intent: [{"id", "name", "suites": [{"id", "name"}]}].
    datasets: List[Dict[str, Any]]

    @classmethod
    def _from_dict(cls, d: Dict[str, Any]) -> "TraceCaseDraft":
        return cls(
            trace_id=d["trace_id"], domain_key=d["domain_key"], intent_key=d["intent_key"], message=d.get("message"),
            input=d.get("input") or {}, input_available=bool(d.get("input_available", False)), observed_output=d.get("observed_output"),
            expected_output=None, notes=d.get("notes", ""), already_redacted=bool(d.get("already_redacted", False)), datasets=d.get("datasets") or [],
        )


def _query(**params: Any) -> str:
    pairs: Dict[str, str] = {}
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, bool):
            pairs[key] = "true" if value else "false"
        elif isinstance(value, datetime):
            pairs[key] = value.isoformat()
        else:
            pairs[key] = str(value)
    return f"?{urlencode(pairs)}" if pairs else ""


class TracesResource:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def list(
        self,
        *,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        domain: Optional[str] = None,
        intent: Optional[str] = None,
        flagged: Optional[bool] = None,
        issue: Optional[str] = None,
        from_: Optional[Any] = None,
        to: Optional[Any] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        model: Optional[str] = None,
        min_latency_ms: Optional[int] = None,
        from_cache: Optional[bool] = None,
        capture: Optional[str] = None,
        q: Optional[str] = None,
        sort: Optional[str] = None,
        order: Optional[str] = None,
        scope: Optional[str] = None,
        kind: Optional[str] = None,
        nested: Optional[bool] = None,
    ) -> TracesPage:
        """A page of traces, newest first by default, with the pagination and sort that were applied.

        `issue` is one of "safety", "validation", "grounding", "other". `from_` and `to` take a datetime or an
        ISO 8601 string. `sort` is "time", "latency", "ttft" or "cost". `scope="traces"` returns one row per
        request, agent run or workflow run; narrow with `kind` and add `nested=True` to list what runs started.
        """
        qs = _query(
            limit=limit, offset=offset, domain=domain, intent=intent, flagged=flagged, issue=issue,
            **{"from": from_}, to=to, userId=user_id, sessionId=session_id, model=model,
            minLatencyMs=min_latency_ms, fromCache=from_cache, capture=capture, q=q, sort=sort, order=order,
            scope=scope, kind=kind, nested=nested,
        )
        body = self._http.get_envelope(f"/v1/traces{qs}")
        return TracesPage(
            traces=[TraceSummary._from_dict(t) for t in body["data"]["traces"]],
            pagination=body["pagination"],
            sort=body["sort"],
        )

    def get(self, trace_id: str) -> Trace:
        """The full trace for one request. The id is the `message_id` that run() returned."""
        data = self._http.get(f"/v1/traces/{quote(trace_id, safe='')}")
        return Trace._from_dict(cast(Dict[str, Any], data["trace"]))

    def case_draft(self, trace_id: str) -> TraceCaseDraft:
        """A redacted draft evaluation case built from a request trace, plus the datasets that test the same intent.
        Raises a 409 `TRACE_CONTENT_NOT_STORED` when the workspace keeps no trace text and a 422 `TRACE_NOT_EVALUABLE`
        for a built-in intent."""
        data = self._http.get(f"/v1/traces/{quote(trace_id, safe='')}/eval-case-draft")
        return TraceCaseDraft._from_dict(cast(Dict[str, Any], data["draft"]))

    def failure_clusters(self, *, days: Optional[int] = None) -> Dict[str, Any]:
        """Runs and requests that stopped for the same reason, grouped by counting. No model is called and nothing is billed.
        `days` is 1 to 30 (default 7). Each cluster says what failed in `resource_kind` (agent, workflow or intent),
        `resource_id` and `resource_name`, and has a `kind`: `run`, `tool` (a tool call in an agent run), `step` (a step
        in a workflow run) or `request` (a call to an intent). It also has `runs`, `runs_ended_failed` (for a tool or step
        cluster often far below `runs`, because the agent or workflow recovers), a `cause` that names the fixed rule that
        fired, and the version and release `changes` that lined up in time: leads, never proof of cause. `by_source` splits
        the totals into agent, workflow and request. Status is reliability, not quality."""
        suffix = f"?{urlencode({'days': days})}" if days is not None else ""
        return cast(Dict[str, Any], self._http.get(f"/v1/traces/failure-clusters{suffix}"))

    def get_run(self, kind: str, run_id: str) -> Trace:
        """The trace of an agent or workflow run (`kind` is "agent" or "workflow"): its steps as nested
        observations, with the model and tool calls each made."""
        data = self._http.get(f"/v1/traces/runs/{quote(kind, safe='')}/{quote(run_id, safe='')}")
        return Trace._from_dict(cast(Dict[str, Any], data["trace"]))

    def stats(
        self,
        *,
        domain: Optional[str] = None,
        intent: Optional[str] = None,
        flagged: Optional[bool] = None,
        issue: Optional[str] = None,
        from_: Optional[Any] = None,
        to: Optional[Any] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        model: Optional[str] = None,
        min_latency_ms: Optional[int] = None,
        from_cache: Optional[bool] = None,
        capture: Optional[str] = None,
        q: Optional[str] = None,
        scope: Optional[str] = None,
        kind: Optional[str] = None,
        nested: Optional[bool] = None,
    ) -> TraceStats:
        """Totals for every trace matching the filters: counts, tokens, cost, latency percentiles, quality
        score, issues and a per-intent breakdown. Defaults to the last 30 days."""
        qs = _query(
            domain=domain, intent=intent, flagged=flagged, issue=issue, **{"from": from_}, to=to,
            userId=user_id, sessionId=session_id, model=model, minLatencyMs=min_latency_ms,
            fromCache=from_cache, capture=capture, q=q, scope=scope, kind=kind, nested=nested,
        )
        return TraceStats._from_dict(cast(Dict[str, Any], self._http.get(f"/v1/traces/stats{qs}")))
