"""AI Gateway chat_completion must raise, never return None."""

from unittest.mock import Mock, patch

import pytest
import requests

from core.ai_gateway_provider import (
    AIGatewayProvider,
    RateLimitError,
    retry_after_seconds,
)
from services.ablation_service import AblationService
from services.embedding_service import EmbeddingService


def _http_error(status_code, message='rate limited', headers=None):
    response = Mock()
    response.status_code = status_code
    response.headers = headers or {}
    response.json.return_value = {'error': {'message': message}}
    response.text = message
    err = requests.exceptions.HTTPError(response=response)
    err.response = response
    return err


def _requests_mod(post_side_effect):
    mod = Mock()
    mod.exceptions = requests.exceptions
    mod.post.side_effect = post_side_effect
    return mod


@patch('core.ai_gateway_provider.time.sleep', return_value=None)
@patch('core.ai_gateway_provider._check_requests')
def test_persistent_429_raises_rate_limit(check, _sleep):
    check.return_value = _requests_mod(_http_error(429))
    provider = AIGatewayProvider('test-key')
    with pytest.raises(RateLimitError, match='Rate limit exceeded') as exc:
        provider.chat_completion(
            [{'role': 'user', 'content': 'hi'}],
            model='gpt-4o-mini',
            provider='openai',
        )
    assert exc.value.retry_after >= 1
    assert check.return_value.post.call_count == 2


@patch('core.ai_gateway_provider.time.sleep', return_value=None)
@patch('core.ai_gateway_provider._check_requests')
def test_429_then_success_returns_content(check, _sleep):
    ok = Mock()
    ok.raise_for_status.return_value = None
    ok.json.return_value = {
        'choices': [{'message': {'content': 'hello'}}],
        'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2},
    }
    check.return_value = _requests_mod([_http_error(429), ok])
    provider = AIGatewayProvider('test-key')
    out = provider.chat_completion(
        [{'role': 'user', 'content': 'hi'}],
        model='gpt-4o-mini',
        provider='openai',
    )
    assert out['content'] == 'hello'


def test_retry_after_seconds_prefers_ms_header():
    response = Mock()
    response.headers = {'retry-after-ms': '7000', 'retry-after': '1'}
    assert retry_after_seconds(response, fallback=5) == 7.0


@patch('core.ai_gateway_provider.time.sleep', return_value=None)
@patch('core.ai_gateway_provider._check_requests')
def test_429_uses_retry_after_header(check, _sleep):
    ok = Mock()
    ok.raise_for_status.return_value = None
    ok.json.return_value = {
        'choices': [{'message': {'content': 'hello'}}],
        'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2},
    }
    check.return_value = _requests_mod([
        _http_error(429, headers={'retry-after': '12'}),
        ok,
    ])
    provider = AIGatewayProvider('test-key')
    out = provider.chat_completion(
        [{'role': 'user', 'content': 'hi'}],
        model='gpt-4o-mini',
        provider='openai',
    )
    assert out['content'] == 'hello'
    assert _sleep.call_args_list[0].args[0] == 12.0


def test_ablation_complete_does_not_stack_rate_limit_retries():
    provider = Mock()
    provider.chat_completion.side_effect = Exception(
        'Rate limit exceeded. Please wait a minute and try again, '
        'or lower baseline/ablated sample counts.'
    )
    service = AblationService(
        provider,
        'gpt-4o-mini',
        provider_name='openai',
        embedding_service=Mock(spec=EmbeddingService),
    )
    with pytest.raises(Exception, match='Rate limit exceeded'):
        service._complete('prompt', 0.7)
    assert provider.chat_completion.call_count == 1


def test_ablation_complete_does_not_treat_none_as_success():
    provider = Mock()
    provider.chat_completion.return_value = None
    service = AblationService(
        provider,
        'gpt-4o-mini',
        provider_name='openai',
        embedding_service=Mock(spec=EmbeddingService),
    )
    with pytest.raises(Exception, match='empty response'):
        service._complete('prompt', 0.7)
