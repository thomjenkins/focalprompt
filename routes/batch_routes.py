#!/usr/bin/env python3
"""
Batch analysis route handlers.

These routes will be fully implemented after batch_analysis_service is complete.
For now, they import from the old app.py to maintain functionality.
"""

from flask import Blueprint, request, jsonify, Response, stream_with_context
import json
import os
from services.checkpoint_service import CheckpointService
from services.usage_service import UsageService
from services.billing_service import BillingService
from services.database import Database
from middleware.auth import optional_auth
from utils.data_processing import (
    calculate_statistics_from_results,
    calculate_focus_distribution_statistics,
)
from utils.model_provider import resolve_model_and_provider


batch_bp = Blueprint('batch', __name__)

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


@batch_bp.route('/api/list-checkpoints', methods=['GET'])
def list_checkpoints():
    """List all available checkpoints."""
    try:
        checkpoint_type = request.args.get('type', 'batch_analysis')
        checkpoint_service = CheckpointService()
        checkpoints = checkpoint_service.list_checkpoints(checkpoint_type)
        return jsonify({'checkpoints': checkpoints})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@batch_bp.route('/api/get-checkpoint', methods=['GET'])
def get_checkpoint():
    """Retrieve checkpoint data for a session."""
    try:
        session_id = request.args.get('session_id')
        checkpoint_type = request.args.get('type', 'batch_analysis')
        if not session_id:
            return jsonify({'error': 'session_id required'}), 400
        
        checkpoint_service = CheckpointService()
        checkpoint = checkpoint_service.load_checkpoint(session_id, checkpoint_type)
        
        if checkpoint:
            # Always derive batch statistics from pair results so logic stays in sync
            if checkpoint_type == 'batch_analysis':
                pair_results = checkpoint.get('pair_results', [])
                if pair_results:
                    checkpoint['statistics'] = calculate_statistics_from_results(pair_results)
                    checkpoint['focus_distribution_statistics'] = (
                        calculate_focus_distribution_statistics(pair_results)
                    )
            
            return jsonify(checkpoint)
        else:
            return jsonify({'error': 'Checkpoint not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@batch_bp.route('/api/batch-analysis-stream', methods=['POST'])
@batch_bp.route('/api/batch-ablation-analysis-stream', methods=['POST'])  # legacy URL
@stream_with_context
@optional_auth
def batch_analysis_stream():
    """Run batch ablation analysis with streaming progress updates via SSE."""
    from services.assessor_factory import get_assessor
    from services.batch_analysis_service import BatchAnalysisService
    from services.embedding_service import EmbeddingService
    from services.cost_calculator import CostCalculator
    from services.checkpoint_service import CheckpointService
    from services.assessment_service import AssessmentService
    
    def generate():
        try:
            data = request.json
            pairs = data.get('pairs', [])
            foci_list = data.get('foci', [])
            model = data.get('model', 'gpt-4o-mini')
            num_samples = data.get('num_samples', 20)
            session_id = data.get('session_id')
            resume = data.get('resume', False)
            
            if not pairs or len(pairs) == 0:
                yield f"data: {json.dumps({'type': 'error', 'message': 'At least one pair is required'})}\n\n"
                return
            
            if not foci_list or len(foci_list) == 0:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Foci are required'})}\n\n"
                return
            
            # Check usage limits if authenticated
            if request.user:
                endpoint = '/api/batch-analysis-stream'
                allowed, error_msg = usage_service.check_limit(request.user['id'], endpoint)
                if not allowed:
                    yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"
                    return
            
            # Get model and provider from request (API key no longer needed - uses AI Gateway)
            _, model, provider = get_api_key_and_model(data)
            
            assessor = get_assessor(api_key=None, model=model, provider=provider)
            provider_instance = assessor.provider
            assessment_service = AssessmentService(assessor)
            
            # Create services - embedding service uses AI Gateway
            embedding_service = EmbeddingService()
            cost_calculator = CostCalculator()
            checkpoint_service = CheckpointService()
            
            batch_service = BatchAnalysisService(
                provider_instance,
                model,
                None,
                embedding_service,
                cost_calculator,
                checkpoint_service,
                assessment_service=assessment_service,
                provider_name=getattr(assessor, 'provider_name', provider),
            )
            
            # Track usage for authenticated users
            total_tokens = 0
            total_cost = 0.0
            
            # Stream results
            for chunk in batch_service.stream_batch_analysis(
                pairs,
                foci_list,
                num_samples,
                session_id,
                resume
            ):
                # Parse chunk to track usage
                if chunk.startswith('data: '):
                    try:
                        chunk_data = json.loads(chunk[6:].strip())
                        if chunk_data.get('type') == 'complete' and 'cost_breakdown' in chunk_data:
                            cost_breakdown = chunk_data['cost_breakdown']
                            total_tokens = cost_breakdown.get('total_tokens', 0)
                            total_cost = cost_breakdown.get('total_cost', 0.0)
                    except:
                        pass
                
                yield chunk
            
            # Record usage and charge after streaming completes
            if request.user:
                # Estimate token split from total
                input_tokens_est = int(total_tokens * 0.7)
                output_tokens_est = total_tokens - input_tokens_est
                
                usage_service.record_usage(
                    user_id=request.user['id'],
                    endpoint='/api/batch-analysis-stream',
                    tokens_used=total_tokens,
                    cost=total_cost,
                    model=model,
                    provider=provider,
                    input_tokens=input_tokens_est,
                    output_tokens=output_tokens_est,
                    embedding_tokens=0,
                    charge_user=True
                )
                
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no'
    })


@batch_bp.route('/api/test-api-key', methods=['POST'])
def test_api_key():
    """Test if an API key is valid for the specified provider."""
    try:
        data = request.json
        api_key = data.get('api_key', '')
        provider = data.get('provider', 'openai')
        
        if not api_key:
            return jsonify({'valid': False, 'error': 'No API key provided'}), 400
        
        # Try to create a provider and make a simple request
        try:
            from core.llm_providers import get_provider
            test_provider = get_provider(provider, api_key)
            # Make a minimal test call (list models or simple completion)
            test_provider.list_models()
            return jsonify({'valid': True})
        except Exception as e:
            return jsonify({'valid': False, 'error': str(e)}), 400
            
    except Exception as e:
        return jsonify({'valid': False, 'error': str(e)}), 500

