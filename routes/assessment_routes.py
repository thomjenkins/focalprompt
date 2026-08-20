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
        
        assessor = get_assessor(data=request_inference_fields(data))
        service = AssessmentService(assessor)
        
        try:
            result = service.detect_foci(prompt)
        except (ValueError, json.JSONDecodeError) as e:
            # JSON parsing or validation error
            import sys
            import traceback
            print(f"Error parsing LLM response in detect_foci: {type(e).__name__}: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            return jsonify({'error': f'Failed to parse LLM response: {str(e)}'}), 500
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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
        
        assessor = get_assessor(data=request_inference_fields(data))
        service = AssessmentService(assessor)
        
        result = service.detect_dynamic_foci(prompt, foci, pairs)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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
        
        assessor = get_assessor(data=request_inference_fields(data))
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
        return jsonify({'error': str(e)}), 500


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
        
        fields = request_inference_fields(data)
        model = fields.get('model', 'gpt-4o-mini')
        provider = fields.get('provider', 'openai')
        
        print(f"   Using model: {model}, provider: {provider}", file=sys.stderr)
        
        assessor = get_assessor(data=fields)
        output = assessor.generate_output(prompt, temperature=temperature)
        
        print(f"   ✅ Output generated successfully", file=sys.stderr)
        return jsonify({'output': output})
        
    except Exception as e:
        print(f"   ❌ Error in generate_output: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return jsonify({'error': str(e)}), 500


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
        
        assessor = get_assessor(data=request_inference_fields(data))
        service = PromptRewriteService(assessor)
        
        rewritten = service.rewrite_prompt(prompt, foci_weights)
        
        return jsonify({'rewritten_prompt': rewritten})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@assessment_bp.route('/api/build-agent-prompt', methods=['POST'])
def build_agent_prompt():
    """Build a prompt from relevant foci and dynamic inputs."""
    try:
        data = request.json
        relevant_foci = data.get('foci', [])
        foci_list = data.get('all_foci', [])
        inputs = data.get('inputs', {})
        chat_weight = data.get('chat_weight', 0.5)
        
        if not relevant_foci:
            return jsonify({'error': 'Relevant foci are required'}), 400
        
        # Build prompt using utility function
        constructed_prompt = build_prompt_with_dynamic_foci(relevant_foci, foci_list, inputs, chat_weight)
        
        return jsonify({
            'constructed_prompt': constructed_prompt
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
