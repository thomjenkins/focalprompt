#!/usr/bin/env python3
"""
Behavioral-difference review routes (LLM + human).

Separate from quality/preference evaluation in agent_routes / EvaluationService.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from services.assessor_factory import get_assessor
from services.behavioral_difference_service import (
    HumanBehavioralDifferenceRecord,
    LLMBehavioralDifferenceEvaluator,
    aggregate_behavioral_batch_stats,
    estimate_judge_cost_units,
    recommend_behavioral_review,
    select_foci_for_behavioral_review,
)
from utils.request_inference import request_inference_fields


behavioral_difference_bp = Blueprint('behavioral_difference', __name__)


def _llm_evaluator(data):
    fields = request_inference_fields(data)
    assessor = get_assessor(data=fields)
    return LLMBehavioralDifferenceEvaluator(
        assessor.provider,
        fields['model'],
        provider_name=getattr(assessor, 'provider_name', fields['provider']),
        max_per_group=int(data.get('max_per_group') or 5),
    ), fields


@behavioral_difference_bp.route('/api/behavioral-difference/estimate-cost', methods=['POST'])
def estimate_cost():
    data = request.json or {}
    n = int(data.get('n_reviews') or 0)
    return jsonify(
        estimate_judge_cost_units(
            n,
            n_judges=int(data.get('n_judges') or 1),
            max_per_group=int(data.get('max_per_group') or 5),
        )
    )


@behavioral_difference_bp.route('/api/behavioral-difference/recommend', methods=['POST'])
def recommend():
    data = request.json or {}
    item = data.get('focus_result') or data
    return jsonify(
        recommend_behavioral_review(
            item,
            reported_score=data.get('reported_score'),
        )
    )


@behavioral_difference_bp.route('/api/behavioral-difference/llm-judge', methods=['POST'])
def llm_judge():
    """
    Run LLM behavioral-difference judgment on stored baseline/ablated samples.

    Does not regenerate experiment outputs. Does not evaluate quality/preference.
    """
    try:
        data = request.json or {}
        focus = data.get('focus') or data.get('focus_name') or ''
        removed_span = data.get('removed_span') or data.get('prompt_section') or ''
        baseline_outputs = data.get('baseline_outputs') or []
        ablated_outputs = data.get('ablated_outputs') or []
        if not focus:
            return jsonify({'error': 'focus is required'}), 400
        if not baseline_outputs or not ablated_outputs:
            return jsonify({
                'error': 'baseline_outputs and ablated_outputs are required',
            }), 400

        max_reviews = data.get('max_reviews')
        if max_reviews is not None and int(max_reviews) <= 0:
            return jsonify({
                'error': 'max_reviews cap is 0; LLM behavioral-difference review disabled',
                'code': 'review_cap',
            }), 400

        evaluator, fields = _llm_evaluator(data)
        result = evaluator.evaluate(
            focus=focus,
            removed_span=removed_span,
            baseline_outputs=baseline_outputs,
            ablated_outputs=ablated_outputs,
            prompt_context=data.get('prompt') or data.get('prompt_context'),
            temperature=float(data.get('temperature') or 0.2),
            blind=bool(data.get('blind', True)),
            seed=data.get('seed'),
            n_judges=int(data.get('n_judges') or 1),
        )
        result['model'] = fields['model']
        result['provider'] = fields['provider']
        return jsonify(result), (200 if result.get('status') == 'complete' else 422)
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'failed'}), 500


@behavioral_difference_bp.route('/api/behavioral-difference/human-review', methods=['POST'])
def human_review():
    """Record a human-observed behavioral-difference judgment (not preference)."""
    try:
        data = request.json or {}
        record = HumanBehavioralDifferenceRecord().evaluate(data)
        return jsonify(record)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@behavioral_difference_bp.route('/api/behavioral-difference/batch-aggregate', methods=['POST'])
def batch_aggregate_lenses():
    data = request.json or {}
    rows = data.get('focus_rows') or data.get('influence_scores') or []
    if isinstance(rows, dict):
        rows = list(rows.values())
    return jsonify(aggregate_behavioral_batch_stats(rows))


@behavioral_difference_bp.route('/api/behavioral-difference/select', methods=['POST'])
def select_for_review():
    """
    Select a capped set of foci for optional LLM/human difference review.

    Advisory only — does not run judges and does not escalate every focus.
    """
    data = request.json or {}
    rows = data.get('focus_rows') or data.get('influence_scores') or []
    if isinstance(rows, dict):
        rows = list(rows.values())
    max_reviews = data.get('max_reviews')
    if max_reviews is not None:
        max_reviews = int(max_reviews)
    return jsonify(
        select_foci_for_behavioral_review(
            rows,
            max_reviews=max_reviews,
            include_manual=data.get('include_manual') or data.get('manual_foci'),
            reported_scores=data.get('reported_scores'),
            only_recommended=bool(data.get('only_recommended', True)),
        )
    )
