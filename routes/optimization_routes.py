#!/usr/bin/env python3
"""
Optimization route handlers.
"""

from flask import Blueprint, request, jsonify
import os
from services.assessor_factory import get_assessor
from services.optimization_service import OptimizationService
from services.cost_calculator import CostCalculator

optimization_bp = Blueprint('optimization', __name__)


def get_api_key_and_model(data):
    """Extract API key, model, and provider from request data, with fallbacks."""
    api_key = data.get('api_key') or os.getenv("OPENAI_API_KEY")
    model = data.get('model', 'gpt-4o')
    provider = data.get('provider', 'openai')
    return api_key, model, provider


@optimization_bp.route('/api/analyze-prompt-optimization', methods=['POST'])
def analyze_prompt_optimization():
    """Analyze all data and get LLM recommendations for prompt optimization."""
    try:
        data = request.json
        single_assessment = data.get('single_assessment', [])
        single_ablation = data.get('single_ablation', {})
        batch_analysis = data.get('batch_analysis', {})
        agent_results = data.get('agent_results', [])
        foci_list = data.get('foci', [])
        original_prompt = data.get('original_prompt', '')
        
        # Get model and provider from request (API key no longer needed - uses AI Gateway)
        _, model, provider = get_api_key_and_model(data)
        
        assessor = get_assessor(api_key=None, model=model, provider=provider)
        cost_calculator = CostCalculator()
        
        service = OptimizationService(
            assessor.provider,
            model,
            cost_calculator
        )
        
        result = service.analyze_prompt_optimization(
            single_assessment,
            single_ablation,
            batch_analysis,
            agent_results,
            foci_list,
            original_prompt
        )
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

