"""Tests for the coordinated scenario rewrite and its target focus mix."""

from __future__ import annotations

import json
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from services.prompt_rewrite_service import (
    PromptRewriteService,
    focus_targets_by_message,
    looks_like_sample_completion,
    normalize_focus_targets,
    normalize_rewrite_weight,
    parse_rewritten_messages,
    strip_rewrite_fences,
)
from utils.inference_scenario import validate_scenario


def _scenario():
    return validate_scenario({
        'version': 1,
        'messages': [
            {
                'id': 'sys',
                'role': 'system',
                'content': 'You are a triage nurse. Always return valid JSON. Be concise.',
                'analysis_mode': 'analyse',
            },
            {
                'id': 'dev',
                'role': 'developer',
                'content': 'Escalate chest pain. Mention the on-call number.',
                'analysis_mode': 'analyse',
            },
            {
                'id': 'user-input',
                'role': 'user',
                'content': 'My chest hurts.',
                'analysis_mode': 'retain',
                'input_name': 'question',
            },
        ],
        'output_contract': {
            'type': 'json_schema',
            'name': 'triage',
            'strict': True,
            'schema': {
                'type': 'object',
                'properties': {'answer': {'type': 'string'}},
                'required': ['answer'],
                'additionalProperties': False,
            },
        },
    })


def _foci():
    return [
        {'focus': 'Role', 'prompt_section': 'You are a triage nurse.',
         'message_id': 'sys', 'rewrite_weight': 30},
        {'focus': 'JSON', 'prompt_section': 'Always return valid JSON.',
         'message_id': 'sys', 'rewrite_weight': 0},
        {'focus': 'Escalation', 'prompt_section': 'Escalate chest pain.',
         'message_ids': ['dev'], 'rewrite_weight': 90},
    ]


def _service(side_effect):
    provider = MagicMock()
    provider.chat_completion.side_effect = side_effect
    assessor = SimpleNamespace(provider=provider, model='mock-model', provider_name='openai')
    return PromptRewriteService(assessor), provider


def _reply(mapping):
    return {'content': json.dumps({'rewritten_messages': mapping})}


def test_normalize_does_not_clamp_zero_upward():
    assert normalize_rewrite_weight(0) == 0.0
    assert normalize_rewrite_weight('0') == 0.0
    assert normalize_rewrite_weight(None) == 0.0
    assert normalize_rewrite_weight(-5) == 0.0
    assert normalize_rewrite_weight(150) == 100.0


def test_targets_are_normalized_globally_not_banded():
    targets = normalize_focus_targets([
        {'focus': 'a', 'rewrite_weight': 10},
        {'focus': 'b', 'rewrite_weight': 30},
        {'focus': 'c', 'rewrite_weight': 0, 'weight': 40, 'reported_focus_score': 90},
    ])
    shares = {t['focus']: t['target_share'] for t in targets}
    assert shares['a'] == pytest.approx(25.0)
    assert shares['b'] == pytest.approx(75.0)
    assert shares['c'] == 0.0
    assert sum(shares.values()) == pytest.approx(100.0)
    assert [t['omit'] for t in targets] == [False, False, True]


def test_relative_shares_are_invariant_to_weight_scale():
    small = normalize_focus_targets([
        {'focus': 'a', 'rewrite_weight': 5},
        {'focus': 'b', 'rewrite_weight': 15},
    ])
    large = normalize_focus_targets([
        {'focus': 'a', 'rewrite_weight': 20},
        {'focus': 'b', 'rewrite_weight': 60},
    ])
    assert [t['target_share'] for t in small] == pytest.approx([25.0, 75.0])
    assert [t['target_share'] for t in large] == pytest.approx([25.0, 75.0])


def test_all_zero_weights_leave_every_share_at_zero():
    targets = normalize_focus_targets([
        {'focus': 'a', 'rewrite_weight': 0},
        {'focus': 'b', 'rewrite_weight': 0},
    ])
    assert [t['target_share'] for t in targets] == [0.0, 0.0]


def test_targeting_uses_every_mapping_field_including_spans():
    targets = normalize_focus_targets([
        {'focus': 'single', 'message_id': 'a', 'rewrite_weight': 10},
        {'focus': 'multi', 'message_ids': ['a', 'b'], 'rewrite_weight': 10},
        {'focus': 'spanned', 'spans': [{'message_id': 'c', 'start': 0, 'end': 2}],
         'rewrite_weight': 10},
        {'focus': 'unmapped', 'rewrite_weight': 10},
    ])
    by_message = focus_targets_by_message(targets, ['a', 'b', 'c', 'd'])
    assert list(by_message) == ['a', 'b', 'c']
    assert [t['focus'] for t in by_message['a']] == ['single', 'multi']
    assert [t['focus'] for t in by_message['b']] == ['multi']
    assert [t['focus'] for t in by_message['c']] == ['spanned']


def test_unmapped_foci_target_every_message_only_when_nothing_is_mapped():
    targets = normalize_focus_targets([{'focus': 'legacy', 'rewrite_weight': 40}])
    assert list(focus_targets_by_message(targets, ['a', 'b'])) == ['a', 'b']


def test_one_request_rewrites_both_targeted_messages():
    scenario = _scenario()

    def fake(**kwargs):
        return _reply({
            'sys': 'You are a triage nurse. Be concise.',
            'dev': 'Escalate chest pain immediately. Give the on-call number.',
        })

    service, provider = _service(fake)
    result = service.rewrite_scenario(scenario, _foci())

    assert provider.chat_completion.call_count == 1

    ids = [m['id'] for m in result['messages']]
    roles = [m['role'] for m in result['messages']]
    assert ids == ['sys', 'dev', 'user-input']
    assert roles == ['system', 'developer', 'user']
    assert result['messages'][0]['content'] == 'You are a triage nurse. Be concise.'
    assert result['messages'][1]['content'].startswith('Escalate chest pain immediately')
    # Retained bytes and contract are untouched.
    assert result['messages'][2] == scenario['messages'][2]
    assert result['output_contract'] == scenario['output_contract']


def test_untargeted_analyse_message_keeps_its_bytes():
    scenario = _scenario()
    service, provider = _service(
        lambda **kwargs: _reply({'sys': 'You are a triage nurse.'})
    )
    result = service.rewrite_scenario(scenario, [
        {'focus': 'Role', 'prompt_section': 'You are a triage nurse.',
         'message_id': 'sys', 'rewrite_weight': 40},
    ])
    assert result['messages'][1]['content'] == scenario['messages'][1]['content']
    assert provider.chat_completion.call_count == 1


def test_no_targeted_message_makes_no_request():
    scenario = _scenario()
    service, provider = _service(lambda **kwargs: _reply({}))
    result = service.rewrite_scenario(scenario, [
        {'focus': 'Elsewhere', 'message_id': 'user-input', 'rewrite_weight': 50},
    ])
    assert provider.chat_completion.call_count == 0
    assert result == scenario


def test_all_omitted_message_may_come_back_empty():
    scenario = _scenario()
    service, _ = _service(lambda **kwargs: _reply({'sys': ''}))
    result = service.rewrite_scenario(scenario, [
        {'focus': 'Role', 'message_id': 'sys', 'rewrite_weight': 0},
        {'focus': 'JSON', 'message_id': 'sys', 'rewrite_weight': 0},
    ])
    assert result['messages'][0] == {
        'id': 'sys', 'role': 'system', 'content': '', 'analysis_mode': 'analyse',
    }
    assert result['messages'][2] == scenario['messages'][2]


def test_empty_rewrite_rejected_while_a_focus_keeps_positive_target():
    scenario = _scenario()
    service, _ = _service(lambda **kwargs: _reply({'sys': '   '}))
    with pytest.raises(ValueError, match='positive target share'):
        service.rewrite_scenario(scenario, [
            {'focus': 'Role', 'message_id': 'sys', 'rewrite_weight': 40},
            {'focus': 'JSON', 'message_id': 'sys', 'rewrite_weight': 0},
        ])


def test_missing_or_extra_ids_are_rejected_without_partial_apply():
    with pytest.raises(ValueError, match='missing: dev'):
        parse_rewritten_messages(
            json.dumps({'rewritten_messages': {'sys': 'ok'}}), ['sys', 'dev']
        )
    with pytest.raises(ValueError, match='unexpected: user-input'):
        parse_rewritten_messages(
            json.dumps({'rewritten_messages': {
                'sys': 'ok', 'dev': 'ok', 'user-input': 'nope',
            }}),
            ['sys', 'dev'],
        )


def test_scenario_untouched_when_response_ids_are_wrong():
    scenario = _scenario()
    original = deepcopy(scenario)
    service, _ = _service(lambda **kwargs: _reply({'sys': 'only one'}))
    with pytest.raises(ValueError, match='wrong message ids'):
        service.rewrite_scenario(scenario, _foci())
    assert scenario == original


def test_non_string_and_malformed_values_are_rejected():
    with pytest.raises(ValueError, match="must be text, got dict"):
        parse_rewritten_messages(
            json.dumps({'rewritten_messages': {'sys': {'content': 'x'}}}), ['sys']
        )
    with pytest.raises(ValueError, match='rewritten_messages'):
        parse_rewritten_messages(json.dumps({'messages': {'sys': 'x'}}), ['sys'])
    with pytest.raises(ValueError, match='valid JSON'):
        parse_rewritten_messages('You are a triage nurse.', ['sys'])


def test_parse_accepts_markdown_fenced_json():
    parsed = parse_rewritten_messages(
        '```json\n{"rewritten_messages": {"sys": "Rewritten."}}\n```',
        ['sys'],
    )
    assert parsed == {'sys': 'Rewritten.'}


def test_parse_strips_a_fence_around_a_message_value():
    parsed = parse_rewritten_messages(
        json.dumps({'rewritten_messages': {'sys': '```text\nRewritten.\n```'}}),
        ['sys'],
    )
    assert parsed == {'sys': 'Rewritten.'}


def test_cross_message_focus_is_rewritten_in_one_request():
    scenario = _scenario()

    def fake(**kwargs):
        return _reply({'sys': 'Nurse. Concise.', 'dev': 'Escalate chest pain.'})

    service, provider = _service(fake)
    result = service.rewrite_scenario(scenario, [
        {'focus': 'Chest pain', 'prompt_section': 'chest pain',
         'spans': [{'message_id': 'sys'}, {'message_id': 'dev'}],
         'rewrite_weight': 60},
    ])
    assert provider.chat_completion.call_count == 1
    assert result['messages'][1]['content'] == 'Escalate chest pain.'


def test_strip_rewrite_fences():
    assert strip_rewrite_fences('```\nhello\n```') == 'hello'
    assert strip_rewrite_fences('```text\nYou are helpful.\n```') == 'You are helpful.'
    assert strip_rewrite_fences('plain') == 'plain'


def test_looks_like_sample_completion_suggested_message():
    original = (
        'You are a veterinary clinic assistant. Always be professional. '
        'Return JSON with a suggestedMessage field for the client. '
        'Include clinic hours Monday–Friday 9am–7pm and the address on Example St. '
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


def _long_prompt():
    return (
        'You are a veterinary clinic assistant for Example Animal Hospital. '
        'Always respond with JSON containing suggestedMessage. Include hours, '
        'address at 123 Example St, parking guidance, and booster scheduling help. '
        + ('Detailed policy text. ' * 25)
    )


def test_rewrite_retries_once_when_model_returns_sample_completion():
    original = _long_prompt()
    good = (
        'You are a veterinary clinic assistant. Prefer booster scheduling clarity. '
        'Always respond with JSON containing suggestedMessage. Include hours and address.'
        + (' Retained policy. ' * 20)
    )
    responses = [
        _reply({'legacy-prompt': '{"suggestedMessage": "Thank you for your message!"}'}),
        _reply({'legacy-prompt': good}),
    ]
    service, provider = _service(lambda **kwargs: responses.pop(0))

    rewritten = service.rewrite_prompt(original, [
        {'focus': 'Role', 'prompt_section': 'You are a veterinary clinic assistant',
         'rewrite_weight': 80},
        {'focus': 'JSON', 'prompt_section': 'Always respond with JSON',
         'rewrite_weight': 40},
    ])
    assert rewritten.startswith('You are a veterinary clinic assistant.')
    assert provider.chat_completion.call_count == 2


def test_rewrite_raises_when_completion_persists():
    original = _long_prompt()
    service, provider = _service(
        lambda **kwargs: _reply({
            'legacy-prompt': '{"suggestedMessage": "Thanks for writing in about boosters."}'
        })
    )
    with pytest.raises(ValueError, match='sample reply or completion'):
        service.rewrite_prompt(original, [
            {'focus': 'Role', 'prompt_section': 'You are', 'rewrite_weight': 50},
        ])
    assert provider.chat_completion.call_count == 2


def test_legacy_prompt_rewrite_returns_text():

    def fake(**kwargs):
        return _reply({'legacy-prompt': 'You are a triage nurse. Be concise.'})

    service, _ = _service(fake)
    rewritten = service.rewrite_prompt(
        'You are a triage nurse. Always return valid JSON. Be concise.',
        [
            {'focus': 'Role', 'prompt_section': 'You are a triage nurse.', 'weight': 20},
            {'focus': 'JSON', 'prompt_section': 'Always return valid JSON.', 'weight': 0},
            {'focus': 'Concision', 'prompt_section': 'Be concise.', 'weight': 60},
        ],
    )
    assert rewritten == 'You are a triage nurse. Be concise.'


def test_empty_prompt_is_rejected():
    service, provider = _service(lambda **kwargs: _reply({}))
    with pytest.raises(ValueError, match='Prompt is required'):
        service.rewrite_prompt('   ', [{'focus': 'x', 'rewrite_weight': 50}])
    assert provider.chat_completion.call_count == 0
