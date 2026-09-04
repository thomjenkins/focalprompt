#!/usr/bin/env python3
"""
Assessment route handlers.

Handles:
- Focus detection
- Dynamic focus detection
- Focus assessment
- Output generation
- Prompt rewriting
"""

from flask import Blueprint, request, jsonify
from datetime import datetime
import uuid
import json
from services.assessor_factory import get_assessor
from services.assessment_service import AssessmentService
from services.prompt_rewrite_service import PromptRewriteService
from services.checkpoint_service import CheckpointService
from utils.prompt_builder import build_prompt_with_dynamic_foci
from routes.http_errors import internal_error
from utils.request_inference import request_inference_fields


assessment_bp = Blueprint('assessment', __name__)


@assessment_bp.route('/api/detect-foci', methods=['POST'])
def detect_foci():
    """Use an agent to automatically detect foci from the prompt."""
    try:
        data = request.json
        prompt = data.get('prompt', '')
        
        if not prompt:
            return jsonify({'error': 'Prompt is required'}), 400
        
        assessor = get_assessor(data=request_inference_fields(data, model_role='analysis'))
        service = AssessmentService(assessor)
        
        try:
            result = service.detect_foci(prompt)
        except (ValueError, json.JSONDecodeError) as e:
            return internal_error('assessment_detect_foci_parse', e)
        
        return jsonify(result)
        
    except Exception as e:
        return internal_error('assessment_detect_foci', e)


@assessment_bp.route('/api/detect-dynamic-foci', methods=['POST'])
def detect_dynamic_foci():
    """Auto-detect which foci should be marked as dynamic."""
    try:
        data = request.json
        prompt = data.get('prompt', '')
        foci = data.get('foci', [])
        pairs = data.get('pairs', [])
        
        if not prompt:
            return jsonify({'error': 'Prompt is required'}), 400
        if not foci or len(foci) == 0:
            return jsonify({'error': 'Foci are required'}), 400
        if not pairs or len(pairs) == 0:
            return jsonify({'error': 'At least one pair is required to detect dynamic patterns'}), 400
        
        assessor = get_assessor(data=request_inference_fields(data, model_role='analysis'))
        service = AssessmentService(assessor)
        
        result = service.detect_dynamic_foci(prompt, foci, pairs)
        return jsonify(result)
        
    except Exception as e:
        return internal_error('assessment_detect_dynamic_foci', e)


@assessment_bp.route('/api/assess', methods=['POST'])
def assess():
    """Assess focus distribution."""
    try:
        data = request.json
        prompt = data.get('prompt', '')
        output = data.get('output', '')
        user_foci = data.get('foci', [])
        max_foci = data.get('max_foci', None)
        
        if not prompt:
            return jsonify({'error': 'Prompt is required'}), 400
        if not output:
            return jsonify({'error': 'Output is required'}), 400
        
        assessor = get_assessor(data=request_inference_fields(data, model_role='analysis'))
        checkpoint_service = CheckpointService()
        service = AssessmentService(assessor, checkpoint_service=checkpoint_service)
        
        result = service.assess_focus(prompt, output, user_foci, max_foci)
        
        # Save checkpoint for single assessment (optional - don't fail if it doesn't work)
        try:
            session_id = str(uuid.uuid4())
            checkpoint_data = {
                'session_id': session_id,
                'timestamp': datetime.now().isoformat(),
                'type': 'single_assessment',
                'result_data': {
                    **result,
                    'prompt': prompt,
                    'output': output,
                    'user_foci': user_foci if user_foci else None,
                    'max_foci': max_foci
                },
                'complete': True
            }
            checkpoint_service.save_checkpoint(session_id, checkpoint_data, 'single_assessment')
        except Exception as e:
            # Don't fail the request if checkpoint saving fails
            import sys
            print(f"Warning: Could not save assessment checkpoint: {e}", file=sys.stderr)
        
        return jsonify(result)
        
    except Exception as e:
        return internal_error('assessment_assess', e)


@assessment_bp.route('/api/generate-output', methods=['POST', 'GET'])
def generate_output():
    """Generate output using an agent."""
    import sys
    # Log that this route was hit
    print(f"✅ /api/generate-output route handler called", file=sys.stderr)
    print(f"   Method: {request.method}", file=sys.stderr)
    print(f"   Path: {request.path}", file=sys.stderr)
    print(f"   Blueprint: {assessment_bp.name}", file=sys.stderr)
    
    # Handle GET for testing
    if request.method == 'GET':
        return jsonify({
            'status': 'ok',
            'message': 'Route is registered and accessible',
            'method': request.method,
            'path': request.path,
            'blueprint': assessment_bp.name
        })
    
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'Request body is required'}), 400
            
        prompt = data.get('prompt', '')
        temperature = data.get('temperature', 0.7)
        
        if not prompt:
            return jsonify({'error': 'Prompt is required'}), 400
        
        fields = request_inference_fields(data, model_role='mut')
        model = fields.get('model', 'gpt-4o-mini')
        provider = fields.get('provider', 'openai')
        
        print(f"   Using model: {model}, provider: {provider}", file=sys.stderr)
        
        assessor = get_assessor(data=fields)
        output = assessor.generate_output(prompt, temperature=temperature)
        
        print(f"   ✅ Output generated successfully", file=sys.stderr)
        return jsonify({'output': output})
        
    except Exception as e:
        return internal_error('assessment_generate_output', e)


@assessment_bp.route('/api/rewrite-prompt', methods=['POST'])
def rewrite_prompt():
    """Rewrite prompt with emphasis based on focus weights."""
    try:
        data = request.json
        prompt = data.get('prompt', '')
        foci_weights = data.get('foci', [])
        
        if not prompt:
            return jsonify({'error': 'Prompt is required'}), 400
        if not foci_weights:
            return jsonify({'error': 'Foci with weights are required'}), 400
        
        assessor = get_assessor(data=request_inference_fields(data, model_role='analysis'))
        service = PromptRewriteService(assessor)
        
        rewritten = service.rewrite_prompt(prompt, foci_weights)
        
        return jsonify({'rewritten_prompt': rewritten})
        
    except Exception as e:
        return internal_error('assessment_rewrite_prompt', e)


@assessment_bp.route('/api/build-agent-prompt-from-inputs', methods=['POST'])
def build_agent_prompt_from_inputs():
    """Build a prompt from relevant foci and an inputs dict (legacy helper).

    Prefer ``/api/build-agent-prompt`` on the agent blueprint for the Agent Builder UI.
    """
    try:
        data = request.json or {}
        relevant_foci = data.get('foci', [])
        foci_list = data.get('all_foci') or relevant_foci
        inputs = dict(data.get('inputs') or {})
        # Accept top-level chat_content as well (same shape as agent builder).
        if not inputs.get('chat_content') and data.get('chat_content'):
            inputs['chat_content'] = data.get('chat_content')
        chat_weight = data.get('chat_weight', 0.5)
        
        if not relevant_foci:
            return jsonify({'error': 'Relevant foci are required'}), 400
        
        constructed_prompt = build_prompt_with_dynamic_foci(
            relevant_foci, foci_list, inputs, chat_weight
        )
        
        return jsonify({
            'constructed_prompt': constructed_prompt
        })
        
    except Exception as e:
        return internal_error('assessment_build_agent_prompt', e)
