import json

import httpx
import pytest
import respx

from liyaengine import LiyaEngine, LiyaEngineAPIError

BASE_URL = "https://api.test.liyaengine.ai"


@pytest.fixture
def client():
    with LiyaEngine(api_key="liya_test_key", base_url=BASE_URL) as c:
        yield c


def _ok(already=False):
    return httpx.Response(201, json={"success": True, "data": {
        "correction_id": "cor_1", "already_recorded": already, "note": None,
        "passages": [
            {"document_id": "doc1", "file_name": "shipping.pdf", "rank": 1, "attribution": "passage", "counted": True, "flagged": True},
            {"document_id": "doc2", "file_name": None, "rank": 2, "attribution": "document_only", "counted": False, "flagged": False},
            {"document_id": "doc3", "file_name": "returns.md", "rank": 3, "attribution": "lower_ranked", "counted": False, "flagged": False},
        ],
    }})


@respx.mock
def test_report_sends_the_wire_fields_and_reads_the_result(client):
    route = respx.post(f"{BASE_URL}/v1/corrections").mock(return_value=_ok())
    out = client.corrections.report(message_id="msg_1", correct_answer="Free over $75.", note="thumbs down", end_user_id="u_9")
    assert json.loads(route.calls.last.request.content) == {"message_id": "msg_1", "correct_answer": "Free over $75.", "note": "thumbs down", "end_user_id": "u_9"}
    assert out.correction_id == "cor_1" and out.already_recorded is False and out.note is None
    assert (out.passages[0].document_id, out.passages[0].attribution, out.passages[0].counted, out.passages[0].flagged) == ("doc1", "passage", True, True)
    assert out.passages[1].attribution == "document_only" and out.passages[1].counted is False
    assert (out.passages[2].rank, out.passages[2].attribution, out.passages[2].counted) == (3, "lower_ranked", False)


@respx.mock
def test_report_leaves_out_optional_fields_when_not_given(client):
    route = respx.post(f"{BASE_URL}/v1/corrections").mock(return_value=_ok(already=True))
    out = client.corrections.report(message_id="msg_1", correct_answer="Right")
    assert json.loads(route.calls.last.request.content) == {"message_id": "msg_1", "correct_answer": "Right"}
    assert out.already_recorded is True


@respx.mock
def test_an_unknown_answer_raises_a_typed_error(client):
    respx.post(f"{BASE_URL}/v1/corrections").mock(return_value=httpx.Response(404, json={"success": False, "error": {"code": "MESSAGE_NOT_FOUND", "message": "none"}}))
    with pytest.raises(LiyaEngineAPIError) as e:
        client.corrections.report(message_id="msg_gone", correct_answer="Right")
    assert e.value.code == "MESSAGE_NOT_FOUND" and e.value.status == 404


@respx.mock
def test_report_names_an_agent_run_by_run_id_and_refuses_both_or_neither(client):
    route = respx.post(f"{BASE_URL}/v1/corrections").mock(return_value=_ok())
    client.corrections.report(run_id="run_7", correct_answer="Right")
    assert json.loads(route.calls.last.request.content) == {"run_id": "run_7", "correct_answer": "Right"}
    with pytest.raises(ValueError):
        client.corrections.report(message_id="m", run_id="r", correct_answer="x")
    with pytest.raises(ValueError):
        client.corrections.report(correct_answer="x")


@respx.mock
def test_delete_erases_a_correction(client):
    respx.delete(f"{BASE_URL}/v1/corrections/cor_1").mock(return_value=httpx.Response(200, json={"success": True, "data": {"deleted": True, "already_deleted": False}}))
    assert client.corrections.delete("cor_1") == {"deleted": True, "already_deleted": False}
