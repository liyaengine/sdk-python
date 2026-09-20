from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, cast
from urllib.parse import quote, urlencode

from .._http import HttpClient


@dataclass(frozen=True)
class EvalDataset:
    id: str
    tenant_id: str
    name: str
    description: Optional[str]
    created_at: str
    updated_at: str
    # Present only on datasets.get() — the single-dataset fetch. list()/create() return a lighter shape.
    cases: Optional[List["EvalCase"]] = None

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "EvalDataset":
        cases = data.get("cases")
        return cls(
            id=data["id"],
            tenant_id=data["tenant_id"],
            name=data["name"],
            description=data.get("description"),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            cases=[EvalCase._from_dict(c) for c in cases] if cases is not None else None,
        )


@dataclass(frozen=True)
class EvalCase:
    id: str
    tenant_id: str
    # Null for an ephemeral case created inline by a run submission.
    dataset_id: Optional[str]
    input: Any
    message: Optional[str]
    expected_output: Any
    notes: Optional[str]
    created_at: str

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "EvalCase":
        return cls(
            id=data["id"],
            tenant_id=data["tenant_id"],
            dataset_id=data.get("dataset_id"),
            input=data.get("input"),
            message=data.get("message"),
            expected_output=data.get("expected_output"),
            notes=data.get("notes"),
            created_at=data["created_at"],
        )


@dataclass(frozen=True)
class CreatedEvalDataset:
    id: str
    name: str
    description: Optional[str]
    case_count: int
    created_at: str

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "CreatedEvalDataset":
        return cls(
            id=data["id"], name=data["name"], description=data.get("description"),
            case_count=data["case_count"], created_at=data["created_at"],
        )


@dataclass(frozen=True)
class EvalDatasetTemplate:
    id: str
    name: str
    description: Optional[str]
    case_count: int
    example_cases: List[Dict[str, Any]]

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "EvalDatasetTemplate":
        return cls(
            id=data["id"], name=data["name"], description=data.get("description"),
            case_count=data["case_count"], example_cases=data.get("example_cases", []),
        )


@dataclass(frozen=True)
class EvalSuite:
    """Binds a Dataset to one specific (domain_key, intent_key); at most one custom scorer, either kind."""

    id: str
    tenant_id: str
    name: str
    domain_key: str
    intent_key: str
    dataset_id: str
    custom_scorer_expression: Optional[str]
    custom_scorer_label: Optional[str]
    custom_scorer_webhook_url: Optional[str]
    # The webhook secret itself is never returned after initial submission — only whether one is set.
    custom_scorer_webhook_secret_set: bool
    baseline_run_id: Optional[str]
    created_at: str
    updated_at: str

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "EvalSuite":
        return cls(
            id=data["id"], tenant_id=data["tenant_id"], name=data["name"],
            domain_key=data["domain_key"], intent_key=data["intent_key"], dataset_id=data["dataset_id"],
            custom_scorer_expression=data.get("custom_scorer_expression"),
            custom_scorer_label=data.get("custom_scorer_label"),
            custom_scorer_webhook_url=data.get("custom_scorer_webhook_url"),
            custom_scorer_webhook_secret_set=data.get("custom_scorer_webhook_secret_set", False),
            baseline_run_id=data.get("baseline_run_id"),
            created_at=data["created_at"], updated_at=data["updated_at"],
        )


@dataclass(frozen=True)
class EvalRun:
    """Always async — creation endpoints return this in 'pending' status; poll runs.get() for progress/results."""

    id: str
    tenant_id: str
    # Null for an execution_mode 'external_output' run — no suite/domain/intent is involved.
    suite_id: Optional[str]
    domain_key: Optional[str]
    intent_key: Optional[str]
    execution_mode: str
    triggered_by: str
    status: str
    stage: Optional[str]
    progress: int
    mean_score: Optional[float]
    dimension_scores: Optional[Dict[str, float]]
    cases_total: int
    cases_passed: int
    started_at: str
    completed_at: Optional[str]
    error: Optional[str]
    judge_total_cost_usd: Optional[float]
    judge_model: Optional[str]
    judge_calls: Optional[int]
    judge_failures: Optional[int]
    judge_cap_reached: bool
    model_override: Optional[str]

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "EvalRun":
        return cls(
            id=data["id"], tenant_id=data["tenant_id"], suite_id=data.get("suite_id"),
            domain_key=data.get("domain_key"), intent_key=data.get("intent_key"),
            execution_mode=data["execution_mode"], triggered_by=data["triggered_by"], status=data["status"],
            stage=data.get("stage"), progress=data["progress"], mean_score=data.get("mean_score"),
            dimension_scores=data.get("dimension_scores"), cases_total=data["cases_total"],
            cases_passed=data["cases_passed"], started_at=data["started_at"], completed_at=data.get("completed_at"),
            error=data.get("error"), judge_total_cost_usd=data.get("judge_total_cost_usd"),
            judge_model=data.get("judge_model"), judge_calls=data.get("judge_calls"),
            judge_failures=data.get("judge_failures"), judge_cap_reached=data.get("judge_cap_reached", False),
            model_override=data.get("model_override"),
        )


@dataclass(frozen=True)
class EvalReview:
    """A human reviewer's verdict on one case result's judge score, independent of who triggered the run."""

    id: str
    tenant_id: str
    run_result_id: str
    reviewer_id: str
    verdict: str
    # 1-5. Only meaningful when verdict is 'override'.
    corrected_score: Optional[float]
    note: Optional[str]
    created_at: str

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "EvalReview":
        return cls(
            id=data["id"], tenant_id=data["tenant_id"], run_result_id=data["run_result_id"],
            reviewer_id=data["reviewer_id"], verdict=data["verdict"], corrected_score=data.get("corrected_score"),
            note=data.get("note"), created_at=data["created_at"],
        )


def _query(**params: Any) -> str:
    pairs = {k: v for k, v in params.items() if v is not None}
    return f"?{urlencode(pairs)}" if pairs else ""


class EvalDatasetTemplatesResource:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def list(self) -> List[EvalDatasetTemplate]:
        data = self._http.get("/v1/evals/datasets/templates")
        return [EvalDatasetTemplate._from_dict(t) for t in data["templates"]]

    def clone(self, id: str) -> EvalDataset:
        data = self._http.post(f"/v1/evals/datasets/templates/{quote(id)}/clone")
        return EvalDataset._from_dict(data["dataset"])


class EvalDatasetsResource:
    def __init__(self, http: HttpClient) -> None:
        self._http = http
        self.templates = EvalDatasetTemplatesResource(http)

    def list(self) -> List[EvalDataset]:
        data = self._http.get("/v1/evals/datasets")
        return [EvalDataset._from_dict(d) for d in data["datasets"]]

    def get(self, id: str) -> EvalDataset:
        data = self._http.get(f"/v1/evals/datasets/{quote(id)}")
        return EvalDataset._from_dict(data["dataset"])

    def create(
        self, *, name: str, description: Optional[str] = None, cases: Optional[List[Dict[str, Any]]] = None,
    ) -> CreatedEvalDataset:
        """Response shape here is narrower than EvalDataset (no updated_at, no cases array — just a case_count)."""
        body: Dict[str, Any] = {"name": name}
        if description is not None:
            body["description"] = description
        if cases is not None:
            body["cases"] = cases
        data = self._http.post("/v1/evals/datasets", body)
        return CreatedEvalDataset._from_dict(data)

    def update(self, id: str, *, name: Optional[str] = None, description: Optional[str] = None) -> EvalDataset:
        body: Dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        data = self._http.patch(f"/v1/evals/datasets/{quote(id)}", body)
        return EvalDataset._from_dict(data["dataset"])

    def delete(self, id: str) -> None:
        self._http.delete(f"/v1/evals/datasets/{quote(id)}")

    def import_cases(self, id: str, cases: List[Dict[str, Any]]) -> int:
        """Plain JSON body, not multipart — you already have structured data if you're calling the API directly."""
        data = self._http.post(f"/v1/evals/datasets/{quote(id)}/import", {"cases": cases})
        return cast(int, data["imported"])


class EvalCasesResource:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def create(
        self, dataset_id: str, *, input: Dict[str, Any],
        message: Optional[str] = None, expected_output: Any = None, notes: Optional[str] = None,
    ) -> EvalCase:
        body: Dict[str, Any] = {"input": input}
        if message is not None:
            body["message"] = message
        if expected_output is not None:
            body["expected_output"] = expected_output
        if notes is not None:
            body["notes"] = notes
        data = self._http.post(f"/v1/evals/datasets/{quote(dataset_id)}/cases", body)
        return EvalCase._from_dict(data["case"])

    def update(
        self, case_id: str, *, input: Optional[Dict[str, Any]] = None,
        message: Optional[str] = None, expected_output: Any = None, notes: Optional[str] = None,
    ) -> EvalCase:
        body: Dict[str, Any] = {}
        if input is not None:
            body["input"] = input
        if message is not None:
            body["message"] = message
        if expected_output is not None:
            body["expected_output"] = expected_output
        if notes is not None:
            body["notes"] = notes
        data = self._http.patch(f"/v1/evals/cases/{quote(case_id)}", body)
        return EvalCase._from_dict(data["case"])

    def delete(self, case_id: str) -> None:
        self._http.delete(f"/v1/evals/cases/{quote(case_id)}")


class EvalSuitesResource:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def list(self, *, domain_key: Optional[str] = None, intent_key: Optional[str] = None) -> List[EvalSuite]:
        qs = _query(domain_key=domain_key, intent_key=intent_key)
        data = self._http.get(f"/v1/evals/suites{qs}")
        return [EvalSuite._from_dict(s) for s in data["suites"]]

    def create(
        self, *, name: str, domain_key: str, intent_key: str, dataset_id: str,
        custom_scorer_expression: Optional[str] = None, custom_scorer_label: Optional[str] = None,
        custom_scorer_webhook_url: Optional[str] = None, custom_scorer_webhook_secret: Optional[str] = None,
    ) -> EvalSuite:
        """A suite has at most one custom scorer — either an expression or a webhook, not both."""
        body: Dict[str, Any] = {"name": name, "domain_key": domain_key, "intent_key": intent_key, "dataset_id": dataset_id}
        optional = {
            "custom_scorer_expression": custom_scorer_expression, "custom_scorer_label": custom_scorer_label,
            "custom_scorer_webhook_url": custom_scorer_webhook_url, "custom_scorer_webhook_secret": custom_scorer_webhook_secret,
        }
        body.update({k: v for k, v in optional.items() if v is not None})
        data = self._http.post("/v1/evals/suites", body)
        return EvalSuite._from_dict(data["suite"])

    def update(
        self, id: str, *, name: Optional[str] = None, dataset_id: Optional[str] = None,
        custom_scorer_expression: Optional[str] = None, custom_scorer_label: Optional[str] = None,
        custom_scorer_webhook_url: Optional[str] = None, custom_scorer_webhook_secret: Optional[str] = None,
    ) -> EvalSuite:
        """Does not allow changing domain_key/intent_key — that changes what the suite tests, which should be a new suite."""
        body: Dict[str, Any] = {}
        optional = {
            "name": name, "dataset_id": dataset_id, "custom_scorer_expression": custom_scorer_expression,
            "custom_scorer_label": custom_scorer_label, "custom_scorer_webhook_url": custom_scorer_webhook_url,
            "custom_scorer_webhook_secret": custom_scorer_webhook_secret,
        }
        body.update({k: v for k, v in optional.items() if v is not None})
        data = self._http.patch(f"/v1/evals/suites/{quote(id)}", body)
        return EvalSuite._from_dict(data["suite"])

    def delete(self, id: str) -> None:
        self._http.delete(f"/v1/evals/suites/{quote(id)}")

    def set_baseline(self, id: str, run_id: Optional[str]) -> EvalSuite:
        """Every later completed run of this suite is auto-compared against whichever run is pinned here. Pass None to clear."""
        data = self._http.patch(f"/v1/evals/suites/{quote(id)}/baseline", {"run_id": run_id})
        return EvalSuite._from_dict(data["suite"])

    def run(self, id: str, *, model: Optional[str] = None) -> EvalRun:
        """
        Calls the suite's real intent for every case in its dataset and scores each response — the
        API-key counterpart to the dashboard's "run a suite" button. Returns immediately with a
        'pending' run; poll runs.get(). Budget-gated against the tenant's monthly Evals quota.
        """
        body = {"model": model} if model is not None else None
        data = self._http.post(f"/v1/evals/suites/{quote(id)}/run", body)
        return EvalRun._from_dict(data["run"])

    def list_runs(self, id: str) -> List[EvalRun]:
        data = self._http.get(f"/v1/evals/suites/{quote(id)}/runs")
        return [EvalRun._from_dict(r) for r in data["runs"]]

    def compare_models(self, id: str, model_a: str, model_b: str) -> Dict[str, EvalRun]:
        """Creates two ordinary runs against different force_model overrides — compare afterward via runs.compare()/compare_pairwise()."""
        data = self._http.post(f"/v1/evals/suites/{quote(id)}/compare-models", {"model_a": model_a, "model_b": model_b})
        return {"run_a": EvalRun._from_dict(data["run_a"]), "run_b": EvalRun._from_dict(data["run_b"])}


class EvalReviewsResource:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def create(
        self, result_id: str, *, verdict: str, corrected_score: Optional[float] = None, note: Optional[str] = None,
    ) -> EvalReview:
        """verdict is one of agree|override|flag. corrected_score (1-5) is required when verdict is 'override'."""
        body: Dict[str, Any] = {"verdict": verdict}
        if corrected_score is not None:
            body["corrected_score"] = corrected_score
        if note is not None:
            body["note"] = note
        data = self._http.post(f"/v1/evals/results/{quote(result_id)}/reviews", body)
        return EvalReview._from_dict(data["review"])

    def delete(self, id: str) -> None:
        self._http.delete(f"/v1/evals/reviews/{quote(id)}")


class EvalRunsResource:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def list(self, *, suite_id: Optional[str] = None) -> List[EvalRun]:
        qs = _query(suite_id=suite_id)
        data = self._http.get(f"/v1/evals/runs{qs}")
        return [EvalRun._from_dict(r) for r in data["runs"]]

    def submit(
        self, *, dataset_id: Optional[str] = None, cases: List[Dict[str, Any]],
        custom_scorer_expression: Optional[str] = None, custom_scorer_webhook_url: Optional[str] = None,
        custom_scorer_webhook_secret: Optional[str] = None,
    ) -> str:
        """
        Submit a batch of already-generated (input, output) pairs for async scoring — no
        domain/intent/engine.execute() involved, the runner just scores what you already produced.
        Returns a run id immediately; poll get(). Capped at 100 cases per request.
        """
        body: Dict[str, Any] = {"cases": cases}
        if dataset_id is not None:
            body["dataset_id"] = dataset_id
        if custom_scorer_expression is not None:
            body["custom_scorer_expression"] = custom_scorer_expression
        if custom_scorer_webhook_url is not None:
            body["custom_scorer_webhook_url"] = custom_scorer_webhook_url
        if custom_scorer_webhook_secret is not None:
            body["custom_scorer_webhook_secret"] = custom_scorer_webhook_secret
        data = self._http.post("/v1/evals/runs", body)
        return cast(str, data["run_id"])

    def get(self, id: str) -> Dict[str, Any]:
        return cast(Dict[str, Any], self._http.get(f"/v1/evals/runs/{quote(id)}"))

    def cancel(self, id: str) -> EvalRun:
        """Cooperative — the worker checks before its next case and stops there; the case in progress isn't scored."""
        data = self._http.post(f"/v1/evals/runs/{quote(id)}/cancel")
        return EvalRun._from_dict(data["run"])

    def resume(self, id: str) -> EvalRun:
        """
        Only a 'failed' run can be resumed. Already-scored cases are skipped — this continues from
        where the run stopped rather than re-billing every case. Works for both execution modes.
        """
        data = self._http.post(f"/v1/evals/runs/{quote(id)}/resume")
        return EvalRun._from_dict(data["run"])

    def compare(self, id: str, against: str) -> Dict[str, Any]:
        """Statistical comparison (pass rate, mean score, cost/latency deltas, significance test)."""
        return cast(Dict[str, Any], self._http.get(f"/v1/evals/runs/{quote(id)}/compare?against={quote(against)}"))

    def compare_pairwise(self, id: str, against: str) -> Dict[str, Any]:
        """Real LLM judge calls, cost-incurring — picks a winner (a/b/tie) per shared case. Both runs must share the same intent_key."""
        return cast(Dict[str, Any], self._http.post(f"/v1/evals/runs/{quote(id)}/compare-pairwise", {"against": against}))


class EvaluationsResource:
    """
    Evaluation Studio — Datasets/Cases/Suites/Runs/Reviews, plus standalone scoring (score()).
    Mirrors the full /v1/evals surface (see openapi.yaml). A Suite binds a Dataset to one intent;
    suites.run() calls that intent for real and scores what it produces, while runs.submit()/score()
    score a response you already generated yourself.
    """

    def __init__(self, http: HttpClient) -> None:
        self._http = http
        self.datasets = EvalDatasetsResource(http)
        self.cases = EvalCasesResource(http)
        self.suites = EvalSuitesResource(http)
        self.runs = EvalRunsResource(http)
        self.reviews = EvalReviewsResource(http)

    def score(
        self, *, input: Dict[str, Any], output: str,
        expected_output: Any = None, message: Optional[str] = None, custom_scorer_expression: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Score one (input, output) pair synchronously — no domain, intent, or dataset required."""
        body: Dict[str, Any] = {"input": input, "output": output}
        if expected_output is not None:
            body["expected_output"] = expected_output
        if message is not None:
            body["message"] = message
        if custom_scorer_expression is not None:
            body["custom_scorer_expression"] = custom_scorer_expression
        return cast(Dict[str, Any], self._http.post("/v1/evals/score", body))
