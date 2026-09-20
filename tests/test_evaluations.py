import httpx
import pytest
import respx

from liyaengine import LiyaEngine, LiyaEngineAPIError

BASE_URL = "https://api.test.liyaengine.ai"

FIXTURE_DATASET = {
    "id": "ds_123",
    "tenant_id": "tenant_1",
    "name": "Support Replies",
    "description": None,
    "created_at": "2026-01-01T00:00:00.000Z",
    "updated_at": "2026-01-01T00:00:00.000Z",
}

FIXTURE_CASE = {
    "id": "case_123",
    "tenant_id": "tenant_1",
    "dataset_id": "ds_123",
    "input": {"q": "hi"},
    "message": None,
    "expected_output": None,
    "notes": None,
    "created_at": "2026-01-01T00:00:00.000Z",
}

FIXTURE_SUITE = {
    "id": "suite_123",
    "tenant_id": "tenant_1",
    "name": "Refund Suite",
    "domain_key": "support",
    "intent_key": "refund",
    "dataset_id": "ds_123",
    "custom_scorer_expression": None,
    "custom_scorer_label": None,
    "custom_scorer_webhook_url": None,
    "custom_scorer_webhook_secret_set": False,
    "baseline_run_id": None,
    "created_at": "2026-01-01T00:00:00.000Z",
    "updated_at": "2026-01-01T00:00:00.000Z",
}

FIXTURE_RUN = {
    "id": "run_123",
    "tenant_id": "tenant_1",
    "suite_id": "suite_123",
    "domain_key": "support",
    "intent_key": "refund",
    "execution_mode": "liya_intent",
    "triggered_by": "api",
    "status": "pending",
    "stage": None,
    "progress": 0,
    "mean_score": None,
    "dimension_scores": None,
    "cases_total": 1,
    "cases_passed": 0,
    "started_at": "2026-01-01T00:00:00.000Z",
    "completed_at": None,
    "error": None,
    "judge_total_cost_usd": None,
    "judge_model": None,
    "judge_calls": None,
    "judge_failures": None,
    "judge_cap_reached": False,
    "model_override": None,
}


@pytest.fixture
def client():
    with LiyaEngine(api_key="liya_test_key", base_url=BASE_URL) as c:
        yield c


@respx.mock
def test_list_datasets(client):
    respx.get(f"{BASE_URL}/v1/evals/datasets").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"datasets": [FIXTURE_DATASET]}})
    )
    datasets = client.evaluations.datasets.list()
    assert len(datasets) == 1
    assert datasets[0].name == "Support Replies"


@respx.mock
def test_get_dataset_with_cases(client):
    respx.get(f"{BASE_URL}/v1/evals/datasets/ds_123").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"dataset": {**FIXTURE_DATASET, "cases": [FIXTURE_CASE]}}})
    )
    dataset = client.evaluations.datasets.get("ds_123")
    assert dataset.cases is not None
    assert len(dataset.cases) == 1


@respx.mock
def test_create_dataset(client):
    respx.post(f"{BASE_URL}/v1/evals/datasets").mock(
        return_value=httpx.Response(201, json={"success": True, "data": {"id": "ds_new", "name": "New Dataset", "description": None, "case_count": 0, "created_at": "2026-01-01T00:00:00.000Z"}})
    )
    created = client.evaluations.datasets.create(name="New Dataset")
    assert created.id == "ds_new"


@respx.mock
def test_update_and_delete_dataset(client):
    respx.patch(f"{BASE_URL}/v1/evals/datasets/ds_123").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"dataset": {**FIXTURE_DATASET, "name": "Renamed"}}})
    )
    updated = client.evaluations.datasets.update("ds_123", name="Renamed")
    assert updated.name == "Renamed"

    respx.delete(f"{BASE_URL}/v1/evals/datasets/ds_123").mock(return_value=httpx.Response(200, json={"success": True}))
    client.evaluations.datasets.delete("ds_123")


@respx.mock
def test_import_cases(client):
    respx.post(f"{BASE_URL}/v1/evals/datasets/ds_123/import").mock(
        return_value=httpx.Response(201, json={"success": True, "data": {"imported": 2}})
    )
    imported = client.evaluations.datasets.import_cases("ds_123", [{"input": {"q": "a"}}, {"input": {"q": "b"}}])
    assert imported == 2


@respx.mock
def test_list_and_clone_templates(client):
    respx.get(f"{BASE_URL}/v1/evals/datasets/templates").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"templates": [{"id": "tpl_1", "name": "Starter", "description": None, "case_count": 3, "example_cases": []}]}})
    )
    templates = client.evaluations.datasets.templates.list()
    assert len(templates) == 1

    respx.post(f"{BASE_URL}/v1/evals/datasets/templates/tpl_1/clone").mock(
        return_value=httpx.Response(201, json={"success": True, "data": {"dataset": {**FIXTURE_DATASET, "id": "ds_cloned"}}})
    )
    cloned = client.evaluations.datasets.templates.clone("tpl_1")
    assert cloned.id == "ds_cloned"


@respx.mock
def test_case_crud(client):
    respx.post(f"{BASE_URL}/v1/evals/datasets/ds_123/cases").mock(
        return_value=httpx.Response(201, json={"success": True, "data": {"case": FIXTURE_CASE}})
    )
    created = client.evaluations.cases.create("ds_123", input={"q": "hi"})
    assert created.id == "case_123"

    respx.patch(f"{BASE_URL}/v1/evals/cases/case_123").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"case": {**FIXTURE_CASE, "notes": "flagged"}}})
    )
    updated = client.evaluations.cases.update("case_123", notes="flagged")
    assert updated.notes == "flagged"

    respx.delete(f"{BASE_URL}/v1/evals/cases/case_123").mock(return_value=httpx.Response(200, json={"success": True}))
    client.evaluations.cases.delete("case_123")


@respx.mock
def test_suite_crud(client):
    respx.get(f"{BASE_URL}/v1/evals/suites").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"suites": [FIXTURE_SUITE]}})
    )
    suites = client.evaluations.suites.list()
    assert suites[0].custom_scorer_webhook_secret_set is False

    respx.post(f"{BASE_URL}/v1/evals/suites").mock(
        return_value=httpx.Response(201, json={"success": True, "data": {"suite": FIXTURE_SUITE}})
    )
    created = client.evaluations.suites.create(name="Refund Suite", domain_key="support", intent_key="refund", dataset_id="ds_123")
    assert created.id == "suite_123"

    respx.patch(f"{BASE_URL}/v1/evals/suites/suite_123").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"suite": {**FIXTURE_SUITE, "name": "Renamed Suite"}}})
    )
    updated = client.evaluations.suites.update("suite_123", name="Renamed Suite")
    assert updated.name == "Renamed Suite"

    respx.delete(f"{BASE_URL}/v1/evals/suites/suite_123").mock(return_value=httpx.Response(200, json={"success": True}))
    client.evaluations.suites.delete("suite_123")


@respx.mock
def test_set_baseline(client):
    respx.patch(f"{BASE_URL}/v1/evals/suites/suite_123/baseline").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"suite": {**FIXTURE_SUITE, "baseline_run_id": "run_123"}}})
    )
    suite = client.evaluations.suites.set_baseline("suite_123", "run_123")
    assert suite.baseline_run_id == "run_123"


@respx.mock
def test_run_suite_and_list_runs(client):
    respx.post(f"{BASE_URL}/v1/evals/suites/suite_123/run").mock(
        return_value=httpx.Response(202, json={"success": True, "data": {"run": FIXTURE_RUN}})
    )
    run = client.evaluations.suites.run("suite_123")
    assert run.status == "pending"

    respx.get(f"{BASE_URL}/v1/evals/suites/suite_123/runs").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"runs": [FIXTURE_RUN]}})
    )
    runs = client.evaluations.suites.list_runs("suite_123")
    assert len(runs) == 1


@respx.mock
def test_compare_models(client):
    respx.post(f"{BASE_URL}/v1/evals/suites/suite_123/compare-models").mock(
        return_value=httpx.Response(202, json={"success": True, "data": {
            "run_a": {**FIXTURE_RUN, "id": "run_a", "model_override": "gpt-4o-mini"},
            "run_b": {**FIXTURE_RUN, "id": "run_b", "model_override": "gpt-4o"},
        }})
    )
    result = client.evaluations.suites.compare_models("suite_123", "gpt-4o-mini", "gpt-4o")
    assert result["run_a"].model_override == "gpt-4o-mini"
    assert result["run_b"].model_override == "gpt-4o"


@respx.mock
def test_review_create_and_delete(client):
    respx.post(f"{BASE_URL}/v1/evals/results/result_1/reviews").mock(
        return_value=httpx.Response(201, json={"success": True, "data": {"review": {
            "id": "rev_1", "tenant_id": "tenant_1", "run_result_id": "result_1", "reviewer_id": "key_1",
            "verdict": "agree", "corrected_score": None, "note": None, "created_at": "2026-01-01T00:00:00.000Z",
        }}})
    )
    review = client.evaluations.reviews.create("result_1", verdict="agree")
    assert review.verdict == "agree"

    respx.delete(f"{BASE_URL}/v1/evals/reviews/rev_1").mock(return_value=httpx.Response(200, json={"success": True}))
    client.evaluations.reviews.delete("rev_1")


@respx.mock
def test_runs_list_submit_get(client):
    respx.get(f"{BASE_URL}/v1/evals/runs").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"runs": [FIXTURE_RUN]}})
    )
    runs = client.evaluations.runs.list()
    assert len(runs) == 1

    respx.post(f"{BASE_URL}/v1/evals/runs").mock(
        return_value=httpx.Response(202, json={"success": True, "data": {"run_id": "run_ext"}})
    )
    run_id = client.evaluations.runs.submit(cases=[{"input": {"q": "a"}, "output": "the answer"}])
    assert run_id == "run_ext"

    respx.get(f"{BASE_URL}/v1/evals/runs/run_123").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {
            "id": "run_123", "status": "completed", "stage": None, "progress": 100, "mean_score": 4.5,
            "dimension_scores": {"llm_coherence": 4.5}, "cases_total": 1, "cases_passed": 1,
            "started_at": "2026-01-01T00:00:00.000Z", "completed_at": "2026-01-01T00:01:00.000Z", "error": None,
            "results": [{"case_id": "case_123", "passed": True, "scores": [], "latency_ms": 100, "error": None}],
        }})
    )
    run = client.evaluations.runs.get("run_123")
    assert run["status"] == "completed"


@respx.mock
def test_get_run_raises_typed_404(client):
    respx.get(f"{BASE_URL}/v1/evals/runs/missing").mock(
        return_value=httpx.Response(404, json={"success": False, "error": {"code": "NOT_FOUND", "message": "not found"}})
    )
    with pytest.raises(LiyaEngineAPIError) as exc_info:
        client.evaluations.runs.get("missing")
    assert exc_info.value.code == "NOT_FOUND"


@respx.mock
def test_cancel_and_resume_run(client):
    respx.post(f"{BASE_URL}/v1/evals/runs/run_123/cancel").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"run": {**FIXTURE_RUN, "status": "cancelled"}}})
    )
    cancelled = client.evaluations.runs.cancel("run_123")
    assert cancelled.status == "cancelled"

    respx.post(f"{BASE_URL}/v1/evals/runs/run_123/resume").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"run": {**FIXTURE_RUN, "status": "pending"}}})
    )
    resumed = client.evaluations.runs.resume("run_123")
    assert resumed.status == "pending"


@respx.mock
def test_compare_and_compare_pairwise(client):
    respx.get(f"{BASE_URL}/v1/evals/runs/run_123/compare", params={"against": "run_456"}).mock(
        return_value=httpx.Response(200, json={"success": True, "data": {
            "comparison": {"run_a": {}, "run_b": {}, "score_delta": {}, "winner": "run_a", "summary": "Run A wins."},
            "run_a": {}, "run_b": {},
        }})
    )
    stat = client.evaluations.runs.compare("run_123", "run_456")
    assert stat["comparison"]["winner"] == "run_a"

    respx.post(f"{BASE_URL}/v1/evals/runs/run_123/compare-pairwise").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {
            "comparison": {"cases_compared": 1, "total_cost_usd": 0.001, "unmatched_cases": 0}, "run_a": {}, "run_b": {},
        }})
    )
    pairwise = client.evaluations.runs.compare_pairwise("run_123", "run_456")
    assert pairwise["comparison"]["cases_compared"] == 1


@respx.mock
def test_score(client):
    respx.post(f"{BASE_URL}/v1/evals/score").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"passed": True, "score": 4, "checks": [{"check_type": "llm_coherence", "passed": True, "judge_score": 4}]}})
    )
    result = client.evaluations.score(input={"q": "hi"}, output="hello there")
    assert result["passed"] is True
    assert result["score"] == 4
