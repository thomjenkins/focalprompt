#!/usr/bin/env python3
"""
Pricing route handlers.

Unauthenticated helpers for model pricing and cost estimates (no billing).
"""

from flask import Blueprint, request, jsonify
from services.cost_calculator import CostCalculator
import os

from routes.http_errors import internal_error

pricing_bp = Blueprint('pricing', __name__)


@pricing_bp.route('/api/pricing/estimate', methods=['POST'])
def get_cost_estimate():
    """Estimate cost for a given number of input/output tokens."""
    try:
        data = request.json
        model = data.get('model')
        provider = data.get('provider')
        estimated_input_tokens = data.get('estimated_input_tokens', 0)
        estimated_output_tokens = data.get('estimated_output_tokens', 0)

        if not model or not provider:
            return jsonify({'error': 'Model and provider are required'}), 400
        
        cost_breakdown = CostCalculator.calculate_cost(
            estimated_input_tokens,
            estimated_output_tokens,
            0,
            model,
            provider,
        )
        total_cost = cost_breakdown['total_cost']
        return jsonify({
            'estimated_input_tokens': estimated_input_tokens,
            'estimated_output_tokens': estimated_output_tokens,
            'total_cost': total_cost,
            'total_cents': int(round(total_cost * 100)),
            'model': model,
            'provider': provider,
        })
    except Exception as e:
        return internal_error('pricing_estimate', e)


@pricing_bp.route('/api/pricing/models', methods=['GET'])
def get_models_pricing():
    """Get list of all models with their base pricing (no markup)."""
    try:
        providers = {
            'openai': CostCalculator.OPENAI_PRICING,
            'anthropic': CostCalculator.ANTHROPIC_PRICING,
            'google': CostCalculator.GOOGLE_PRICING,
            'grok': CostCalculator.GROK_PRICING,
        }
        result = {}
        for provider_name, pricing in providers.items():
            models = {}
            for model_name, rates in pricing.items():
                if model_name == 'embedding' or not isinstance(rates, dict):
                    continue
                models[model_name] = {
                    'input_per_1k': (rates['input'] * 1_000_000) / 1000,
                    'output_per_1k': (rates['output'] * 1_000_000) / 1000,
                }
            result[provider_name] = {
                'name': provider_name.title(),
                'models': models,
            }
        return jsonify(result)
    except Exception as e:
        return internal_error('pricing_models', e)


@pricing_bp.route('/api/models', methods=['GET'])
def get_models():
    """
    Fetch all available models from AI Gateway dynamically.
    
    Returns models in format suitable for the frontend model selector.
    """
    try:
        # Get AI Gateway API key
        gateway_api_key = os.getenv('AI_GATEWAY_API_KEY')
        if not gateway_api_key:
            return jsonify({'error': 'AI Gateway not configured'}), 503
        
        # Create a temporary provider instance to fetch models
        from core.ai_gateway_provider import AIGatewayProvider
        provider = AIGatewayProvider(gateway_api_key)
        
        # Fetch all models from gateway
        all_models = provider.list_all_models()
        
        if not all_models:
            # If fetch failed, return empty list (frontend will use fallback)
            return jsonify({'models': [], 'source': 'fallback'})
        
        # Organize models by provider for frontend
        models_by_provider = {}
        for model in all_models:
            model_id = model.get('id', '')
            if '/' in model_id:
                provider_name, model_name = model_id.split('/', 1)
                provider_name = provider_name.lower()
                
                if provider_name not in models_by_provider:
                    models_by_provider[provider_name] = []
                
                models_by_provider[provider_name].append({
                    'value': model_name,
                    'label': model_id,
                    'provider': provider_name,
                    'name': model.get('name', model_name),
                    'description': model.get('description', ''),
                    'context_length': model.get('context_length'),
                    'max_output_tokens': model.get('max_output_tokens'),
                    'type': model.get('type', 'language'),
                    'pricing': model.get('pricing', {})
                })
        
        # Sort models within each provider
        for provider_name in models_by_provider:
            models_by_provider[provider_name].sort(key=lambda x: x['value'])
        
        return jsonify({
            'models': models_by_provider,
            'source': 'gateway',
            'total': len(all_models)
        })
        
    except Exception as e:
        return internal_error('pricing_gateway_models', e, extra={'models': {}, 'source': 'error'})
