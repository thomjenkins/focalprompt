"""Hosted demo gate and experiment pages."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def client():
    from app_new import app
    app.config['TESTING'] = True
    return app.test_client()


def _request(headers=None, remote_addr='10.0.0.1'):
    return SimpleNamespace(
        headers=headers or {},
        remote_addr=remote_addr,
    )


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


def test_resolve_client_ip_local_uses_remote_addr(monkeypatch):
    from utils import hosted_mode as hm

    monkeypatch.delenv('FOCALPROMPT_HOSTED_MODE', raising=False)
    req = _request(
        headers={'X-Forwarded-For': '203.0.113.9, 198.51.100.1'},
        remote_addr='192.168.1.5',
    )
    assert hm.resolve_client_ip(req) == '192.168.1.5'


def test_resolve_client_ip_hosted_prefers_vercel_header(monkeypatch):
    from utils import hosted_mode as hm

    monkeypatch.setenv('FOCALPROMPT_HOSTED_MODE', '1')
    req = _request(
        headers={
            'x-vercel-forwarded-for': '  203.0.113.9 , 198.51.100.1',
            'X-Forwarded-For': '1.2.3.4',
        },
        remote_addr='10.0.0.1',
    )
    assert hm.resolve_client_ip(req) == '203.0.113.9'


def test_resolve_client_ip_hosted_falls_back_to_xff(monkeypatch):
    from utils import hosted_mode as hm

    monkeypatch.setenv('FOCALPROMPT_HOSTED_MODE', '1')
    req = _request(
        headers={'X-Forwarded-For': '198.51.100.2, 10.0.0.99'},
        remote_addr='10.0.0.1',
    )
    assert hm.resolve_client_ip(req) == '198.51.100.2'


def test_hosted_cors_origins_branch(monkeypatch):
    from utils import hosted_mode as hm

    monkeypatch.delenv('FOCALPROMPT_HOSTED_MODE', raising=False)
    assert hm.hosted_cors_origins() is None

    monkeypatch.setenv('FOCALPROMPT_HOSTED_MODE', '1')
    monkeypatch.delenv('FOCALPROMPT_ALLOWED_ORIGINS', raising=False)
    assert hm.hosted_cors_origins() == ['https://focalprompt.com']

    monkeypatch.setenv(
        'FOCALPROMPT_ALLOWED_ORIGINS',
        'https://focalprompt.com, https://staging.focalprompt.com',
    )
    assert hm.hosted_cors_origins() == [
        'https://focalprompt.com',
        'https://staging.focalprompt.com',
    ]


def test_route_500_hides_exception_text(client, monkeypatch):
    from services import cost_calculator as cc

    secret = 'super-secret-gateway-failure-detail-xyz'
    monkeypatch.setattr(
        cc.CostCalculator,
        'calculate_cost',
        staticmethod(lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError(secret))),
    )
    r = client.post(
        '/api/pricing/estimate',
        json={
            'model': 'gpt-4o-mini',
            'provider': 'openai',
            'estimated_input_tokens': 100,
            'estimated_output_tokens': 50,
        },
    )
    assert r.status_code == 500
    body = r.get_json()
    assert body['error'] == 'internal error'
    assert body['code'] == 'pricing_estimate'
    assert secret not in r.get_data(as_text=True)


def test_before_request_gate(client, monkeypatch):
    monkeypatch.setattr(
        'app_new.check_live_allowed',
        lambda *_a, **_k: (False, {'error': 'blocked', 'code': 'live_disabled'}),
    )
    monkeypatch.setattr('app_new.path_requires_live', lambda path: path.startswith('/api/detect-foci'))
    r = client.post('/api/detect-foci', json={'prompt': 'hello'})
    assert r.status_code == 503
    assert r.get_json()['code'] == 'live_disabled'
