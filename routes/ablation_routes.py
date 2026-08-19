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
from services.usage_service import UsageService
from services.billing_service import BillingService
from services.database import Database
from middleware.auth import optional_auth
from core.ai_gateway_provider import RateLimitError
from utils.model_provider import resolve_model_and_provider


ablation_bp = Blueprint('ablation', __name__)

# Initialize services
db = Database()
billing_service = BillingService(db)
usage_service = UsageService(db, billing_service)


def get_api_key_and_model(data):
    """Extract model and provider from request data. API key no longer needed (uses AI Gateway)."""
    model = data.get('model', 'gpt-4o-mini')
    provider = data.get('provider', 'openai')
    model, provider = resolve_model_and_provider(model, provider)
    return None, model, provider


def _ablation_service(model, provider):
    assessor = get_assessor(api_key=None, model=model, provider=provider)
    return AblationService(
        assessor.provider,
        model,
        api_key=None,
        embedding_service=EmbeddingService(),
        cost_calculator=CostCalculator(),
        provider_name=getattr(assessor, 'provider_name', provider),
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
@optional_auth
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
        
        # Check usage limits if authenticated
        if request.user:
            endpoint = '/api/ablation-analysis'
            allowed, error_msg = usage_service.check_limit(request.user['id'], endpoint)
            if not allowed:
                return jsonify({'error': error_msg}), 429
        
        # Get model and provider from request (API key no longer needed - uses AI Gateway)
        _, model, provider = get_api_key_and_model(data)
        ablation_service = _ablation_service(model, provider)
        
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
        
        # Record usage if authenticated
        if request.user:
            tokens = result_data.get('cost_breakdown', {}).get('total_tokens', 0)
            cost = result_data.get('cost_breakdown', {}).get('total_cost', 0.0)
            usage_service.record_usage(request.user['id'], '/api/ablation-analysis', tokens, cost)
        
        return jsonify(result_data)
        
    except RateLimitError as e:
        return _rate_limit_response(e)
    except Exception as e:
        msg = str(e)
        if 'rate limit' in msg.lower() or '429' in msg:
            return _rate_limit_response(e)
        return jsonify({'error': msg}), 500


@ablation_bp.route('/api/ablation-sample', methods=['POST'])
@optional_auth
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
        _, model, provider = get_api_key_and_model(data)
        service = _ablation_service(model, provider)
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
@optional_auth
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
        if request.user:
            allowed, error_msg = usage_service.check_limit(
                request.user['id'], '/api/ablation-analysis'
            )
            if not allowed:
                return jsonify({'error': error_msg}), 429
        _, model, provider = get_api_key_and_model(data)
        service = _ablation_service(model, provider)
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
        if request.user:
            tokens = result_data.get('cost_breakdown', {}).get('total_tokens', 0)
            cost = result_data.get('cost_breakdown', {}).get('total_cost', 0.0)
            usage_service.record_usage(
                request.user['id'], '/api/ablation-analysis', tokens, cost
            )
        return jsonify(result_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


