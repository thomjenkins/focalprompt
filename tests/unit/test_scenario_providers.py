"""Provider-specific scenario translation tests."""

import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from google import genai
from google.genai import types as genai_types
from google.genai import _api_client as genai_api_client

from core.ai_gateway_provider import AIGatewayProvider
from core.llm_providers import AnthropicProvider, GoogleProvider
from utils.inference_scenario import (
    ProviderCapabilityError,
    StructuredOutputError,
    complete_scenario,
)


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


def _gemini_provider(body, captured):
    """Build a GoogleProvider whose real SDK client serializes to `captured`."""

    def fake_request(self, http_method, path, request_dict, http_options=None):
        captured['path'] = path
        captured['request'] = request_dict
        return genai_types.HttpResponse(headers={}, body=json.dumps(body))

    provider = GoogleProvider.__new__(GoogleProvider)
    provider.types = genai_types
    patcher = patch.object(genai_api_client.BaseApiClient, 'request', fake_request)
    patcher.start()
    provider.client = genai.Client(api_key='test-key')
    return provider, patcher


def _gemini_body(text, finish_reason):
    return {
        'candidates': [{
            'content': {'role': 'model', 'parts': [{'text': text}]},
            'finishReason': finish_reason,
        }],
        'usageMetadata': {
            'promptTokenCount': 11,
            'candidatesTokenCount': 7,
            'totalTokenCount': 18,
        },
    }


def test_gemini_serializes_strict_json_schema_and_ordered_conversation():
    captured = {}
    provider, patcher = _gemini_provider(
        _gemini_body('{"answer":"ok"}', 'STOP'), captured
    )
    try:
        result = provider.chat_completion(
            [
                {'role': 'system', 'content': 'System one'},
                {'role': 'developer', 'content': 'Developer two'},
                {'role': 'user', 'content': 'first'},
                {'role': 'assistant', 'content': 'prior answer'},
                {'role': 'user', 'content': 'Question'},
            ],
            model='gemini-2.5-flash',
            response_format=RESPONSE_FORMAT,
            max_tokens=64,
        )
    finally:
        patcher.stop()

    request = captured['request']
    assert request['systemInstruction']['parts'] == [
        {'text': 'System one\n\nDeveloper two'}
    ]
    assert request['contents'] == [
        {'role': 'user', 'parts': [{'text': 'first'}]},
        {'role': 'model', 'parts': [{'text': 'prior answer'}]},
        {'role': 'user', 'parts': [{'text': 'Question'}]},
    ]
    generation_config = request['generationConfig']
    assert generation_config['responseMimeType'] == 'application/json'
    # The wire payload must carry the contract unweakened: the legacy proto
    # Schema field drops/rejects additionalProperties before the request.
    assert generation_config['responseJsonSchema'] == RESPONSE_FORMAT['json_schema']['schema']
    assert generation_config['responseJsonSchema']['additionalProperties'] is False
    assert generation_config['maxOutputTokens'] == 64

    assert result['provider_metadata']['structured_output'] == 'response_json_schema'
    assert result['finish_reason'] == 'stop'
    assert result['usage'] == {
        'prompt_tokens': 11, 'completion_tokens': 7, 'total_tokens': 18
    }


def test_gemini_rejects_an_unrepresentable_conversation_tail():
    provider, patcher = _gemini_provider(_gemini_body('ok', 'STOP'), {})
    try:
        with pytest.raises(ProviderCapabilityError, match='end with a user'):
            provider.chat_completion([
                {'role': 'user', 'content': 'first'},
                {'role': 'assistant', 'content': 'prior answer'},
            ], model='gemini-2.5-flash')
    finally:
        patcher.stop()


def test_gemini_truncated_structured_output_fails_even_when_the_text_parses():
    captured = {}
    # The real SDK finish reason enum: str() renders it as FinishReason.MAX_TOKENS
    # here and as a bare ordinal on protobuf enums, so the provider must
    # normalize it rather than pass str(value) downstream.
    provider, patcher = _gemini_provider(
        _gemini_body('{"answer":"ok"}', 'MAX_TOKENS'), captured
    )
    scenario = {
        'version': 1,
        'messages': [
            {'id': 'sys', 'role': 'system', 'content': 'System one'},
            {'id': 'ask', 'role': 'user', 'content': 'Question'},
        ],
        'output_contract': {
            'type': 'json_schema',
            'name': 'answer',
            'strict': True,
            'schema': RESPONSE_FORMAT['json_schema']['schema'],
        },
    }
    try:
        with pytest.raises(StructuredOutputError, match='incomplete'):
            complete_scenario(
                provider, 'gemini-2.5-flash', 'google', scenario, max_tokens=8
            )
    finally:
        patcher.stop()
    assert captured['request']['generationConfig']['maxOutputTokens'] == 8


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
def test_gateway_structured_output_rejection_is_a_capability_error(check):
    import requests

    response = Mock()
    response.status_code = 400
    response.json.return_value = {
        'error': {'message': 'response_format json_schema is unsupported by this model'}
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
            model='model-without-schema',
            provider='anthropic',
            response_format=RESPONSE_FORMAT,
        )
