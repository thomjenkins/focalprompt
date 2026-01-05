#!/usr/bin/env python3
"""
Agent builder route handlers.

These routes will be fully implemented after agent_builder_service is complete.
For now, they import from the old app.py to maintain functionality.
"""

from flask import Blueprint, request, jsonify, Response, stream_with_context
import json
import os
from services.assessor_factory import get_assessor
from services.agent_builder_service import AgentBuilderService
from services.cost_calculator import CostCalculator
from services.checkpoint_service import CheckpointService
from utils.prompt_builder import build_prompt_with_dynamic_foci

agent_bp = Blueprint('agent', __name__)


def get_api_key_and_model(data):
    """Extract API key, model, and provider from request data, with fallbacks."""
    api_key = data.get('api_key') or os.getenv("OPENAI_API_KEY")
    model = data.get('model', 'gpt-4o-mini')
    provider = data.get('provider', 'openai')
    return api_key, model, provider


@agent_bp.route('/api/assess-chat-foci', methods=['POST'])
def assess_chat_foci():
    """Assess chat content and assign weights to foci."""
    try:
        data = request.json
        chat_content = data.get('chat_content', '')
        foci_list = data.get('foci', [])
        
        if not chat_content:
            return jsonify({'error': 'Chat content is required'}), 400
        if not foci_list or len(foci_list) == 0:
            return jsonify({'error': 'Foci are required'}), 400
        
        # Get API key, model, and provider from request
        api_key, model, provider = get_api_key_and_model(data)
        if not api_key:
            return jsonify({'error': 'API key is required'}), 500
        
        assessor = get_assessor(api_key=api_key, model=model, provider=provider)
        cost_calculator = CostCalculator()
        
        service = AgentBuilderService(
            assessor.provider,
            model,
            cost_calculator
        )
        
        result = service.assess_chat_foci(chat_content, foci_list)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@agent_bp.route('/api/generate-agent-response', methods=['POST'])
def generate_agent_response():
    """Generate response using agent prompt."""
    try:
        data = request.json
        constructed_prompt = data.get('constructed_prompt', '')
        temperature = data.get('temperature', 0.7)
        
        if not constructed_prompt:
            return jsonify({'error': 'Constructed prompt is required'}), 400
        
        # Get API key, model, and provider from request
        api_key, model, provider = get_api_key_and_model(data)
        if not api_key:
            return jsonify({'error': 'API key is required'}), 500
        
        assessor = get_assessor(api_key=api_key, model=model, provider=provider)
        service = AgentBuilderService(assessor.provider, model)
        
        output = service.generate_agent_response(constructed_prompt, temperature)
        return jsonify({'output': output})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@agent_bp.route('/api/build-batch-agents-stream', methods=['POST'])
@stream_with_context
def build_batch_agents_stream():
    """Build optimized agents for batch inputs."""
    from services.assessor_factory import get_assessor
    from services.agent_builder_service import AgentBuilderService
    from services.cost_calculator import CostCalculator
    from services.checkpoint_service import CheckpointService
    
    def generate():
        try:
            data = request.json
            pairs = data.get('pairs', [])
            foci_list = data.get('foci', [])
            session_id = data.get('session_id')
            resume = data.get('resume', False)
            
            if not pairs or len(pairs) == 0:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Pairs are required'})}\n\n"
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
            cost_calculator = CostCalculator()
            checkpoint_service = CheckpointService()
            
            service = AgentBuilderService(
                assessor.provider,
                model,
                cost_calculator,
                checkpoint_service
            )
            
            # Stream results
            for chunk in service.stream_batch_agents(pairs, foci_list, session_id, resume):
                yield chunk
                
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no'
    })


@agent_bp.route('/api/llm-evaluate-batch-agents-stream', methods=['POST'])
@stream_with_context
def llm_evaluate_batch_agents_stream():
    """Run LLM evaluation with streaming progress."""
    from flask import Response
    from services.evaluation_service import EvaluationService
    from services.cost_calculator import CostCalculator
    
    def generate():
        try:
            data = request.json
            results = data.get('results', [])
            model = data.get('model', 'gpt-4o-mini')
            
            if not results or len(results) == 0:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Results are required'})}\n\n"
                return
            
            # Get API key, model, and provider from request
            api_key, model, provider = get_api_key_and_model(data)
            if not api_key:
                yield f"data: {json.dumps({'type': 'error', 'message': 'API key is required'})}\n\n"
                return
            
            assessor = get_assessor(api_key=api_key, model=model, provider=provider)
            cost_calculator = CostCalculator()
            
            service = EvaluationService(
                assessor.provider,
                model,
                cost_calculator
            )
            
            # Stream results
            for chunk in service.stream_evaluations(results):
                yield chunk
                
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no'
    })

