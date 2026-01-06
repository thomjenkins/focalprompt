#!/usr/bin/env python3
"""
Pricing route handlers.

Provides endpoints for users to view model pricing and get cost estimates.
"""

from flask import Blueprint, request, jsonify
from services.pricing_service import PricingService
from middleware.auth import optional_auth

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

