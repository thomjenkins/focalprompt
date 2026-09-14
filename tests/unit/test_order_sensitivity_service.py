#!/usr/bin/env python3
"""Tests for focus order sensitivity service."""

from __future__ import annotations

from unittest.mock import Mock

import numpy as np
import pytest

from services.order_sensitivity_service import OrderSensitivityService
from utils.prompt_order import prepare_order_experiment
from utils.span_alignment import classify_foci_for_ablation


PROMPT = (
    "Role: assistant.\n\n"
    "Rule A: cats only.\n\n"
    "Rule B: be kind.\n\n"
    "Rule C: cite sources.\n\n"
    "User: hello"
)


def _foci():
    return [
        {'focus': 'Role', 'prompt_section': 'Role: assistant.', 'is_dynamic': False},
        {'focus': 'Cats', 'prompt_section': 'Rule A: cats only.', 'is_dynamic': False},
        {'focus': 'Tone', 'prompt_section': 'Rule B: be kind.', 'is_dynamic': False},
        {'focus': 'Cite', 'prompt_section': 'Rule C: cite sources.', 'is_dynamic': False},
    ]


@pytest.fixture
def mock_provider():
    provider = Mock()
    n = [0]

    def _complete(**kwargs):
        n[0] += 1
        return {
            'content': f'output {n[0]}',
            'usage': {'prompt_tokens': 5, 'completion_tokens': 3},
        }

    provider.chat_completion.side_effect = lambda **kw: _complete()
    return provider


@pytest.fixture
def mock_embedding():
    svc = Mock()
    dim = 8
    svc.batch_embeddings_with_usage.side_effect = lambda texts: (
        [np.ones(dim) * (i + 1) for i in range(len(texts))],
        len(texts),
    )
    return svc


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr('services.order_sensitivity_service.time.sleep', lambda *_a, **_k: None)


def test_estimate_cost():
    svc = OrderSensitivityService(Mock(), 'm', embedding_service=Mock())
    est = svc.estimate_cost(k_permutations=5, m_samples=3, run_position_sweep=True)
    assert est['global_order_model_calls'] == 15
    assert est['total_model_calls'] >= 15


def test_run_focus_order_experiment_mocked(mock_provider, mock_embedding):
    svc = OrderSensitivityService(
        mock_provider, 'gpt-4o-mini', embedding_service=mock_embedding
    )
    baselines = ['b1', 'b2', 'b3']
    result = svc.run_focus_order_experiment(
        prompt=PROMPT,
        foci=_foci(),
        baseline_outputs=baselines,
        k_permutations=2,
        m_samples=2,
        order_seed=3,
        temperature=0.7,
    )
    assert result['ok'] is True
    assert result['experiment_type'] == 'focus_order_sensitivity'
    assert 'baseline_stability' in result
    assert len(result['global_order_experiment']['permutations']) == 2
    assert result['global_order_experiment']['summary']['n_permutations'] == 2


def test_behavioral_judge_uses_analysis_model_provider(mock_embedding):
    mut_provider = Mock()
    mut_provider.chat_completion.side_effect = [
        {'content': 'mut output 1', 'usage': {'prompt_tokens': 5, 'completion_tokens': 3}},
        {'content': 'mut output 2', 'usage': {'prompt_tokens': 5, 'completion_tokens': 3}},
    ]
    analysis_provider = Mock()
    analysis_provider.chat_completion.return_value = {
        'content': '{"classification":"COMPLIES","score":90,"rationale":"ok"}',
        'usage': {'prompt_tokens': 7, 'completion_tokens': 2},
    }
    svc = OrderSensitivityService(
        mut_provider,
        'gpt-3.5-turbo',
        provider_name='openai',
        judge_provider=analysis_provider,
        judge_model='gpt-4o',
        judge_provider_name='openai',
        embedding_service=mock_embedding,
    )

    result = svc.run_focus_order_experiment(
        prompt=PROMPT,
        foci=_foci(),
        baseline_outputs=['b1', 'b2', 'b3'],
        k_permutations=1,
        m_samples=2,
        order_seed=3,
        temperature=0.7,
        behavioral_criterion='Must comply',
        run_behavioral_judge=True,
    )

    assert result['ok'] is True
    assert mut_provider.chat_completion.call_args_list[0].kwargs['model'] == 'gpt-3.5-turbo'
    assert analysis_provider.chat_completion.call_args_list[0].kwargs['model'] == 'gpt-4o'


def test_prepare_refuses_single_movable():
    prep = prepare_order_experiment('Only one.\n\nTwo.', [
        {'focus': 'A', 'prompt_section': 'Only one.', 'is_dynamic': False},
    ])
    assert prep['ok'] is False


def test_scenario_order_experiment_preserves_message_boundaries(mock_provider, mock_embedding):
    scenario = {
        'version': 1,
        'messages': [
            {
                'id': 'rules',
                'role': 'system',
                'content': 'Rule A.\n\nRule B.',
                'analysis_mode': 'analyse',
            },
            {
                'id': 'question',
                'role': 'user',
                'content': 'Never move me',
                'analysis_mode': 'retain',
            },
        ],
    }
    foci = [
        {
            'focus': 'A',
            'spans': [{
                'message_id': 'rules',
                'char_start': 0,
                'char_end': 7,
                'text_snapshot': 'Rule A.',
            }],
        },
        {
            'focus': 'B',
            'spans': [{
                'message_id': 'rules',
                'char_start': 9,
                'char_end': 16,
                'text_snapshot': 'Rule B.',
            }],
        },
    ]
    svc = OrderSensitivityService(
        mock_provider, 'gpt-4o-mini', embedding_service=mock_embedding
    )

    result = svc.run_scenario_order_experiment(
        scenario=scenario,
        foci=foci,
        baseline_outputs=['baseline 1', 'baseline 2'],
        k_permutations=2,
        m_samples=1,
        order_seed=4,
        temperature=0.7,
    )

    assert result['ok'] is True
    assert result['scenario'] == scenario
    assert result['scenario_metadata']['ordering_message_id'] == 'rules'
    assert result['ordering_groups'] == [{
        'message_id': 'rules',
        'role': 'system',
        'focus_indices': [0, 1],
    }]
    for call in mock_provider.chat_completion.call_args_list:
        assert [message['role'] for message in call.kwargs['messages']] == ['system', 'user']
        assert call.kwargs['messages'][1]['content'] == 'Never move me'



RULES_CONTENT = 'Rule A.\n\nRule B.\n\nRule C.\n\nRule D.'


def _rules_scenario():
    return {
        'version': 1,
        'messages': [
            {
                'id': 'rules',
                'role': 'system',
                'content': RULES_CONTENT,
                'analysis_mode': 'analyse',
            },
            {
                'id': 'question',
                'role': 'user',
                'content': 'Never move me',
                'analysis_mode': 'retain',
            },
        ],
    }


def _span(start, end):
    return {
        'message_id': 'rules',
        'char_start': start,
        'char_end': end,
        'text_snapshot': RULES_CONTENT[start:end],
    }


def test_focus_overlapping_fixed_multi_span_focus_is_not_reordered(
    mock_provider, mock_embedding
):
    """A span also held by a fixed multi-span focus must stay put."""
    foci = [
        {'focus': 'A', 'spans': [_span(0, 7)]},
        {'focus': 'B', 'spans': [_span(9, 16)]},
        {'focus': 'C', 'spans': [_span(18, 25)]},
        {'focus': 'D', 'spans': [_span(27, 34)]},
        {'focus': 'A+C', 'spans': [_span(0, 7), _span(18, 25)]},
    ]
    svc = OrderSensitivityService(
        mock_provider, 'gpt-4o-mini', embedding_service=mock_embedding
    )

    result = svc.run_scenario_order_experiment(
        scenario=_rules_scenario(),
        foci=foci,
        baseline_outputs=['baseline 1', 'baseline 2'],
        k_permutations=2,
        m_samples=1,
        order_seed=4,
        temperature=0.7,
    )

    assert result['ok'] is True
    assert result['ordering_groups'] == [{
        'message_id': 'rules',
        'role': 'system',
        'focus_indices': [1, 3],
    }]
    assert result['overlapping_fixed_focus_indices'] == [0, 2]
    assert result['n_movable_slots'] == 2
    assert result['scenario_metadata']['focus_index_map'] == {'0': 1, '1': 3}
    for permutation in result['global_order_experiment']['permutations']:
        reordered = permutation['reordered_prompt']
        assert reordered.startswith('Rule A.')
        assert reordered.index('Rule C.') == 18


def test_all_movable_foci_overlapping_fixed_focus_refuses_run(
    mock_provider, mock_embedding
):
    foci = [
        {'focus': 'A', 'spans': [_span(0, 7)]},
        {'focus': 'B', 'spans': [_span(9, 16)]},
        {'focus': 'A+C', 'spans': [_span(0, 7), _span(18, 25)]},
    ]
    svc = OrderSensitivityService(
        mock_provider, 'gpt-4o-mini', embedding_service=mock_embedding
    )

    result = svc.run_scenario_order_experiment(
        scenario=_rules_scenario(),
        foci=foci,
        baseline_outputs=['baseline 1', 'baseline 2'],
        k_permutations=2,
        m_samples=1,
        order_seed=4,
        temperature=0.7,
    )

    assert result['ok'] is False
    assert 'overlap foci held fixed' in result['error']
    assert result['overlapping_fixed_focus_indices'] == [0]
    assert mock_provider.chat_completion.call_count == 0
    assert mock_embedding.batch_embeddings_with_usage.call_count == 0


def test_scenario_sweep_target_outside_eligible_group_fails_before_sampling(
    mock_provider, mock_embedding
):
    foci = [
        {'focus': 'A', 'spans': [_span(0, 7)]},
        {'focus': 'B', 'spans': [_span(9, 16)]},
        {'focus': 'A+C', 'spans': [_span(0, 7), _span(18, 25)]},
    ]
    svc = OrderSensitivityService(
        mock_provider, 'gpt-4o-mini', embedding_service=mock_embedding
    )

    result = svc.run_scenario_order_experiment(
        scenario=_rules_scenario(),
        foci=[foci[0], foci[1]],
        baseline_outputs=['baseline 1', 'baseline 2'],
        k_permutations=2,
        m_samples=1,
        order_seed=4,
        temperature=0.7,
        focus_index_for_sweep=7,
        run_position_sweep=True,
    )

    assert result['ok'] is False
    assert 'focus_index_for_sweep 7' in result['error']
    assert result['ordering_groups'] == [{
        'message_id': 'rules',
        'role': 'system',
        'focus_indices': [0, 1],
    }]
    assert mock_provider.chat_completion.call_count == 0
    assert mock_embedding.batch_embeddings_with_usage.call_count == 0


def test_legacy_sweep_target_not_movable_fails_before_sampling(
    mock_provider, mock_embedding
):
    svc = OrderSensitivityService(
        mock_provider, 'gpt-4o-mini', embedding_service=mock_embedding
    )

    with pytest.raises(ValueError, match='focus_index_for_sweep 9'):
        svc.run_focus_order_experiment(
            prompt=PROMPT,
            foci=_foci(),
            baseline_outputs=['b1', 'b2', 'b3'],
            k_permutations=2,
            m_samples=1,
            order_seed=3,
            temperature=0.7,
            focus_index_for_sweep=9,
            run_position_sweep=True,
        )

    assert mock_provider.chat_completion.call_count == 0
    assert mock_embedding.batch_embeddings_with_usage.call_count == 0


class _RecordedService:
    """Captures constructor wiring instead of running an experiment."""

    instances: list = []

    def __init__(self, provider, model, **kwargs):
        self.provider = provider
        self.model = model
        self.kwargs = kwargs
        _RecordedService.instances.append(self)

    def run_focus_order_experiment(self, **kwargs):
        self.call_kwargs = kwargs
        return {'ok': True, 'experiment_type': 'focus_order_sensitivity'}


@pytest.fixture
def order_client(monkeypatch):
    from flask import Flask

    import routes.order_sensitivity_routes as order_routes

    _RecordedService.instances = []
    resolved_roles = []

    def fake_get_assessor(data=None, **_kwargs):
        fields = data or {}
        role = fields.get('model_role')
        resolved_roles.append(role)
        if role == 'analysis' and not fields.get('api_key'):
            raise ValueError('Analysis model API key is required')
        assessor = Mock()
        assessor.provider_name = fields.get('provider')
        return assessor

    monkeypatch.setattr(order_routes, 'get_assessor', fake_get_assessor)
    monkeypatch.setattr(order_routes, 'OrderSensitivityService', _RecordedService)

    app = Flask(__name__)
    app.register_blueprint(order_routes.order_sensitivity_bp)
    return app.test_client(), resolved_roles


def test_direct_mut_run_does_not_require_analysis_credentials(order_client):
    client, resolved_roles = order_client

    response = client.post('/api/focus-order-sensitivity', json={
        'prompt': PROMPT,
        'foci': _foci(),
        'baseline_outputs': ['b1', 'b2'],
        'mut_model': 'gpt-4o-mini',
        'mut_provider': 'openai',
    })

    assert response.status_code == 200
    assert resolved_roles == ['mut']
    assert 'judge_provider' not in _RecordedService.instances[0].kwargs


def test_behavioral_judge_run_resolves_analysis_role(order_client):
    client, resolved_roles = order_client

    response = client.post('/api/focus-order-sensitivity', json={
        'prompt': PROMPT,
        'foci': _foci(),
        'baseline_outputs': ['b1', 'b2'],
        'mut_model': 'gpt-4o-mini',
        'analysis_model': 'gpt-4o',
        'analysis_provider': 'openai',
        'api_key': 'sk-test',
        'run_behavioral_judge': True,
        'behavioral_criterion': 'Must comply',
    })

    assert response.status_code == 200
    assert resolved_roles == ['mut', 'analysis']
    assert _RecordedService.instances[0].kwargs['judge_model'] == 'gpt-4o'