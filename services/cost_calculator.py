#!/usr/bin/env python3
"""
Cost calculation service for LLM API usage.

Centralizes pricing logic and cost calculation across all providers.
"""

from typing import Dict, Optional


class CostCalculator:
    """Calculate costs for LLM API usage."""
    
    # Pricing per million tokens (as of 2024)
    # OpenAI pricing
    OPENAI_PRICING = {
        'gpt-4o-mini': {'input': 0.15 / 1_000_000, 'output': 0.60 / 1_000_000},
        'gpt-4o': {'input': 2.50 / 1_000_000, 'output': 10.00 / 1_000_000},
        'gpt-4-turbo': {'input': 10.00 / 1_000_000, 'output': 30.00 / 1_000_000},
        'gpt-3.5-turbo': {'input': 0.50 / 1_000_000, 'output': 1.50 / 1_000_000},
        'embedding': 0.02 / 1_000_000
    }
    
    # Anthropic pricing
    ANTHROPIC_PRICING = {
        'claude-3-5-sonnet-20241022': {'input': 3.00 / 1_000_000, 'output': 15.00 / 1_000_000},
        'claude-3-5-haiku-20241022': {'input': 0.80 / 1_000_000, 'output': 4.00 / 1_000_000},
        'claude-3-opus-20240229': {'input': 15.00 / 1_000_000, 'output': 75.00 / 1_000_000},
        'claude-3-sonnet-20240229': {'input': 3.00 / 1_000_000, 'output': 15.00 / 1_000_000},
        'claude-3-haiku-20240307': {'input': 0.25 / 1_000_000, 'output': 1.25 / 1_000_000}
    }
    
    # Google pricing
    GOOGLE_PRICING = {
        'gemini-1.5-pro': {'input': 1.25 / 1_000_000, 'output': 5.00 / 1_000_000},
        'gemini-1.5-flash': {'input': 0.075 / 1_000_000, 'output': 0.30 / 1_000_000},
        'gemini-pro': {'input': 0.50 / 1_000_000, 'output': 1.50 / 1_000_000}
    }
    
    # Grok pricing (using OpenAI-compatible API, similar pricing)
    GROK_PRICING = {
        'grok-beta': {'input': 0.10 / 1_000_000, 'output': 0.40 / 1_000_000},
        'grok-2': {'input': 0.10 / 1_000_000, 'output': 0.40 / 1_000_000}
    }
    
    @classmethod
    def get_pricing(cls, model: str, provider: str = 'openai') -> Dict[str, float]:
        """
        Get pricing for a specific model and provider.
        
        Args:
            model: Model name
            provider: Provider name ('openai', 'anthropic', 'google', 'grok')
            
        Returns:
            Dict with 'input' and 'output' pricing per token
        """
        pricing_map = {
            'openai': cls.OPENAI_PRICING,
            'anthropic': cls.ANTHROPIC_PRICING,
            'google': cls.GOOGLE_PRICING,
            'grok': cls.GROK_PRICING
        }
        
        provider_pricing = pricing_map.get(provider, cls.OPENAI_PRICING)
        return provider_pricing.get(model, cls.OPENAI_PRICING['gpt-4o-mini'])
    
    @classmethod
    def calculate_cost(
        cls,
        input_tokens: int,
        output_tokens: int,
        embedding_tokens: int,
        model: str,
        provider: str = 'openai'
    ) -> Dict:
        """
        Calculate total cost for API usage.
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            embedding_tokens: Number of embedding tokens (OpenAI only)
            model: Model name
            provider: Provider name
            
        Returns:
            Dict with cost breakdown
        """
        model_pricing = cls.get_pricing(model, provider)
        
        # Calculate chat completion costs
        chat_input_cost = input_tokens * model_pricing['input']
        chat_output_cost = output_tokens * model_pricing['output']
        chat_total_cost = chat_input_cost + chat_output_cost
        
        # Calculate embedding costs (only OpenAI supports embeddings)
        embedding_cost = 0.0
        if provider == 'openai' and embedding_tokens > 0:
            embedding_pricing = cls.OPENAI_PRICING.get('embedding', 0.02 / 1_000_000)
            embedding_cost = embedding_tokens * embedding_pricing
        
        total_cost = chat_total_cost + embedding_cost
        
        return {
            'chat_completions': {
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'cost': chat_total_cost
            },
            'embeddings': {
                'tokens': embedding_tokens,
                'cost': embedding_cost
            },
            'total_cost': total_cost,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'embedding_tokens': embedding_tokens,
            'total_tokens': input_tokens + output_tokens + embedding_tokens,
            'model': model
        }
    
    @classmethod
    def estimate_batch_cost(
        cls,
        num_pairs: int,
        num_foci: int,
        num_samples: int = 20,
        model: str = 'gpt-4o-mini',
        provider: str = 'openai'
    ) -> Dict:
        """
        Estimate cost for batch analysis.
        
        Args:
            num_pairs: Number of input-output pairs
            num_foci: Number of foci to analyze
            num_samples: Number of baseline samples
            model: Model name
            provider: Provider name
            
        Returns:
            Dict with estimated cost breakdown
        """
        # Rough estimates per operation
        tokens_per_prompt = 500  # Average prompt size
        tokens_per_output = 200  # Average output size
        tokens_per_embedding = 200  # Average text for embedding
        
        # For each pair:
        # - 1 baseline generation
        # - num_samples baseline generations
        # - num_foci ablated generations
        # - num_foci ablated generations
        # - (num_samples + num_foci + 1) embeddings
        
        operations_per_pair = 1 + num_samples + num_foci
        embeddings_per_pair = num_samples + num_foci + 1
        
        total_input_tokens = operations_per_pair * num_pairs * tokens_per_prompt
        total_output_tokens = operations_per_pair * num_pairs * tokens_per_output
        total_embedding_tokens = embeddings_per_pair * num_pairs * tokens_per_embedding
        
        return cls.calculate_cost(
            total_input_tokens,
            total_output_tokens,
            total_embedding_tokens,
            model,
            provider
        )


