"""Thin httpx wrapper: bearer auth, JSON in/out, the {success,data} /
{success,error} envelope unwrapped into a return value or a raised
LiyaEngineAPIError, and retry-with-backoff on 429/5xx (not on 4xx, which
are the caller's own mistake and won't succeed on retry).
"""
from __future__ import annotations

import time
from typing import Any, Dict, Optional

import httpx

from .errors import LiyaEngineAPIError, LiyaEngineNetworkError

_DEFAULT_TIMEOUT_S = 30.0
_DEFAULT_MAX_RETRIES = 2
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class HttpClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        timeout_s: float = _DEFAULT_TIMEOUT_S,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        client: Optional[httpx.Client] = None,
    ) -> None:
        self._max_retries = max_retries
        self._client = client or httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout_s,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

    def request(self, method: str, path: str, json_body: Optional[Dict[str, Any]] = None) -> Any:
        last_error: Optional[BaseException] = None

        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.request(method, path, json=json_body)
            except httpx.TimeoutException as exc:
                last_error = LiyaEngineNetworkError(f"Request timed out: {exc}", exc)
                if attempt >= self._max_retries:
                    raise last_error from exc
                time.sleep(2**attempt * 0.25)
                continue
            except httpx.RequestError as exc:
                last_error = LiyaEngineNetworkError(f"Network request failed: {exc}", exc)
                if attempt >= self._max_retries:
                    raise last_error from exc
                time.sleep(2**attempt * 0.25)
                continue

            if response.status_code in _RETRYABLE_STATUS and attempt < self._max_retries:
                time.sleep(2**attempt * 0.25)
                continue

            try:
                payload = response.json()
            except ValueError as exc:
                raise LiyaEngineNetworkError(
                    f"Invalid JSON response (status {response.status_code})", exc
                ) from exc

            if not payload.get("success"):
                error = payload.get("error", {})
                raise LiyaEngineAPIError(
                    response.status_code,
                    error.get("code", "UNKNOWN_ERROR"),
                    error.get("message", "Unknown error"),
                    error.get("details"),
                )
            return payload.get("data")

        if last_error is not None:
            raise last_error
        raise LiyaEngineNetworkError("Request failed")

    def get(self, path: str) -> Any:
        return self.request("GET", path)

    def post(self, path: str, json_body: Optional[Dict[str, Any]] = None) -> Any:
        return self.request("POST", path, json_body)

    def patch(self, path: str, json_body: Optional[Dict[str, Any]] = None) -> Any:
        return self.request("PATCH", path, json_body)

    def delete(self, path: str) -> Any:
        return self.request("DELETE", path)

    def close(self) -> None:
        self._client.close()
