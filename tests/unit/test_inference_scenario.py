"""Canonical ordered scenario behavior."""

from copy import deepcopy
from unittest.mock import Mock

import numpy as np
import pytest

from services.ablation_service import AblationService

from utils.inference_scenario import (
    ProviderCapabilityError,
    ScenarioValidationError,
    StructuredOutputError,
    ablate_scenario,
    bind_scenario_inputs,
    compile_scenario,
    complete_scenario,
    default_scenario,
    legacy_prompt_to_scenario,
    normalize_scenario_foci,
    normalize_scenario_input,
    reorder_scenario_focus_group,
    scenario_coverage,
    scenario_order_groups,
    validate_scenario,
    validate_structured_response,
)


def scenario(*, contract=False):
    value = {
        'version': 1,
        'messages': [
            {
                'id': 'rules',
                'role': 'system',
                'content': 'Be safe. Be concise.',
                'analysis_mode': 'analyse',
            },
            {
                'id': 'history',
                'role': 'assistant',
                'content': 'How can I help?',
                'analysis_mode': 'retain',
            },
            {
                'id': 'question',
                'role': 'user',
                'content': 'template',
                'analysis_mode': 'retain',
                'input_name': 'customer_message',
            },
        ],
    }
    if contract:
        value['output_contract'] = {
            'type': 'json_schema',
            'name': 'answer',
            'strict': True,
            'schema': {
                'type': 'object',
                'properties': {'answer': {'type': 'string'}},
                'required': ['answer'],
                'additionalProperties': False,
            },
        }
    return value


def test_defaults_and_legacy_preserve_historical_user_role():
    assert default_scenario()['messages'][0]['analysis_mode'] == 'analyse'
    assert default_scenario()['messages'][1]['analysis_mode'] == 'retain'
    legacy = legacy_prompt_to_scenario('hello')
    assert legacy['messages'] == [{
        'id': 'legacy-prompt',
        'role': 'user',
        'content': 'hello',
        'analysis_mode': 'analyse',
    }]
    resolved, is_legacy = normalize_scenario_input(prompt='hello')
    assert is_legacy is True
    assert resolved == legacy


def test_role_defaults_order_ids_and_exactly_one_source():
    raw = scenario()
    del raw['messages'][0]['analysis_mode']
    del raw['messages'][1]['analysis_mode']
    checked = validate_scenario(raw)
    assert checked['messages'][0]['analysis_mode'] == 'analyse'
    assert checked['messages'][1]['analysis_mode'] == 'retain'
    with pytest.raises(ScenarioValidationError, match='exactly one'):
        normalize_scenario_input(prompt='x', scenario=scenario())
    invalid = scenario()
    invalid['messages'].append({
        'id': 'late-system', 'role': 'system', 'content': 'late', 'analysis_mode': 'analyse'
    })
    with pytest.raises(ScenarioValidationError, match='must precede'):
        validate_scenario(invalid)
    duplicate = scenario()
    duplicate['messages'][1]['id'] = 'rules'
    with pytest.raises(ScenarioValidationError, match='Duplicate'):
        validate_scenario(duplicate)
    unexpected = scenario()
    unexpected['future_field'] = True
    with pytest.raises(ScenarioValidationError, match='unsupported fields'):
        validate_scenario(unexpected)


def test_named_inputs_replace_complete_retained_content_and_report_unused():
    original = scenario()
    defaulted, default_meta = bind_scenario_inputs(original, None)
    assert defaulted['messages'][2]['content'] == 'template'
    assert default_meta['used_defaults'] == ['customer_message']
    bound, metadata = bind_scenario_inputs(
        original, {'customer_message': 'My pup needs a booster', 'unused': 'x'}
    )
    assert bound['messages'][2]['content'] == 'My pup needs a booster'
    assert original['messages'][2]['content'] == 'template'
    assert metadata['unused'] == ['unused']
    with pytest.raises(ScenarioValidationError, match='Missing named inputs'):
        bind_scenario_inputs(original, {})
    with pytest.raises(ScenarioValidationError, match='Blank named inputs'):
        bind_scenario_inputs(original, {'customer_message': '  '})


def test_multi_message_focus_ablation_preserves_retained_messages_and_contract():
    original = scenario(contract=True)
    original['messages'].insert(1, {
        'id': 'style',
        'role': 'developer',
        'content': 'Warm tone.',
        'analysis_mode': 'analyse',
    })
    focus = {
        'focus': 'Tone and brevity',
        'spans': [
            {'message_id': 'rules', 'char_start': 9, 'char_end': 20, 'text_snapshot': 'Be concise.'},
            {'message_id': 'style', 'char_start': 0, 'char_end': 10, 'text_snapshot': 'Warm tone.'},
        ],
    }
    ablated, metadata = ablate_scenario(original, focus)
    assert ablated['messages'][0]['content'] == 'Be safe. '
    assert 'style' not in [message['id'] for message in ablated['messages']]
    assert ablated['messages'][-2:] == original['messages'][-2:]
    assert ablated['output_contract'] == original['output_contract']
    assert metadata['removed_message_ids'] == ['style']


def test_grounding_rejects_retained_spans_and_reports_per_message_coverage():
    raw = scenario()
    with pytest.raises(ScenarioValidationError, match='retained'):
        normalize_scenario_foci(raw, [{
            'focus': 'input',
            'spans': [{'message_id': 'question', 'char_start': 0, 'char_end': 8, 'text_snapshot': 'template'}],
        }])
    foci = [{
        'focus': 'safe',
        'spans': [{'message_id': 'rules', 'char_start': 3, 'char_end': 7, 'text_snapshot': 'safe'}],
    }]
    coverage = scenario_coverage(raw, foci)
    assert set(coverage['messages']) == {'rules'}
    assert coverage['messages']['rules']['covered_chars_unique'] == 4
    assert coverage['covered_chars_unique'] == 4


def test_ordering_is_grouped_within_one_message_and_role():
    raw = scenario()
    foci = [
        {'focus': 'safe', 'spans': [{'message_id': 'rules', 'char_start': 3, 'char_end': 7, 'text_snapshot': 'safe'}]},
        {'focus': 'concise', 'spans': [{'message_id': 'rules', 'char_start': 12, 'char_end': 19, 'text_snapshot': 'concise'}]},
    ]
    assert scenario_order_groups(raw, foci) == [{
        'message_id': 'rules', 'role': 'system', 'focus_indices': [0, 1]
    }]
    reordered = reorder_scenario_focus_group(
        raw, foci, focus_indices=[0, 1], assignment=[1, 0]
    )
    assert reordered['messages'][0]['content'] == 'Be concise. Be safe.'
    assert reordered['messages'][1:] == raw['messages'][1:]
    cross = deepcopy(foci)
    cross[1]['spans'][0] = {
        'message_id': 'question', 'char_start': 0, 'char_end': 8, 'text_snapshot': 'template'
    }
    with pytest.raises(ScenarioValidationError):
        reorder_scenario_focus_group(raw, cross, focus_indices=[0, 1], assignment=[1, 0])


def test_compile_and_local_structured_response_validation():
    raw = scenario(contract=True)
    compiled = compile_scenario(raw)
    assert [message['role'] for message in compiled['messages']] == ['system', 'assistant', 'user']
    assert compiled['response_format']['json_schema']['schema'] == raw['output_contract']['schema']
    assert validate_structured_response('{"answer":"ok"}', raw['output_contract']) == {'answer': 'ok'}
    with pytest.raises(StructuredOutputError, match='malformed'):
        validate_structured_response('{bad', raw['output_contract'])
    with pytest.raises(StructuredOutputError, match='malformed'):
        validate_structured_response('{"answer": NaN}', raw['output_contract'])
    with pytest.raises(StructuredOutputError, match='does not match'):
        validate_structured_response('{"wrong":1}', raw['output_contract'])
    with pytest.raises(StructuredOutputError, match='refused'):
        validate_structured_response('{}', raw['output_contract'], refusal='no')
    with pytest.raises(StructuredOutputError, match='incomplete'):
        validate_structured_response('{}', raw['output_contract'], incomplete=True)


def test_compile_omits_blank_rows_and_preserves_source_and_nonblank_whitespace():
    raw = scenario(contract=True)
    raw['messages'][0]['content'] = '  Keep this spacing.\n'
    raw['messages'].insert(0, {'id': 'empty-instructions', 'role': 'developer',
                             'analysis_mode': 'analyse', 'content': '\n\t '})
    raw['messages'].extend([
        {'id': 'ablated-user', 'role': 'user', 'analysis_mode': 'analyse', 'content': '\n\n'},
        {'id': 'empty-history', 'role': 'assistant', 'analysis_mode': 'retain', 'content': ''},
        {'id': 'unused-row', 'role': 'user', 'analysis_mode': 'retain', 'content': ''},
    ])
    original = deepcopy(raw)
    provider = Mock()
    provider.chat_completion.return_value = {'content': '{"answer":"ok"}'}
    result = complete_scenario(provider, 'model', 'openai', raw)
    sent = provider.chat_completion.call_args.kwargs['messages']
    assert sent == [{'role': m['role'], 'content': m['content']}
                    for m in raw['messages'] if m['content'].strip()]
    assert sent[0]['content'] == '  Keep this spacing.\n'
    assert raw == original
    metadata = result['scenario_metadata']
    assert metadata['source_message_ids'] == [m['id'] for m in raw['messages']]
    assert metadata['message_ids'] == ['rules', 'history', 'question']
    assert metadata['omitted_blank_message_ids'] == ['empty-instructions', 'ablated-user', 'empty-history', 'unused-row']
    assert result['parsed_output'] == {'answer': 'ok'}


def test_compile_rejects_blank_named_inputs_and_missing_nonblank_user_before_generation():
    raw = scenario()
    raw['messages'][-1]['content'] = ''
    provider = Mock()
    with pytest.raises(ScenarioValidationError, match="Named input 'customer_message'.*has no content"):
        complete_scenario(provider, 'model', 'openai', raw)
    assert not provider.chat_completion.called
    bound, _ = bind_scenario_inputs(raw, {'customer_message': '  Actual user input.\n'})
    assert compile_scenario(bound)['messages'][-1]['content'] == '  Actual user input.\n'
    del raw['messages'][-1]['input_name']
    with pytest.raises(ScenarioValidationError, match='nonblank user message'):
        complete_scenario(provider, 'model', 'openai', raw)
    assert not provider.chat_completion.called
    assert validate_scenario(raw)['messages'][-1]['content'] == '', 'drafts remain exportable'


def test_complete_scenario_passes_exact_roles_and_never_downgrades_contract():
    provider = Mock()
    provider.chat_completion.return_value = {
        'content': '{"answer":"ok"}',
        'usage': {'prompt_tokens': 1, 'completion_tokens': 1},
    }
    raw = scenario(contract=True)
    result = complete_scenario(provider, 'model', 'openai', raw)
    kwargs = provider.chat_completion.call_args.kwargs
    assert kwargs['messages'] == [
        {'role': message['role'], 'content': message['content']}
        for message in raw['messages']
    ]
    assert kwargs['response_format']['type'] == 'json_schema'
    assert result['parsed_output'] == {'answer': 'ok'}
    provider.chat_completion.side_effect = TypeError('response_format unsupported')
    with pytest.raises(ProviderCapabilityError, match='structured output contract'):
        complete_scenario(provider, 'model', 'provider', raw)


@pytest.mark.parametrize('error', [
    Exception('Service temporarily unavailable. Please try again in a moment.'),
    RuntimeError('Model not found'),
    RuntimeError('Invalid API key'),
    RuntimeError('Unexpected internal error'),
    TimeoutError('Timed out while generating json_schema output'),
])
def test_contract_does_not_turn_other_failures_into_capability_errors(error):
    provider = Mock()
    provider.chat_completion.side_effect = error
    with pytest.raises(type(error)) as failure:
        complete_scenario(provider, 'model', 'openai', scenario(contract=True))
    assert failure.value is error
    assert provider.chat_completion.call_count == 1
    assert provider.chat_completion.call_args.kwargs['response_format']['type'] == 'json_schema'


def test_end_to_end_fake_provider_changes_only_selected_analysed_span(monkeypatch):
    raw = scenario(contract=True)
    focus = {
        'focus': 'brevity',
        'spans': [{
            'message_id': 'rules',
            'char_start': 9,
            'char_end': 20,
            'text_snapshot': 'Be concise.',
        }],
    }
    calls = []
    provider = Mock()

    def respond(**kwargs):
        calls.append(deepcopy(kwargs['messages']))
        return {
            'content': '{"answer":"ok"}',
            'usage': {'prompt_tokens': 2, 'completion_tokens': 1},
        }

    provider.chat_completion.side_effect = respond
    embeddings = Mock()
    embeddings.batch_embeddings_with_usage.side_effect = lambda texts: (
        [np.array([1.0, float(index + 1)]) for index, _ in enumerate(texts)], len(texts)
    )
    monkeypatch.setattr('services.ablation_service.time.sleep', lambda *_args: None)
    service = AblationService(
        provider, 'model', provider_name='openai', embedding_service=embeddings
    )
    result = service.run_scenario_ablation(
        raw,
        [focus],
        inputs={'customer_message': 'My dog is coughing'},
        n_baseline=2,
        n_ablated=2,
        n_permutations=16,
    )
    assert result['scenario']['messages'][2]['content'] == 'My dog is coughing'
    assert len(calls) == 4
    baseline, ablated = calls[0], calls[-1]
    assert baseline[1:] == ablated[1:]
    assert baseline[0] == {'role': 'system', 'content': 'Be safe. Be concise.'}
    assert ablated[0] == {'role': 'system', 'content': 'Be safe. '}
    assert all(call[-1]['content'] == 'My dog is coughing' for call in calls)
