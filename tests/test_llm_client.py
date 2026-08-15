import pytest

from packages.llm.client import LLMClient, LLMResponseError, LLMUnavailableError, _parse_json_block


def test_client_unavailable_without_api_key():
    client = LLMClient(api_key="")
    assert not client.is_available()


def test_complete_json_raises_when_unavailable():
    client = LLMClient(api_key="")
    with pytest.raises(LLMUnavailableError):
        client.complete_json("system", "user")


def test_parse_json_block_plain():
    assert _parse_json_block('[{"a": 1}]') == [{"a": 1}]


def test_parse_json_block_fenced_with_language_tag():
    text = '```json\n[{"a": 1}]\n```'
    assert _parse_json_block(text) == [{"a": 1}]


def test_parse_json_block_fenced_without_language_tag():
    text = '```\n{"a": 1}\n```'
    assert _parse_json_block(text) == {"a": 1}


def test_parse_json_block_invalid_raises_response_error():
    with pytest.raises(LLMResponseError):
        _parse_json_block("this is not json")
