"""A domain's agentic tool configuration — the custom webhook tools (and
enabled platform tools) an agent-mode intent (agent_config.enabled) can
call mid-conversation. Was dashboard-only before this; the tool's real
definition (endpoint, auth) can now be set from here too, not just
referenced by name in an intent's agent_config.tools[].
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, TypedDict, cast
from urllib.parse import quote

from .._http import HttpClient


class CustomToolInput(TypedDict, total=False):
    """URL-safe `name` (/^[a-z0-9_-]+$/) is what agent_config.tools[] references,
    and what the model passes as tool_name at run time. `description` is the
    ONLY thing the model sees to decide when/how to call this tool — there's
    no separate JSON-schema parameter definition today, so be explicit about
    expected fields there. `auth_value` is write-only: omit on update to keep
    the existing stored credential; required on first create for any
    auth_type other than "none"."""

    name: str
    display_name: str
    description: str
    endpoint_url: str
    auth_type: Literal["none", "api_key", "bearer"]
    auth_value: str


@dataclass(frozen=True)
class PlatformTool:
    name: str
    description: str
    enabled: bool

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "PlatformTool":
        return cls(name=data["name"], description=data["description"], enabled=data["enabled"])


@dataclass(frozen=True)
class MaskedCustomTool:
    """A CustomToolInput as returned by the API — auth_value replaced by
    auth_configured; the real credential is never returned once stored."""

    name: str
    display_name: str
    description: str
    endpoint_url: str
    auth_type: Literal["none", "api_key", "bearer"]
    auth_configured: bool

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "MaskedCustomTool":
        return cls(
            name=data["name"], display_name=data["display_name"], description=data["description"],
            endpoint_url=data["endpoint_url"], auth_type=data["auth_type"], auth_configured=data["auth_configured"],
        )


@dataclass(frozen=True)
class DomainToolsConfig:
    platform_tools: List[PlatformTool]
    custom_tools: List[MaskedCustomTool]
    web_search_configured: bool

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "DomainToolsConfig":
        return cls(
            platform_tools=[PlatformTool._from_dict(t) for t in data["platform_tools"]],
            custom_tools=[MaskedCustomTool._from_dict(t) for t in data["custom_tools"]],
            web_search_configured=data["web_search_configured"],
        )


@dataclass(frozen=True)
class TestDomainToolResult:
    status_code: int
    ok: bool
    body: Any
    latency_ms: int

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "TestDomainToolResult":
        return cls(status_code=data["status_code"], ok=data["ok"], body=data["body"], latency_ms=data["latency_ms"])


class DomainToolsResource:
    """Domain-scoped tool configuration. Sits at client.domains.tools rather
    than a top-level resource — a tool only ever exists in the context of
    the one domain it's defined on."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def get(self, domain_key: str) -> DomainToolsConfig:
        data = self._http.get(f"/v1/domains/{quote(domain_key)}/tools")
        return DomainToolsConfig._from_dict(data)

    def update(
        self,
        domain_key: str,
        *,
        enabled_platform_tools: Optional[List[str]] = None,
        custom_tools: Optional[List[CustomToolInput]] = None,
        web_search_api_key: Optional[str] = None,
    ) -> DomainToolsConfig:
        """`custom_tools`, when given, REPLACES the entire array — not a
        per-tool merge/patch. `web_search_api_key=""` clears the stored key;
        omit to leave it unchanged."""
        body: Dict[str, Any] = {}
        if enabled_platform_tools is not None:
            body["enabled_platform_tools"] = enabled_platform_tools
        if custom_tools is not None:
            body["custom_tools"] = custom_tools
        if web_search_api_key is not None:
            body["web_search_api_key"] = web_search_api_key
        data = self._http.patch(f"/v1/domains/{quote(domain_key)}/tools", body)
        return DomainToolsConfig._from_dict(cast(Dict[str, Any], data)["tools_config"])

    def test(
        self, domain_key: str, tool_name: str, payload: Optional[Dict[str, Any]] = None,
    ) -> TestDomainToolResult:
        """Dispatches a real request to one custom tool's endpoint_url — the
        exact same request shape (headers, auth, `_liya_meta` envelope) an
        agent's real webhook_sender tool call would send — without needing a
        live conversation to trigger it."""
        body: Dict[str, Any] = {"tool_name": tool_name}
        if payload is not None:
            body["payload"] = payload
        data = self._http.post(f"/v1/domains/{quote(domain_key)}/tools/test", body)
        return TestDomainToolResult._from_dict(cast(Dict[str, Any], data))
