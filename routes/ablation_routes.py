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


ablation_bp = Blueprint('ablation', __name__)


def get_api_key_and_model(data):
    """Extract API key, model, and provider from request data, with fallbacks."""
    api_key = data.get('api_key') or os.getenv("OPENAI_API_KEY")
    model = data.get('model', 'gpt-4o-mini')
    provider = data.get('provider', 'openai')
    return api_key, model, provider


@ablation_bp.route('/api/ablation-analysis', methods=['POST'])
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
        
        return jsonify(result_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


