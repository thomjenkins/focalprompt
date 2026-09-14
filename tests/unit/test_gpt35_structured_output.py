"""Strict schema transport for GPT-3.5, including baseline/ablation parity."""

import copy
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests

from core.ai_gateway_provider import AIGatewayProvider
from core.llm_providers import OpenAIProvider
from services.ablation_service import AblationService
from utils.inference_scenario import StructuredOutputError, complete_scenario


@pytest.fixture
def scenario():
    return {'version': 1, 'messages': [
        {'id': 'rules', 'role': 'developer', 'analysis_mode': 'analyse',
         'content': 'Be concise. The bicycle shop opens at 9am.'},
        {'id': 'chat', 'role': 'user', 'analysis_mode': 'retain',
         'content': 'When does the shop open?'},
    ], 'output_contract': {'type': 'json_schema', 'name': 'answer', 'strict': True,
        'schema': {'type': 'object', 'properties': {'answer': {'type': 'string'}},
                   'required': ['answer'], 'additionalProperties': False}}}


@pytest.fixture(params=['direct', 'gateway'])
def transport(request, monkeypatch):
    wire = {'choices': [{'message': {'content': None, 'tool_calls': [{
        'id': 'call_output', 'type': 'function',
        'function': {'name': 'answer', 'arguments': '{"answer":"9am"}'},
    }]}, 'finish_reason': 'stop'}],
        'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}}
    sent = []

    def namespace(value):
        if isinstance(value, dict):
            return SimpleNamespace(**{k: namespace(v) for k, v in value.items()})
        if isinstance(value, list):
            return [namespace(v) for v in value]
        return value

    if request.param == 'direct':
        provider = OpenAIProvider.__new__(OpenAIProvider)
        provider.client = Mock()

        def create(**kwargs):
            sent.append(copy.deepcopy(kwargs))
            return namespace(wire)

        provider.client.chat.completions.create.side_effect = create
    else:
        provider = AIGatewayProvider('test-key')

        def post(url, **kwargs):
            sent.append(copy.deepcopy(kwargs['json']))
            response = Mock()
            response.json.return_value = copy.deepcopy(wire)
            return response

        monkeypatch.setattr('core.ai_gateway_provider._check_requests', lambda: SimpleNamespace(
            post=post, exceptions=requests.exceptions))
    return provider, sent, wire


def test_strict_contract_and_sampling_match_across_baseline_and_ablation(transport, scenario):
    provider, sent, _ = transport
    original = copy.deepcopy(scenario)
    service = AblationService(provider, 'gpt-3.5-turbo', embedding_service=Mock())
    foci = [{'focus': 'Brevity', 'spans': [{'message_id': 'rules', 'char_start': 0,
             'char_end': 11, 'text_snapshot': 'Be concise.'}]}]
    results = [service.sample_scenario_completion(scenario, foci, kind, 0.7, focus_index=0)
               for kind in ('baseline', 'ablated')]
    assert len(sent) == 2
    for payload, result in zip(sent, results):
        assert 'response_format' not in payload
        assert payload['model'].endswith('gpt-3.5-turbo')
        assert payload['temperature'] == 0.7
        function = payload['tools'][0]['function']
        assert function['parameters'] == scenario['output_contract']['schema']
        assert function['strict'] is True
        assert payload['tool_choice'] == {'type': 'function', 'function': {'name': 'answer'}}
        assert payload['parallel_tool_calls'] is False
        assert result['content'] == '{"answer":"9am"}'
        assert result['parsed_output'] == {'answer': '9am'}
        assert result['scenario_metadata']['structured_output'] == 'strict_function_call'
        assert result['scenario_metadata']['structured_output_function'] == 'answer'
        assert result['usage']['total_tokens'] == 15
    assert sent[0]['tools'] == sent[1]['tools']
    assert [m['role'] for m in sent[0]['messages']] == ['developer', 'user']
    assert sent[0]['messages'][0]['content'] == original['messages'][0]['content']
    assert sent[1]['messages'][0]['content'] == ' The bicycle shop opens at 9am.'
    assert sent[0]['messages'][1] == sent[1]['messages'][1]
    assert scenario == original


@pytest.mark.parametrize('failure', ['missing_call', 'multiple_calls', 'wrong_name',
                                    'empty_arguments', 'malformed_json', 'schema_mismatch',
                                    'extra_property', 'refusal', 'incomplete'])
def test_invalid_function_output_is_rejected_without_resampling(transport, scenario, failure):
    provider, sent, wire = transport
    choice = wire['choices'][0]
    message = choice['message']
    function = message['tool_calls'][0]['function']
    if failure == 'missing_call':
        message['tool_calls'] = []
        message['content'] = '{"answer":"Do not accept a different response channel"}'
    elif failure == 'multiple_calls':
        message['tool_calls'] *= 2
    elif failure == 'wrong_name':
        function['name'] = 'different_function'
    elif failure == 'empty_arguments':
        function['arguments'] = ''
    elif failure == 'malformed_json':
        function['arguments'] = '{broken'
    elif failure == 'schema_mismatch':
        function['arguments'] = '{"answer":42}'
    elif failure == 'extra_property':
        function['arguments'] = '{"answer":"9am","extra":true}'
    elif failure == 'refusal':
        message['refusal'] = 'Cannot answer'
        message.pop('tool_calls')
    elif failure == 'incomplete':
        choice['finish_reason'] = 'length'
    with pytest.raises(StructuredOutputError):
        complete_scenario(provider, 'gpt-3.5-turbo', 'openai', scenario)
    assert len(sent) == 1


@pytest.mark.parametrize('model', ['gpt-3.5-turbo-0125', 'gpt-3.5-turbo-1106'])
def test_supported_snapshots_use_the_same_transport(transport, scenario, model):
    provider, sent, _ = transport
    result = complete_scenario(provider, model, 'openai', scenario, max_tokens=100)
    assert result['parsed_output'] == {'answer': '9am'}
    assert sent[0]['max_tokens'] == 100
    assert sent[0]['tools'][0]['function']['strict'] is True


@pytest.mark.parametrize('mode', ['native_schema', 'json_mode', 'plain_text'])
def test_other_output_modes_keep_their_existing_transport(transport, scenario, mode):
    provider, sent, wire = transport
    wire['choices'][0]['message'] = {'content': '{"answer":"9am"}'}
    kwargs = {'messages': [{'role': 'user', 'content': 'Answer in JSON.'}], 'model': 'gpt-3.5-turbo'}
    if mode == 'native_schema':
        kwargs.update(model='gpt-4o-mini', response_format={
            'type': 'json_schema', 'json_schema': {
                k: v for k, v in scenario['output_contract'].items() if k != 'type'}})
    elif mode == 'json_mode':
        kwargs['response_format'] = {'type': 'json_object'}
    result = provider.chat_completion(**kwargs)
    assert 'tools' not in sent[0]
    assert sent[0].get('response_format') == kwargs.get('response_format')
    assert json.loads(result['content']) == {'answer': '9am'}
