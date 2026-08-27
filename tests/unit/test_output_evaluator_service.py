"""Tests for criterion-based output quality evaluation."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from services.output_evaluator_service import (
    OutputQualityEvaluator,
    build_quality_evaluation_prompt,
    normalize_output_items,
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
    assert result['evaluations'][0]['criterion_breakdown'][0]['name'] == 'Politeness'


def test_evaluate_requires_criteria():
    ev = OutputQualityEvaluator(MagicMock(), 'm')
    with pytest.raises(ValueError, match='criteria'):
        ev.evaluate_outputs(
            eval_criteria='',
            outputs=[{'label': 'A', 'text': 'x'}],
        )
