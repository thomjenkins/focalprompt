#!/usr/bin/env python3
"""
Optimization route handlers.
"""

from flask import Blueprint, request, jsonify
from services.assessor_factory import get_assessor
from services.optimization_service import OptimizationService
from services.cost_calculator import CostCalculator
from routes.http_errors import internal_error
from utils.request_inference import request_inference_fields

optimization_bp = Blueprint('optimization', __name__)


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
        
        fields = request_inference_fields(data, model_role='analysis')
        assessor = get_assessor(data=fields)
        cost_calculator = CostCalculator()
        
        service = OptimizationService(
            assessor.provider,
            fields['model'],
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
        return internal_error('optimization_analyze_prompt', e)
