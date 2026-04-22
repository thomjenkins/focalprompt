"""Smoke tests for /api/v1 surface and OpenAPI route."""

import pytest


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


def test_v1_openapi_json(client):
    r = client.get('/api/v1/openapi.json')
    assert r.status_code == 200
    data = r.get_json()
    assert 'openapi' in data
    assert data.get('info', {}).get('title') == 'FocalPrompt API'


def test_v1_assess_not_found_if_wrong_path(client):
    r = client.post('/api/v1/assess', json={})
    assert r.status_code == 400


def test_create_key_requires_session(client):
    r = client.post('/api/v1/keys', json={})
    assert r.status_code == 401
