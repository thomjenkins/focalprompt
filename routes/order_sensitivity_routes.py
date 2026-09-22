#!/usr/bin/env python3
"""Routes for focus order / position sensitivity experiments."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from services.assessor_factory import get_assessor
from services.order_sensitivity_service import OrderSensitivityService
from routes.http_errors import internal_error
from utils.json_safe import sanitize_non_finite
from utils.request_inference import request_inference_fields
from utils.inference_scenario import ScenarioValidationError, scenario_from_request

order_sensitivity_bp = Blueprint('order_sensitivity', __name__)


def _workflow_settings(data):
    return {
        'foci': data.get('foci') or [],
        'baseline_outputs': data.get('baseline_outputs') or [],
        'k_permutations': int(data.get('k_permutations', 5)),
        'm_samples': int(data.get('m_samples', 3)),
        'temperature': float(data.get('temperature', .7)),
        'order_seed': int(data.get('order_seed', 7)),
        'statistical_seed': int(data.get('statistical_seed', 42)),
        'focus_index_for_sweep': data.get('focus_index_for_sweep'),
        'run_position_sweep': bool(data.get('run_position_sweep')),
        'run_behavioral_judge': bool(data.get('run_behavioral_judge')),
        'behavioral_criterion': data.get('behavioral_criterion') or '',
        'task_context': data.get('task_context') or '',
    }


@order_sensitivity_bp.route('/api/focus-order-sensitivity/<action>', methods=['POST'])
def focus_order_workflow(action):
    """Bound generation/judging to one output; score only completed saved work."""
    if action not in ('plan', 'sample', 'judge', 'score'):
        return jsonify({'error': 'Unknown focus order action.'}), 404
    try:
        data = request.get_json() or {}
        if not isinstance(data, dict):
            raise ValueError('Request must be a JSON object.')
        scenario, _ = scenario_from_request(data)
        settings = _workflow_settings(data)
        fields = request_inference_fields(data, model_role='mut')
        service = OrderSensitivityService(None, fields['model'], provider_name=fields['provider'])
        plan = service.run_scenario_order_experiment(scenario=scenario, plan_only=True, **settings)
        if not plan.get('ok'):
            return _analysis_json(plan), 400
        if action == 'plan':
            return _analysis_json(plan)
        if action == 'score':
            samples = data.get('samples')
            if not isinstance(samples, dict):
                raise ValueError('Saved samples are required for scoring.')
            for condition in plan['conditions']:
                for sample in samples.get(condition['id'], []):
                    if not isinstance(sample, dict) or sample.get('scenario') != condition['scenario']:
                        raise ValueError('A saved sample does not match its planned scenario.')
            result = service.run_scenario_order_experiment(
                scenario=scenario, recorded_samples=samples,
                recorded_judgments=data.get('judgments'), **settings,
            )
            result['sampling_protocol'] = plan['protocol']
            return _analysis_json(result)

        condition = next((c for c in plan['conditions'] if c['id'] == data.get('condition_id')), None)
        if action == 'sample':
            if condition is None:
                raise ValueError('Select a planned order condition.')
            from utils.inference_scenario import complete_scenario
            assessor = get_assessor(data=fields)
            response = complete_scenario(assessor.provider, fields['model'], fields['provider'],
                                         condition['scenario'], temperature=settings['temperature'])
            if not isinstance(response.get('content'), str) or not response['content'].strip():
                raise ValueError('Model returned an empty response. Retry this sample.')
            return _analysis_json({**response, 'condition_id': condition['id'], 'scenario': condition['scenario']})

        if not settings['run_behavioral_judge']:
            raise ValueError('Behavioural judging is not enabled for this run.')
        if condition is None and data.get('condition_id') != 'baseline':
            raise ValueError('Select a planned order condition or baseline.')
        index = data.get('sample_index')
        count = condition['n_samples'] if condition else len(plan['baseline_outputs'])
        if type(index) is not int or not 0 <= index < count:
            raise ValueError('Invalid sample index.')
        output = data.get('output')
        if not isinstance(output, str) or not output.strip():
            raise ValueError('A completed output is required for judging.')
        if condition is None and output != plan['baseline_outputs'][index]:
            raise ValueError('The output does not match the saved baseline.')
        from services.behavioral_criterion_judge import BehavioralCriterionJudge
        judge_fields = request_inference_fields(data, model_role='analysis')
        assessor = get_assessor(data=judge_fields)
        judgment = BehavioralCriterionJudge(assessor.provider, judge_fields['model'], judge_fields['provider']).judge_output(
            criterion=settings['behavioral_criterion'], output_text=output,
            task_context=settings['task_context'], temperature=settings['temperature'],
        )
        return _analysis_json({'sample_index': index, **judgment})
    except (ScenarioValidationError, ValueError, TypeError) as error:
        return jsonify({'error': str(error)}), 400
    except Exception as error:
        return internal_error('order_sensitivity_' + action, error)


def _analysis_json(data):
    return jsonify(sanitize_non_finite(data))


@order_sensitivity_bp.route('/api/focus-order-sensitivity/estimate-cost', methods=['POST'])
def estimate_focus_order_cost():
    try:
        data = request.json or {}
        fields = request_inference_fields(data, model_role='mut')
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
        scenario, is_legacy = scenario_from_request(data)
        prompt = data.get('prompt') or ''
        foci = data.get('foci') or data.get('foci_list') or []
        baseline_outputs = data.get('baseline_outputs') or []
        if is_legacy and not prompt.strip():
            return jsonify({'error': 'prompt is required'}), 400
        if not foci:
            return jsonify({'error': 'foci is required'}), 400
        if not baseline_outputs:
            return jsonify({'error': 'baseline_outputs from Experiment B are required'}), 400

        fields = request_inference_fields(data, model_role='mut')
        assessor = get_assessor(data=fields)
        analysis_fields = request_inference_fields(data, model_role='analysis')
        analysis_assessor = get_assessor(data=analysis_fields)
        svc = OrderSensitivityService(
            assessor.provider,
            fields['model'],
            provider_name=getattr(assessor, 'provider_name', fields['provider']),
            judge_provider=analysis_assessor.provider,
            judge_model=analysis_fields['model'],
            judge_provider_name=getattr(
                analysis_assessor, 'provider_name', analysis_fields['provider']
            ),
        )

        assessment_service = None
        if data.get('run_reported_focus'):
            from services.assessment_service import AssessmentService
            assessment_service = AssessmentService(analysis_assessor)

        experiment_kwargs = dict(
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
        if is_legacy:
            result = svc.run_focus_order_experiment(prompt=prompt, **experiment_kwargs)
        else:
            result = svc.run_scenario_order_experiment(
                scenario=scenario,
                **experiment_kwargs,
            )
        if not result.get('ok'):
            return _analysis_json(result), 400
        return _analysis_json(result)
    except (ScenarioValidationError, ValueError) as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return internal_error('order_sensitivity_run', e)
