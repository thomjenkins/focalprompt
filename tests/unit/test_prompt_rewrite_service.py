"""Tests for prompt rewrite weight semantics (0% = omit)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from services.prompt_rewrite_service import (
    PromptRewriteService,
    build_rewrite_instruction,
    looks_like_sample_completion,
    normalize_rewrite_weight,
    strip_rewrite_fences,
    weight_band,
)


def test_weight_bands_distinguish_zero_from_minimize():
    assert weight_band(0) == 'omit'
    assert weight_band(0.0) == 'omit'
    assert weight_band(1) == 'minimize'
    assert weight_band(29) == 'minimize'
    assert weight_band(30) == 'retain'
    assert weight_band(69) == 'retain'
    assert weight_band(70) == 'emphasize'
    assert weight_band(100) == 'emphasize'


def test_normalize_does_not_clamp_zero_upward():
    assert normalize_rewrite_weight(0) == 0.0
    assert normalize_rewrite_weight('0') == 0.0
    assert normalize_rewrite_weight(None) == 0.0
    assert normalize_rewrite_weight(-5) == 0.0
    assert normalize_rewrite_weight(150) == 100.0


def test_instruction_says_zero_means_omit_not_mention_briefly():
    instruction = build_rewrite_instruction(
        'Be safe. Be helpful. Return JSON.',
        [
            {'focus': 'Safety', 'prompt_section': 'Be safe.', 'rewrite_weight': 0},
            {'focus': 'Help', 'prompt_section': 'Be helpful.', 'rewrite_weight': 50},
            {'focus': 'JSON', 'prompt_section': 'Return JSON.', 'rewrite_weight': 80},
        ],
    )
    lower = instruction.lower()
    assert '0%' in instruction or 'rewrite_weight = 0' in lower or 'exactly 0%' in lower
    assert 'omit' in lower
    assert 'do not paraphrase' in lower or 'do not retain equivalent' in lower
    assert 'mention them briefly' not in lower
    assert 'mention briefly or implicitly' not in lower
    assert '0-30%' not in instruction
    assert '0–30%' not in instruction
    # 1–29 distinct from 0
    assert '1–29%' in instruction or '1-29%' in instruction
    assert 'minimize' in lower
    assert 'instruction text' in lower or 'do not' in lower
    assert 'suggestedmessage' in lower or 'sample reply' in lower


def test_instruction_does_not_let_preserve_meaning_override_zero():
    instruction = build_rewrite_instruction(
        'Role text. Schema text.',
        [
            {'focus': 'Role', 'prompt_section': 'Role text.', 'weight': 100},
            {'focus': 'Schema', 'prompt_section': 'Schema text.', 'rewrite_weight': 0},
        ],
    )
    lower = instruction.lower()
    assert 'do not preserve the original prompt\'s overall meaning' in lower
    assert 'retained foci' in lower
    # Must not include the old blanket that fought omission:
    assert 'maintain the original structure and meaning' not in lower


def test_instruction_lists_omit_foci_explicitly():
    instruction = build_rewrite_instruction(
        'A. B.',
        [
            {'focus': 'Keep', 'prompt_section': 'A.', 'rewrite_weight': 60},
            {'focus': 'Drop', 'prompt_section': 'B.', 'rewrite_weight': 0},
        ],
    )
    assert 'FOCI TO OMIT' in instruction
    assert 'Drop' in instruction
    assert '[omit]' in instruction
    assert '[retain]' in instruction or 'retain' in instruction.lower()


def test_reported_focus_and_rewrite_weight_are_separate_fields_in_payload_contract():
    """Service prefers rewrite_weight over legacy weight; reported score is ignored for banding."""
    instruction = build_rewrite_instruction(
        'Keep me. Drop me.',
        [
            {
                'focus': 'Keep',
                'prompt_section': 'Keep me.',
                'reported_focus_score': 0,  # introspective — must NOT force omit
                'rewrite_weight': 80,
            },
            {
                'focus': 'Drop',
                'prompt_section': 'Drop me.',
                'reported_focus_score': 90,  # high report — must NOT force retain
                'rewrite_weight': 0,
            },
        ],
    )
    assert 'Keep: rewrite_weight=80.0% [emphasize]' in instruction
    assert 'Drop: rewrite_weight=0.0% [omit]' in instruction
    assert 'reported_focus_score' not in instruction  # not used as rewrite authority


def test_nonzero_emphasize_and_retain_language_intact():
    instruction = build_rewrite_instruction(
        'Low. Mid. High.',
        [
            {'focus': 'Low', 'prompt_section': 'Low.', 'rewrite_weight': 10},
            {'focus': 'Mid', 'prompt_section': 'Mid.', 'rewrite_weight': 40},
            {'focus': 'High', 'prompt_section': 'High.', 'rewrite_weight': 90},
        ],
    )
    assert '[minimize]' in instruction
    assert '[retain]' in instruction
    assert '[emphasize]' in instruction
    assert '70–100%' in instruction or '70-100%' in instruction
    assert '30–69%' in instruction or '30-69%' in instruction


def test_strip_rewrite_fences():
    assert strip_rewrite_fences('```\nhello\n```') == 'hello'
    assert strip_rewrite_fences('```text\nYou are helpful.\n```') == 'You are helpful.'
    assert strip_rewrite_fences('plain') == 'plain'


def test_looks_like_sample_completion_suggested_message():
    original = (
        'You are a veterinary clinic assistant. Always be professional. '
        'Return JSON with a suggestedMessage field for the client. '
        'Include clinic hours Monday–Friday 9am–7pm and the address on Ambrose St. '
        'Parking notes and booster appointment scheduling guidance go here as well. '
        + ('Extra instruction padding. ' * 20)
    )
    bad = (
        '{\n  "suggestedMessage": "Thank you for your message! To schedule a '
        'booster appointment for {{patientName}}, please let us know."\n}'
    )
    assert looks_like_sample_completion(original, bad) is True

    good = (
        'You are a veterinary clinic assistant. Emphasize scheduling boosters. '
        'Return JSON with a suggestedMessage field. Include clinic hours and address.'
        + (' Keep retained rules explicit. ' * 15)
    )
    assert looks_like_sample_completion(original, good) is False


def test_rewrite_prompt_omits_zero_weight_focus_with_deterministic_mock():
    """Mock model deletes 0%-weight sections; service must surface that omission."""
    prompt = (
        "You are a triage nurse.\n\n"
        "Always return valid JSON.\n\n"
        "Be concise."
    )
    foci = [
        {
            'focus': 'Role',
            'prompt_section': 'You are a triage nurse.',
            'rewrite_weight': 50,
        },
        {
            'focus': 'JSON schema',
            'prompt_section': 'Always return valid JSON.',
            'rewrite_weight': 0,
        },
        {
            'focus': 'Concision',
            'prompt_section': 'Be concise.',
            'rewrite_weight': 50,
        },
    ]

    captured = {}

    def fake_chat_completion(**kwargs):
        captured['messages'] = kwargs['messages']
        user = kwargs['messages'][1]['content']
        # Deterministic rewrite: drop any focus the instruction marks as omit.
        parts = []
        for item in foci:
            w = float(item.get('rewrite_weight', item.get('weight', 0)))
            if w > 0:
                parts.append(item['prompt_section'])
            else:
                # Prove the model was told to omit — section must appear in OMIT list.
                assert item['focus'] in user
                assert 'omit' in user.lower()
        return {'content': '\n\n'.join(parts)}

    provider = MagicMock()
    provider.chat_completion.side_effect = fake_chat_completion
    assessor = SimpleNamespace(provider=provider, model='mock-model', provider_name='openai')
    service = PromptRewriteService(assessor)

    rewritten = service.rewrite_prompt(prompt, foci)

    assert 'Always return valid JSON.' not in rewritten
    assert 'You are a triage nurse.' in rewritten
    assert 'Be concise.' in rewritten

    system = captured['messages'][0]['content'].lower()
    user = captured['messages'][1]['content'].lower()
    assert '0%' in system or 'omit' in system
    assert 'sample' in system or 'completion' in system
    assert 'for low-weight foci (0-30%), mention' not in user
    assert 'mention them briefly or implicitly' not in user
    assert 'maintain the original structure and meaning' not in user


def test_rewrite_retries_when_model_returns_sample_completion():
    original = (
        'You are a veterinary clinic assistant for Sackets Harbor Animal Hospital. '
        'Always respond with JSON containing suggestedMessage. Include hours, '
        'address at 213 Ambrose St, parking guidance, and booster scheduling help. '
        + ('Detailed policy text. ' * 25)
    )
    foci = [
        {'focus': 'Role', 'prompt_section': 'You are a veterinary clinic assistant', 'rewrite_weight': 80},
        {'focus': 'JSON', 'prompt_section': 'Always respond with JSON', 'rewrite_weight': 40},
    ]
    bad = '{"suggestedMessage": "Thank you for your message! To schedule a booster."}'
    good = (
        'You are a veterinary clinic assistant. Prefer booster scheduling clarity. '
        'Always respond with JSON containing suggestedMessage. Include hours and address.'
        + (' Retained policy. ' * 20)
    )
    responses = [{'content': bad}, {'content': good}]

    provider = MagicMock()
    provider.chat_completion.side_effect = lambda **kwargs: responses.pop(0)
    assessor = SimpleNamespace(provider=provider, model='mock-model', provider_name='openai')
    service = PromptRewriteService(assessor)

    rewritten = service.rewrite_prompt(original, foci)
    assert 'You are a veterinary clinic assistant' in rewritten
    assert 'suggestedMessage": "Thank you' not in rewritten
    assert provider.chat_completion.call_count == 2
    second_user = provider.chat_completion.call_args_list[1].kwargs['messages'][1]['content']
    assert 'CRITICAL RETRY' in second_user


def test_rewrite_raises_when_completion_persists():
    original = (
        'You are a veterinary clinic assistant. Always respond with JSON. '
        + ('Policy. ' * 40)
    )
    foci = [{'focus': 'Role', 'prompt_section': 'You are', 'rewrite_weight': 50}]
    bad = '{"suggestedMessage": "Thanks for writing in about boosters."}'

    provider = MagicMock()
    provider.chat_completion.return_value = {'content': bad}
    assessor = SimpleNamespace(provider=provider, model='mock-model', provider_name='openai')
    service = PromptRewriteService(assessor)

    with pytest.raises(ValueError, match='sample reply or completion'):
        service.rewrite_prompt(original, foci)


def test_legacy_weight_field_still_accepted():
    instruction = build_rewrite_instruction(
        'X',
        [{'focus': 'X', 'prompt_section': 'X', 'weight': 0}],
    )
    assert '[omit]' in instruction


def test_partition_by_band():
    parts = PromptRewriteService.partition_by_band([
        {'focus': 'a', 'weight': 0},
        {'focus': 'b', 'rewrite_weight': 15},
        {'focus': 'c', 'rewrite_weight': 50},
        {'focus': 'd', 'rewrite_weight': 90},
    ])
    assert [x['focus'] for x in parts['omit']] == ['a']
    assert [x['focus'] for x in parts['minimize']] == ['b']
    assert [x['focus'] for x in parts['retain']] == ['c']
    assert [x['focus'] for x in parts['emphasize']] == ['d']
