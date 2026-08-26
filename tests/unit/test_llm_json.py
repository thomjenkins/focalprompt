"""Tests for LLM JSON extraction (markdown fences, nested objects)."""

import pytest

from utils.llm_json import parse_llm_json


def test_plain_json():
    assert parse_llm_json('{"a": 1}') == {'a': 1}


def test_markdown_fenced_nested():
    content = '''```json
{
  "foci": [
    {"focus": "Role", "score": 40, "explanation": "x"}
  ],
  "overall_summary": "ok"
}
```'''
    result = parse_llm_json(content)
    assert result['foci'][0]['focus'] == 'Role'
    assert result['overall_summary'] == 'ok'


def test_prose_wrapper():
    content = 'Here is the result:\n{"foci": [], "overall_summary": "none"}\nThanks'
    assert parse_llm_json(content)['overall_summary'] == 'none'


def test_empty_raises():
    with pytest.raises(ValueError, match='Empty'):
        parse_llm_json('')


def test_truncated_json_mentions_truncation():
    truncated = (
        '{\n  "foci": [\n    {\n      "focus": "Role",\n'
        '      "prompt_section": "You are an AI assistant designed to help veterinary'
    )
    with pytest.raises(ValueError, match='truncat|incomplete'):
        parse_llm_json(truncated)
