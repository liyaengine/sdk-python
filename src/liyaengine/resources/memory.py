from __future__ import annotations

from typing import Any, Dict, Optional, cast

from .._http import HttpClient

# Learned memory. Today this resource covers outcomes only: /v1/memory/outcomes (see openapi.yaml). The rest of /v1/memory/*
# (files, history, approvals, curation) is not wrapped yet.


class MemoryResource:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def outcomes(self, *, days: Optional[int] = None) -> Dict[str, Any]:
        """How agents' runs ended after opening each note, over the last 7, 30 (default) or 90 days. Per note: runs with and
        without it, success rates, the difference in points, and a verdict ("helps", "hurts", "neutral", or "not_enough_data"
        below 30 runs with and 10 without). Also `unopened_files`.

        "Finished" means the run's status is `completed`: a reliability signal, not a judgment of the answer. A verdict is an
        association, not a cause: agents tend to open notes on harder questions. Reads only; nothing is changed."""
        qs = f"?days={days}" if days is not None else ""
        return cast(Dict[str, Any], self._http.get(f"/v1/memory/outcomes{qs}"))
