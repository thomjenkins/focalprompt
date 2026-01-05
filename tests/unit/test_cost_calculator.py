"""
Unit tests for CostCalculator.
"""

import pytest
from services.cost_calculator import CostCalculator


def test_get_pricing_openai():
    """Test getting OpenAI pricing."""
    pricing = CostCalculator.get_pricing('gpt-4o-mini', 'openai')
    assert 'input' in pricing
    assert 'output' in pricing
    assert pricing['input'] > 0
    assert pricing['output'] > 0


def test_get_pricing_anthropic():
    """Test getting Anthropic pricing."""
    pricing = CostCalculator.get_pricing('claude-3-5-sonnet-20241022', 'anthropic')
    assert 'input' in pricing
    assert 'output' in pricing


def test_calculate_cost():
    """Test cost calculation."""
    result = CostCalculator.calculate_cost(
        input_tokens=1000,
        output_tokens=500,
        embedding_tokens=2000,
        model='gpt-4o-mini',
        provider='openai'
    )
    
    assert 'chat_completions' in result
    assert 'embeddings' in result
    assert 'total_cost' in result
    assert result['total_cost'] > 0


def test_estimate_batch_cost():
    """Test batch cost estimation."""
    result = CostCalculator.estimate_batch_cost(
        num_pairs=10,
        num_foci=5,
        num_samples=20,
        model='gpt-4o-mini',
        provider='openai'
    )
    
    assert 'total_cost' in result
    assert result['total_cost'] > 0


