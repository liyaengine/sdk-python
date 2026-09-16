"""Every non-2xx /v1 response carries {"success": false, "error": {"code", "message"}}
(see liyaengine-api's ErrorEnvelope in openapi.yaml). This maps that envelope onto
real exceptions instead of a plain dict, so callers can `except LiyaEngineAPIError`.
"""
from __future__ import annotations

from typing import Any, Optional


class LiyaEngineAPIError(Exception):
    """The API returned a well-formed error envelope."""

    def __init__(self, status: int, code: str, message: str, details: Optional[Any] = None) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details

    def __repr__(self) -> str:
        return f"LiyaEngineAPIError(status={self.status}, code={self.code!r}, message={self.message!r})"


class LiyaEngineNetworkError(Exception):
    """The request never reached the server, timed out, or the response wasn't valid JSON."""

    def __init__(self, message: str, cause: Optional[BaseException] = None) -> None:
        super().__init__(message)
        self.cause = cause
