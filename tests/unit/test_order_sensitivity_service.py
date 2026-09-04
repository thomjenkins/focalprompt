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
