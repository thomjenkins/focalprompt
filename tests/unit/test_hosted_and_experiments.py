"""Hosted demo gate and experiment pages."""

import json
from pathlib import Path

import pytest


@pytest.fixture
def client():
    from app_new import app
    app.config['TESTING'] = True
    return app.test_client()


def test_lab_and_experiments(client):
    r = client.get('/lab')
    assert r.status_code == 200

    r = client.get('/experiments')
    assert r.status_code == 200

    r = client.get('/experiments/vet-triage-reported-vs-revealed')
    assert r.status_code == 200
    assert b'JSON schema' in r.data


def test_canonical_json_loads():
    path = Path('examples/canonical/vet-triage-reported-vs-revealed.json')
    data = json.loads(path.read_text())
    assert data['id'] == 'vet-triage-reported-vs-revealed'
    assert 'comparison' in data
    assert len(data['comparison']['rows']) >= 3


def test_hosted_mode_helpers(monkeypatch):
    from utils import hosted_mode as hm

    monkeypatch.setenv('FOCALPROMPT_HOSTED_MODE', '1')
    monkeypatch.delenv('FOCALPROMPT_ALLOW_LIVE_INFERENCE', raising=False)
    assert hm.is_hosted_mode() is True
    assert hm.allow_live_inference() is False
    ok, err = hm.check_live_allowed('1.2.3.4')
    assert ok is False
    assert err['code'] == 'live_disabled'

    monkeypatch.setenv('FOCALPROMPT_ALLOW_LIVE_INFERENCE', '1')
    assert hm.allow_live_inference() is True
    ok, err = hm.check_live_allowed('1.2.3.4')
    assert ok is True


def test_before_request_gate(client, monkeypatch):
    monkeypatch.setattr(
        'app_new.check_live_allowed',
        lambda *_a, **_k: (False, {'error': 'blocked', 'code': 'live_disabled'}),
    )
    monkeypatch.setattr('app_new.path_requires_live', lambda path: path.startswith('/api/detect-foci'))
    r = client.post('/api/detect-foci', json={'prompt': 'hello'})
    assert r.status_code == 503
    assert r.get_json()['code'] == 'live_disabled'
