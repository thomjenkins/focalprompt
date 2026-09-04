"""Provider failures remain actionable at the HTTP/UI boundary."""

from unittest.mock import Mock, patch

import pytest


@pytest.fixture
def client():
    from app_new import app

    app.config['TESTING'] = True
    return app.test_client()


class BadRequestError(Exception):
    status_code = 400
    body = {
        'message': (
            "Unsupported value: 'temperature' does not support 0.3 with this model. "
            'Only the default (1) value is supported.'
        ),
        'type': 'invalid_request_error',
        'param': 'temperature',
        'code': 'unsupported_value',
    }


def test_detect_foci_surfaces_provider_parameter_error(client):
    assessor = Mock()
    with (
        patch('routes.assessment_routes.get_assessor', return_value=assessor),
        patch(
            'routes.assessment_routes.AssessmentService.detect_foci_scenario',
            side_effect=BadRequestError(),
        ),
    ):
        response = client.post('/api/detect-foci', json={'prompt': 'hello'})

    assert response.status_code == 422
    body = response.get_json()
    assert body['code'] == 'provider_request_error'
    assert body['route_code'] == 'assessment_detect_foci'
    assert body['provider_error'] == {
        'type': 'invalid_request_error',
        'code': 'unsupported_value',
        'param': 'temperature',
        'status': 400,
    }
    assert "Unsupported value: 'temperature'" in body['error']


def test_quality_evaluation_surfaces_provider_parameter_error(client):
    assessor = Mock()
    assessor.provider_name = 'openai'
    error = BadRequestError()
    error.body = {
        'message': (
            "Unsupported parameter: 'max_tokens' is not supported with this model. "
            "Use 'max_completion_tokens' instead."
        ),
        'type': 'invalid_request_error',
        'param': 'max_tokens',
        'code': 'unsupported_parameter',
    }
    with (
        patch('routes.evaluation_routes.get_assessor', return_value=assessor),
        patch(
            'routes.evaluation_routes.OutputQualityEvaluator.evaluate_outputs',
            side_effect=error,
        ),
    ):
        response = client.post('/api/evaluate-outputs-quality', json={
            'eval_criteria': 'Be useful',
            'outputs': [{'output': 'hello'}],
        })

    assert response.status_code == 422
    body = response.get_json()
    assert "Unsupported parameter: 'max_tokens'" in body['error']
    assert body['provider_error']['param'] == 'max_tokens'


def test_unknown_internal_error_remains_private(client):
    secret = 'private-database-detail'
    with patch(
        'routes.assessment_routes.get_assessor',
        side_effect=RuntimeError(secret),
    ):
        response = client.post('/api/detect-foci', json={'prompt': 'hello'})

    assert response.status_code == 500
    assert response.get_json()['error'] == 'internal error'
    assert secret not in response.get_data(as_text=True)


def test_provider_message_redacts_api_keys(client):
    error = BadRequestError('')
    error.body = {
        **BadRequestError.body,
        'message': 'Invalid api_key=sk-example-secret-value for this request',
    }
    with patch(
        'routes.assessment_routes.get_assessor',
        side_effect=error,
    ):
        response = client.post('/api/detect-foci', json={'prompt': 'hello'})

    text = response.get_data(as_text=True)
    assert response.status_code == 422
    assert '[redacted]' in text
    assert 'sk-example-secret-value' not in text
