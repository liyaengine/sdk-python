from __future__ import annotations

from typing import Any, Dict, Optional, cast
from urllib.parse import urlencode

from .._http import HttpClient

# Self-healing settings and the answer checks. Mirrors /v1/healing/* (see openapi.yaml). Needs a full-access key: changing the settings can
# start spending money, so a runtime-scoped key cannot.


class HealingResource:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def settings(self) -> Dict[str, Any]:
        """What self-healing may do on its own. A workspace that never saved any has every default: nothing automatic and no
        answer checks. `rollback_mode` and `limit_mode` are "off" or "stage" (a nightly job puts an open proposal in as a DRAFT;
        it never deploys)."""
        data = cast(Dict[str, Any], self._http.get("/v1/healing/settings"))
        return cast(Dict[str, Any], data["settings"])

    def update_settings(
        self,
        *,
        rollback_mode: Optional[str] = None,
        limit_mode: Optional[str] = None,
        answer_checks_enabled: Optional[bool] = None,
        answer_check_sample_pct: Optional[int] = None,
        answer_check_daily_cap_usd: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Change only the fields given. Takes effect at the next nightly run. Each answer check is a metered model call billed
        to the workspace, so `answer_check_sample_pct` (1 to 25) and `answer_check_daily_cap_usd` (0.5 to 500) limit it. Raises a
        400 `INVALID_SETTINGS` for a value out of range."""
        body: Dict[str, Any] = {}
        for key, value in (
            ("rollback_mode", rollback_mode), ("limit_mode", limit_mode), ("answer_checks_enabled", answer_checks_enabled),
            ("answer_check_sample_pct", answer_check_sample_pct), ("answer_check_daily_cap_usd", answer_check_daily_cap_usd),
        ):
            if value is not None:
                body[key] = value
        data = cast(Dict[str, Any], self._http.put("/v1/healing/settings", body))
        return cast(Dict[str, Any], data["settings"])

    def answer_checks(self, *, days: Optional[int] = None) -> Dict[str, Any]:
        """What the sampled answer checks found, and what they cost. A verdict is a model's reading of whether the passages an
        answer was built from support it: a reason to look, not proof. `days` is 7 to 90 (default 30)."""
        suffix = f"?{urlencode({'days': days})}" if days is not None else ""
        return cast(Dict[str, Any], self._http.get(f"/v1/healing/answer-checks{suffix}"))
