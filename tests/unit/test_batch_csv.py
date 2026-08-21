"""Unit tests for deterministic batch CSV parsing."""

from __future__ import annotations

import pytest

from utils.batch_csv import (
    MAX_CSV_ROWS,
    parse_batch_csv_bytes,
    parse_result_to_response,
)


def _parse(text: str) -> tuple:
    result = parse_batch_csv_bytes(text.encode('utf-8'))
    body, status = parse_result_to_response(result)
    return result, body, status


def test_valid_minimal_csv():
    _, body, status = _parse('input,output\nhello,world\n')
    assert status == 200
    assert len(body['pairs']) == 1
    assert body['pairs'][0]['inputs']['chat_content'] == 'hello'
    assert body['pairs'][0]['output'] == 'world'
    assert body['count'] == 1


def test_multiple_rows():
    csv = 'chat_content,suggested_message\na,1\nb,2\nc,3\n'
    _, body, status = _parse(csv)
    assert status == 200
    assert body['count'] == 3
    assert [p['inputs']['chat_content'] for p in body['pairs']] == ['a', 'b', 'c']


def test_prompt_containing_commas():
    _, body, status = _parse('input,output\n"hello, world",ok\n')
    assert status == 200
    assert body['pairs'][0]['inputs']['chat_content'] == 'hello, world'


def test_prompt_containing_quoted_strings():
    _, body, status = _parse('prompt,output\n"Say ""hello"" then stop",ok\n')
    assert status == 200
    assert body['pairs'][0]['prompt'] == 'Say "hello" then stop'


def test_multiline_prompt():
    _, body, status = _parse('prompt,output\n"line1\nline2\nline3",ok\n')
    assert status == 200
    assert body['pairs'][0]['prompt'] == 'line1\nline2\nline3'


def test_literal_backslash_n_preserved():
    _, body, status = _parse('prompt,output\n"a\\nb",ok\n')
    assert status == 200
    assert body['pairs'][0]['prompt'] == 'a\\nb'
    assert '\n' not in body['pairs'][0]['prompt']


def test_actual_newline_in_quoted_field():
    _, body, status = _parse('prompt,output\n"a\nb",ok\n')
    assert status == 200
    assert body['pairs'][0]['prompt'] == 'a\nb'


def test_unicode():
    _, body, status = _parse('input,output\ncafé 日本語 🐾,ответ\n')
    assert status == 200
    assert body['pairs'][0]['inputs']['chat_content'] == 'café 日本語 🐾'
    assert body['pairs'][0]['output'] == 'ответ'


def test_bom():
    raw = 'input,output\nx,y\n'.encode('utf-8-sig')
    result = parse_batch_csv_bytes(raw)
    body, status = parse_result_to_response(result)
    assert status == 200
    assert body['pairs'][0]['inputs']['chat_content'] == 'x'


def test_blank_rows_skipped():
    # Empty physical lines AND empty-field rows
    result, body, status = _parse('input,output\na,1\n\n,\n\nb,2\n')
    assert status == 200
    assert len(body['pairs']) == 2
    assert any('blank' in w.lower() for w in result.warnings)


def test_malformed_csv():
    result, body, status = _parse('input,output\n"unclosed,ok\n')
    assert status == 400
    joined = ' '.join(result.errors) + body.get('error', '')
    assert 'malformed' in joined.lower() or 'error' in joined.lower()


def test_missing_required_columns():
    _, body, status = _parse('foo,bar\n1,2\n')
    assert status == 400
    assert 'Missing' in body['error'] or any('Missing' in e for e in body['errors'])


def test_missing_output_column():
    _, body, status = _parse('input\nhello\n')
    assert status == 400
    assert 'output' in body['error'].lower()


def test_empty_csv():
    _, body, status = _parse('')
    assert status == 400
    assert 'empty' in body['error'].lower()


def test_header_only():
    _, body, status = _parse('input,output\n')
    assert status == 400


def test_dynamic_input_columns():
    csv = (
        'chat_content,rag_context,tool_results,other_input,output\n'
        'chat,rag,tools,other,out\n'
    )
    _, body, status = _parse(csv)
    assert status == 200
    inp = body['pairs'][0]['inputs']
    assert inp['chat_content'] == 'chat'
    assert inp['rag_context'] == 'rag'
    assert inp['tool_results'] == 'tools'
    assert inp['other_input'] == 'other'


def test_prompt_whitespace_not_normalized():
    _, body, status = _parse('prompt,output\n"  keep  spaces  \\tand\\ttabs  ",ok\n')
    assert status == 200
    assert body['pairs'][0]['prompt'] == '  keep  spaces  \\tand\\ttabs  '


def test_row_missing_output_reports_error_keeps_valid():
    result, body, status = _parse('input,output\nok,yes\nbad,\n')
    assert status == 200
    assert len(body['pairs']) == 1
    assert any('missing required output' in e.lower() for e in result.errors)


def test_prompt_only_rows_without_input_columns():
    _, body, status = _parse('prompt,output\n"You are helpful.",answer\n')
    assert status == 200
    assert body['pairs'][0]['prompt'] == 'You are helpful.'
    assert body['pairs'][0]['output'] == 'answer'


def test_row_limit_exceeded(monkeypatch):
    monkeypatch.setattr('utils.batch_csv.MAX_CSV_ROWS', 2)
    _, body, status = _parse('input,output\na,1\nb,2\nc,3\n')
    assert status == 400
    assert 'maximum' in body['error'].lower()


def test_parsed_pairs_usable_as_batch_payload():
    """Response pairs can be passed to batch analysis after attaching prompt."""
    _, body, status = _parse('input,output\nuser hi,assistant bye\n')
    assert status == 200
    pairs = body['pairs']
    for p in pairs:
        assert 'inputs' in p and 'output' in p
        p['prompt'] = 'System prompt for ablation.'
    assert pairs[0]['prompt'] == 'System prompt for ablation.'
    assert pairs[0]['inputs']['chat_content'] == 'user hi'
