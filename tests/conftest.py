"""
Pytest configuration and fixtures for FocalPrompt tests.
"""

import pytest
from unittest.mock import Mock, MagicMock


@pytest.fixture
def mock_provider():
    """Create a mock LLM provider."""
    provider = Mock()
    provider.chat_completion = Mock(return_value={
        'content': 'Test response',
        'usage': {
            'prompt_tokens': 10,
            'completion_tokens': 5,
            'total_tokens': 15
        }
    })
    provider.list_models = Mock(return_value=['gpt-4o-mini', 'gpt-4o'])
    return provider


@pytest.fixture
def mock_embedding_service():
    """Create a mock embedding service."""
    import numpy as np
    service = Mock()
    service.get_embedding = Mock(return_value=np.random.rand(1536))
    service.get_embedding_with_usage = Mock(return_value=(np.random.rand(1536), 10))
    service.batch_embeddings = Mock(return_value=[np.random.rand(1536) for _ in range(3)])
    return service


@pytest.fixture
def sample_foci():
    """Sample foci for testing."""
    return [
        {
            'focus': 'Focus 1',
            'prompt_section': 'Section 1 content',
            'is_dynamic': False
        },
        {
            'focus': 'Focus 2',
            'prompt_section': 'Section 2 content',
            'is_dynamic': True,
            'dynamic_type': 'chat'
        }
    ]


@pytest.fixture
def sample_pairs():
    """Sample pairs for testing."""
    return [
        {
            'inputs': {
                'chat_content': 'User message 1',
                'rag_context': '',
                'tool_results': ''
            },
            'output': 'Response 1'
        },
        {
            'inputs': {
                'chat_content': 'User message 2',
                'rag_context': '',
                'tool_results': ''
            },
            'output': 'Response 2'
        }
    ]


