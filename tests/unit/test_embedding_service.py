"""
Unit tests for EmbeddingService.
"""

import pytest
from unittest.mock import Mock, patch
from services.embedding_service import EmbeddingService
import numpy as np


@patch('services.embedding_service.OpenAI')
def test_get_embedding(mock_openai_class):
    """Test getting an embedding."""
    mock_client = Mock()
    mock_openai_class.return_value = mock_client
    
    mock_response = Mock()
    mock_response.data = [Mock(embedding=[0.1] * 1536)]
    mock_client.embeddings.create.return_value = mock_response
    
    service = EmbeddingService('test-key')
    embedding = service.get_embedding("Test text")
    
    assert isinstance(embedding, np.ndarray)
    assert len(embedding) == 1536


@patch('services.embedding_service.OpenAI')
def test_get_embedding_with_usage(mock_openai_class):
    """Test getting embedding with usage tracking."""
    mock_client = Mock()
    mock_openai_class.return_value = mock_client
    
    mock_response = Mock()
    mock_response.data = [Mock(embedding=[0.1] * 1536)]
    mock_response.usage = Mock(total_tokens=10)
    mock_client.embeddings.create.return_value = mock_response
    
    service = EmbeddingService('test-key')
    embedding, tokens = service.get_embedding_with_usage("Test text")
    
    assert isinstance(embedding, np.ndarray)
    assert tokens == 10


