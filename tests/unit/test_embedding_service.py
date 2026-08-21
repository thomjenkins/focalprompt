"""Unit tests for EmbeddingService (HTTP / OpenAI-compatible embeddings)."""

from unittest.mock import Mock, patch

import numpy as np

from services.embedding_service import EmbeddingService


def _ok_response(embedding=None, tokens=10):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        'data': [{'embedding': embedding or ([0.1] * 8)}],
        'usage': {'total_tokens': tokens, 'prompt_tokens': tokens},
    }
    return response


@patch('services.embedding_service._check_requests')
def test_get_embedding(check):
    mod = Mock()
    mod.exceptions = Mock()
    mod.exceptions.HTTPError = type('HTTPError', (Exception,), {})
    mod.post.return_value = _ok_response()
    check.return_value = mod
    service = EmbeddingService(api_key='test-key', base_url='https://example.test/v1', model='text-embedding-3-small')
    embedding = service.get_embedding('Test text')
    assert isinstance(embedding, np.ndarray)
    assert len(embedding) == 8


@patch('services.embedding_service._check_requests')
def test_get_embedding_with_usage(check):
    mod = Mock()
    mod.exceptions = Mock()
    mod.exceptions.HTTPError = type('HTTPError', (Exception,), {})
    mod.post.return_value = _ok_response(tokens=10)
    check.return_value = mod
    service = EmbeddingService(api_key='test-key', base_url='https://example.test/v1')
    embedding, tokens = service.get_embedding_with_usage('Test text')
    assert isinstance(embedding, np.ndarray)
    assert tokens == 10
