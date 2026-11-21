from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Literal, Optional, TypedDict, Union, cast
from urllib.parse import quote, urlencode

from .._http import HttpClient


class AgentStep(TypedDict, total=False):
    """One orchestration step (@liyaengine/core's AgentOrchestrator) — an llm_call turn or a tool_execution."""

    step_number: int
    type: Literal["llm_call", "tool_execution"]
    model: str
    tool_name: str
    tool_input: Any
    tool_output: Any
    tool_success: bool
    input_tokens: int
    output_tokens: int
    cost: float
    served_by: Literal["platform", "byok"]
    latency_ms: int
    timestamp: str
    error: str
    error_code: str


class AgentRunStepEvent(TypedDict):
    type: Literal["step"]
    step: AgentStep


class AgentRunDoneEvent(TypedDict):
    type: Literal["done"]
    run_id: str
    session_id: str
    history_truncated: bool
    status: str
    output: str
    steps: int
    total_cost: float
    total_latency_ms: Optional[int]


class AgentRunErrorEvent(TypedDict):
    type: Literal["error"]
    code: str
    message: str


AgentRunStreamEvent = Union[AgentRunStepEvent, AgentRunDoneEvent, AgentRunErrorEvent]


@dataclass(frozen=True)
class Agent:
    id: str
    tenant_id: str
    agent_key: str
    name: str
    goal: str
    status: str
    description: Optional[str]
    system_instructions: Optional[str]
    model: Optional[str]
    temperature: Optional[float]
    intent_ids: List[str]
    workflow_ids: List[str]
    action_ids: List[str]
    knowledge_domain_keys: List[str]
    tools_config: Optional[Dict[str, Any]]
    memory_config: Optional[Dict[str, Any]]
    behavior_config: Optional[Dict[str, Any]]
    guardrail_policy_id: Optional[str]
    created_at: str
    updated_at: str
    effective_runtime_config: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "Agent":
        return cls(
            id=data["id"],
            tenant_id=data["tenant_id"],
            agent_key=data["agent_key"],
            name=data["name"],
            goal=data["goal"],
            status=data["status"],
            description=data.get("description"),
            system_instructions=data.get("system_instructions"),
            model=data.get("model"),
            temperature=data.get("temperature"),
            intent_ids=data.get("intent_ids", []),
            workflow_ids=data.get("workflow_ids", []),
            action_ids=data.get("action_ids", []),
            knowledge_domain_keys=data.get("knowledge_domain_keys", []),
            tools_config=data.get("tools_config"),
            memory_config=data.get("memory_config"),
            behavior_config=data.get("behavior_config"),
            guardrail_policy_id=data.get("guardrail_policy_id"),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            effective_runtime_config=data.get("effective_runtime_config", {}),
        )


def _query(**params: Any) -> str:
    pairs = {k: v for k, v in params.items() if v is not None}
    return f"?{urlencode(pairs)}" if pairs else ""


class AgentsResource:
    """Standalone Agents — composes Intents/Workflows/Tools/Knowledge as
    capabilities. Mirrors the full /v1/agents surface (see openapi.yaml):
    CRUD + deploy, plus run/run-history/sessions/transcript.
    """

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def list(self) -> List[Dict[str, Any]]:
        """Flat catalog (agent_key, endpoint, etc.) — not full Agent objects. Use get() for full config."""
        data = self._http.get("/v1/agents")
        return cast(List[Dict[str, Any]], data["agents"])

    def regressions(self, *, days: Optional[int] = None) -> Dict[str, Any]:
        """Agents whose live version fails clearly more often than the version before it, counted from runs. No model is
        called and nothing is billed. Failure means the run stopped (a limit, an error, a block), not that an answer was
        wrong. A gap is a lead, never proof. Nothing is applied: each item's `restore` names the existing restore call, which
        stages the older version as the draft, and `changes` lists everything rolling back would undo. `days` is 7 to 90 (default 30)."""
        suffix = f"?{urlencode({'days': days})}" if days is not None else ""
        return cast(Dict[str, Any], self._http.get(f"/v1/agents/regressions{suffix}"))

    def stage_regression(self, proposal_id: str) -> Dict[str, Any]:
        """Stage a roll-back proposal: the existing restore, so on a live agent the earlier version becomes the draft and
        nothing goes live until the agent is deployed. Replaces an existing draft. Calls no model. Raises a 409
        `PROPOSAL_NOT_OPEN` when the proposal is no longer open. `recorded` is False if the restore worked but the decision
        could not be saved."""
        return cast(Dict[str, Any], self._http.post(f"/v1/agents/regressions/{quote(proposal_id, safe='')}/stage", {}))

    def dismiss_regression(self, proposal_id: str, *, reason: Optional[str] = None) -> Dict[str, Any]:
        """Dismiss a roll-back proposal. It stays hidden while the two versions are unchanged. `reason` is optional, at most
        500 characters. Changes no agent."""
        body: Dict[str, Any] = {} if reason is None else {"reason": reason}
        return cast(Dict[str, Any], self._http.post(f"/v1/agents/regressions/{quote(proposal_id, safe='')}/dismiss", body))

    def regression_decisions(self, *, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Roll-back proposals for agents and workflows that were staged or dismissed, newest first (`resource_type` says which). A staged one carries an `outcome` worked out from
        runs (`not_deployed`, `measuring`, or `measured` after 20 runs). `limit` is 1 to 200 (default 50)."""
        suffix = f"?{urlencode({'limit': limit})}" if limit is not None else ""
        data = cast(Dict[str, Any], self._http.get(f"/v1/agents/regressions/decided{suffix}"))
        return cast(List[Dict[str, Any]], data["decisions"])

    def snooze_regression(self, proposal_id: str, *, days: int, reason: Optional[str] = None) -> Dict[str, Any]:
        """Snooze a roll-back proposal for 7, 14 or 30 days. It comes back after that if it still qualifies. Changes nothing
        else. Returns `decision_id` and `snoozed_until`."""
        body: Dict[str, Any] = {"days": days}
        if reason is not None:
            body["reason"] = reason
        return cast(Dict[str, Any], self._http.post(f"/v1/agents/regressions/{quote(proposal_id, safe='')}/snooze", body))

    def limit_proposals(self, *, days: Optional[int] = None) -> Dict[str, Any]:
        """Agents whose live version keeps stopping at its step or tool-call limit, counted from runs. No model is called and
        nothing is billed. A proposal raises the limit by half. An agent whose stopped runs mostly ended in a loop is not
        proposed (more room only lets it loop longer): it is in `not_proposed` with the reason, as is one already at the
        highest limit. Timeouts and cost limits are never proposed. `days` is 7 to 90 (default 30)."""
        suffix = f"?{urlencode({'days': days})}" if days is not None else ""
        return cast(Dict[str, Any], self._http.get(f"/v1/agents/limit-proposals{suffix}"))

    def stage_limit_proposal(self, proposal_id: str) -> Dict[str, Any]:
        """Stage a limit proposal: the raised limit goes into the agent's draft (added to one that exists), and nothing goes
        live until the agent is deployed. Calls no model. Raises a 409 `PROPOSAL_NOT_OPEN` when it is no longer open."""
        return cast(Dict[str, Any], self._http.post(f"/v1/agents/limit-proposals/{quote(proposal_id, safe='')}/stage", {}))

    def dismiss_limit_proposal(self, proposal_id: str, *, reason: Optional[str] = None) -> Dict[str, Any]:
        """Dismiss a limit proposal. It stays hidden while the agent's limit is unchanged. `reason` is optional, at most 500 characters."""
        body: Dict[str, Any] = {} if reason is None else {"reason": reason}
        return cast(Dict[str, Any], self._http.post(f"/v1/agents/limit-proposals/{quote(proposal_id, safe='')}/dismiss", body))

    def snooze_limit_proposal(self, proposal_id: str, *, days: int, reason: Optional[str] = None) -> Dict[str, Any]:
        """Snooze a limit proposal for 7, 14 or 30 days. It comes back after that if it still qualifies."""
        body: Dict[str, Any] = {"days": days}
        if reason is not None:
            body["reason"] = reason
        return cast(Dict[str, Any], self._http.post(f"/v1/agents/limit-proposals/{quote(proposal_id, safe='')}/snooze", body))

    def get(self, agent_key: str) -> Agent:
        data = self._http.get(f"/v1/agents/{quote(agent_key)}")
        return Agent._from_dict(data["agent"])

    def create(
        self,
        *,
        agent_key: str,
        name: str,
        goal: str,
        description: Optional[str] = None,
        system_instructions: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        intent_ids: Optional[List[str]] = None,
        workflow_ids: Optional[List[str]] = None,
        action_ids: Optional[List[str]] = None,
        knowledge_domain_keys: Optional[List[str]] = None,
        tools_config: Optional[Dict[str, Any]] = None,
        memory_config: Optional[Dict[str, Any]] = None,
        behavior_config: Optional[Dict[str, Any]] = None,
    ) -> Agent:
        body: Dict[str, Any] = {"agent_key": agent_key, "name": name, "goal": goal}
        optional = {
            "description": description, "system_instructions": system_instructions,
            "model": model, "temperature": temperature,
            "intent_ids": intent_ids, "workflow_ids": workflow_ids,
            "action_ids": action_ids, "knowledge_domain_keys": knowledge_domain_keys,
            "tools_config": tools_config, "memory_config": memory_config, "behavior_config": behavior_config,
        }
        body.update({k: v for k, v in optional.items() if v is not None})

        data = self._http.post("/v1/agents", body)
        return Agent._from_dict(data["agent"])

    def update(
        self,
        agent_key: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        goal: Optional[str] = None,
        system_instructions: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        status: Optional[str] = None,
        intent_ids: Optional[List[str]] = None,
        workflow_ids: Optional[List[str]] = None,
        action_ids: Optional[List[str]] = None,
        knowledge_domain_keys: Optional[List[str]] = None,
        tools_config: Optional[Dict[str, Any]] = None,
        memory_config: Optional[Dict[str, Any]] = None,
        behavior_config: Optional[Dict[str, Any]] = None,
    ) -> Agent:
        """Setting status='active' directly raises LiyaEngineAPIError(code='DEPLOY_REQUIRED') — use deploy() instead."""
        body: Dict[str, Any] = {}
        optional = {
            "name": name, "description": description, "goal": goal, "system_instructions": system_instructions,
            "model": model, "temperature": temperature, "status": status,
            "intent_ids": intent_ids, "workflow_ids": workflow_ids,
            "action_ids": action_ids, "knowledge_domain_keys": knowledge_domain_keys,
            "tools_config": tools_config, "memory_config": memory_config, "behavior_config": behavior_config,
        }
        body.update({k: v for k, v in optional.items() if v is not None})

        data = self._http.patch(f"/v1/agents/{quote(agent_key)}", body)
        return Agent._from_dict(data["agent"])

    def delete(self, agent_key: str) -> None:
        self._http.delete(f"/v1/agents/{quote(agent_key)}")

    def deploy(self, agent_key: str) -> Agent:
        """Activates an agent for execution — a deliberate, separately audited transition distinct from update()."""
        data = self._http.post(f"/v1/agents/{quote(agent_key)}/deploy")
        return Agent._from_dict(data["agent"])

    def run(
        self, agent_key: str, *, input: Dict[str, Any], session_id: Optional[str] = None,
        access: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """`access={"groups": [...]}` is the end user's retrieval access context (see intents.run)."""
        body: Dict[str, Any] = {"input": input}
        if session_id is not None:
            body["session_id"] = session_id
        if access is not None:
            body["access"] = access
        return cast(Dict[str, Any], self._http.post(f"/v1/agents/{quote(agent_key)}/run", body))

    def run_stream(
        self, agent_key: str, *, input: Dict[str, Any], session_id: Optional[str] = None,
        access: Optional[Dict[str, Any]] = None,
    ) -> Iterator[AgentRunStreamEvent]:
        """Same input as run() — real-time step progress instead of one awaited result.

        Step-level, not token-level: AgentOrchestrator has no streaming
        synthesis call, so there's no token delta to yield. A "step" event
        fires in real time as each llm_call/tool_execution happens, and a
        single "done" event carries the complete, already-generated final
        answer — never token-chunked.
        """
        body: Dict[str, Any] = {"input": input}
        if session_id is not None:
            body["session_id"] = session_id
        if access is not None:
            body["access"] = access
        for frame in self._http.stream(f"/v1/agents/{quote(agent_key)}/run/stream", body):
            yield cast(AgentRunStreamEvent, frame)

    def list_runs(
        self, agent_key: str, *, page: Optional[int] = None, page_size: Optional[int] = None,
        status: Optional[str] = None, session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        qs = _query(page=page, pageSize=page_size, status=status, session_id=session_id)
        return cast(Dict[str, Any], self._http.get(f"/v1/agents/{quote(agent_key)}/runs{qs}"))

    def get_run(self, agent_key: str, run_id: str) -> Dict[str, Any]:
        data = self._http.get(f"/v1/agents/{quote(agent_key)}/runs/{quote(run_id)}")
        return cast(Dict[str, Any], data["run"])

    def list_sessions(
        self, agent_key: str, *, page: Optional[int] = None, page_size: Optional[int] = None, status: Optional[str] = None,
    ) -> Dict[str, Any]:
        qs = _query(page=page, pageSize=page_size, status=status)
        return cast(Dict[str, Any], self._http.get(f"/v1/agents/{quote(agent_key)}/sessions{qs}"))

    def get_transcript(self, agent_key: str, session_id: str) -> Dict[str, Any]:
        return cast(Dict[str, Any], self._http.get(f"/v1/agents/{quote(agent_key)}/sessions/{quote(session_id)}/transcript"))
