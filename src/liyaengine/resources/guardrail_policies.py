"""Guardrail Policies — the tenant-configurable safety config that replaces
a single hardcoded, global pipeline every tenant used to share identically.
Attach a policy to a Domain, Intent, Agent, or Action; an unattached
consumer falls through to the tenant's is_default policy. Every tenant
always has exactly one default — creating or promoting a new one demotes
the previous, and the current default can't be deleted or deactivated
until another is promoted first.

attach()/detach() are the ONLY way to set a consumer's guardrail_policy_id
— it is not writable via that consumer's own create()/update() call (e.g.
agents.create() has no guardrail_policy_id parameter).

`config` is typed as a plain dict (matching agent_config/execution_config/
etc. elsewhere in this SDK) rather than a deep TypedDict — every field is
optional and server-defaulted, and the shape is documented in the API
reference rather than duplicated here field-for-field.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, Union, cast
from urllib.parse import quote

from .._http import HttpClient

ConsumerType = Literal["domain", "intent", "agent", "action"]


@dataclass(frozen=True)
class GuardrailPolicy:
    id: str
    name: str
    description: Optional[str]
    is_default: bool
    is_active: bool
    config: Dict[str, Any]
    created_at: str
    updated_at: str
    # Only populated on list() — attached-consumer count summed across
    # domains/intents/agents/actions.
    attached_count: Optional[int] = None

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "GuardrailPolicy":
        return cls(
            id=data["id"], name=data["name"], description=data.get("description"),
            is_default=data["is_default"], is_active=data["is_active"], config=data.get("config") or {},
            created_at=data["created_at"], updated_at=data["updated_at"],
            attached_count=data.get("attached_count"),
        )


@dataclass(frozen=True)
class GuardrailPolicyConnections:
    domains: List[Dict[str, Any]]
    intents: List[Dict[str, Any]]
    agents: List[Dict[str, Any]]
    actions: List[Dict[str, Any]]

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "GuardrailPolicyConnections":
        return cls(domains=data["domains"], intents=data["intents"], agents=data["agents"], actions=data["actions"])


@dataclass(frozen=True)
class GuardrailIssue:
    code: str
    severity: Literal["info", "warning", "error", "critical"]
    message: str
    action_taken: Literal["none", "modified", "blocked", "flagged"]
    field: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "GuardrailIssue":
        return cls(
            code=data["code"], severity=data["severity"], message=data["message"],
            action_taken=data["action_taken"], field=data.get("field"), details=data.get("details"),
        )


@dataclass(frozen=True)
class TestGuardrailPolicyResult:
    passed: bool
    issues: List[GuardrailIssue]
    # Present for stage="pre_llm" — content after any redaction.
    content: Optional[str] = None
    # Present for stage="post_llm" — response after any stage modified it.
    response: Optional[Union[str, Dict[str, Any]]] = None
    # Present for pre_llm when passed is False — a user-safe message to show instead of calling an LLM.
    fallback: Optional[str] = None
    # Present for post_llm — True when a stage suggests re-generating with stricter prompting.
    should_retry: Optional[bool] = None

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "TestGuardrailPolicyResult":
        return cls(
            passed=data["passed"], issues=[GuardrailIssue._from_dict(i) for i in data.get("issues", [])],
            content=data.get("content"), response=data.get("response"),
            fallback=data.get("fallback"), should_retry=data.get("shouldRetry"),
        )


@dataclass(frozen=True)
class GuardrailPolicyVersionSummary:
    id: str
    version_number: int
    changed_fields: List[str]
    change_type: Literal["create", "update", "restore"]
    restored_from_version: Optional[int]
    created_by: Optional[str]
    actor_name: Optional[str]
    created_at: str

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "GuardrailPolicyVersionSummary":
        return cls(
            id=data["id"], version_number=data["version_number"], changed_fields=data["changed_fields"],
            change_type=data["change_type"], restored_from_version=data.get("restored_from_version"),
            created_by=data.get("created_by"), actor_name=data.get("actorName"), created_at=data["created_at"],
        )


@dataclass(frozen=True)
class GuardrailPolicyAnalytics:
    window_days: int
    total_checks: int
    blocked_checks: int
    pass_rate: Optional[float]
    top_issue_codes: List[Dict[str, Any]]
    trend: List[Dict[str, Any]]

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "GuardrailPolicyAnalytics":
        return cls(
            window_days=data["window_days"], total_checks=data["total_checks"],
            blocked_checks=data["blocked_checks"], pass_rate=data.get("pass_rate"),
            top_issue_codes=data["top_issue_codes"], trend=data["trend"],
        )


class GuardrailPolicyVersionsResource:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def list(self, id: str) -> List[GuardrailPolicyVersionSummary]:
        """Newest first, max 50."""
        data = self._http.get(f"/v1/guardrail-policies/{quote(id)}/versions")
        return [GuardrailPolicyVersionSummary._from_dict(v) for v in cast(Dict[str, Any], data)["versions"]]

    def get(self, id: str, version_number: int) -> GuardrailPolicyVersionSummary:
        data = self._http.get(f"/v1/guardrail-policies/{quote(id)}/versions/{version_number}")
        return GuardrailPolicyVersionSummary._from_dict(cast(Dict[str, Any], data)["version"])

    def restore(self, id: str, version_number: int) -> GuardrailPolicy:
        """Writes the version's snapshot back onto the live policy. The restore itself is versioned too."""
        data = self._http.post(f"/v1/guardrail-policies/{quote(id)}/versions/{version_number}/restore", {})
        return GuardrailPolicy._from_dict(cast(Dict[str, Any], data)["policy"])


class GuardrailPoliciesResource:
    def __init__(self, http: HttpClient) -> None:
        self._http = http
        self.versions = GuardrailPolicyVersionsResource(http)

    def list(self) -> List[GuardrailPolicy]:
        data = self._http.get("/v1/guardrail-policies")
        return [GuardrailPolicy._from_dict(p) for p in cast(Dict[str, Any], data)["policies"]]

    def get(self, id: str) -> GuardrailPolicy:
        data = self._http.get(f"/v1/guardrail-policies/{quote(id)}")
        return GuardrailPolicy._from_dict(cast(Dict[str, Any], data)["policy"])

    def create(
        self, *, name: str, description: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None, is_default: Optional[bool] = None,
    ) -> GuardrailPolicy:
        """Creating with is_default=True demotes the tenant's current default policy in the same transaction."""
        body: Dict[str, Any] = {"name": name}
        if description is not None:
            body["description"] = description
        if config is not None:
            body["config"] = config
        if is_default is not None:
            body["is_default"] = is_default
        data = self._http.post("/v1/guardrail-policies", body)
        return GuardrailPolicy._from_dict(cast(Dict[str, Any], data)["policy"])

    def update(
        self, id: str, *, name: Optional[str] = None, description: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None, is_active: Optional[bool] = None,
    ) -> GuardrailPolicy:
        """Every update snapshots a new version automatically (a no-op save is skipped)."""
        body: Dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        if config is not None:
            body["config"] = config
        if is_active is not None:
            body["is_active"] = is_active
        data = self._http.patch(f"/v1/guardrail-policies/{quote(id)}", body)
        return GuardrailPolicy._from_dict(cast(Dict[str, Any], data)["policy"])

    def delete(self, id: str) -> None:
        """Detaches from every consumer first, then deletes. The tenant default can't be deleted — promote a different policy first."""
        self._http.delete(f"/v1/guardrail-policies/{quote(id)}")

    def set_default(self, id: str) -> None:
        """Demotes the current default in the same transaction. An inactive policy can't be promoted — reactivate it first."""
        self._http.post(f"/v1/guardrail-policies/{quote(id)}/set-default", {})

    def attach(self, id: str, consumer_type: ConsumerType, consumer_id: str) -> None:
        self._http.post(f"/v1/guardrail-policies/{quote(id)}/attach", {
            "consumer_type": consumer_type, "consumer_id": consumer_id,
        })

    def detach(self, id: str, consumer_type: ConsumerType, consumer_id: str) -> None:
        """Only clears the consumer's guardrail_policy_id if it currently points at THIS policy — safe to call even if already unattached."""
        self._http.post(f"/v1/guardrail-policies/{quote(id)}/detach", {
            "consumer_type": consumer_type, "consumer_id": consumer_id,
        })

    def connections(self, id: str) -> GuardrailPolicyConnections:
        data = self._http.get(f"/v1/guardrail-policies/{quote(id)}/connections")
        return GuardrailPolicyConnections._from_dict(cast(Dict[str, Any], data))

    def analytics(self, id: str, days: Optional[int] = None) -> GuardrailPolicyAnalytics:
        """Plain aggregation, computed on the fly — not a cached rollup."""
        qs = f"?days={days}" if days is not None else ""
        data = self._http.get(f"/v1/guardrail-policies/{quote(id)}/analytics{qs}")
        return GuardrailPolicyAnalytics._from_dict(cast(Dict[str, Any], data))

    def test(
        self, *, stage: Literal["pre_llm", "post_llm"], content: Union[str, Dict[str, Any]],
        policy_id: Optional[str] = None, config: Optional[Dict[str, Any]] = None,
        grounding_source_text: Optional[str] = None,
    ) -> TestGuardrailPolicyResult:
        """Runs the real guardrail pipeline against `content` — the same stages a live request
        would hit. Pass `config` to test an unsaved draft, or `policy_id` to test a saved one;
        omit both to test the tenant's current default. `grounding_source_text` (post_llm only)
        lets the hallucination/grounding check run here too — without it, it silently no-ops."""
        body: Dict[str, Any] = {"stage": stage, "content": content}
        if policy_id is not None:
            body["policy_id"] = policy_id
        if config is not None:
            body["config"] = config
        if grounding_source_text is not None:
            body["grounding_source_text"] = grounding_source_text
        data = self._http.post("/v1/guardrail-policies/test", body)
        return TestGuardrailPolicyResult._from_dict(cast(Dict[str, Any], data))
