"""
Unit tests for AblationService.
"""

import pytest
from unittest.mock import Mock
from services.ablation_service import AblationService
from services.embedding_service import EmbeddingService
import numpy as np


@pytest.fixture
def mock_provider():
    """Create a mock provider."""
    provider = Mock()
    provider.chat_completion.return_value = {
        'content': 'Test output',
        'usage': {'prompt_tokens': 10, 'completion_tokens': 5}
    }
    return provider


@pytest.fixture
def mock_embedding_service():
    """Create a mock embedding service."""
    service = Mock(spec=EmbeddingService)
    service.get_embedding_with_usage.return_value = (np.random.rand(1536), 10)
    return service


def test_run_ablation(mock_provider, mock_embedding_service):
    """Test running ablation analysis."""
    service = AblationService(
        mock_provider,
        'gpt-4o-mini',
        'test-key',
        mock_embedding_service
    )
    
    prompt = "Test prompt"
    foci_list = [
        {'focus': 'Focus 1', 'prompt_section': 'Section 1'},
        {'focus': 'Focus 2', 'prompt_section': 'Section 2'}
    ]
    
    result = service.run_ablation(prompt, foci_list, num_samples=2)
    
    assert 'baseline_output' in result
    assert 'influence_scores' in result
    assert 'cost_breakdown' in result
    assert len(result['influence_scores']) == len(foci_list)


