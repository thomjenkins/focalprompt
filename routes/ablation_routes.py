#!/usr/bin/env python3
"""
Ablation analysis route handlers.
"""

from flask import Blueprint, request, jsonify
from datetime import datetime
import uuid
from services.assessor_factory import get_assessor
from services.ablation_service import AblationService
from services.embedding_service import EmbeddingService
from services.cost_calculator import CostCalculator
from services.checkpoint_service import CheckpointService
from core.ai_gateway_provider import RateLimitError
from utils.request_inference import request_inference_fields


ablation_bp = Blueprint('ablation', __name__)


def _ablation_service(data):
    fields = request_inference_fields(data)
    assessor = get_assessor(data=fields)
    api_key = fields.get('api_key')
    return AblationService(
        assessor.provider,
        fields['model'],
        api_key=api_key,
        embedding_service=EmbeddingService(),
        cost_calculator=CostCalculator(),
        provider_name=getattr(assessor, 'provider_name', fields['provider']),
    )


def _rate_limit_response(exc):
    retry_after = getattr(exc, 'retry_after', None)
    if retry_after is None:
        retry_after = 8
    return jsonify({
        'error': str(exc),
        'retry_after': float(retry_after),
    }), 429


@ablation_bp.route('/api/ablation-analysis', methods=['POST'])
def ablation_analysis():
    """Run ablation analysis to determine focus influence."""
    try:
        data = request.json
        prompt = data.get('prompt', '')
        foci_list = data.get('foci', [])
        num_samples = data.get('num_samples')
        n_baseline = data.get('n_baseline', 10)
        n_ablated = data.get('n_ablated', 5)
        n_permutations = data.get('n_permutations', 10000)
        alpha = data.get('alpha', 0.05)
        permutation_seed = data.get('permutation_seed')
        temperature = data.get('temperature', 0.7)
        inputs = data.get('inputs', {})
        
        if not prompt:
            return jsonify({'error': 'Prompt is required'}), 400
        
        if not foci_list or len(foci_list) == 0:
            return jsonify({'error': 'Foci are required for ablation analysis'}), 400
        
        ablation_service = _ablation_service(data)
        
        # Run ablation
        result_data = ablation_service.run_ablation(
            prompt,
            foci_list,
            num_samples=num_samples,
            inputs=inputs,
            n_baseline=n_baseline,
            n_ablated=n_ablated,
            n_permutations=n_permutations,
            alpha=alpha,
            permutation_seed=permutation_seed,
            temperature=temperature,
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
        
    except RateLimitError as e:
        return _rate_limit_response(e)
    except Exception as e:
        msg = str(e)
        if 'rate limit' in msg.lower() or '429' in msg:
            return _rate_limit_response(e)
        return jsonify({'error': msg}), 500


@ablation_bp.route('/api/ablation-sample', methods=['POST'])
def ablation_sample():
    """One chat completion for client-paced ablation sampling."""
    try:
        data = request.json or {}
        prompt = data.get('prompt', '')
        foci_list = data.get('foci', [])
        kind = data.get('kind', 'baseline')
        focus_index = data.get('focus_index')
        temperature = data.get('temperature', 0.7)
        if not prompt:
            return jsonify({'error': 'Prompt is required'}), 400
        service = _ablation_service(data)
        result = service.sample_completion(
            prompt,
            foci_list,
            kind=kind,
            temperature=temperature,
            focus_index=focus_index,
        )
        return jsonify(result)
    except RateLimitError as e:
        return _rate_limit_response(e)
    except Exception as e:
        msg = str(e)
        if 'rate limit' in msg.lower() or '429' in msg:
            return _rate_limit_response(e)
        return jsonify({'error': msg}), 500


@ablation_bp.route('/api/ablation-score', methods=['POST'])
def ablation_score():
    """Permutation test on samples collected by /api/ablation-sample."""
    try:
        data = request.json or {}
        prompt = data.get('prompt', '')
        foci_list = data.get('foci', [])
        baseline_outputs = data.get('baseline_outputs') or []
        ablated_outputs = data.get('ablated_outputs') or {}
        n_permutations = data.get('n_permutations', 10000)
        alpha = data.get('alpha', 0.05)
        permutation_seed = data.get('permutation_seed')
        temperature = data.get('temperature', 0.7)
        input_tokens = data.get('input_tokens', 0)
        output_tokens = data.get('output_tokens', 0)
        if not prompt:
            return jsonify({'error': 'Prompt is required'}), 400
        if not foci_list:
            return jsonify({'error': 'Foci are required for ablation analysis'}), 400
        service = _ablation_service(data)
        result_data = service.score_from_samples(
            prompt,
            foci_list,
            baseline_outputs,
            ablated_outputs,
            n_permutations=n_permutations,
            alpha=alpha,
            permutation_seed=permutation_seed,
            temperature=temperature,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        checkpoint_service = CheckpointService()
        session_id = str(uuid.uuid4())
        checkpoint_service.save_checkpoint(
            session_id,
            {
                'session_id': session_id,
                'timestamp': datetime.now().isoformat(),
                'type': 'single_ablation',
                'result_data': result_data,
                'complete': True,
            },
            'single_ablation',
        )
        return jsonify(result_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@ablation_bp.route('/api/ablation-shuffle-robustness', methods=['POST'])
def ablation_shuffle_robustness():
    """Re-test one focus with remaining spans in shuffled order (sensitivity check)."""
    try:
        data = request.json or {}
        prompt = data.get('prompt', '')
        foci_list = data.get('foci', [])
        focus_index = data.get('focus_index')
        baseline_outputs = data.get('baseline_outputs') or []
        n_ablated = data.get('n_ablated', 5)
        shuffle_seed = data.get('shuffle_seed')
        n_permutations = data.get('n_permutations', 10000)
        alpha = data.get('alpha', 0.05)
        permutation_seed = data.get('permutation_seed')
        temperature = data.get('temperature', 0.7)

        if not prompt:
            return jsonify({'error': 'Prompt is required'}), 400
        if not foci_list:
            return jsonify({'error': 'Foci are required'}), 400
        if focus_index is None:
            return jsonify({'error': 'focus_index is required'}), 400
        if not baseline_outputs:
            return jsonify({'error': 'baseline_outputs is required (reuse original run)'}), 400

        service = _ablation_service(data)
        result = service.run_shuffle_robustness(
            prompt,
            foci_list,
            int(focus_index),
            baseline_outputs,
            n_ablated=int(n_ablated),
            shuffle_seed=shuffle_seed,
            n_permutations=int(n_permutations),
            alpha=float(alpha),
            permutation_seed=permutation_seed,
            temperature=float(temperature),
        )
        return jsonify(result)
    except RateLimitError as e:
        return _rate_limit_response(e)
    except Exception as e:
        msg = str(e)
        if 'rate limit' in msg.lower() or '429' in msg:
            return _rate_limit_response(e)
        return jsonify({'error': msg}), 500
