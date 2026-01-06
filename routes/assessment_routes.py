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
import os
from services.assessor_factory import get_assessor
from services.assessment_service import AssessmentService
from services.prompt_rewrite_service import PromptRewriteService
from services.checkpoint_service import CheckpointService
from services.database import Database
from services.usage_service import UsageService
from services.billing_service import BillingService
from middleware.auth import require_auth, optional_auth
from utils.prompt_builder import build_prompt_with_dynamic_foci


assessment_bp = Blueprint('assessment', __name__)

# Initialize services lazily (only when needed, not at import time)
_db = None
_billing_service = None
_usage_service = None

def get_db():
    """Get database instance (lazy initialization)."""
    global _db
    if _db is None:
        _db = Database()
    return _db

def get_billing_service():
    """Get billing service instance (lazy initialization)."""
    global _billing_service
    if _billing_service is None:
        _billing_service = BillingService(get_db())
    return _billing_service

def get_usage_service():
    """Get usage service instance (lazy initialization)."""
    global _usage_service
    if _usage_service is None:
        _usage_service = UsageService(get_db(), get_billing_service())
    return _usage_service


def get_api_key_and_model(data):
    """Extract model and provider from request data. API key no longer needed (uses AI Gateway)."""
    model = data.get('model', 'gpt-4o-mini')
    provider = data.get('provider', 'openai')
    # API key is ignored - we use AI Gateway now
    return None, model, provider


@assessment_bp.route('/api/detect-foci', methods=['POST'])
@optional_auth  # Optional auth - can work with or without login
def detect_foci():
    """Use an agent to automatically detect foci from the prompt."""
    try:
        data = request.json
        prompt = data.get('prompt', '')
        
        if not prompt:
            return jsonify({'error': 'Prompt is required'}), 400
        
        # Check usage limits if authenticated
        if request.user:
            endpoint = '/api/detect-foci'
            allowed, error_msg = get_usage_service().check_limit(request.user['id'], endpoint)
            if not allowed:
                return jsonify({'error': error_msg}), 429
        
        # Get model and provider from request (API key no longer needed - uses AI Gateway)
        _, model, provider = get_api_key_and_model(data)
        
        # Estimate cost before processing (for credit check)
        estimated_cost = 0.0
        if request.user:
            from services.pricing_service import PricingService
            pricing_service = PricingService()
            estimated_tokens = len(prompt) // 4 + 500 + 1000  # Rough estimate
            estimate = pricing_service.estimate_request_cost(
                estimated_tokens, 1000, model, provider
            )
            estimated_cost = estimate.get('total_cost', 0.0)
            
            # Check credit balance
            credit_balance = get_billing_service().get_user_credit_balance(request.user['id'])
            if credit_balance < estimated_cost:
                return jsonify({
                    'error': f'Insufficient credit. You have ${credit_balance:.2f}, estimated cost is ${estimated_cost:.4f}. Please top up your account.'
                }), 402  # Payment Required
        
        assessor = get_assessor(api_key=None, model=model, provider=provider)
        service = AssessmentService(assessor)
        
        try:
            result = service.detect_foci(prompt)
        except ValueError as e:
            # JSON parsing or validation error
            import sys
            print(f"ValueError in detect_foci: {e}", file=sys.stderr)
            return jsonify({'error': f'Failed to parse LLM response: {str(e)}'}), 500
        except json.JSONDecodeError as e:
            # JSON parsing error
            import sys
            print(f"JSONDecodeError in detect_foci: {e}", file=sys.stderr)
            return jsonify({'error': 'LLM did not return valid JSON. Please try again.'}), 500
        
        # Calculate actual cost and use credit if authenticated
        if request.user:
            # Calculate actual cost from usage
            usage = result.get('usage', {})
            tokens = usage.get('total_tokens', 0)
            input_tokens = usage.get('prompt_tokens', 0)
            output_tokens = usage.get('completion_tokens', 0)
            
            # Calculate actual cost with markup
            cost_breakdown = get_billing_service().calculate_charge_amount(
                input_tokens, output_tokens, 0, model, provider
            )
            actual_cost = cost_breakdown['total_cost']
            
            # Use credit
            credit_result = get_billing_service().use_credit(request.user['id'], actual_cost)
            if not credit_result.get('success'):
                return jsonify({'error': credit_result.get('error', 'Failed to process payment')}), 402
            
            # Record usage
            get_usage_service().record_usage(request.user['id'], '/api/detect-foci', tokens, actual_cost)
            
            # Add remaining balance to result
            result['credit_remaining'] = credit_result.get('remaining_balance', 0.0)
        
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
        
        # Get model and provider from request (API key no longer needed - uses AI Gateway)
        _, model, provider = get_api_key_and_model(data)
        
        assessor = get_assessor(api_key=None, model=model, provider=provider)
        service = AssessmentService(assessor)
        
        result = service.detect_dynamic_foci(prompt, foci, pairs)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@assessment_bp.route('/api/assess', methods=['POST'])
@optional_auth
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
        
        # Check usage limits if authenticated
        if request.user:
            endpoint = '/api/assess'
            allowed, error_msg = get_usage_service().check_limit(request.user['id'], endpoint)
            if not allowed:
                return jsonify({'error': error_msg}), 429
        
        # Get model and provider from request (API key no longer needed - uses AI Gateway)
        _, model, provider = get_api_key_and_model(data)
        
        assessor = get_assessor(api_key=None, model=model, provider=provider)
        checkpoint_service = CheckpointService()
        service = AssessmentService(assessor, checkpoint_service=checkpoint_service)
        
        result = service.assess_focus(prompt, output, user_foci, max_foci)
        
        # Save checkpoint for single assessment
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
        
        # Record usage if authenticated
        if request.user:
            # Estimate tokens and cost from result
            tokens = 0
            cost = 0.0
            if 'cost_breakdown' in result:
                cost_breakdown = result['cost_breakdown']
                tokens = cost_breakdown.get('total_tokens', 0)
                cost = cost_breakdown.get('total_cost', 0.0)
            get_usage_service().record_usage(request.user['id'], '/api/assess', tokens, cost)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@assessment_bp.route('/api/generate-output', methods=['POST', 'GET'])
def generate_output():
    """Generate output using an agent."""
    import sys
    import traceback
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
        
        # Get model and provider from request (API key no longer needed - uses AI Gateway)
        # Defaults: model='gpt-4o-mini', provider='openai'
        _, model, provider = get_api_key_and_model(data)
        
        # Ensure we have defaults
        if not model:
            model = 'gpt-4o-mini'
        if not provider:
            provider = 'openai'
        
        print(f"   Using model: {model}, provider: {provider}", file=sys.stderr)
        
        assessor = get_assessor(api_key=None, model=model, provider=provider)
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
        
        # Get model and provider from request (API key no longer needed - uses AI Gateway)
        _, model, provider = get_api_key_and_model(data)
        
        assessor = get_assessor(api_key=None, model=model, provider=provider)
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


