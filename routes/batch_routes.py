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
from utils.data_processing import calculate_statistics_from_results


batch_bp = Blueprint('batch', __name__)


def get_api_key_and_model(data):
    """Extract API key, model, and provider from request data, with fallbacks."""
    api_key = data.get('api_key') or os.getenv("OPENAI_API_KEY")
    model = data.get('model', 'gpt-4o-mini')
    provider = data.get('provider', 'openai')
    return api_key, model, provider


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
            # Calculate statistics if missing
            if checkpoint_type == 'batch_analysis' and 'statistics' not in checkpoint:
                pair_results = checkpoint.get('pair_results', [])
                if pair_results:
                    checkpoint['statistics'] = calculate_statistics_from_results(pair_results)
            
            return jsonify(checkpoint)
        else:
            return jsonify({'error': 'Checkpoint not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@batch_bp.route('/api/batch-analysis-stream', methods=['POST'])
@stream_with_context
def batch_analysis_stream():
    """Run batch ablation analysis with streaming progress updates via SSE."""
    from services.assessor_factory import get_assessor
    from services.batch_analysis_service import BatchAnalysisService
    from services.embedding_service import EmbeddingService
    from services.cost_calculator import CostCalculator
    from services.checkpoint_service import CheckpointService
    
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
            
            # Get API key, model, and provider from request
            api_key, model, provider = get_api_key_and_model(data)
            if not api_key:
                yield f"data: {json.dumps({'type': 'error', 'message': 'API key is required'})}\n\n"
                return
            
            assessor = get_assessor(api_key=api_key, model=model, provider=provider)
            provider_instance = assessor.provider
            
            # Create services
            embedding_service = EmbeddingService(api_key)
            cost_calculator = CostCalculator()
            checkpoint_service = CheckpointService()
            
            batch_service = BatchAnalysisService(
                provider_instance,
                model,
                api_key,
                embedding_service,
                cost_calculator,
                checkpoint_service
            )
            
            # Stream results
            for chunk in batch_service.stream_batch_analysis(
                pairs,
                foci_list,
                num_samples,
                session_id,
                resume
            ):
                yield chunk
                
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

