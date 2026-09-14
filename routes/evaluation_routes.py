#!/usr/bin/env python3
"""Routes for task/quality output evaluation (not behavioral difference)."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from services.assessor_factory import get_assessor
from services.cost_calculator import CostCalculator
from services.output_evaluator_service import OutputQualityEvaluator
from routes.http_errors import internal_error
from utils.request_inference import request_inference_fields

evaluation_bp = Blueprint('evaluation', __name__)


@evaluation_bp.route('/api/evaluate-outputs-quality', methods=['POST'])
def evaluate_outputs_quality():
    """
    LLM-evaluate one or more outputs against user-defined criteria.

    Quality / task-fit only — not perturbation sensitivity or behavioral difference.
    """
    try:
        data = request.json or {}
        eval_criteria = data.get('eval_criteria') or data.get('criteria') or ''
        outputs = data.get('outputs') or []
        task_context = data.get('task_context') or data.get('input') or ''
        prompt = data.get('prompt') or data.get('original_prompt') or ''

        if not eval_criteria.strip():
            return jsonify({'error': 'eval_criteria is required'}), 400
        if not outputs:
            return jsonify({'error': 'outputs array is required'}), 400

        fields = request_inference_fields(data, model_role='analysis')
        assessor = get_assessor(data=fields)
        evaluator = OutputQualityEvaluator(
            assessor.provider,
            fields['model'],
            provider_name=getattr(assessor, 'provider_name', fields['provider']),
        )
        raw_sample = data.get('sample_fraction')
        if raw_sample is None:
            raw_sample = data.get('sample_pct', 100)
        sample_fraction = float(raw_sample)
        if sample_fraction > 1.0:
            sample_fraction /= 100.0
        sample_fraction = max(0.01, min(1.0, sample_fraction))

        result = evaluator.evaluate_outputs(
            eval_criteria=eval_criteria,
            outputs=outputs,
            task_context=task_context,
            prompt=prompt,
            temperature=float(data.get('temperature') or 0.2),
            sample_fraction=sample_fraction,
            sample_seed=int(data.get('sample_seed') or 0),
        )

        usage = result.pop('usage', None) or {}
        evaluation_scope = (data.get('evaluation_scope') or 'experiment_b').strip()
        cost_breakdown = None
        if usage:
            cost_breakdown = CostCalculator().calculate_cost(
                int(usage.get('prompt_tokens') or 0),
                int(usage.get('completion_tokens') or 0),
                0,
                fields['model'],
                getattr(assessor, 'provider_name', fields['provider']),
            )

        return jsonify({
            **result,
            'evaluation_scope': evaluation_scope,
            'cost_breakdown': cost_breakdown,
        })
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return internal_error('evaluation_outputs_quality', e)
