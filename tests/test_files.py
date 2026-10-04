import json

import httpx
import respx

from liyaengine import LiyaEngine, ParsedFile

BASE_URL = "https://api.test.liyaengine.ai"


@respx.mock
def test_parse_returns_text_and_sends_snake_case_fields():
    route = respx.post(f"{BASE_URL}/v1/files/parse").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {
            "file_name": "acord.png", "format": "image", "text": "Insured: Harbor Foods",
            "warnings": [], "transcribed_pages": [1],
        }})
    )
    with LiyaEngine(api_key="liya_test_key", base_url=BASE_URL) as client:
        parsed = client.files.parse(file_name="acord.png", file_base64="iVBORw0K")

    assert json.loads(route.calls[0].request.content) == {"file_name": "acord.png", "file_base64": "iVBORw0K"}
    assert isinstance(parsed, ParsedFile)
    assert parsed.text == "Insured: Harbor Foods"
    assert parsed.transcribed_pages == [1]
    assert parsed.pages is None
