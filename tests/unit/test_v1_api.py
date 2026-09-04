"""Remove key-creation SaaS test; keep analytical v1 smoke tests."""

import pytest
from unittest.mock import Mock, patch

from utils.inference_scenario import ProviderCapabilityError


@pytest.fixture
def client():
    from app_new import app
    app.config['TESTING'] = True
    return app.test_client()


def test_v1_root(client):
    r = client.get('/api/v1')
    assert r.status_code == 200
    data = r.get_json()
    assert data.get('version') == 1
    assert data.get('documentation') == '/api/v1/openapi.json'
    assert 'keys' not in (data.get('endpoints') or {})


def test_v1_openapi_json(client):
    r = client.get('/api/v1/openapi.json')
    assert r.status_code == 200
    data = r.get_json()
    assert 'openapi' in data
    assert data.get('info', {}).get('title') == 'FocalPrompt API'


def test_v1_assess_not_found_if_wrong_path(client):
    r = client.post('/api/v1/assess', json={})
    assert r.status_code == 400


def test_v1_keys_gone(client):
    r = client.post('/api/v1/keys', json={})
    assert r.status_code == 404


def test_v1_generate_accepts_scenario_and_rejects_two_sources(client):
    scenario = {
        'version': 1,
        'messages': [
            {'id': 'user', 'role': 'user', 'content': 'hello', 'analysis_mode': 'analyse'}
        ],
    }
    assessor = Mock()
    assessor.provider_name = 'openai'
    assessor.generate_output_response.return_value = {
        'content': 'response', 'scenario_metadata': {'scenario_version': 1}
    }
    with patch('routes.assessment_routes.get_assessor', return_value=assessor):
        response = client.post('/api/v1/generate-output', json={'scenario': scenario})
    assert response.status_code == 200
    assert response.get_json()['output'] == 'response'

    response = client.post(
        '/api/v1/generate-output', json={'scenario': scenario, 'prompt': 'legacy'}
    )
    assert response.status_code == 400
    assert 'exactly one' in response.get_json()['error']


def test_v1_openapi_documents_scenario_contract(client):
    spec = client.get('/api/v1/openapi.json').get_json()
    schemas = spec['components']['schemas']
    assert 'InferenceScenario' in schemas
    assert schemas['OutputContract']['properties']['strict']['enum'] == [True]
    assert schemas['FocusSpan']['required'] == [
        'message_id', 'char_start', 'char_end', 'text_snapshot'
    ]


def test_v1_generate_surfaces_structured_output_capability_error(client):
    scenario = {
        'version': 1,
        'messages': [
            {'id': 'user', 'role': 'user', 'content': 'hello', 'analysis_mode': 'analyse'}
        ],
        'output_contract': {
            'type': 'json_schema', 'name': 'answer', 'strict': True,
            'schema': {'type': 'object'},
        },
    }
    assessor = Mock()
    assessor.generate_output_response.side_effect = ProviderCapabilityError(
        'provider cannot express required structured output contract'
    )
    with patch('routes.assessment_routes.get_assessor', return_value=assessor):
        response = client.post('/api/v1/generate-output', json={'scenario': scenario})
    assert response.status_code == 422
    assert response.get_json()['code'] == 'inference_contract_error'
    assert 'structured output contract' in response.get_json()['error']
