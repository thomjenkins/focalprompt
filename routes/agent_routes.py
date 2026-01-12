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
from services.usage_service import UsageService
from services.billing_service import BillingService
from services.database import Database
from middleware.auth import optional_auth
from utils.prompt_builder import build_prompt_with_dynamic_foci

agent_bp = Blueprint('agent', __name__)

# Initialize services
db = Database()
billing_service = BillingService(db)
usage_service = UsageService(db, billing_service)


def get_api_key_and_model(data):
    """Extract model and provider from request data. API key no longer needed (uses AI Gateway)."""
    model = data.get('model', 'gpt-4o-mini')
    provider = data.get('provider', 'openai')
    # API key is ignored - we use AI Gateway now
    return None, model, provider


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
        
        # Get model and provider from request (API key no longer needed - uses AI Gateway)
        _, model, provider = get_api_key_and_model(data)
        
        assessor = get_assessor(api_key=None, model=model, provider=provider)
        cost_calculator = CostCalculator()
        
        # Get provider name from assessor
        provider_name = getattr(assessor, 'provider_name', None) or provider
        
        service = AgentBuilderService(
            assessor.provider,
            model,
            cost_calculator,
            provider_name=provider_name
        )
        
        result = service.assess_chat_foci(chat_content, foci_list)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@agent_bp.route('/api/build-agent-prompt', methods=['POST'])
def build_agent_prompt():
    """Build agent prompt from foci weights and chat content."""
    try:
        data = request.json
        foci = data.get('foci', [])  # List of foci with weights
        chat_content = data.get('chat_content', '')
        chat_weight = data.get('chat_weight', 0.5)
        
        if not foci or len(foci) == 0:
            return jsonify({'error': 'Foci are required'}), 400
        
        # Get model and provider from request
        _, model, provider = get_api_key_and_model(data)
        
        # Build inputs dict for prompt builder
        inputs = {
            'chat_content': chat_content,
            'rag_context': '',
            'tool_results': ''
        }
        
        # Get full foci list from agentFoci (we need prompt_section for each)
        # For now, use the foci passed in (they should have prompt_section)
        foci_list = foci  # These should already have prompt_section from frontend
        
        # Build prompt using the prompt builder
        from utils.prompt_builder import build_prompt_with_dynamic_foci
        constructed_prompt = build_prompt_with_dynamic_foci(
            foci,  # relevant_foci (with weights)
            foci_list,  # full foci list
            inputs,
            chat_weight
        )
        
        if not constructed_prompt or not constructed_prompt.strip():
            return jsonify({'error': 'Failed to build prompt - result was empty'}), 500
        
        return jsonify({
            'constructed_prompt': constructed_prompt,
            'foci_count': len(foci),
            'chat_weight': chat_weight
        })
        
    except Exception as e:
        import sys
        import traceback
        print(f"Error building agent prompt: {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
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
        
        # Get model and provider from request (API key no longer needed - uses AI Gateway)
        _, model, provider = get_api_key_and_model(data)
        
        assessor = get_assessor(api_key=None, model=model, provider=provider)
        provider_name = getattr(assessor, 'provider_name', None) or provider
        service = AgentBuilderService(assessor.provider, model, provider_name=provider_name)
        
        output = service.generate_agent_response(constructed_prompt, temperature)
        return jsonify({'output': output})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@agent_bp.route('/api/build-batch-agents-stream', methods=['POST'])
@stream_with_context
@optional_auth
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
            
            # Check usage limits if authenticated
            if request.user:
                endpoint = '/api/build-batch-agents-stream'
                allowed, error_msg = usage_service.check_limit(request.user['id'], endpoint)
                if not allowed:
                    yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"
                    return
            
            # Get model and provider from request (API key no longer needed - uses AI Gateway)
            _, model, provider = get_api_key_and_model(data)
            
            assessor = get_assessor(api_key=None, model=model, provider=provider)
            cost_calculator = CostCalculator()
            checkpoint_service = CheckpointService()
            provider_name = getattr(assessor, 'provider_name', None) or provider
            
            service = AgentBuilderService(
                assessor.provider,
                model,
                cost_calculator,
                checkpoint_service,
                provider_name=provider_name
            )
            
            # Track usage for authenticated users
            total_tokens = 0
            total_cost = 0.0
            
            # Stream results
            for chunk in service.stream_batch_agents(pairs, foci_list, session_id, resume):
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
            
            # Record usage after streaming completes
            if request.user:
                usage_service.record_usage(
                    request.user['id'], 
                    '/api/build-batch-agents-stream', 
                    total_tokens, 
                    total_cost
                )
                
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no'
    })


@agent_bp.route('/api/llm-evaluate-batch-agents-stream', methods=['POST'])
@stream_with_context
@optional_auth
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
            
            # Check usage limits if authenticated
            if request.user:
                endpoint = '/api/llm-evaluate-batch-agents-stream'
                allowed, error_msg = usage_service.check_limit(request.user['id'], endpoint)
                if not allowed:
                    yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"
                    return
            
            # Get model and provider from request (API key no longer needed - uses AI Gateway)
            _, model, provider = get_api_key_and_model(data)
            
            assessor = get_assessor(api_key=None, model=model, provider=provider)
            cost_calculator = CostCalculator()
            
            service = EvaluationService(
                assessor.provider,
                model,
                cost_calculator
            )
            
            # Track usage for authenticated users
            total_tokens = 0
            total_cost = 0.0
            
            # Stream results
            for chunk in service.stream_evaluations(results):
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
                    endpoint='/api/llm-evaluate-batch-agents-stream',
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

