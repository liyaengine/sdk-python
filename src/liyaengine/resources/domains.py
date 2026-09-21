from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, cast
from urllib.parse import quote

from .._http import HttpClient


@dataclass(frozen=True)
class Intent:
    """Real columns also include agent_config/execution_config/retrieval_config/
    cache_config/prompt_binding/guardrail_policy_id — dashboard-only to write today,
    not on create()/update()'s keyword args below."""

    id: str
    tenant_id: str
    domain_key: str
    intent_key: str
    display_name: str
    description: Optional[str]
    prompt_template: str
    output_schema: Optional[Dict[str, Any]]
    input_schema: Optional[Dict[str, Any]]
    guardrails_config: Optional[Dict[str, Any]]
    is_active: bool
    sort_order: int
    created_at: str
    updated_at: str

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "Intent":
        return cls(
            id=data["id"], tenant_id=data["tenant_id"], domain_key=data["domain_key"], intent_key=data["intent_key"],
            display_name=data["display_name"], description=data.get("description"),
            prompt_template=data["prompt_template"], output_schema=data.get("output_schema"),
            input_schema=data.get("input_schema"), guardrails_config=data.get("guardrails_config"),
            is_active=data["is_active"], sort_order=data["sort_order"],
            created_at=data["created_at"], updated_at=data["updated_at"],
        )


@dataclass(frozen=True)
class Domain:
    """Real columns also include status/guardrail_policy_id/prompt_binding/tools_config/
    default_top_k/default_similarity_threshold — dashboard-only to write today."""

    id: str
    tenant_id: str
    domain_key: str
    display_name: str
    description: Optional[str]
    icon: str
    color: str
    system_prompt: Optional[str]
    context_enrichment_webhook_url: Optional[str]
    retrieval_scope: Optional[str]
    is_active: bool
    created_at: str
    updated_at: str
    # Present on get()/list() only when a domain has intents/source types — not on create().
    intents: Optional[List[Intent]] = None
    source_types: Optional[List[Dict[str, Any]]] = None

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "Domain":
        intents = data.get("intents")
        return cls(
            id=data["id"], tenant_id=data["tenant_id"], domain_key=data["domain_key"],
            display_name=data["display_name"], description=data.get("description"),
            icon=data["icon"], color=data["color"], system_prompt=data.get("system_prompt"),
            context_enrichment_webhook_url=data.get("context_enrichment_webhook_url"),
            retrieval_scope=data.get("retrieval_scope"), is_active=data["is_active"],
            created_at=data["created_at"], updated_at=data["updated_at"],
            intents=[Intent._from_dict(i) for i in intents] if intents is not None else None,
            source_types=data.get("source_types"),
        )


@dataclass(frozen=True)
class DomainSource:
    """A domain-scoped view of a Collection — same underlying resource as
    client.collections. Prefer client.collections for the full config surface;
    this covers only the create/list/delete + attach-a-document routes nested
    under a domain."""

    id: str
    tenant_id: str
    domain_key: str
    slug: str
    label: str
    color: str
    created_at: str
    # Present on create() only.
    domain_keys: Optional[List[str]] = None

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "DomainSource":
        return cls(
            id=data["id"], tenant_id=data["tenant_id"], domain_key=data["domain_key"],
            slug=data["slug"], label=data["label"], color=data["color"],
            created_at=data["created_at"], domain_keys=data.get("domain_keys"),
        )


@dataclass(frozen=True)
class IntentCatalogEntry:
    domain: str
    domain_label: str
    intent: str
    display_name: str
    description: Optional[str]
    endpoint: str
    method: str
    input_schema: Dict[str, Any]
    output_schema: Optional[Dict[str, Any]]

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "IntentCatalogEntry":
        return cls(
            domain=data["domain"], domain_label=data["domainLabel"], intent=data["intent"],
            display_name=data["displayName"], description=data.get("description"),
            endpoint=data["endpoint"], method=data["method"],
            input_schema=data.get("inputSchema", {}), output_schema=data.get("outputSchema"),
        )


class DomainIntentsResource:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def list(self, domain_key: str) -> List[Intent]:
        data = self._http.get(f"/v1/domains/{quote(domain_key)}/intents")
        return [Intent._from_dict(i) for i in data["intents"]]

    # /v1/domains/:key/intents predates the snake_case wire convention every
    # other /v1 resource in this SDK uses, and has real external consumers
    # (A3LearningLabs, Qistara, StoryHire per the API's own doc comment) — its
    # request bodies are camelCase. Translated here so this SDK's own public
    # shape stays consistent with every other resource; changing the wire
    # format itself would break those existing integrations.
    def create(
        self, domain_key: str, *, intent_key: str, display_name: str, prompt_template: str,
        description: Optional[str] = None, output_schema: Optional[Dict[str, Any]] = None,
        input_schema: Optional[Dict[str, Any]] = None, guardrails_config: Optional[Dict[str, Any]] = None,
    ) -> Intent:
        body: Dict[str, Any] = {"intentKey": intent_key, "displayName": display_name, "promptTemplate": prompt_template}
        optional = {
            "description": description, "outputSchema": output_schema,
            "inputSchema": input_schema, "guardrailsConfig": guardrails_config,
        }
        body.update({k: v for k, v in optional.items() if v is not None})
        data = self._http.post(f"/v1/domains/{quote(domain_key)}/intents", body)
        return Intent._from_dict(data["intent"])

    def update(
        self, domain_key: str, intent_key: str, *, display_name: Optional[str] = None,
        description: Optional[str] = None, prompt_template: Optional[str] = None,
        output_schema: Optional[Dict[str, Any]] = None, input_schema: Optional[Dict[str, Any]] = None,
        guardrails_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, int]:
        """Returns {"updated": 1}, not the updated Intent — this door has no
        get-single-intent route to re-fetch from either. Call list() again if
        you need the fresh object."""
        body: Dict[str, Any] = {}
        optional = {
            "displayName": display_name, "description": description, "promptTemplate": prompt_template,
            "outputSchema": output_schema, "inputSchema": input_schema, "guardrailsConfig": guardrails_config,
        }
        body.update({k: v for k, v in optional.items() if v is not None})
        return cast(Dict[str, int], self._http.patch(f"/v1/domains/{quote(domain_key)}/intents/{quote(intent_key)}", body))

    def delete(self, domain_key: str, intent_key: str) -> None:
        """Soft delete."""
        self._http.delete(f"/v1/domains/{quote(domain_key)}/intents/{quote(intent_key)}")


class DomainSourcesResource:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def list(self, domain_key: str) -> List[DomainSource]:
        data = self._http.get(f"/v1/domains/{quote(domain_key)}/sources")
        return [DomainSource._from_dict(s) for s in data["sources"]]

    def create(self, domain_key: str, *, slug: str, label: str, color: Optional[str] = None) -> DomainSource:
        body: Dict[str, Any] = {"slug": slug, "label": label}
        if color is not None:
            body["color"] = color
        data = self._http.post(f"/v1/domains/{quote(domain_key)}/sources", body)
        return DomainSource._from_dict(data["sourceType"])

    def delete(self, domain_key: str, slug: str) -> None:
        self._http.delete(f"/v1/domains/{quote(domain_key)}/sources/{quote(slug)}")


class DomainsResource:
    """Custom domains — the top-level container tenants configure first (system
    prompt, retrieval scope, then intents and knowledge underneath). Mirrors the
    full /v1/domains surface. Basic CRUD only today — agent/execution/retrieval/
    cache config, guardrail policy attachment, and versioning are still
    dashboard-only (no /v1 route yet)."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http
        self.intents = DomainIntentsResource(http)
        self.sources = DomainSourcesResource(http)

    def list(self) -> List[Domain]:
        data = self._http.get("/v1/domains")
        return [Domain._from_dict(d) for d in data["domains"]]

    def get(self, domain_key: str) -> Domain:
        """Includes this domain's intents and source types."""
        data = self._http.get(f"/v1/domains/{quote(domain_key)}")
        return Domain._from_dict(data["domain"])

    # /v1/domains predates the snake_case wire convention every other /v1
    # resource in this SDK uses, and has real external consumers
    # (A3LearningLabs, Qistara, StoryHire per the API's own doc comment) — its
    # request bodies are camelCase. Translated here so this SDK's own public
    # shape stays consistent with every other resource.
    def create(
        self, *, domain_key: str, display_name: str, description: Optional[str] = None,
        icon: Optional[str] = None, color: Optional[str] = None, system_prompt: Optional[str] = None,
        context_enrichment_webhook_url: Optional[str] = None,
    ) -> Domain:
        body: Dict[str, Any] = {"domainKey": domain_key, "displayName": display_name}
        optional = {
            "description": description, "icon": icon, "color": color, "systemPrompt": system_prompt,
            "contextEnrichmentWebhookUrl": context_enrichment_webhook_url,
        }
        body.update({k: v for k, v in optional.items() if v is not None})
        data = self._http.post("/v1/domains", body)
        return Domain._from_dict(data["domain"])

    def update(
        self, domain_key: str, *, display_name: Optional[str] = None, description: Optional[str] = None,
        icon: Optional[str] = None, color: Optional[str] = None, system_prompt: Optional[str] = None,
        retrieval_scope: Optional[str] = None, context_enrichment_webhook_url: Optional[str] = None,
    ) -> Dict[str, int]:
        """Returns {"updated": 1}, not the updated Domain — call get() again for the fresh object."""
        body: Dict[str, Any] = {}
        optional = {
            "displayName": display_name, "description": description, "icon": icon, "color": color,
            "systemPrompt": system_prompt, "retrievalScope": retrieval_scope,
            "contextEnrichmentWebhookUrl": context_enrichment_webhook_url,
        }
        body.update({k: v for k, v in optional.items() if v is not None})
        return cast(Dict[str, int], self._http.patch(f"/v1/domains/{quote(domain_key)}", body))

    def delete(self, domain_key: str) -> None:
        """Soft delete."""
        self._http.delete(f"/v1/domains/{quote(domain_key)}")

    def query(self, domain_key: str, *, query: str, top_k: Optional[int] = None) -> Dict[str, Any]:
        """Direct retrieval — runs this domain's knowledge search with no LLM
        call and no intent involved. Useful for testing collection/retrieval-scope
        configuration, or for building your own retrieval-then-generate flow."""
        body: Dict[str, Any] = {"query": query}
        if top_k is not None:
            body["top_k"] = top_k
        return cast(Dict[str, Any], self._http.post(f"/v1/domains/{quote(domain_key)}/query", body))

    def upload_document(self, domain_key: str, source_slug: str, *, file_base64: str, file_name: str) -> Dict[str, Any]:
        """Uploads a file (base64), extracts text, chunks, embeds, and attaches
        it to the named source (collection) — a real but narrow ingestion path:
        no category, no URL crawl, no async job, and it always uses
        text-embedding-3-small regardless of the collection's own
        default_embedding_model. For anything beyond a quick file drop, use the
        dashboard's Knowledge tab today."""
        data = self._http.post(
            f"/v1/domains/{quote(domain_key)}/sources/{quote(source_slug)}/docs",
            {"fileBase64": file_base64, "fileName": file_name},
        )
        return cast(Dict[str, Any], data["document"])


class IntentsResource:
    """Flat intent catalog — cuts across every custom domain, for external
    discovery (mirrors the dashboard's API Explorer page). Read-only; create/
    update/delete an intent via client.domains.intents."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def list_all(self) -> List[IntentCatalogEntry]:
        data = self._http.get("/v1/intents")
        return [IntentCatalogEntry._from_dict(i) for i in data["intents"]]
