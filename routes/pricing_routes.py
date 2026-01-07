#!/usr/bin/env python3
"""
Pricing route handlers.

Provides endpoints for users to view model pricing and get cost estimates.
"""

from flask import Blueprint, request, jsonify
from services.pricing_service import PricingService
from services.assessor_factory import get_assessor
from middleware.auth import optional_auth
import os

pricing_bp = Blueprint('pricing', __name__)

# Initialize service
pricing_service = PricingService()


@pricing_bp.route('/api/pricing/estimate', methods=['POST'])
@optional_auth
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
        
        estimate = pricing_service.estimate_request_cost(
            estimated_input_tokens,
            estimated_output_tokens,
            model,
            provider
        )
        return jsonify(estimate)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@pricing_bp.route('/api/pricing/models', methods=['GET'])
@optional_auth
def get_models_pricing():
    """Get list of all models with their pricing (including markup)."""
    try:
        models_pricing = pricing_service.get_all_models_pricing()
        return jsonify(models_pricing)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@pricing_bp.route('/api/models', methods=['GET'])
@optional_auth
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
        import sys
        import traceback
        print(f"Error fetching models from gateway: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return jsonify({'error': str(e), 'models': {}, 'source': 'error'}), 500

