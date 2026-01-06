#!/usr/bin/env python3
"""
Pricing service for displaying model costs to users.

Provides pricing information with markup for user-facing display.
"""

from typing import Dict
from services.cost_calculator import CostCalculator


class PricingService:
    """Service for providing pricing information to users."""
    
    # Markup multiplier (50% = 1.5x)
    MARKUP_MULTIPLIER = 1.5
    
    def __init__(self):
        """Initialize pricing service."""
        self.cost_calculator = CostCalculator()
    
    def get_model_pricing(self, model: str, provider: str = 'openai') -> Dict:
        """
        Get pricing for a model with markup applied.
        
        Args:
            model: Model name
            provider: Provider name
            
        Returns:
            Dict with pricing information (per 1K tokens, with markup already applied)
        """
        base_pricing = self.cost_calculator.get_pricing(model, provider)
        
        return {
            'input_per_1k': (base_pricing['input'] * 1_000_000 * self.MARKUP_MULTIPLIER) / 1000,
            'output_per_1k': (base_pricing['output'] * 1_000_000 * self.MARKUP_MULTIPLIER) / 1000
        }
    
    def estimate_request_cost(
        self,
        estimated_input_tokens: int,
        estimated_output_tokens: int,
        model: str,
        provider: str = 'openai'
    ) -> Dict:
        """
        Estimate cost for a request.
        
        Args:
            estimated_input_tokens: Estimated input tokens
            estimated_output_tokens: Estimated output tokens
            model: Model name
            provider: Provider name
            
        Returns:
            Dict with cost estimate
        """
        cost_breakdown = self.cost_calculator.calculate_cost(
            estimated_input_tokens,
            estimated_output_tokens,
            0,  # No embeddings in estimate
            model,
            provider
        )
        
        base_cost = cost_breakdown['total_cost']
        total_cost = base_cost * self.MARKUP_MULTIPLIER
        
        return {
            'estimated_input_tokens': estimated_input_tokens,
            'estimated_output_tokens': estimated_output_tokens,
            'base_cost': base_cost,
            'markup': total_cost - base_cost,
            'total_cost': total_cost,
            'total_cents': int(round(total_cost * 100)),
            'model': model,
            'provider': provider
        }
    
    def get_all_models_pricing(self) -> Dict:
        """
        Get pricing for all available models.
        
        Returns:
            Dict organized by provider, then model
        """
        providers = {
            'openai': {
                'name': 'OpenAI',
                'models': [
                    {'id': 'gpt-4o-mini', 'name': 'GPT-4o Mini', 'description': 'Fast, Cheap'},
                    {'id': 'gpt-4o', 'name': 'GPT-4o', 'description': 'Balanced'},
                    {'id': 'gpt-4-turbo', 'name': 'GPT-4 Turbo', 'description': 'High Quality'},
                    {'id': 'gpt-3.5-turbo', 'name': 'GPT-3.5 Turbo', 'description': 'Legacy'}
                ]
            },
            'anthropic': {
                'name': 'Anthropic (Claude)',
                'models': [
                    {'id': 'claude-3-5-sonnet-20241022', 'name': 'Claude 3.5 Sonnet', 'description': 'Latest, Best'},
                    {'id': 'claude-3-5-haiku-20241022', 'name': 'Claude 3.5 Haiku', 'description': 'Fast, Cheap'},
                    {'id': 'claude-3-opus-20240229', 'name': 'Claude 3 Opus', 'description': 'Premium'},
                    {'id': 'claude-3-sonnet-20240229', 'name': 'Claude 3 Sonnet', 'description': 'Balanced'},
                    {'id': 'claude-3-haiku-20240307', 'name': 'Claude 3 Haiku', 'description': 'Fast'}
                ]
            },
            'google': {
                'name': 'Google (Gemini)',
                'models': [
                    {'id': 'gemini-1.5-pro', 'name': 'Gemini 1.5 Pro', 'description': 'Premium'},
                    {'id': 'gemini-1.5-flash', 'name': 'Gemini 1.5 Flash', 'description': 'Fast'},
                    {'id': 'gemini-pro', 'name': 'Gemini Pro', 'description': 'Standard'}
                ]
            },
            'grok': {
                'name': 'Grok (X)',
                'models': [
                    {'id': 'grok-beta', 'name': 'Grok Beta', 'description': 'Beta'},
                    {'id': 'grok-2', 'name': 'Grok 2', 'description': 'Latest'}
                ]
            }
        }
        
        result = {}
        for provider_id, provider_info in providers.items():
            result[provider_id] = {
                'name': provider_info['name'],
                'models': []
            }
            
            for model_info in provider_info['models']:
                pricing = self.get_model_pricing(model_info['id'], provider_id)
                result[provider_id]['models'].append({
                    **model_info,
                    'pricing': pricing
                })
        
        return result

