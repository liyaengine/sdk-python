import json

import httpx
import pytest
import respx

from liyaengine import LiyaEngine, LiyaEngineAPIError

BASE_URL = "https://api.test.liyaengine.ai"
ROW = {"rollback_mode": "off", "limit_mode": "off", "answer_checks_enabled": False, "answer_check_sample_pct": 5, "answer_check_daily_cap_usd": 5, "updated_at": None, "updated_by": None}


@pytest.fixture
def client():
    return LiyaEngine(api_key="liya_test_key", base_url=BASE_URL)


@respx.mock
def test_settings_reads_the_defaults(client):
    respx.get(f"{BASE_URL}/v1/healing/settings").mock(return_value=httpx.Response(200, json={"success": True, "data": {"settings": ROW}}))
    out = client.healing.settings()
    assert out["rollback_mode"] == "off" and out["answer_checks_enabled"] is False


@respx.mock
def test_update_settings_sends_only_the_fields_given(client):
    route = respx.put(f"{BASE_URL}/v1/healing/settings").mock(return_value=httpx.Response(200, json={"success": True, "data": {"settings": {**ROW, "rollback_mode": "stage"}}}))
    out = client.healing.update_settings(rollback_mode="stage", answer_check_daily_cap_usd=8)
    assert json.loads(route.calls.last.request.content) == {"rollback_mode": "stage", "answer_check_daily_cap_usd": 8}
    assert out["rollback_mode"] == "stage"


@respx.mock
def test_update_settings_raises_a_typed_error_for_a_value_out_of_range(client):
    respx.put(f"{BASE_URL}/v1/healing/settings").mock(return_value=httpx.Response(400, json={"success": False, "error": {"code": "INVALID_SETTINGS", "message": "out of range"}}))
    with pytest.raises(LiyaEngineAPIError) as exc_info:
        client.healing.update_settings(answer_check_sample_pct=90)
    assert exc_info.value.code == "INVALID_SETTINGS"


@respx.mock
def test_answer_checks_passes_the_window(client):
    route = respx.get(f"{BASE_URL}/v1/healing/answer-checks").mock(return_value=httpx.Response(200, json={"success": True, "data": {"window_days": 14, "checked": 50, "unsupported_rate": 8, "examples": []}}))
    out = client.healing.answer_checks(days=14)
    assert route.calls.last.request.url.params["days"] == "14" and out["checked"] == 50
