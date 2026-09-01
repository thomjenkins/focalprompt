#!/usr/bin/env python3
"""Routes for focus order / position sensitivity experiments."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from services.assessor_factory import get_assessor
from services.order_sensitivity_service import OrderSensitivityService
from routes.http_errors import internal_error
from utils.json_safe import sanitize_non_finite
from utils.request_inference import request_inference_fields

order_sensitivity_bp = Blueprint('order_sensitivity', __name__)


def _analysis_json(data):
    return jsonify(sanitize_non_finite(data))


@order_sensitivity_bp.route('/api/focus-order-sensitivity/estimate-cost', methods=['POST'])
def estimate_focus_order_cost():
    try:
        data = request.json or {}
        fields = request_inference_fields(data)
        assessor = get_assessor(data=fields)
        svc = OrderSensitivityService(
            assessor.provider,
            fields['model'],
            provider_name=getattr(assessor, 'provider_name', fields['provider']),
        )
        estimate = svc.estimate_cost(
            k_permutations=int(data.get('k_permutations') or 5),
            m_samples=int(data.get('m_samples') or 3),
            n_position_slots=int(data.get('n_position_slots') or 5),
            run_position_sweep=bool(data.get('run_position_sweep')),
            run_behavioral_judge=bool(data.get('run_behavioral_judge')),
            n_baseline=len(data.get('baseline_outputs') or []),
        )
        return jsonify(estimate)
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@order_sensitivity_bp.route('/api/focus-order-sensitivity', methods=['POST'])
def run_focus_order_sensitivity():
    """
    Focus order / position sensitivity experiment.

    Reuses Experiment B baseline outputs. Not mechanistic attention analysis.
    """
    try:
        data = request.json or {}
        prompt = data.get('prompt') or ''
        foci = data.get('foci') or data.get('foci_list') or []
        baseline_outputs = data.get('baseline_outputs') or []
        if not prompt.strip():
            return jsonify({'error': 'prompt is required'}), 400
        if not foci:
            return jsonify({'error': 'foci is required'}), 400
        if not baseline_outputs:
            return jsonify({'error': 'baseline_outputs from Experiment B are required'}), 400

        fields = request_inference_fields(data)
        assessor = get_assessor(data=fields)
        svc = OrderSensitivityService(
            assessor.provider,
            fields['model'],
            provider_name=getattr(assessor, 'provider_name', fields['provider']),
        )

        assessment_service = None
        if data.get('run_reported_focus'):
            from services.assessment_service import AssessmentService
            assessment_service = AssessmentService(assessor)

        result = svc.run_focus_order_experiment(
            prompt=prompt,
            foci=foci,
            baseline_outputs=baseline_outputs,
            k_permutations=int(data.get('k_permutations') or 5),
            m_samples=int(data.get('m_samples') or 3),
            order_seed=int(data.get('order_seed') or 7),
            permutation_seed=data.get('permutation_seed'),
            statistical_seed=data.get('statistical_seed'),
            temperature=float(data.get('temperature') or 0.7),
            inputs=data.get('inputs'),
            user_policies=data.get('ordering_policy'),
            behavioral_criterion=data.get('behavioral_criterion') or data.get('eval_criteria'),
            task_context=data.get('task_context') or '',
            focus_index_for_sweep=data.get('focus_index_for_sweep'),
            run_position_sweep=bool(data.get('run_position_sweep')),
            run_behavioral_judge=bool(data.get('run_behavioral_judge')),
            assessment_service=assessment_service,
            run_reported_focus=bool(data.get('run_reported_focus')),
        )
        if not result.get('ok'):
            return _analysis_json(result), 400
        return _analysis_json(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return internal_error('order_sensitivity_run', e)
