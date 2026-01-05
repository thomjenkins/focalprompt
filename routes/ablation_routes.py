#!/usr/bin/env python3
"""
Ablation analysis route handlers.
"""

from flask import Blueprint, request, jsonify
from datetime import datetime
import uuid
import os
from services.assessor_factory import get_assessor
from services.ablation_service import AblationService
from services.embedding_service import EmbeddingService
from services.cost_calculator import CostCalculator
from services.checkpoint_service import CheckpointService
from services.usage_service import UsageService
from services.database import Database
from middleware.auth import optional_auth


ablation_bp = Blueprint('ablation', __name__)

# Initialize services
db = Database()
usage_service = UsageService(db)


def get_api_key_and_model(data):
    """Extract API key, model, and provider from request data, with fallbacks."""
    api_key = data.get('api_key') or os.getenv("OPENAI_API_KEY")
    model = data.get('model', 'gpt-4o-mini')
    provider = data.get('provider', 'openai')
    return api_key, model, provider


@ablation_bp.route('/api/ablation-analysis', methods=['POST'])
@optional_auth
def ablation_analysis():
    """Run ablation analysis to determine focus influence."""
    try:
        data = request.json
        prompt = data.get('prompt', '')
        foci_list = data.get('foci', [])
        num_samples = data.get('num_samples', 20)
        inputs = data.get('inputs', {})
        
        if not prompt:
            return jsonify({'error': 'Prompt is required'}), 400
        
        if not foci_list or len(foci_list) == 0:
            return jsonify({'error': 'Foci are required for ablation analysis'}), 400
        
        # Check usage limits if authenticated
        if request.user:
            endpoint = '/api/ablation-analysis'
            allowed, error_msg = usage_service.check_limit(request.user['id'], endpoint)
            if not allowed:
                return jsonify({'error': error_msg}), 429
        
        # Get API key, model, and provider from request
        api_key, model, provider = get_api_key_and_model(data)
        if not api_key:
            return jsonify({'error': 'API key is required. Please provide it in settings or set OPENAI_API_KEY environment variable.'}), 500
        
        assessor = get_assessor(api_key=api_key, model=model, provider=provider)
        provider_instance = assessor.provider
        
        # Create services
        embedding_service = EmbeddingService(api_key)
        cost_calculator = CostCalculator()
        ablation_service = AblationService(
            provider_instance,
            model,
            api_key,
            embedding_service,
            cost_calculator
        )
        
        # Run ablation
        result_data = ablation_service.run_ablation(
            prompt,
            foci_list,
            num_samples,
            inputs
        )
        
        # Save checkpoint
        checkpoint_service = CheckpointService()
        session_id = str(uuid.uuid4())
        checkpoint_data = {
            'session_id': session_id,
            'timestamp': datetime.now().isoformat(),
            'type': 'single_ablation',
            'result_data': result_data,
            'complete': True
        }
        checkpoint_service.save_checkpoint(session_id, checkpoint_data, 'single_ablation')
        
        # Record usage if authenticated
        if request.user:
            tokens = result_data.get('cost_breakdown', {}).get('total_tokens', 0)
            cost = result_data.get('cost_breakdown', {}).get('total_cost', 0.0)
            usage_service.record_usage(request.user['id'], '/api/ablation-analysis', tokens, cost)
        
        return jsonify(result_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


