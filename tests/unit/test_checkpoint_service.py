"""
Unit tests for CheckpointService path-traversal hardening.
"""

import json
import os
import shutil
import tempfile

import pytest
from flask import Flask

from routes.batch_routes import batch_bp
from services.checkpoint_service import (
    ALLOWED_CHECKPOINT_TYPES,
    CheckpointService,
    validate_checkpoint_identifiers,
)


@pytest.fixture
def temp_checkpoint_dir():
    """Create a temporary checkpoint directory."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def client(temp_checkpoint_dir, monkeypatch):
    """Flask test client with checkpoints rooted in a temp dir."""
    monkeypatch.setenv('CHECKPOINT_DIR', temp_checkpoint_dir)

    def _factory(checkpoint_dir=None):
        return CheckpointService(checkpoint_dir=checkpoint_dir or temp_checkpoint_dir)

    monkeypatch.setattr('routes.batch_routes.CheckpointService', _factory)
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.register_blueprint(batch_bp)
    return app.test_client()


def test_save_and_load_checkpoint(temp_checkpoint_dir):
    """Test saving and loading a checkpoint."""
    service = CheckpointService(checkpoint_dir=temp_checkpoint_dir)

    test_data = {
        'session_id': 'test123',
        'data': 'test data',
        'complete': False,
    }

    success = service.save_checkpoint('test123', test_data, 'batch_analysis')
    assert success

    loaded = service.load_checkpoint('test123', 'batch_analysis')
    assert loaded is not None
    assert loaded['session_id'] == 'test123'
    assert loaded['data'] == 'test data'


def test_list_checkpoints(temp_checkpoint_dir):
    """Test listing checkpoints."""
    service = CheckpointService(checkpoint_dir=temp_checkpoint_dir)

    for i in range(3):
        service.save_checkpoint(f'session{i}', {'data': f'test{i}'}, 'batch_analysis')

    checkpoints = service.list_checkpoints('batch_analysis')
    assert len(checkpoints) == 3


def test_delete_checkpoint(temp_checkpoint_dir):
    """Test deleting a checkpoint."""
    service = CheckpointService(checkpoint_dir=temp_checkpoint_dir)

    service.save_checkpoint('test123', {'data': 'test'}, 'batch_analysis')

    deleted = service.delete_checkpoint('test123', 'batch_analysis')
    assert deleted

    loaded = service.load_checkpoint('test123', 'batch_analysis')
    assert loaded is None


@pytest.mark.parametrize(
    'session_id',
    [
        '../x',
        '..%2Fx',
        '/etc/passwd',
        '',
        'a' * 65,
        'has space',
        'dot.dot',
        'semi;colon',
        '..',
        '../',
        'foo/bar',
        'foo\\bar',
        'x' * 100,
    ],
)
def test_rejects_unsafe_session_ids(temp_checkpoint_dir, session_id):
    service = CheckpointService(checkpoint_dir=temp_checkpoint_dir)
    with pytest.raises(ValueError) as exc:
        service.get_checkpoint_path(session_id, 'batch_analysis')
    # Must not echo the rejected value back to callers.
    assert session_id == '' or session_id not in str(exc.value)


@pytest.mark.parametrize('session_id', ['ok', 'a', 'A-Z_0-9', 'x' * 64, '20240101_120000'])
def test_accepts_valid_session_ids(temp_checkpoint_dir, session_id):
    service = CheckpointService(checkpoint_dir=temp_checkpoint_dir)
    path = service.get_checkpoint_path(session_id, 'batch_analysis')
    assert path.endswith(f'batch_analysis_{session_id}.json')
    assert os.path.commonpath([temp_checkpoint_dir, path]) == os.path.realpath(temp_checkpoint_dir)


def test_rejects_unknown_checkpoint_type(temp_checkpoint_dir):
    service = CheckpointService(checkpoint_dir=temp_checkpoint_dir)
    with pytest.raises(ValueError) as exc:
        service.get_checkpoint_path('ok', 'not_a_real_type')
    assert 'not_a_real_type' not in str(exc.value)


def test_rejects_type_that_matches_charset_but_not_whitelist(temp_checkpoint_dir):
    service = CheckpointService(checkpoint_dir=temp_checkpoint_dir)
    with pytest.raises(ValueError):
        service.get_checkpoint_path('ok', 'batch_analysis_extra')


@pytest.mark.parametrize('checkpoint_type', sorted(ALLOWED_CHECKPOINT_TYPES))
def test_allows_whitelisted_types(temp_checkpoint_dir, checkpoint_type):
    service = CheckpointService(checkpoint_dir=temp_checkpoint_dir)
    path = service.get_checkpoint_path('sess1', checkpoint_type)
    assert f'{checkpoint_type}_sess1.json' in path


def test_traversal_cannot_escape_checkpoint_dir(temp_checkpoint_dir):
    """Even if validation were bypassed, resolved path must stay inside base."""
    service = CheckpointService(checkpoint_dir=temp_checkpoint_dir)
    # Valid identifiers only — path must resolve under the temp dir.
    path = service.get_checkpoint_path('safe-id', 'batch_analysis')
    assert os.path.realpath(path).startswith(os.path.realpath(temp_checkpoint_dir) + os.sep)


def test_save_load_delete_reject_traversal(temp_checkpoint_dir):
    service = CheckpointService(checkpoint_dir=temp_checkpoint_dir)
    with pytest.raises(ValueError):
        service.save_checkpoint('../escape', {'a': 1}, 'batch_analysis')
    with pytest.raises(ValueError):
        service.load_checkpoint('../escape', 'batch_analysis')
    with pytest.raises(ValueError):
        service.delete_checkpoint('../escape', 'batch_analysis')


def test_list_checkpoints_rejects_bad_type(temp_checkpoint_dir):
    service = CheckpointService(checkpoint_dir=temp_checkpoint_dir)
    with pytest.raises(ValueError):
        service.list_checkpoints('../x')
    with pytest.raises(ValueError):
        service.list_checkpoints('unknown_type')


def test_validate_does_not_echo_value():
    with pytest.raises(ValueError) as exc:
        validate_checkpoint_identifiers('../secret', 'batch_analysis')
    assert '../secret' not in str(exc.value)


def test_route_get_checkpoint_returns_400_for_traversal(client):
    response = client.get('/api/get-checkpoint', query_string={
        'session_id': '../x',
        'type': 'batch_analysis',
    })
    assert response.status_code == 400
    payload = response.get_json()
    assert payload['error'] == 'invalid session_id or type'
    assert '../x' not in json.dumps(payload)


def test_route_get_checkpoint_returns_400_for_bad_type(client):
    response = client.get('/api/get-checkpoint', query_string={
        'session_id': 'ok',
        'type': 'not_whitelisted',
    })
    assert response.status_code == 400
    assert response.get_json()['error'] == 'invalid session_id or type'


def test_route_get_checkpoint_returns_400_for_empty_and_long_id(client):
    # Empty is already rejected as missing session_id by the route (400 with different message).
    empty = client.get('/api/get-checkpoint', query_string={
        'session_id': '',
        'type': 'batch_analysis',
    })
    assert empty.status_code == 400

    long_id = client.get('/api/get-checkpoint', query_string={
        'session_id': 'a' * 65,
        'type': 'batch_analysis',
    })
    assert long_id.status_code == 400
    assert long_id.get_json()['error'] == 'invalid session_id or type'


def test_route_get_checkpoint_returns_400_for_encoded_slash(client):
    # Flask decodes %2F in query values before our code sees them.
    response = client.get('/api/get-checkpoint?session_id=..%2Fx&type=batch_analysis')
    assert response.status_code == 400
    assert response.get_json()['error'] == 'invalid session_id or type'


def test_route_list_checkpoints_returns_400_for_bad_type(client):
    response = client.get('/api/list-checkpoints', query_string={'type': '../x'})
    assert response.status_code == 400
    assert response.get_json()['error'] == 'invalid session_id or type'


def test_route_get_checkpoint_valid_still_works(client, temp_checkpoint_dir):
    service = CheckpointService(checkpoint_dir=temp_checkpoint_dir)
    service.save_checkpoint('good-session', {'session_id': 'good-session', 'ok': True}, 'batch_analysis')

    response = client.get('/api/get-checkpoint', query_string={
        'session_id': 'good-session',
        'type': 'batch_analysis',
    })
    assert response.status_code == 200
    assert response.get_json()['ok'] is True
