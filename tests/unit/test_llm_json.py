"""Tests for LLM JSON extraction (markdown fences, nested objects)."""

import pytest

from utils.llm_json import (
    parse_assessment_json,
    parse_llm_json,
    recover_assessment_foci,
    strip_prompt_section_fields,
)


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


def test_strip_prompt_section_fields_complete_and_truncated():
    complete = '{"focus":"Role","prompt_section":"long text here","score":10}'
    assert '"prompt_section"' not in strip_prompt_section_fields(complete)
    assert '"score":10' in strip_prompt_section_fields(complete)

    truncated = (
        '{\n  "foci": [\n    {\n      "focus": "Role",\n'
        '      "prompt_section": "You are an AI assistant designed to help veterinary'
    )
    stripped = strip_prompt_section_fields(truncated)
    assert 'You are an AI assistant' not in stripped
    assert '"focus": "Role"' in stripped


def test_recover_and_parse_assessment_json_from_truncated_echo():
    """Classic production failure: model pastes Role span and hits output cap."""
    truncated = (
        '{\n  "foci": [\n'
        '    {\n'
        '      "focus": "Role",\n'
        '      "prompt_section": "You are an AI assistant designed to help veterinary '
        'teams provide informative, empathetic, and professional responses to queries fro'
    )
    # Pure truncation with no completed scores cannot recover — must raise
    with pytest.raises(ValueError):
        parse_assessment_json(truncated)

    # Truncated after one complete focus + mid prompt_section on the next
    salvageable = (
        '{\n  "foci": [\n'
        '    {"focus": "Tone", "score": 30.0, "explanation": "Warm tone."},\n'
        '    {\n'
        '      "focus": "Role",\n'
        '      "prompt_section": "You are an AI assistant designed to help veterinary '
        'teams provide informative, empathetic, and professional responses to queries fro'
    )
    recovered = recover_assessment_foci(salvageable)
    assert recovered is not None
    assert recovered['foci'][0]['focus'] == 'Tone'
    assert recovered['foci'][0]['score'] == 30.0

    parsed = parse_assessment_json(salvageable)
    assert parsed['foci'][0]['focus'] == 'Tone'
    assert 'prompt_section' not in parsed['foci'][0]


def test_parse_assessment_json_strips_residual_prompt_section():
    raw = (
        '{"foci":[{"focus":"Role","prompt_section":"long","score":100,'
        '"explanation":"ok"}],"overall_summary":"done"}'
    )
    result = parse_assessment_json(raw)
    assert result['foci'][0]['score'] == 100
    assert 'prompt_section' not in result['foci'][0]
