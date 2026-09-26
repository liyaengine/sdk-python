"""Prompt Studio — a versioned, immutably-pinned prompt library. A prompt's
content only ever changes by adding a new immutable version via
versions.create() — there is no update-in-place, matching the dashboard's
own shape exactly (no PATCH exists there either). publish() promotes one
exact version to the tenant's production pointer; existing consumers bound
via prompt_binding={"kind": "library_version", ...} stay pinned to their
own version until explicitly repointed. AI-authoring (draft/improve a
prompt with Prompt Copilot) is dashboard-only — no SDK equivalent.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, TypedDict, cast
from urllib.parse import quote, urlencode

from .._http import HttpClient


class PromptVariable(TypedDict, total=False):
    """Referenced in content as {{name}}."""

    name: str
    type: Literal["string", "number", "boolean", "json"]
    required: bool
    description: str
    default: Any


class PromptModelHints(TypedDict, total=False):
    provider: str
    model: str
    temperature: float
    max_output_tokens: int


@dataclass(frozen=True)
class PromptVersion:
    id: str
    prompt_id: str
    version_number: int
    content: str
    variables: List[PromptVariable]
    output_schema: Optional[Dict[str, Any]]
    model_hints: Optional[PromptModelHints]
    provenance: Optional[Dict[str, Any]]
    # Re-verified at PromptBinding resolve time — tamper-evident.
    content_hash: str
    change_note: Optional[str]
    created_by: Optional[str]
    created_at: str

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "PromptVersion":
        return cls(
            id=data["id"], prompt_id=data["prompt_id"], version_number=data["version_number"],
            content=data["content"], variables=data.get("variables") or [],
            output_schema=data.get("output_schema"), model_hints=data.get("model_hints"),
            provenance=data.get("provenance"), content_hash=data["content_hash"],
            change_note=data.get("change_note"), created_by=data.get("created_by"), created_at=data["created_at"],
        )


@dataclass(frozen=True)
class PromptDeployment:
    environment: str
    version_id: str
    deployed_at: str

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "PromptDeployment":
        return cls(environment=data["environment"], version_id=data["version_id"], deployed_at=data["deployed_at"])


@dataclass(frozen=True)
class Prompt:
    id: str
    prompt_key: str
    name: str
    description: Optional[str]
    role: Literal["system", "developer", "user", "assistant"]
    tags: List[str]
    status: Literal["draft", "active", "archived"]
    created_by: Optional[str]
    updated_by: Optional[str]
    created_at: str
    updated_at: str
    # Only the single latest version — call versions.list() for full history.
    versions: List[PromptVersion]
    deployments: List[PromptDeployment]

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "Prompt":
        return cls(
            id=data["id"], prompt_key=data["prompt_key"], name=data["name"], description=data.get("description"),
            role=data["role"], tags=data.get("tags") or [], status=data["status"],
            created_by=data.get("created_by"), updated_by=data.get("updated_by"),
            created_at=data["created_at"], updated_at=data["updated_at"],
            versions=[PromptVersion._from_dict(v) for v in data.get("versions") or []],
            deployments=[PromptDeployment._from_dict(d) for d in data.get("deployments") or []],
        )


@dataclass(frozen=True)
class PublishPromptResult:
    deployment: Dict[str, Any]
    # True if the requested version was already the live one — still a success, not an error.
    unchanged: bool

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "PublishPromptResult":
        return cls(deployment=data["deployment"], unchanged=data["unchanged"])


def _query(**params: Optional[str]) -> str:
    filtered = {k: v for k, v in params.items() if v is not None}
    return f"?{urlencode(filtered)}" if filtered else ""


class PromptVersionsResource:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def list(self, prompt_id: str) -> List[PromptVersion]:
        """Newest first, max 100."""
        data = self._http.get(f"/v1/prompts/{quote(prompt_id)}/versions")
        return [PromptVersion._from_dict(v) for v in cast(Dict[str, Any], data)["versions"]]

    def create(
        self, prompt_id: str, *, content: str,
        variables: Optional[List[PromptVariable]] = None,
        output_schema: Optional[Dict[str, Any]] = None,
        model_hints: Optional[PromptModelHints] = None,
        change_note: Optional[str] = None,
    ) -> PromptVersion:
        """A no-op save (content/variables/output_schema/model_hints all identical to the
        current latest version) raises a LiyaEngineAPIError (PROMPT_VERSION_UNCHANGED, 409)
        instead of creating an empty entry."""
        body: Dict[str, Any] = {"content": content}
        if variables is not None:
            body["variables"] = variables
        if output_schema is not None:
            body["output_schema"] = output_schema
        if model_hints is not None:
            body["model_hints"] = model_hints
        if change_note is not None:
            body["change_note"] = change_note
        data = self._http.post(f"/v1/prompts/{quote(prompt_id)}/versions", body)
        return PromptVersion._from_dict(cast(Dict[str, Any], data)["version"])


class PromptsResource:
    def __init__(self, http: HttpClient) -> None:
        self._http = http
        self.versions = PromptVersionsResource(http)

    def list(self, *, search: Optional[str] = None, status: Optional[str] = None) -> List[Prompt]:
        qs = _query(search=search, status=status)
        data = self._http.get(f"/v1/prompts{qs}")
        return [Prompt._from_dict(p) for p in cast(Dict[str, Any], data)["prompts"]]

    def get(self, prompt_id: str) -> Prompt:
        data = self._http.get(f"/v1/prompts/{quote(prompt_id)}")
        return Prompt._from_dict(cast(Dict[str, Any], data)["prompt"])

    def create(
        self, *, prompt_key: str, name: str, content: str,
        description: Optional[str] = None,
        role: Optional[Literal["system", "developer", "user", "assistant"]] = None,
        tags: Optional[List[str]] = None,
        variables: Optional[List[PromptVariable]] = None,
        output_schema: Optional[Dict[str, Any]] = None,
        model_hints: Optional[PromptModelHints] = None,
        change_note: Optional[str] = None,
    ) -> Prompt:
        """Creates the prompt and its immutable version 1 in one call — there is no
        separate "create empty prompt" step."""
        body: Dict[str, Any] = {"prompt_key": prompt_key, "name": name, "content": content}
        if description is not None:
            body["description"] = description
        if role is not None:
            body["role"] = role
        if tags is not None:
            body["tags"] = tags
        if variables is not None:
            body["variables"] = variables
        if output_schema is not None:
            body["output_schema"] = output_schema
        if model_hints is not None:
            body["model_hints"] = model_hints
        if change_note is not None:
            body["change_note"] = change_note
        data = self._http.post("/v1/prompts", body)
        return Prompt._from_dict(cast(Dict[str, Any], data)["prompt"])

    def publish(self, prompt_id: str, *, version_id: str, deployment_note: Optional[str] = None) -> PublishPromptResult:
        body: Dict[str, Any] = {"version_id": version_id}
        if deployment_note is not None:
            body["deployment_note"] = deployment_note
        data = self._http.post(f"/v1/prompts/{quote(prompt_id)}/publish", body)
        return PublishPromptResult._from_dict(cast(Dict[str, Any], data))
