#!/usr/bin/env python3
"""
Agent builder route handlers.

These routes will be fully implemented after agent_builder_service is complete.
For now, they import from the old app.py to maintain functionality.
"""

from flask import Blueprint, request, jsonify, Response, stream_with_context
import json
from services.assessor_factory import get_assessor
from services.agent_builder_service import AgentBuilderService
from services.cost_calculator import CostCalculator
from services.checkpoint_service import CheckpointService
from routes.http_errors import internal_error
from utils.request_inference import request_inference_fields
from utils.inference_scenario import (
    ProviderCapabilityError,
    ScenarioValidationError,
    StructuredOutputError,
    validate_scenario,
)

agent_bp = Blueprint('agent', __name__)


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
        
        fields = request_inference_fields(data, model_role='analysis')
        assessor = get_assessor(data=fields)
        cost_calculator = CostCalculator()
        
        # Get provider name from assessor
        provider_name = getattr(assessor, 'provider_name', None) or fields['provider']
        
        service = AgentBuilderService(
            assessor.provider,
            fields['model'],
            cost_calculator,
            provider_name=provider_name
        )
        
        result = service.assess_chat_foci(chat_content, foci_list)
        return jsonify(result)
        
    except Exception as e:
        return internal_error('agent_assess_chat_foci', e)


@agent_bp.route('/api/build-agent-prompt', methods=['POST'])
def build_agent_prompt():
    """Build a scenario (or legacy prompt) from focus weights."""
    try:
        data = request.json
        foci = data.get('foci', [])  # List of foci with weights
        chat_content = data.get('chat_content', '')
        chat_weight = data.get('chat_weight', 0.5)
        # The full focus catalog retains exact spans for scenario construction.
        foci_list = data.get('all_foci') or foci
        
        if not foci or len(foci) == 0:
            return jsonify({'error': 'Foci are required'}), 400

        if data.get('scenario') is not None:
            scenario = validate_scenario(data['scenario'])
            constructed_scenario, metadata = AgentBuilderService.build_agent_scenario(
                scenario,
                foci_list,
                foci,
            )
            return jsonify({
                'constructed_scenario': constructed_scenario,
                'scenario_metadata': metadata,
                'foci_count': len(foci),
                'chat_weight': chat_weight,
            })
        
        # Build inputs dict for prompt builder
        inputs = {
            'chat_content': chat_content,
            'rag_context': data.get('rag_context', '') or '',
            'tool_results': data.get('tool_results', '') or '',
            'other_input': data.get('other_input', '') or '',
        }
        
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

        if (chat_content or '').strip() and chat_content not in constructed_prompt:
            return jsonify({
                'error': 'Constructed prompt is missing chat content; refusing to generate a useless reply prompt.'
            }), 500
        
        return jsonify({
            'constructed_prompt': constructed_prompt,
            'foci_count': len(foci),
            'chat_weight': chat_weight
        })
        
    except ScenarioValidationError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return internal_error('agent_build_prompt', e)


@agent_bp.route('/api/generate-agent-response', methods=['POST'])
def generate_agent_response():
    """Generate response using agent prompt."""
    try:
        data = request.json
        constructed_prompt = data.get('constructed_prompt')
        scenario = data.get('scenario')
        temperature = data.get('temperature', 0.7)
        
        if (scenario is None) == (not bool((constructed_prompt or '').strip())):
            return jsonify({'error': 'Provide exactly one of scenario or constructed_prompt'}), 400
        
        fields = request_inference_fields(data, model_role='mut')
        assessor = get_assessor(data=fields)
        provider_name = getattr(assessor, 'provider_name', None) or fields['provider']
        service = AgentBuilderService(assessor.provider, fields['model'], provider_name=provider_name)
        
        output = service.generate_agent_response(
            constructed_prompt,
            temperature,
            scenario=validate_scenario(scenario) if scenario is not None else None,
            inputs=data.get('inputs'),
        )
        return jsonify(output if isinstance(output, dict) else {'output': output})
        
    except (ProviderCapabilityError, StructuredOutputError) as e:
        return jsonify({'error': str(e), 'code': 'inference_contract_error'}), 422
    except ScenarioValidationError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return internal_error('agent_generate_response', e)


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
            scenario = validate_scenario(data['scenario']) if data.get('scenario') is not None else None
            
            if not pairs or len(pairs) == 0:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Pairs are required'})}\n\n"
                return
            
            if not foci_list or len(foci_list) == 0:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Foci are required'})}\n\n"
                return
            
            fields = request_inference_fields(data, model_role='analysis')
            assessor = get_assessor(data=fields)
            mut_fields = request_inference_fields(data, model_role='mut')
            mut_assessor = get_assessor(data=mut_fields)
            cost_calculator = CostCalculator()
            checkpoint_service = CheckpointService()
            provider_name = getattr(assessor, 'provider_name', None) or fields['provider']
            mut_provider_name = (
                getattr(mut_assessor, 'provider_name', None) or mut_fields['provider']
            )
            
            service = AgentBuilderService(
                assessor.provider,
                fields['model'],
                cost_calculator,
                checkpoint_service,
                provider_name=provider_name,
                generation_provider=mut_assessor.provider,
                generation_model=mut_fields['model'],
                generation_provider_name=mut_provider_name
            )
            
            # Stream results
            for chunk in service.stream_batch_agents(
                pairs, foci_list, session_id, resume, scenario=scenario
            ):
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
            
            if not results or len(results) == 0:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Results are required'})}\n\n"
                return
            
            fields = request_inference_fields(data, model_role='analysis')
            assessor = get_assessor(data=fields)
            cost_calculator = CostCalculator()
            
            service = EvaluationService(
                assessor.provider,
                fields['model'],
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
