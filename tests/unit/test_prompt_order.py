#!/usr/bin/env python3
"""Tests for slot-preserving prompt order reconstruction."""

from __future__ import annotations

import pytest

from utils.prompt_order import (
    assignment_for_focus_at_slot,
    build_loo_shuffle_prompt,
    build_reordered_prompt,
    prepare_order_experiment,
    reassemble_from_assignment,
    sample_random_assignments,
    validate_semantic_completeness,
)
from utils.span_alignment import classify_foci_for_ablation


VET_PROMPT = (
    "SYSTEM: You are a veterinary clinic assistant.\n\n"
    "EDITABLE INSTRUCTIONS:\n"
    "You are a cat-only clinic.\n\n"
    "Always be empathetic.\n\n"
    "Respond professionally.\n\n"
    "{{CHAT}}\n\n"
    "End of prompt."
)

CHAT = "Owner: my dog needs a booster shot tomorrow."


def _vet_foci():
    return [
        {
            'focus': 'Cats',
            'prompt_section': 'You are a cat-only clinic.',
            'is_dynamic': False,
        },
        {
            'focus': 'Tone',
            'prompt_section': 'Always be empathetic.',
            'is_dynamic': False,
        },
        {
            'focus': 'Role',
            'prompt_section': 'Respond professionally.',
            'is_dynamic': False,
        },
        {
            'focus': 'Chat',
            'prompt_section': '{{CHAT}}',
            'is_dynamic': True,
            'dynamic_type': 'chat',
        },
    ]


def test_prepare_requires_two_movable_foci():
    classified = classify_foci_for_ablation(VET_PROMPT, _vet_foci())
    prep = prepare_order_experiment(VET_PROMPT, _vet_foci())
    assert prep['ok'] is True
    assert prep['n_movable_slots'] == 3


def test_reorder_preserves_chat_and_glue_exactly_once():
    prompt = VET_PROMPT.replace('{{CHAT}}', CHAT)
    classified = classify_foci_for_ablation(prompt, _vet_foci())
    prep = prepare_order_experiment(prompt, _vet_foci())
    template = prep['template']
    assignment = list(range(prep['n_movable_slots']))
    assignment.reverse()
    reconstructed, meta = build_reordered_prompt(
        prompt, classified, assignment, policies=prep['ordering_policy']
    )
    ok, errors = validate_semantic_completeness(prompt, reconstructed, template)
    assert ok, errors
    assert reconstructed.count(CHAT) == 1
    assert 'SYSTEM: You are a veterinary clinic assistant.' in reconstructed
    assert 'End of prompt.' in reconstructed
    assert reconstructed.count('You are a cat-only clinic.') == 1


def test_loo_shuffle_omits_removed_focus_and_keeps_chat():
    prompt = VET_PROMPT.replace('{{CHAT}}', CHAT)
    classified = classify_foci_for_ablation(prompt, _vet_foci())
    removed = next(i for i, f in enumerate(classified) if f.get('focus') == 'Tone')
    shuffled, empty, doc, shuf, meta = build_loo_shuffle_prompt(
        prompt, classified, removed, shuffle_seed=11
    )
    assert not empty
    assert 'Always be empathetic.' not in shuffled
    assert shuffled.count(CHAT) == 1
    assert 'SYSTEM:' in shuffled


def test_deterministic_shuffle_from_seed():
    prompt = VET_PROMPT.replace('{{CHAT}}', CHAT)
    classified = classify_foci_for_ablation(prompt, _vet_foci())
    removed = 0
    a, _, _, order_a, _ = build_loo_shuffle_prompt(
        prompt, classified, removed, shuffle_seed=99
    )
    b, _, _, order_b, _ = build_loo_shuffle_prompt(
        prompt, classified, removed, shuffle_seed=99
    )
    assert a == b
    assert order_a == order_b


def test_position_sweep_preserves_relative_order_of_others():
    n = 4
    target = 2
    for slot in range(n):
        assignment = assignment_for_focus_at_slot(n, target, slot)
        assert assignment[slot] == target
        others = [assignment[i] for i in range(n) if i != slot]
        assert others == sorted(others)


def test_sample_random_assignments_respects_k():
    perms = sample_random_assignments(4, 3, seed=1)
    assert len(perms) == 3
    assert len(set(tuple(p[1]) for p in perms)) == 3


def test_inputs_chat_appended_once_when_missing():
    prompt = VET_PROMPT.replace('{{CHAT}}', '{{CHAT}}')
    classified = classify_foci_for_ablation(prompt, _vet_foci())
    prep = prepare_order_experiment(prompt, _vet_foci())
    out = reassemble_from_assignment(
        prep['template'],
        list(range(prep['n_movable_slots'])),
        inputs={'chat_content': CHAT},
    )
    assert out.count(CHAT) == 1
