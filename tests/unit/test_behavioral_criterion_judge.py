#!/usr/bin/env python3
"""Tests for behavioural criterion judge."""

from __future__ import annotations

import json
from unittest.mock import Mock

from services.behavioral_criterion_judge import BehavioralCriterionJudge, normalize_judgment


def test_normalize_judgment():
    row = normalize_judgment({
        'classification': 'complies',
        'score': 120,
        'rationale': 'ok',
    })
    assert row['classification'] == 'COMPLIES'
    assert row['score'] == 100.0


def test_judge_output():
    provider = Mock()
    provider.chat_completion.return_value = {
        'content': json.dumps({
            'classification': 'VIOLATES',
            'score': 10,
            'rationale': 'Booked a dog.',
        }),
    }
    judge = BehavioralCriterionJudge(provider, 'mock')
    result = judge.judge_output(
        criterion='Only offer cat appointments.',
        output_text='Your dog is booked for Tuesday.',
    )
    assert result['classification'] == 'VIOLATES'
