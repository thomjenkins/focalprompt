"""Tests for criterion-based output quality evaluation."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from services.output_evaluator_service import (
    OutputQualityEvaluator,
    build_quality_evaluation_prompt,
    normalize_output_items,
    quality_eval_max_tokens,
    sample_outputs_stratified,
)


def test_normalize_output_items_rejects_empty():
    with pytest.raises(ValueError, match='At least one'):
        normalize_output_items([])
    with pytest.raises(ValueError, match='empty'):
        normalize_output_items([{'label': 'A', 'text': '   '}])


def test_build_prompt_includes_criteria_and_outputs():
    text = build_quality_evaluation_prompt(
        eval_criteria='Must schedule appointment politely.',
        outputs=[{'label': 'Baseline', 'text': 'Thanks for writing in.'}],
        task_context='User wants a booster.',
        prompt='You are a clinic assistant.',
    )
    assert 'Must schedule appointment politely' in text
    assert 'Baseline' in text
    assert 'User wants a booster' in text
    assert 'JSON compactness' in text
    assert 'Score every output' in text


def test_quality_eval_max_tokens_scales_with_outputs():
    assert quality_eval_max_tokens(1) == 4096
    assert quality_eval_max_tokens(5) > 4096
    assert quality_eval_max_tokens(100) <= 16384


def test_evaluate_outputs_parses_response():
    provider = MagicMock()
    provider.chat_completion.return_value = {
        'content': json.dumps({
            'evaluations': [
                {
                    'label': 'Baseline',
                    'overall_score': 82,
                    'meets_primary_criterion': True,
                    'criterion_breakdown': [
                        {'name': 'Politeness', 'score': 5, 'met': True, 'notes': 'Warm tone'},
                    ],
                    'strengths': ['Clear'],
                    'weaknesses': [],
                    'summary': 'Good reply.',
                }
            ],
            'comparative_notes': '',
        }),
        'usage': {'prompt_tokens': 100, 'completion_tokens': 50},
    }
    ev = OutputQualityEvaluator(provider, 'mock-model', provider_name='openai')
    result = ev.evaluate_outputs(
        eval_criteria='Be polite and helpful.',
        outputs=[{'label': 'Baseline', 'text': 'Hello! We can help schedule.'}],
        prompt='Clinic assistant.',
    )
    assert result['evaluation_type'] == 'task_quality'
    assert result['explicitly_not_behavioral_difference'] is True
    assert result['evaluations'][0]['overall_score'] == 82.0
    assert result['evaluations'][0]['output_text'] == 'Hello! We can help schedule.'
    assert result['evaluations'][0]['criterion_breakdown'][0]['name'] == 'Politeness'


def test_evaluate_requires_criteria():
    ev = OutputQualityEvaluator(MagicMock(), 'm')
    with pytest.raises(ValueError, match='criteria'):
        ev.evaluate_outputs(
            eval_criteria='',
            outputs=[{'label': 'A', 'text': 'x'}],
        )


def test_evaluate_outputs_retries_when_first_response_truncated():
    provider = MagicMock()
    truncated = (
        '{\n  "evaluations": [\n    {\n'
        '      "label": "Current output",\n'
        '      "criterion_breakdown": [\n'
        '        {"name": "Polite Decline", "score":'
    )
    good = json.dumps({
        'evaluations': [
            {
                'label': 'Current output',
                'overall_score': 90,
                'meets_primary_criterion': True,
                'criterion_breakdown': [],
                'strengths': [],
                'weaknesses': [],
                'summary': 'Good.',
            }
        ],
        'comparative_notes': '',
    })
    provider.chat_completion.side_effect = [
        {'content': truncated, 'usage': {'prompt_tokens': 5, 'completion_tokens': 5}},
        {'content': good, 'usage': {'prompt_tokens': 5, 'completion_tokens': 10}},
    ]
    ev = OutputQualityEvaluator(provider, 'mock-model', provider_name='openai')
    result = ev.evaluate_outputs(
        eval_criteria='Decline politely.',
        outputs=[{'label': 'Current output', 'text': 'Thanks, but we cannot help.'}],
    )
    assert result['evaluations'][0]['overall_score'] == 90.0
    assert provider.chat_completion.call_count == 2
    retry_user = provider.chat_completion.call_args_list[1].kwargs['messages'][1]['content']
    assert 'CRITICAL RETRY' in retry_user
    assert provider.chat_completion.call_args_list[0].kwargs.get('max_tokens') == 4096


def test_evaluate_outputs_recovers_partial_truncated_response():
    provider = MagicMock()
    truncated = (
        '{\n  "evaluations": [\n    {\n'
        '      "label": "Current output",\n'
        '      "overall_score": 90,\n'
        '      "meets_primary_criterion": true,\n'
        '      "criterion_breakdown": [\n'
        '        {"name": "Polite Decline", "score":'
    )
    provider.chat_completion.side_effect = [
        {'content': truncated, 'usage': {'prompt_tokens': 5, 'completion_tokens': 5}},
        {'content': truncated, 'usage': {'prompt_tokens': 5, 'completion_tokens': 5}},
    ]
    ev = OutputQualityEvaluator(provider, 'mock-model', provider_name='openai')
    result = ev.evaluate_outputs(
        eval_criteria='Decline politely.',
        outputs=[{'label': 'Current output', 'text': 'Thanks, but we cannot help.'}],
    )
    assert result['evaluations'][0]['overall_score'] == 90.0
    assert result['evaluations'][0]['meets_primary_criterion'] is True


def test_evaluate_outputs_batches_large_experiment_b_sets():
    provider = MagicMock()

    def _response(labels):
        return {
            'content': json.dumps({
                'evaluations': [
                    {
                        'label': label,
                        'overall_score': 80,
                        'meets_primary_criterion': True,
                        'criterion_breakdown': [],
                        'strengths': [],
                        'weaknesses': [],
                        'summary': 'ok',
                    }
                    for label in labels
                ],
                'comparative_notes': '',
            }),
            'usage': {'prompt_tokens': 5, 'completion_tokens': 5},
        }

    outputs = [
        {'label': f'Baseline (full prompt) — sample {i}', 'text': f'baseline {i}'}
        for i in range(1, 6)
    ]
    provider.chat_completion.side_effect = [
        _response([outputs[0]['label'], outputs[1]['label'], outputs[2]['label'], outputs[3]['label']]),
        _response([outputs[4]['label']]),
    ]
    ev = OutputQualityEvaluator(provider, 'mock-model', provider_name='openai')
    result = ev.evaluate_outputs(
        eval_criteria='Be polite.',
        outputs=outputs,
    )
    assert result['n_batches'] == 2
    assert len(result['evaluations']) == 5
    assert all(row['overall_score'] == 80.0 for row in result['evaluations'])
    assert provider.chat_completion.call_count == 2


def test_sample_outputs_stratified_keeps_groups():
    outputs = [
        {'label': 'Baseline (full prompt) — sample 1', 'text': 'b1', 'group': 'baseline'},
        {'label': 'Baseline (full prompt) — sample 2', 'text': 'b2', 'group': 'baseline'},
        {'label': 'Ablated: Role — sample 1', 'text': 'r1', 'group': 'ablated', 'focus': 'Role'},
        {'label': 'Ablated: Role — sample 2', 'text': 'r2', 'group': 'ablated', 'focus': 'Role'},
        {'label': 'Ablated: Tone — sample 1', 'text': 't1', 'group': 'ablated', 'focus': 'Tone'},
    ]
    sampled = sample_outputs_stratified(outputs, 0.5, seed=42)
    labels = {row['label'] for row in sampled}
    assert any(l.startswith('Baseline') for l in labels)
    assert any('Role' in l for l in labels)
    assert any('Tone' in l for l in labels)
    assert len(sampled) < len(outputs)


def test_evaluate_all_outputs_accepts_100_experiment_b_outputs():
    provider = MagicMock()
    outputs = [
        {'label': f'Baseline (full prompt) — sample {i}', 'text': f'b{i}'}
        for i in range(1, 11)
    ]
    for focus in ('A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J'):
        for i in range(1, 10):
            outputs.append({
                'label': f'Ablated: {focus} — sample {i}',
                'text': f'{focus}-{i}',
                'group': 'ablated',
                'focus': focus,
            })
    assert len(outputs) == 100

    def _response(labels):
        return {
            'content': json.dumps({
                'evaluations': [
                    {
                        'label': label,
                        'overall_score': 80,
                        'meets_primary_criterion': True,
                        'criterion_breakdown': [],
                        'strengths': [],
                        'weaknesses': [],
                        'summary': 'ok',
                    }
                    for label in labels
                ],
                'comparative_notes': '',
            }),
            'usage': {'prompt_tokens': 5, 'completion_tokens': 5},
        }

    batches = [outputs[i:i + 4] for i in range(0, len(outputs), 4)]
    provider.chat_completion.side_effect = [
        _response([o['label'] for o in batch]) for batch in batches
    ]
    ev = OutputQualityEvaluator(provider, 'mock-model', provider_name='openai')
    result = ev.evaluate_outputs(
        eval_criteria='Be polite.',
        outputs=outputs,
        sample_fraction=1.0,
    )
    assert result['n_outputs'] == 100
    assert result['n_outputs_total'] == 100
    assert result['n_batches'] == 25
