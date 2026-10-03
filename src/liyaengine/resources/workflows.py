from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Literal, Optional, TypedDict, Union, cast
from urllib.parse import quote, urlencode

from .._http import HttpClient


class WorkflowStepTrace(TypedDict, total=False):
    """One traced step — a webhook/action call, an ai_intent/ai_agent turn, a condition branch, etc."""

    stepId: str
    stepType: str
    name: Optional[str]
    actionId: Optional[str]
    actionName: Optional[str]
    success: bool
    response: Any
    error: str
    skipped: bool
    durationMs: int


class WorkflowRunStepEvent(TypedDict):
    type: Literal["step"]
    step: WorkflowStepTrace


class WorkflowRunDoneEvent(TypedDict, total=False):
    type: Literal["done"]
    run_id: str
    conversation_id: str
    status: Literal["completed", "needs_input", "failed", "awaiting_approval", "rejected"]
    trace: List[Any]
    missing_parameter: Dict[str, Any]
    approval_id: str


class WorkflowRunErrorEvent(TypedDict):
    type: Literal["error"]
    code: str
    message: str


WorkflowRunStreamEvent = Union[WorkflowRunStepEvent, WorkflowRunDoneEvent, WorkflowRunErrorEvent]


@dataclass(frozen=True)
class Workflow:
    id: str
    tenant_id: str
    name: str
    workflow_key: str
    description: Optional[str]
    is_active: bool
    status: str
    trigger_type: str
    trigger_config: Optional[Dict[str, Any]]
    created_at: str
    updated_at: str
    steps: List[Dict[str, Any]]
    #: Schedule/event dispatch state — None unless active with a valid schedule or event trigger.
    schedule_next_run_at: Optional[str] = None
    schedule_last_run_at: Optional[str] = None
    event_type: Optional[str] = None

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "Workflow":
        return cls(
            id=data["id"],
            tenant_id=data["tenant_id"],
            name=data["name"],
            workflow_key=data["workflow_key"],
            description=data.get("description"),
            is_active=data["is_active"],
            status=data["status"],
            trigger_type=data["trigger_type"],
            trigger_config=data.get("trigger_config"),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            steps=data.get("steps", []),
            schedule_next_run_at=data.get("schedule_next_run_at"),
            schedule_last_run_at=data.get("schedule_last_run_at"),
            event_type=data.get("event_type"),
        )


def _query(**params: Any) -> str:
    pairs = {k: v for k, v in params.items() if v is not None}
    return f"?{urlencode(pairs)}" if pairs else ""


class WorkflowApprovalsResource:
    """Human approval steps. A run that reaches an approval step pauses with
    status "awaiting_approval"; deciding resumes it down the approved or
    rejected branch. Use this to put approvals in Slack, Teams, email or your
    own app — pass decided_by so the audit trail names the person.
    """

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def list(self, *, status: Optional[str] = None, workflow_id: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        qs = _query(status=status, workflow_id=workflow_id, limit=limit)
        return cast(List[Dict[str, Any]], self._http.get(f"/v1/workflows/approvals{qs}"))

    def get(self, approval_id: str) -> Dict[str, Any]:
        return cast(Dict[str, Any], self._http.get(f"/v1/workflows/approvals/{quote(approval_id)}"))

    def decide(
        self, approval_id: str, *, decision: Literal["approve", "reject"], note: Optional[str] = None, decided_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Returns {"approval": ..., "run": {"run_id", "status", ...}}. The run can be
        "awaiting_approval" again if the workflow has a second approval step.
        Raises APPROVAL_ALREADY_DECIDED (409) if someone else decided first."""
        body: Dict[str, Any] = {"decision": decision}
        if note is not None:
            body["note"] = note
        if decided_by is not None:
            body["decided_by"] = decided_by
        return cast(Dict[str, Any], self._http.post(f"/v1/workflows/approvals/{quote(approval_id)}/decision", body))


class WorkflowsResource:
    """Multi-step graphs of intents/agents/actions/conditions. Mirrors the
    full /v1/workflows surface (see openapi.yaml): CRUD + toggle/deploy/
    webhook-secret-rotate, plus run/run-history. `workflow_id_or_key` in
    every method below accepts either the database id or the human-readable
    workflow_key.
    """

    def __init__(self, http: HttpClient) -> None:
        self._http = http
        self.approvals = WorkflowApprovalsResource(http)

    def trigger_catalog(self) -> Dict[str, Any]:
        """Event types (with allowed filters) and schedule rules a trigger step can use.

        Schedule: trigger step config {"trigger_subtype": "schedule", "cron", "timezone", "input"}.
        Event:    {"trigger_subtype": "event", "event_type", "filter"}.
        """
        return cast(Dict[str, Any], self._http.get("/v1/workflows/trigger-catalog"))

    def list(self) -> List[Workflow]:
        data = self._http.get("/v1/workflows")
        return [Workflow._from_dict(w) for w in cast(List[Dict[str, Any]], data)]

    def get(self, workflow_id_or_key: str) -> Workflow:
        data = self._http.get(f"/v1/workflows/{quote(workflow_id_or_key)}")
        return Workflow._from_dict(data)

    def create(
        self,
        *,
        name: str,
        description: Optional[str] = None,
        steps: Optional[List[Dict[str, Any]]] = None,
    ) -> Workflow:
        body: Dict[str, Any] = {"name": name}
        if description is not None:
            body["description"] = description
        if steps is not None:
            body["steps"] = steps

        data = self._http.post("/v1/workflows", body)
        return Workflow._from_dict(data["workflow"])

    def update(
        self,
        workflow_id_or_key: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        workflow_key: Optional[str] = None,
        steps: Optional[List[Dict[str, Any]]] = None,
    ) -> Workflow:
        """`steps` is upsert-by-id: an existing step id present in this list is
        updated in place, a new one is created, and any existing step id
        omitted from this list is deleted.
        """
        body: Dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        if workflow_key is not None:
            body["workflow_key"] = workflow_key
        if steps is not None:
            body["steps"] = steps

        data = self._http.patch(f"/v1/workflows/{quote(workflow_id_or_key)}", body)
        return Workflow._from_dict(data["workflow"])

    def toggle(self, workflow_id_or_key: str) -> Workflow:
        """Flips is_active on an already-deployed workflow. Blocked on a draft
        (raises LiyaEngineAPIError(code='DEPLOY_REQUIRED')) — deploy() it first.
        """
        data = self._http.patch(f"/v1/workflows/{quote(workflow_id_or_key)}/toggle")
        return Workflow._from_dict(data["workflow"])

    def deploy(self, workflow_id_or_key: str) -> Dict[str, Any]:
        """The draft->published transition. On first deploy of a
        webhook-triggered workflow, also mints the webhook infrastructure and
        returns the secret exactly once as `webhook_secret` — capture it
        immediately, it is never retrievable again. Returns
        {"workflow": Workflow-shaped dict, "webhook_url"?: str, "webhook_secret"?: str}.
        """
        return cast(Dict[str, Any], self._http.post(f"/v1/workflows/{quote(workflow_id_or_key)}/deploy"))

    def rotate_webhook_secret(
        self, workflow_id_or_key: str, *, grace_period_seconds: Optional[int] = None
    ) -> Dict[str, Any]:
        """Only valid for a webhook-triggered, already-deployed workflow. The
        previous secret stays valid for `grace_period_seconds` (default 300,
        max 3600) so external senders can roll over without downtime; pass 0
        for an immediate hard cutover. The new secret is returned exactly once.
        """
        body = {"grace_period_seconds": grace_period_seconds} if grace_period_seconds is not None else None
        return cast(Dict[str, Any], self._http.post(f"/v1/workflows/{quote(workflow_id_or_key)}/webhook-secret/rotate", body))

    def delete(self, workflow_id_or_key: str) -> None:
        """A hard delete — unlike Collections and Agents, there is no soft-delete/inactive state for a removed workflow."""
        self._http.delete(f"/v1/workflows/{quote(workflow_id_or_key)}")

    def run(
        self, workflow_id_or_key: str, *, input: Optional[Dict[str, Any]] = None, conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {}
        if input is not None:
            body["input"] = input
        if conversation_id is not None:
            body["conversation_id"] = conversation_id
        return cast(Dict[str, Any], self._http.post(f"/v1/workflows/{quote(workflow_id_or_key)}/run", body))

    def run_stream(
        self, workflow_id_or_key: str, *, input: Optional[Dict[str, Any]] = None, conversation_id: Optional[str] = None
    ) -> Iterator[WorkflowRunStreamEvent]:
        """Same input as run() — real-time step progress instead of one awaited result.

        Step-level, not token-level: no step type in a Workflow streams
        tokens, so there's no delta to yield. A "step" event fires as each
        one is traced, and a single "done" event carries the complete
        trace.
        """
        body: Dict[str, Any] = {}
        if input is not None:
            body["input"] = input
        if conversation_id is not None:
            body["conversation_id"] = conversation_id
        for frame in self._http.stream(f"/v1/workflows/{quote(workflow_id_or_key)}/run/stream", body):
            yield cast(WorkflowRunStreamEvent, frame)

    def list_runs(
        self, workflow_id_or_key: str, *, page: Optional[int] = None, page_size: Optional[int] = None, status: Optional[str] = None,
    ) -> Dict[str, Any]:
        qs = _query(page=page, pageSize=page_size, status=status)
        return cast(Dict[str, Any], self._http.get(f"/v1/workflows/{quote(workflow_id_or_key)}/runs{qs}"))

    def get_run(self, workflow_id_or_key: str, run_id: str) -> Dict[str, Any]:
        data = self._http.get(f"/v1/workflows/{quote(workflow_id_or_key)}/runs/{quote(run_id)}")
        return cast(Dict[str, Any], data["run"])
