#!/usr/bin/env python3
"""Shuffle-order ablation robustness checks."""

from __future__ import annotations

import pytest
from unittest.mock import Mock

import numpy as np

from services.ablation_service import AblationService
from services.embedding_service import EmbeddingService
from utils.span_alignment import (
    align_quote,
    build_shuffled_remaining_prompt,
    classify_foci_for_ablation,
    delete_span,
)


PROMPT = (
    "You are a veterinary triage assistant.\n\n"
    "Always cite the source of any medical claim.\n\n"
    "Respond in JSON with keys: urgency, differentials, next_steps."
)


def _static_foci():
    return [
        {'focus': 'Role', 'prompt_section': 'You are a veterinary triage assistant.', 'is_dynamic': False},
        {'focus': 'Cite', 'prompt_section': 'Always cite the source of any medical claim.', 'is_dynamic': False},
        {
            'focus': 'JSON',
            'prompt_section': 'Respond in JSON with keys: urgency, differentials, next_steps.',
            'is_dynamic': False,
        },
    ]


def test_build_shuffled_remaining_differs_from_subtractive():
    classified = classify_foci_for_ablation(PROMPT, _static_foci())
    removed_index = 1  # Cite
    subtractive, _, _ = delete_span(
        PROMPT,
        classified[removed_index]['char_start'],
        classified[removed_index]['char_end'],
    )
    shuffled, _, doc_order, shuffled_order = build_shuffled_remaining_prompt(
        PROMPT, classified, removed_index, shuffle_seed=42
    )
    assert doc_order == ['Role', 'JSON']
    assert shuffled_order != doc_order
    assert shuffled != subtractive
    assert 'veterinary triage' in shuffled
    assert 'Respond in JSON' in shuffled


def test_build_shuffled_single_remaining_is_noop_order():
    classified = classify_foci_for_ablation(PROMPT, _static_foci())
    removed_index = 0
    _, _, doc_order, shuffled_order = build_shuffled_remaining_prompt(
        PROMPT, classified, removed_index, shuffle_seed=99
    )
    assert doc_order == shuffled_order


@pytest.fixture
def mock_provider():
    provider = Mock()
    provider.chat_completion.return_value = {
        'content': 'Test output',
        'usage': {'prompt_tokens': 10, 'completion_tokens': 5},
    }
    return provider


@pytest.fixture
def mock_embedding_service():
    service = Mock(spec=EmbeddingService)
    service.batch_embeddings_with_usage.side_effect = lambda texts: (
        [np.ones(8) for _ in texts],
        len(texts),
    )
    return service


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr('services.ablation_service.time.sleep', lambda *_a, **_k: None)


def test_run_shuffle_robustness_reuses_baseline(mock_provider, mock_embedding_service):
    svc = AblationService(
        mock_provider,
        'gpt-4o-mini',
        'key',
        mock_embedding_service,
    )
    result = svc.run_shuffle_robustness(
        PROMPT,
        _static_foci(),
        focus_index=1,
        baseline_outputs=['baseline one', 'baseline two'],
        n_ablated=2,
        shuffle_seed=7,
        n_permutations=100,
        temperature=0.7,
    )
    assert result['ablation_mode'] == 'shuffled_remaining'
    assert result['focus'] == 'Cite'
    assert result['shuffle_seed'] == 7
    assert result['remaining_foci_document_order'] == ['Role', 'JSON']
    assert len(result['remaining_foci_shuffled_order']) == 2
    assert result['order_changed'] in (True, False)
    assert result['q_value'] is None
    assert 'p_value' in result
    assert len(result['ablated_outputs']) == 2
    # Only ablated samples — no baseline re-generation
    assert mock_provider.chat_completion.call_count == 2
