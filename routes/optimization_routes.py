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
from utils.inference_scenario import ScenarioValidationError, validate_scenario

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
        original_prompt = data.get('prompt', data.get('original_prompt', ''))
        has_scenario = data.get('scenario') is not None
        has_prompt = isinstance(original_prompt, str) and bool(original_prompt.strip())
        if has_scenario == has_prompt:
            return jsonify({'error': 'Provide exactly one of scenario or prompt'}), 400
        
        fields = request_inference_fields(data, model_role='analysis')
        assessor = get_assessor(data=fields)
        cost_calculator = CostCalculator()
        
        service = OptimizationService(
            assessor.provider,
            fields['model'],
            cost_calculator
        )
        
        if has_scenario:
            result = service.analyze_scenario_optimization(
                single_assessment,
                single_ablation,
                batch_analysis,
                agent_results,
                foci_list,
                validate_scenario(data['scenario']),
            )
        else:
            result = service.analyze_prompt_optimization(
                single_assessment,
                single_ablation,
                batch_analysis,
                agent_results,
                foci_list,
                original_prompt
            )
        
        return jsonify(result)
        
    except ScenarioValidationError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return internal_error('optimization_analyze_prompt', e)
