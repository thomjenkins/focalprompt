#!/usr/bin/env python3
"""Routes for task/quality output evaluation (not behavioral difference)."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from services.assessor_factory import get_assessor
from services.cost_calculator import CostCalculator
from services.output_evaluator_service import OutputQualityEvaluator, prepare_quality_evaluation, QUALITY_EVAL_BATCH_SIZE
from routes.http_errors import internal_error
from utils.request_inference import request_inference_fields
from utils.inference_scenario import validate_scenario
from utils.model_provider import resolve_model_and_provider

evaluation_bp = Blueprint('evaluation', __name__)


def _sample_fraction(data):
    raw = data.get('sample_fraction')
    if raw is None:
        raw = data.get('sample_pct', 100)
    fraction = float(raw)
    if fraction > 1:
        fraction /= 100
    return max(0.01, min(1.0, fraction))


@evaluation_bp.route('/api/quality-evaluation-plan', methods=['POST'])
def quality_evaluation_plan():
    """Deterministic sampling only; no credentials or model calls."""
    try:
        data = request.json or {}
        return jsonify(prepare_quality_evaluation(data.get('outputs') or [], _sample_fraction(data),
                                                  int(data.get('sample_seed') or 0)))
    except (ValueError, TypeError) as exc:
        return jsonify({'error': str(exc)}), 400


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
        batch_mode = data.get('batch_mode') is True
        sample_fraction = _sample_fraction(data)
        if batch_mode and (not isinstance(outputs, list) or len(outputs) > QUALITY_EVAL_BATCH_SIZE or sample_fraction != 1):
            return jsonify({'error': 'A quality batch must contain at most four preselected outputs; do not resample it.'}), 400

        judge_role = data.get('judge_role')
        if judge_role not in (None, 'self', 'external'):
            return jsonify({'error': 'judge_role must be self or external'}), 400
        generation_model = data.get('generation_model') or {}
        if judge_role:
            if not isinstance(generation_model, dict) or not all(
                isinstance(generation_model.get(key), str) and generation_model[key].strip()
                for key in ('model', 'provider')
            ):
                return jsonify({'error': 'The generation model and provider are required for judge attribution.'}), 400
            generated_model, generated_provider = resolve_model_and_provider(
                generation_model['model'], generation_model['provider'])
        if judge_role == 'self':
            fields = request_inference_fields({**data, 'mut_model': generated_model,
                                               'mut_provider': generated_provider}, model_role='mut')
        else:
            fields = request_inference_fields(data, model_role='analysis')
        if judge_role == 'external' and (fields['model'], fields['provider']) == (generated_model, generated_provider):
            return jsonify({'error': 'Choose a different model for the optional second judge.'}), 400
        scenario = validate_scenario(data['scenario']) if data.get('scenario') is not None else None
        assessor = get_assessor(data=fields)
        evaluator = OutputQualityEvaluator(
            assessor.provider,
            fields['model'],
            provider_name=getattr(assessor, 'provider_name', fields['provider']),
        )
        result = evaluator.evaluate_outputs(
            eval_criteria=eval_criteria,
            outputs=outputs,
            task_context=task_context,
            prompt=prompt,
            temperature=float(data.get('temperature') or 0.2),
            sample_fraction=sample_fraction,
            sample_seed=int(data.get('sample_seed') or 0),
            scenario=scenario,
            stable_ids=batch_mode,
        )

        usage = result.get('usage') or {}
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
            'judge': {'role': judge_role or 'legacy', 'model': fields['model'],
                      'provider': getattr(assessor, 'provider_name', fields['provider']),
                      'temperature': float(data.get('temperature') or 0.2)},
            'assessment_protocol': 'task-quality-batches-v2' if batch_mode else 'task-quality-scenario-v1',
        })
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return internal_error('evaluation_outputs_quality', e)
