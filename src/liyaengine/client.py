from __future__ import annotations

from typing import Optional

import httpx

from ._http import HttpClient
from .resources.agents import AgentsResource
from .resources.collections import CollectionsResource
from .resources.workflows import WorkflowsResource

_DEFAULT_BASE_URL = "https://api.liyaengine.ai"


class LiyaEngine:
    """Client for the Liya Engine public API.

    Example:
        >>> client = LiyaEngine(api_key="liya_...")
        >>> collection = client.collections.create(
        ...     slug="contracts", label="Contracts", domain_keys=["legal-ops"]
        ... )
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = _DEFAULT_BASE_URL,
        timeout_s: float = 30.0,
        max_retries: int = 2,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        if not api_key:
            raise ValueError("LiyaEngine: api_key is required.")

        self._http = HttpClient(
            api_key=api_key,
            base_url=base_url,
            timeout_s=timeout_s,
            max_retries=max_retries,
            client=http_client,
        )
        self.collections = CollectionsResource(self._http)
        self.agents = AgentsResource(self._http)
        self.workflows = WorkflowsResource(self._http)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "LiyaEngine":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
