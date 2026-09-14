"""Provider-specific scenario translation tests."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from core.ai_gateway_provider import AIGatewayProvider
from core.llm_providers import AnthropicProvider, GoogleProvider
from utils.inference_scenario import ProviderCapabilityError


RESPONSE_FORMAT = {
    'type': 'json_schema',
    'json_schema': {
        'name': 'answer',
        'strict': True,
        'schema': {
            'type': 'object',
            'properties': {'answer': {'type': 'string'}},
            'required': ['answer'],
            'additionalProperties': False,
        },
    },
}

MESSAGES = [
    {'role': 'system', 'content': 'System one'},
    {'role': 'developer', 'content': 'Developer two'},
    {'role': 'user', 'content': 'Question'},
]


def test_anthropic_preserves_instruction_block_order_and_schema():
    provider = AnthropicProvider.__new__(AnthropicProvider)
    provider.client = Mock()
    provider.client.messages.create.return_value = SimpleNamespace(
        content=[SimpleNamespace(type='text', text='{"answer":"ok"}')],
        stop_reason='end_turn',
        usage=SimpleNamespace(input_tokens=3, output_tokens=2),
    )
    result = provider.chat_completion(
        MESSAGES, model='claude', response_format=RESPONSE_FORMAT
    )
    kwargs = provider.client.messages.create.call_args.kwargs
    assert kwargs['system'] == [
        {'type': 'text', 'text': 'System one'},
        {'type': 'text', 'text': 'Developer two'},
    ]
    assert kwargs['messages'] == [{'role': 'user', 'content': 'Question'}]
    assert kwargs['output_config']['format']['schema'] == RESPONSE_FORMAT['json_schema']['schema']
    assert result['provider_metadata']['structured_output'] == 'output_config.format'


def test_gemini_uses_native_instruction_and_response_schema():
    provider = GoogleProvider.__new__(GoogleProvider)
    chat = Mock()
    chat.send_message.return_value = SimpleNamespace(
        text='{"answer":"ok"}', candidates=[SimpleNamespace(finish_reason='STOP')]
    )
    model = Mock()
    model.start_chat.return_value = chat
    provider.genai = Mock()
    provider.genai.GenerativeModel.return_value = model
    result = provider.chat_completion(
        MESSAGES, model='gemini', response_format=RESPONSE_FORMAT
    )
    assert provider.genai.GenerativeModel.call_args.kwargs['system_instruction'] == (
        'System one\n\nDeveloper two'
    )
    config = chat.send_message.call_args.kwargs['generation_config']
    assert config['response_mime_type'] == 'application/json'
    assert config['response_schema'] == RESPONSE_FORMAT['json_schema']['schema']
    assert result['provider_metadata']['structured_output'] == 'response_schema'


def test_gemini_preserves_conversation_history_and_rejects_an_unrepresentable_tail():
    provider = GoogleProvider.__new__(GoogleProvider)
    chat = Mock()
    chat.send_message.return_value = SimpleNamespace(
        text='ok', candidates=[SimpleNamespace(finish_reason='STOP')]
    )
    model = Mock()
    model.start_chat.return_value = chat
    provider.genai = Mock()
    provider.genai.GenerativeModel.return_value = model

    provider.chat_completion([
        {'role': 'user', 'content': 'first'},
        {'role': 'assistant', 'content': 'prior answer'},
        {'role': 'user', 'content': 'follow-up'},
    ], model='gemini')
    assert model.start_chat.call_args.kwargs['history'] == [
        {'role': 'user', 'parts': ['first']},
        {'role': 'model', 'parts': ['prior answer']},
    ]
    assert chat.send_message.call_args.args[0] == 'follow-up'

    with pytest.raises(ProviderCapabilityError, match='end with a user'):
        provider.chat_completion([
            {'role': 'user', 'content': 'first'},
            {'role': 'assistant', 'content': 'prior answer'},
        ], model='gemini')


@patch('core.ai_gateway_provider._check_requests')
def test_gateway_forwards_json_schema_for_every_model_and_provider(check):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        'choices': [{'message': {'content': '{"answer":"ok"}'}, 'finish_reason': 'stop'}],
        'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2},
    }
    requests_module = Mock()
    import requests
    requests_module.exceptions = requests.exceptions
    requests_module.post.return_value = response
    check.return_value = requests_module
    provider = AIGatewayProvider('key')
    provider.chat_completion(
        MESSAGES,
        model='some-mini-model',
        provider='anthropic',
        response_format=RESPONSE_FORMAT,
    )
    payload = requests_module.post.call_args.kwargs['json']
    assert payload['response_format'] == RESPONSE_FORMAT
    assert payload['messages'] == MESSAGES


@patch('core.ai_gateway_provider._check_requests')
@pytest.mark.parametrize('model, provider_name, message', [
    ('model-without-schema', 'anthropic', 'response_format json_schema is unsupported by this model'),
    ('gpt-3.5-turbo', 'openai', 'strict function output is unsupported by this model'),
])
def test_gateway_structured_output_rejection_is_a_capability_error(check, model, provider_name, message):
    import requests

    response = Mock()
    response.status_code = 400
    response.json.return_value = {
        'error': {'message': message}
    }
    error = requests.exceptions.HTTPError(response=response)
    response.raise_for_status.side_effect = error
    requests_module = Mock()
    requests_module.exceptions = requests.exceptions
    requests_module.post.return_value = response
    check.return_value = requests_module

    provider = AIGatewayProvider('key')
    with pytest.raises(ProviderCapabilityError, match='required structured output'):
        provider.chat_completion(
            MESSAGES,
            model=model,
            provider=provider_name,
            response_format=RESPONSE_FORMAT,
        )
    assert requests_module.post.call_count == 1
