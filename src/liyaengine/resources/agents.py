from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, cast
from urllib.parse import quote, urlencode

from .._http import HttpClient


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

    def run(self, agent_key: str, *, input: Dict[str, Any], session_id: Optional[str] = None) -> Dict[str, Any]:
        body: Dict[str, Any] = {"input": input}
        if session_id is not None:
            body["session_id"] = session_id
        return cast(Dict[str, Any], self._http.post(f"/v1/agents/{quote(agent_key)}/run", body))

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
