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
from utils.inference_scenario import (
    ProviderCapabilityError,
    ScenarioValidationError,
    StructuredOutputError,
    scenario_analysis_document,
    scenario_from_request,
)


assessment_bp = Blueprint('assessment', __name__)


@assessment_bp.route('/api/focus-self-assessment', methods=['POST'])
def focus_self_assessment():
    """One independent prospective or output-specific retrospective self-report."""
    from services.focus_workflow_service import FocusWorkflowService
    from core.ai_gateway_provider import RateLimitError
    try:
        data = request.json or {}
        scenario, _legacy = scenario_from_request(data)
        phase = data.get('phase')
        if phase not in ('prospective', 'retrospective') or not data.get('foci'):
            return jsonify({'error': 'A valid phase and foci are required.'}), 400
        if phase == 'prospective' and any(data.get(k) for k in ('output', 'outputs', 'baseline_outputs')):
            return jsonify({'error': 'Prospective assessment must not receive generated outputs.'}), 400
        if phase == 'retrospective' and not isinstance(data.get('output'), str):
            return jsonify({'error': 'A generated output is required.'}), 400
        assessor = get_assessor(data=request_inference_fields(data, model_role='mut'))
        result = FocusWorkflowService(assessor).assess(
            scenario, data['foci'], phase=phase, output=data.get('output'), inputs=data.get('inputs'),
        )
        return jsonify(result)
    except RateLimitError as exc:
        return jsonify({'error': str(exc), 'retry_after': getattr(exc, 'retry_after', None) or 8}), 429
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:
        return internal_error('focus_self_assessment', exc)


@assessment_bp.route('/api/focus-comparison', methods=['POST'])
def focus_comparison():
    from services.focus_workflow_service import compare_assessments
    try:
        data = request.json or {}
        return jsonify(compare_assessments(data.get('foci') or [], data.get('prospective'),
                                          data.get('retrospective') or []))
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400


@assessment_bp.route('/api/baseline-diagnostics', methods=['POST'])
def baseline_diagnostics():
    from services.embedding_service import EmbeddingService
    from utils.inference_config import resolve_embedding_config
    from utils.output_distribution import describe_output_distribution
    try:
        data = request.json or {}
        outputs = data.get('baseline_outputs')
        if (not isinstance(outputs, list) or not 1 <= len(outputs) <= 50
                or any(not isinstance(s, str) or not s.strip() for s in outputs)):
            return jsonify({'error': 'Provide 1–50 non-empty baseline outputs.'}), 400
        config = resolve_embedding_config(request_inference_fields(data, model_role='mut'))
        embeddings, tokens = EmbeddingService(**config).batch_embeddings_with_usage(outputs)
        return jsonify({**describe_output_distribution(embeddings),
                        'embedding_model': config['model'], 'embedding_tokens': tokens})
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:
        return internal_error('baseline_diagnostics', exc)


@assessment_bp.route('/api/detect-foci', methods=['POST'])
def detect_foci():
    """Use an agent to automatically detect foci from the prompt."""
    try:
        data = request.json
        scenario, _legacy = scenario_from_request(data)
        
        assessor = get_assessor(data=request_inference_fields(data, model_role='analysis'))
        service = AssessmentService(assessor)
        
        try:
            result = service.detect_foci_scenario(scenario)
        except (ValueError, json.JSONDecodeError) as e:
            return internal_error('assessment_detect_foci_parse', e)
        
        return jsonify(result)
        
    except ScenarioValidationError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return internal_error('assessment_detect_foci', e)


@assessment_bp.route('/api/detect-dynamic-foci', methods=['POST'])
def detect_dynamic_foci():
    """Auto-detect which foci should be marked as dynamic."""
    try:
        data = request.json
        scenario, is_legacy = scenario_from_request(data)
        if not is_legacy:
            return jsonify({
                'error': 'Dynamic-focus tagging is replaced by analysis_mode=retain in scenarios.'
            }), 400
        prompt = data.get('prompt', '') if is_legacy else scenario_analysis_document(scenario)
        foci = data.get('foci', [])
        pairs = data.get('pairs', [])
        
        if not foci or len(foci) == 0:
            return jsonify({'error': 'Foci are required'}), 400
        if not pairs or len(pairs) == 0:
            return jsonify({'error': 'At least one pair is required to detect dynamic patterns'}), 400
        
        assessor = get_assessor(data=request_inference_fields(data, model_role='analysis'))
        service = AssessmentService(assessor)
        
        result = service.detect_dynamic_foci(prompt, foci, pairs)
        return jsonify(result)
        
    except ScenarioValidationError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return internal_error('assessment_detect_dynamic_foci', e)


@assessment_bp.route('/api/assess', methods=['POST'])
def assess():
    """Assess focus distribution."""
    try:
        data = request.json
        scenario, is_legacy = scenario_from_request(data)
        prompt = data.get('prompt', '') if is_legacy else scenario_analysis_document(scenario)
        output = data.get('output', '')
        user_foci = data.get('foci', [])
        max_foci = data.get('max_foci', None)
        
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
                    'scenario': scenario,
                    'workspace_version': 2,
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
        
    except ScenarioValidationError as e:
        return jsonify({'error': str(e)}), 400
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
            
        temperature = data.get('temperature', 0.7)
        scenario, is_legacy = scenario_from_request(data)
        
        fields = request_inference_fields(data, model_role='mut')
        model = fields.get('model', 'gpt-4o-mini')
        provider = fields.get('provider', 'openai')
        
        print(f"   Using model: {model}, provider: {provider}", file=sys.stderr)
        
        assessor = get_assessor(data=fields)
        response = assessor.generate_output_response(
            data.get('prompt') if is_legacy else None,
            scenario=None if is_legacy else scenario,
            inputs=data.get('inputs'),
            temperature=temperature,
        )
        output = response['content']
        
        print(f"   ✅ Output generated successfully", file=sys.stderr)
        payload = {
            'output': output,
            'scenario': response.get('scenario'),
            'scenario_metadata': response.get('scenario_metadata'),
        }
        if 'parsed_output' in response:
            payload['parsed_output'] = response['parsed_output']
        return jsonify(payload)
        
    except (ProviderCapabilityError, StructuredOutputError) as e:
        return jsonify({'error': str(e), 'code': 'inference_contract_error'}), 422
    except ScenarioValidationError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return internal_error('assessment_generate_output', e)


@assessment_bp.route('/api/rewrite-prompt', methods=['POST'])
def rewrite_prompt():
    """Rewrite prompt with emphasis based on focus weights."""
    import sys
    print(f"✅ /api/rewrite-prompt route handler called", file=sys.stderr)
    print(f"   Method: {request.method}", file=sys.stderr)
    print(f"   Path: {request.path}", file=sys.stderr)
    print(f"   Blueprint: {assessment_bp.name}", file=sys.stderr)

    try:
        data = request.json
        scenario, is_legacy = scenario_from_request(data)
        foci_weights = data.get('foci', [])
        if not foci_weights:
            return jsonify({'error': 'Foci with weights are required'}), 400
        
        fields = request_inference_fields(data, model_role='analysis')
        model = fields.get('model', 'gpt-4o')
        provider = fields.get('provider', 'openai')

        print(f"   Using model: {model}, provider: {provider}", file=sys.stderr)

        assessor = get_assessor(data=fields)
        service = PromptRewriteService(assessor)
        
        if is_legacy:
            rewritten = service.rewrite_prompt(data.get('prompt', ''), foci_weights)
        else:
            rewritten = service.rewrite_scenario(scenario, foci_weights)

        print(f"   ✅ Prompt rewritten successfully", file=sys.stderr)
        if is_legacy:
            return jsonify({'rewritten_prompt': rewritten})
        return jsonify({'rewritten_scenario': rewritten})
        
    except ScenarioValidationError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        print(f"   ❌ Prompt rewrite failed: {e}", file=sys.stderr)
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
