"""Types for POST /v1/run and POST /v1/run/stream — the primary way to
invoke LiyaEngine directly (no Domain/Agent/Workflow object to create
first). Methods live on IntentsResource (client.intents.run/.stream),
pairing with its list_all() catalog: list what you can run, then run it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, TypedDict, Union


class RunStreamSource(TypedDict, total=False):
    doc: str
    section: str
    relevance: float
    url: str


class RunSourcesEvent(TypedDict):
    """Custom-domain intents only: the retrieved evidence, sent once before the first token."""
    type: Literal["sources"]
    sources: List[RunStreamSource]


class RunTokenEvent(TypedDict):
    type: Literal["token"]
    delta: str


class _RunDoneRequired(TypedDict):
    type: Literal["done"]
    session_id: str
    latency_ms: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    served_by: Literal["platform", "byok"]


class RunDoneEvent(_RunDoneRequired, total=False):
    """The optional keys below are set for custom-domain intents only.

    stream_mode is "live" when tokens arrived as generated, or "buffered"
    when the whole answer arrived as one token event (stream_buffer_reason
    says why, e.g. a grounding block policy). blocked is set when that
    policy replaced the answer with its fallback message.
    """
    request_id: str
    status: Literal["success", "partial", "error"]
    model: str
    stream_mode: Literal["live", "buffered"]
    stream_buffer_reason: str
    structured: Dict[str, Any]
    confidence: float
    blocked: Dict[str, Any]
    escalation: Dict[str, Any]


class _RunErrorRequired(TypedDict):
    type: Literal["error"]
    message: str


class RunErrorEvent(_RunErrorRequired, total=False):
    code: str


RunStreamEvent = Union[RunSourcesEvent, RunTokenEvent, RunDoneEvent, RunErrorEvent]


@dataclass(frozen=True)
class RunIntentResult:
    """`data`'s shape depends on `domain`: for the 'chat' domain it's
    {response, session, execution}; for every other domain (built-in
    non-chat, or a custom domain_key) it's {output, session_id, message_id}.

    `metadata`/`usage` are absent in exactly one narrow case: a chat session
    that has exhausted its per-session token budget short-circuits to a
    canned escalation message (still success, still chat-shaped `data`)
    with no metadata/usage siblings at all — a real, pre-existing envelope
    inconsistency on this endpoint, not an SDK gap.
    """

    data: Dict[str, Any]
    metadata: Optional[Dict[str, Any]]
    usage: Optional[Dict[str, Any]]

    @classmethod
    def _from_dict(cls, payload: Dict[str, Any]) -> "RunIntentResult":
        return cls(data=payload["data"], metadata=payload.get("metadata"), usage=payload.get("usage"))


def _translate_run_input(
    *,
    intent: str,
    domain: Optional[str],
    pack: Optional[str],
    input: Optional[Dict[str, Any]],
    message: Optional[str],
    session_id: Optional[str],
    retrieval: Optional[Dict[str, Any]],
    guardrails: Optional[Dict[str, Any]],
    metadata: Optional[Dict[str, Any]],
    preferences: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    body: Dict[str, Any] = {"intent": intent}
    optional = {
        "pack": pack, "domain": domain, "input": input, "message": message,
        "session_id": session_id, "retrieval": retrieval, "guardrails": guardrails,
        "metadata": metadata, "preferences": preferences,
    }
    body.update({k: v for k, v in optional.items() if v is not None})
    return body
