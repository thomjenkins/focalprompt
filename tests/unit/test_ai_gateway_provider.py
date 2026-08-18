"""AI Gateway chat_completion must raise, never return None."""

from unittest.mock import Mock, patch

import pytest
import requests

from core.ai_gateway_provider import AIGatewayProvider
from services.ablation_service import AblationService
from services.embedding_service import EmbeddingService


def _http_error(status_code, message='rate limited'):
    response = Mock()
    response.status_code = status_code
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
    with pytest.raises(Exception, match='Rate limit exceeded') as exc:
        provider.chat_completion(
            [{'role': 'user', 'content': 'hi'}],
            model='gpt-4o-mini',
            provider='openai',
        )
    assert exc.value.args[0] == 'Rate limit exceeded. Please wait a few minutes and try again.'


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
