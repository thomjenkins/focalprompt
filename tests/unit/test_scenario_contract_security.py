"""Output contract schemas must resolve offline only."""

import pytest

from utils.inference_scenario import (
    StructuredOutputError,
    validate_structured_response,
)


def _contract(schema):
    return {
        'type': 'json_schema',
        'name': 'contract',
        'strict': True,
        'schema': schema,
    }


@pytest.fixture
def no_retrieval(monkeypatch):
    """Fail loudly if anything reaches the network or the local filesystem."""
    calls = []

    def explode(*args, **kwargs):  # pragma: no cover - only runs on regression
        calls.append(args)
        raise AssertionError('structured validation attempted a remote retrieval')

    import urllib.request

    monkeypatch.setattr(urllib.request, 'urlopen', explode)
    monkeypatch.setattr(urllib.request, 'urlretrieve', explode)
    return calls


INTERNAL_REF_SCHEMA = {
    'type': 'object',
    'additionalProperties': False,
    'required': ['label', 'child'],
    'properties': {
        'label': {'$ref': '#/$defs/label'},
        'child': {'$ref': '#/$defs/node'},
    },
    '$defs': {
        'label': {'type': 'string', 'minLength': 1},
        'node': {
            'type': 'object',
            'additionalProperties': False,
            'required': ['label'],
            'properties': {'label': {'$ref': '#/$defs/label'}},
        },
    },
}


def test_internal_defs_refs_still_validate(no_retrieval):
    parsed = validate_structured_response(
        '{"label": "top", "child": {"label": "leaf"}}',
        _contract(INTERNAL_REF_SCHEMA),
    )
    assert parsed == {'label': 'top', 'child': {'label': 'leaf'}}
    assert no_retrieval == []


def test_internal_refs_reject_violations(no_retrieval):
    with pytest.raises(StructuredOutputError) as excinfo:
        validate_structured_response(
            '{"label": "top", "child": {"label": 7}}',
            _contract(INTERNAL_REF_SCHEMA),
        )
    assert 'child.label' in str(excinfo.value)
    assert no_retrieval == []


def test_self_id_anchored_refs_still_validate(no_retrieval):
    schema = {
        '$id': 'https://focalprompt.test/contract.json',
        'type': 'object',
        'required': ['value'],
        'properties': {'value': {'$ref': 'https://focalprompt.test/contract.json#/$defs/v'}},
        '$defs': {'v': {'type': 'integer'}},
    }
    assert validate_structured_response('{"value": 3}', _contract(schema)) == {'value': 3}
    assert no_retrieval == []


def test_external_http_ref_is_not_retrieved(no_retrieval):
    schema = {
        'type': 'object',
        'required': ['value'],
        'properties': {
            'value': {'$ref': 'https://focalprompt.invalid/remote-schema.json'},
        },
    }
    with pytest.raises(StructuredOutputError) as excinfo:
        validate_structured_response('{"value": {}}', _contract(schema))
    message = str(excinfo.value)
    assert 'focalprompt.invalid/remote-schema.json' in message
    assert no_retrieval == []


def test_external_file_ref_is_not_retrieved(tmp_path, no_retrieval):
    secret = tmp_path / 'secret.json'
    secret.write_text('{"type": "string"}', encoding='utf-8')
    schema = {
        'type': 'object',
        'required': ['value'],
        'properties': {'value': {'$ref': secret.as_uri()}},
    }
    with pytest.raises(StructuredOutputError):
        validate_structured_response('{"value": "x"}', _contract(schema))
    assert no_retrieval == []


def test_standard_format_checks_survive_offline_registry(no_retrieval):
    contract = _contract(
        {
            'type': 'object',
            'required': ['host'],
            'properties': {'host': {'type': 'string', 'format': 'ipv4'}},
        }
    )
    assert validate_structured_response('{"host": "10.0.0.1"}', contract) == {
        'host': '10.0.0.1'
    }
    with pytest.raises(StructuredOutputError, match='does not match output_contract'):
        validate_structured_response('{"host": "not-an-address"}', contract)
    assert no_retrieval == []

