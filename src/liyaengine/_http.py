"""Thin httpx wrapper: bearer auth, JSON in/out, the {success,data} /
{success,error} envelope unwrapped into a return value or a raised
LiyaEngineAPIError, and retry-with-backoff on 429/5xx (not on 4xx, which
are the caller's own mistake and won't succeed on retry).
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, Iterator, Optional

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

    def _request_envelope(self, method: str, path: str, json_body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Shared fetch/retry/error-envelope core — returns the parsed body
        as-is (past the success check), not unwrapped to just `data`. Almost
        every endpoint wants `request()` below instead."""
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
                payload: Dict[str, Any] = response.json()
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
            return payload

        if last_error is not None:
            raise last_error
        raise LiyaEngineNetworkError("Request failed")

    def request(self, method: str, path: str, json_body: Optional[Dict[str, Any]] = None) -> Any:
        return self._request_envelope(method, path, json_body).get("data")

    def get(self, path: str) -> Any:
        return self.request("GET", path)

    def post(self, path: str, json_body: Optional[Dict[str, Any]] = None) -> Any:
        return self.request("POST", path, json_body)

    def patch(self, path: str, json_body: Optional[Dict[str, Any]] = None) -> Any:
        return self.request("PATCH", path, json_body)

    def delete(self, path: str) -> Any:
        return self.request("DELETE", path)

    def post_envelope(self, path: str, json_body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """For the rare endpoint whose envelope has extra top-level sibling
        fields beyond {success, data} (today: only POST /v1/run, which also
        returns sibling metadata/usage) — returns the parsed body as-is,
        past the standard success/error check, instead of unwrapping to
        just `data`."""
        return self._request_envelope("POST", path, json_body)

    def stream(self, path: str, json_body: Optional[Dict[str, Any]] = None) -> Iterator[Dict[str, Any]]:
        """Streams POST {path} as server-sent events, yielding each parsed
        `data: {...}` frame in order. No retries — a stream is a single
        long-lived attempt, not a single request with a bounded response the
        usual retry-with-backoff logic can safely redo. No timeout override
        either: this is a token-by-token stream of unbounded duration, not a
        single request racing a fixed deadline (the client's configured
        timeout_s still applies to the initial connection).

        A rejection *before* the stream opens (missing field, plan gate)
        arrives as a normal {success:false,error} JSON body over a non-2xx
        status — raised as a LiyaEngineAPIError, exactly like request().
        Once the stream has opened, every subsequent failure arrives in-band
        as a frame with the caller's own `type` field (e.g. "error") — this
        method has no opinion on frame shape; callers discriminate by
        whatever `type` values that specific endpoint documents.
        """
        with self._client.stream("POST", path, json=json_body) as response:
            content_type = response.headers.get("content-type", "")
            if "text/event-stream" not in content_type:
                response.read()
                try:
                    payload = response.json()
                except ValueError as exc:
                    raise LiyaEngineNetworkError(
                        f"Invalid JSON response (status {response.status_code})", exc
                    ) from exc
                if payload.get("success") is False:
                    error = payload.get("error", {})
                    raise LiyaEngineAPIError(
                        response.status_code,
                        error.get("code", "UNKNOWN_ERROR"),
                        error.get("message", "Unknown error"),
                        error.get("details"),
                    )
                raise LiyaEngineNetworkError(f"Unexpected non-streaming response (status {response.status_code})")

            for line in response.iter_lines():
                if not line or not line.startswith("data: "):
                    continue
                yield json.loads(line[len("data: ") :])

    def close(self) -> None:
        self._client.close()
