from app.routes.chat import _ensure_structured, _determine_asset
from app.models import UIComponent


def test_ensure_structured_parses_code_fenced_json():
    raw = """```json
    {"summary": "hello", "responses": [{"type": "text", "content": "world"}]}
    ```"""

    structured = _ensure_structured(raw)

    assert structured.summary == "hello"
    assert structured.responses[0].type == "text"
    assert structured.responses[0].content == "world"


def test_ensure_structured_handles_json_prefix_without_fence():
    raw = 'json {"summary": "prefix", "responses": [{"type": "text", "content": "ok"}]}'

    structured = _ensure_structured(raw)

    assert structured.summary == "prefix"
    assert structured.responses[0].content == "ok"


def test_ensure_structured_fallback_strips_fences():
    raw = """```json
    this is not json at all
    ```"""

    structured = _ensure_structured(raw)

    assert structured.summary == "this is not json at all"
    assert structured.responses[0].content == "this is not json at all"


def test_ensure_structured_allows_specialized_components():
    raw = (
        '{"summary": "btc intel", '
        '"responses": ['
        '{"type": "asset_intel", "content": "intel", "data": {"asset": "BTC"}}'
        "]}"
    )

    structured = _ensure_structured(raw)

    assert structured.summary == "btc intel"
    assert structured.responses[0].type == "asset_intel"
    assert structured.responses[0].data == {"asset": "BTC"}


def test_determine_asset_extracts_from_content():
    component = UIComponent(type="asset_intel", content="Here's a quick read on Ethereum (ETH).")
    assert _determine_asset(component) == "eth"
