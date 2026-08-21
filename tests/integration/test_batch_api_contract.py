"""
HTTP contract tests for batch CSV parse and batch UI API parity.
"""

from __future__ import annotations

import io
import json
import re
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pytest
from flask import Flask

from routes.ablation_routes import ablation_bp
from routes.agent_routes import agent_bp
from routes.assessment_routes import assessment_bp
from routes.batch_routes import batch_bp
from routes.optimization_routes import optimization_bp
from routes.pricing_routes import pricing_bp


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv('CHECKPOINT_DIR', str(tmp_path))
    application = Flask(__name__)
    application.config['TESTING'] = True
    application.register_blueprint(assessment_bp)
    application.register_blueprint(ablation_bp)
    application.register_blueprint(batch_bp)
    application.register_blueprint(agent_bp)
    application.register_blueprint(optimization_bp)
    application.register_blueprint(pricing_bp)
    return application


@pytest.fixture
def client(app):
    return app.test_client()


def _upload_csv(client, text: str, filename: str = 'batch.csv'):
    return client.post(
        '/api/parse-batch-csv',
        data={'file': (io.BytesIO(text.encode('utf-8')), filename)},
        content_type='multipart/form-data',
    )


def test_post_valid_minimal_csv(client):
    r = _upload_csv(client, 'input,output\nhello,world\n')
    assert r.status_code == 200
    data = r.get_json()
    assert data['pairs'][0]['inputs']['chat_content'] == 'hello'
    assert data['pairs'][0]['output'] == 'world'


def test_post_multiple_rows(client):
    r = _upload_csv(client, 'input,output\na,1\nb,2\n')
    assert r.status_code == 200
    assert len(r.get_json()['pairs']) == 2


def test_post_commas_and_quotes(client):
    r = _upload_csv(client, 'input,output\n"a, b ""c""",ok\n')
    assert r.status_code == 200
    assert r.get_json()['pairs'][0]['inputs']['chat_content'] == 'a, b "c"'


def test_post_multiline_and_literal_backslash_n(client):
    r = _upload_csv(client, 'prompt,output\n"real\nnewline",x\n')
    assert r.status_code == 200
    assert r.get_json()['pairs'][0]['prompt'] == 'real\nnewline'

    r2 = _upload_csv(client, 'prompt,output\n"lit\\neral",y\n')
    assert r2.status_code == 200
    assert r2.get_json()['pairs'][0]['prompt'] == 'lit\\neral'


def test_post_unicode_and_bom(client):
    # Encode with utf-8-sig only (do not also embed U+FEFF in the text).
    raw = 'input,output\n日本語,да\n'.encode('utf-8-sig')
    r = client.post(
        '/api/parse-batch-csv',
        data={'file': (io.BytesIO(raw), 'u.csv')},
        content_type='multipart/form-data',
    )
    assert r.status_code == 200, r.get_json()
    pair = r.get_json()['pairs'][0]
    assert pair['inputs']['chat_content'] == '日本語'
    assert pair['output'] == 'да'


def test_post_blank_rows_and_malformed(client):
    r = _upload_csv(client, 'input,output\nok,1\n\n\n')
    assert r.status_code == 200
    assert len(r.get_json()['pairs']) == 1

    r2 = _upload_csv(client, 'input,output\n"bad\n')
    assert r2.status_code == 400


def test_post_missing_columns(client):
    r = _upload_csv(client, 'foo,bar\n1,2\n')
    assert r.status_code == 400


def test_post_dynamic_columns(client):
    csv = 'chat_content,rag_context,tool_results,output\nc,r,t,o\n'
    r = _upload_csv(client, csv)
    assert r.status_code == 200
    inp = r.get_json()['pairs'][0]['inputs']
    assert inp == {
        'chat_content': 'c',
        'rag_context': 'r',
        'tool_results': 't',
    }


def test_parsed_pairs_accepted_by_batch_stream_shape(client):
    r = _upload_csv(client, 'input,output\nuser says hi,assistant reply\n')
    assert r.status_code == 200
    pairs = r.get_json()['pairs']
    for p in pairs:
        p['prompt'] = 'You are a helpful assistant.'
    resp = client.post(
        '/api/batch-analysis-stream',
        json={'pairs': pairs, 'foci': []},
    )
    assert resp.status_code == 200
    assert 'Foci are required' in resp.data.decode('utf-8')


# Paths the Batch Analysis tab (and closely coupled agent/optimization flows) call.
BATCH_UI_REQUIRED_ROUTES = {
    ('POST', '/api/parse-batch-csv'),
    ('POST', '/api/detect-foci'),
    ('POST', '/api/detect-dynamic-foci'),
    ('POST', '/api/batch-analysis-stream'),
    ('POST', '/api/batch-aggregate'),
    ('POST', '/api/ablation-sample'),
    ('POST', '/api/ablation-score'),
    ('GET', '/api/list-checkpoints'),
    ('GET', '/api/get-checkpoint'),
    ('POST', '/api/build-batch-agents-stream'),
    ('POST', '/api/llm-evaluate-batch-agents-stream'),
    ('POST', '/api/analyze-prompt-optimization'),
    ('GET', '/api/models'),
    ('GET', '/api/pricing/models'),
    ('POST', '/api/pricing/estimate'),
    ('POST', '/api/test-api-key'),
}


def _frontend_api_paths() -> set[str]:
    js = (ROOT / 'static' / 'js' / 'app.js').read_text(encoding='utf-8')
    return set(re.findall(r"""['"`](/api/[^'"`?\s]+)""", js))


def test_batch_frontend_api_paths_have_routes(app):
    rules = {}
    for rule in app.url_map.iter_rules():
        methods = {m for m in rule.methods if m not in ('HEAD', 'OPTIONS')}
        rules[rule.rule] = methods

    front = _frontend_api_paths()
    batch_related = {
        p for p in front
        if any(
            k in p
            for k in (
                'parse-batch',
                'batch-analysis',
                'batch-aggregate',
                'ablation-sample',
                'ablation-score',
                'detect-foci',
                'detect-dynamic',
                'list-checkpoint',
                'get-checkpoint',
                'build-batch',
                'llm-evaluate-batch',
                'analyze-prompt-optimization',
                'pricing',
                'models',
                'test-api-key',
            )
        )
    }

    missing = []
    for path in sorted(batch_related):
        if path not in rules:
            missing.append(f'no route for frontend path {path}')

    for method, path in sorted(BATCH_UI_REQUIRED_ROUTES):
        if path not in rules:
            missing.append(f'missing route {method} {path}')
        elif method not in rules[path]:
            missing.append(f'route {path} lacks method {method} (has {rules[path]})')

    assert not missing, 'Batch UI API contract failures:\n' + '\n'.join(missing)


def test_parse_batch_csv_in_frontend_inventory():
    assert '/api/parse-batch-csv' in _frontend_api_paths()


def test_batch_aggregate_endpoint(client):
    resp = client.post(
        '/api/batch-aggregate',
        json={
            'pair_results': [
                {
                    'success': True,
                    'influence_scores': {
                        'Role': {'influence': 0.4, 'normalized_influence': 80.0},
                        'Tone': {'influence': 0.1, 'normalized_influence': 20.0},
                    },
                }
            ]
        },
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert 'Role' in body['statistics']
    assert body['statistics']['Role']['mean'] == pytest.approx(80.0)


PROMPT = (
    "You are a veterinary triage assistant.\n\n"
    "Always cite the source of any medical claim."
)
FOCI = [
    {'focus': 'Role', 'prompt_section': 'You are a veterinary triage assistant.'},
    {'focus': 'Cite', 'prompt_section': 'Always cite the source of any medical claim.'},
]


def _parse_sse(raw: bytes):
    events = []
    for block in raw.decode('utf-8').strip().split('\n\n'):
        line = block.strip()
        if line.startswith('data: '):
            events.append(json.loads(line[6:]))
    return events


def test_e2e_csv_parse_batch_sse_checkpoint_reload(client, tmp_path, monkeypatch):
    monkeypatch.setenv('CHECKPOINT_DIR', str(tmp_path))

    csv_text = (
        'input,output\n'
        'Owner: coughing dog,Please rest the dog.\n'
        'Owner: itchy cat,Try a diet trial.\n'
    )
    parse_resp = _upload_csv(client, csv_text)
    assert parse_resp.status_code == 200, parse_resp.get_json()
    pairs = parse_resp.get_json()['pairs']
    assert len(pairs) == 2
    for p in pairs:
        p['prompt'] = PROMPT

    session_id = 'e2e-batch-csv-1'

    mock_provider = Mock()
    mock_provider.chat_completion.return_value = {
        'content': 'ok',
        'usage': {'prompt_tokens': 5, 'completion_tokens': 3},
    }

    mock_embed = Mock()
    mock_embed.batch_embeddings_with_usage.side_effect = (
        lambda texts: ([np.ones(8) for _ in texts], len(texts))
    )

    mock_assessor = MagicMock()
    mock_assessor.provider = mock_provider
    mock_assessor.provider_name = 'openai'
    mock_assessor.model = 'gpt-4o-mini'

    from services.checkpoint_service import CheckpointService
    from services.batch_analysis_service import BatchAnalysisService
    from services.cost_calculator import CostCalculator

    real_checkpoint = CheckpointService(checkpoint_dir=str(tmp_path))

    def _fake_batch_service(*_a, **_k):
        return BatchAnalysisService(
            mock_provider,
            'gpt-4o-mini',
            'test-key',
            embedding_service=mock_embed,
            cost_calculator=CostCalculator(),
            checkpoint_service=real_checkpoint,
            assessment_service=None,
            provider_name='openai',
            max_workers=1,
        )

    monkeypatch.setattr(
        'services.batch_analysis_service.time.sleep', lambda *_a, **_k: None
    )
    monkeypatch.setattr(
        'services.ablation_service.time.sleep', lambda *_a, **_k: None
    )

    with patch('services.assessor_factory.get_assessor', return_value=mock_assessor), \
         patch('services.batch_analysis_service.BatchAnalysisService', side_effect=_fake_batch_service), \
         patch('services.embedding_service.EmbeddingService', return_value=mock_embed), \
         patch('services.checkpoint_service.CheckpointService', return_value=real_checkpoint), \
         patch('services.assessment_service.AssessmentService', return_value=MagicMock()):

        stream = client.post(
            '/api/batch-analysis-stream',
            json={
                'pairs': pairs,
                'foci': FOCI,
                'n_baseline': 2,
                'n_ablated': 2,
                'temperature': 0.7,
                'session_id': session_id,
                'resume': False,
                'model': 'gpt-4o-mini',
                'provider': 'openai',
            },
        )
        assert stream.status_code == 200
        events = _parse_sse(stream.data)

    types = [e.get('type') for e in events]
    assert 'progress' in types or 'pair_result' in types
    assert types.count('pair_result') == 2
    assert 'complete' in types
    complete = next(e for e in events if e['type'] == 'complete')
    assert complete.get('statistics') or complete.get('pair_results')
    assert len(complete['pair_results']) == 2

    # CheckpointService is bound on the routes module at import time.
    with patch('routes.batch_routes.CheckpointService', return_value=real_checkpoint):
        listed = client.get('/api/list-checkpoints?type=batch_analysis')
        assert listed.status_code == 200
        cps = listed.get_json()['checkpoints']
        assert any(c.get('session_id') == session_id for c in cps), cps

        loaded = client.get(
            f'/api/get-checkpoint?session_id={session_id}&type=batch_analysis'
        )
        assert loaded.status_code == 200
        ck = loaded.get_json()
        assert ck.get('statistics') or ck.get('pair_results')
        assert len(ck.get('pair_results', [])) >= 2
