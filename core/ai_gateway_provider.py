#!/usr/bin/env python3
"""
Vercel AI Gateway Provider

Wraps LLM providers to route through Vercel AI Gateway for unified access,
cost tracking, and rate limiting.

Vercel AI Gateway provides OpenAI-compatible and Anthropic-compatible APIs.
See: https://vercel.com/docs/ai-gateway
"""

import os
import json
from typing import List, Dict, Any, Optional
from core.llm_providers import LLMProvider

# Lazy import - only import requests when actually needed
_requests_available = None

def _check_requests():
    """Check if requests is available, raise error if not."""
    global _requests_available
    if _requests_available is None:
        try:
            import requests
            _requests_available = requests
        except ImportError:
            raise ImportError("requests package not installed. Install with: pip install requests")
    return _requests_available


class AIGatewayProvider(LLMProvider):
    """
    Vercel AI Gateway provider that routes requests through Vercel's gateway.
    
    Makes direct HTTP requests to the AI Gateway API (OpenAI-compatible format).
    Models are specified as 'provider/model' format.
    
    This allows for:
    - Unified API access
    - Cost tracking and analytics
    - Rate limiting
    - Automatic failover
    - No markup on tokens (0% markup)
    """
    
    def __init__(self, gateway_api_key: str, base_url: str = None):
        """
        Initialize AI Gateway provider.
        
        Args:
            gateway_api_key: Vercel AI Gateway API key
            base_url: Optional custom gateway URL (defaults to Vercel's gateway)
        """
        self.gateway_api_key = gateway_api_key
        
        # Vercel AI Gateway endpoint (OpenAI-compatible)
        # Official URL: https://ai-gateway.vercel.sh/v1
        # Can be overridden with AI_GATEWAY_URL environment variable
        self.base_url = base_url or os.getenv("AI_GATEWAY_URL", "https://ai-gateway.vercel.sh/v1")
        
        # Ensure base_url doesn't end with a slash
        self.base_url = self.base_url.rstrip('/')
    
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        response_format: Optional[Dict] = None,
        provider: str = 'openai'
    ) -> Dict[str, Any]:
        """
        Generate a chat completion via Vercel AI Gateway.
        
        Vercel AI Gateway uses OpenAI-compatible API with model format: 'provider/model'
        For example: 'openai/gpt-4o', 'anthropic/claude-3-5-sonnet-20241022'
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model name to use (e.g., 'gpt-4o', 'claude-3-5-sonnet-20241022')
            temperature: Sampling temperature
            response_format: Optional response format specification
            provider: Provider name ('openai', 'anthropic', 'google', 'grok')
            
        Returns:
            Dict with 'content' (str) and 'usage' (dict with token counts)
        """
        # Vercel AI Gateway uses 'provider/model' format for model names
        # Format: 'openai/gpt-4o', 'anthropic/claude-3-5-sonnet-20241022', etc.
        gateway_model = f"{provider}/{model}"
        
        # Build request payload (OpenAI-compatible format)
        payload = {
            'model': gateway_model,
            'messages': messages,
            'temperature': temperature
        }
        
        # Only include response_format for models that support it
        # gpt-4o-mini doesn't support response_format via AI Gateway
        # Only include for full gpt-4o, gpt-4-turbo, etc.
        if response_format:
            model_lower = model.lower()
            # Check if this is a model that supports response_format
            # Exclude mini models and only include full models
            if 'mini' not in model_lower and any(supported in model_lower for supported in ['gpt-4o', 'gpt-4-turbo', 'gpt-4', 'gpt-3.5-turbo']):
                payload['response_format'] = response_format
            # For mini models or others, skip response_format - prompt will request JSON
        
        # Make direct HTTP request to gateway
        requests = _check_requests()  # Lazy import
        url = f"{self.base_url}/chat/completions"
        headers = {
            'Authorization': f'Bearer {self.gateway_api_key}',
            'Content-Type': 'application/json'
        }
        
        # Add Vercel project context if available (helps gateway route to correct project)
        vercel_project_id = os.getenv('VERCEL_PROJECT_ID')
        if vercel_project_id:
            headers['X-Vercel-Project-ID'] = vercel_project_id
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=60)
            
            # Check for HTTP errors
            response.raise_for_status()
            
            # Parse response
            data = response.json()
            
            return {
                'content': data['choices'][0]['message']['content'],
                'usage': {
                    'prompt_tokens': data['usage']['prompt_tokens'],
                    'completion_tokens': data['usage']['completion_tokens'],
                    'total_tokens': data['usage']['total_tokens']
                }
            }
                
        except requests.exceptions.HTTPError as e:
            # HTTP error from requests library
            error_code = e.response.status_code
            error_msg = str(e)
            error_details = {}
            exception_type = type(e).__name__
            
            # Try to extract JSON error details from response
            try:
                error_data = e.response.json()
                if isinstance(error_data, dict):
                    error_details = error_data
                    if 'error' in error_data:
                        if isinstance(error_data['error'], dict):
                            error_msg = error_data['error'].get('message', str(error_data['error']))
                        else:
                            error_msg = str(error_data['error'])
            except:
                # If JSON parsing fails, use response text
                try:
                    error_msg = e.response.text
                except:
                    pass
            
            # Log detailed error for debugging (server-side only)
            import sys
            print(f"AI Gateway Error (code {error_code}): {error_msg}", file=sys.stderr)
            print(f"Exception type: {exception_type}", file=sys.stderr)
            if error_details:
                print(f"Error details: {error_details}", file=sys.stderr)
            print(f"Gateway URL: {self.base_url}", file=sys.stderr)
            print(f"Model: {gateway_model} (provider={provider}, model={model})", file=sys.stderr)
            print(f"API Key (first 20 chars): {self.gateway_api_key[:20] if self.gateway_api_key else 'None'}...", file=sys.stderr)
            
            # Provide user-friendly error messages (no technical details)
            if error_code == 404:
                # Check if it's a model not found error
                if 'model' in error_msg.lower() or 'not found' in error_msg.lower():
                    user_error_msg = f"Model '{model}' is not available for provider '{provider}'. Please try a different model or provider."
                else:
                    user_error_msg = "Service temporarily unavailable. Please try again in a moment. If the problem persists, please contact support."
            elif error_code == 401:
                user_error_msg = "Service temporarily unavailable. Please try again in a moment. If the problem persists, please contact support."
            elif error_code == 403:
                user_error_msg = "Service temporarily unavailable. Please try again in a moment. If the problem persists, please contact support."
            elif error_code == 429:
                user_error_msg = "Rate limit exceeded. Please wait a moment and try again."
            elif error_code == 500 or error_code == 502 or error_code == 503:
                user_error_msg = "Service temporarily unavailable. Please try again in a moment. If the problem persists, please contact support."
            else:
                user_error_msg = "Service temporarily unavailable. Please try again in a moment. If the problem persists, please contact support."
            
            raise Exception(user_error_msg)
                    
        except requests.exceptions.RequestException as e:
            # Network or connection error
            import sys
            print(f"AI Gateway Network Error: {str(e)}", file=sys.stderr)
            print(f"Gateway URL: {self.base_url}", file=sys.stderr)
            print(f"Model: {gateway_model} (provider={provider}, model={model})", file=sys.stderr)
            
            raise Exception("Service temporarily unavailable. Please try again in a moment. If the problem persists, please contact support.")
            
        except Exception as e:
            # Other unexpected errors
            import sys
            print(f"AI Gateway Unexpected Error: {str(e)}", file=sys.stderr)
            print(f"Exception type: {type(e).__name__}", file=sys.stderr)
            print(f"Gateway URL: {self.base_url}", file=sys.stderr)
            print(f"Model: {gateway_model} (provider={provider}, model={model})", file=sys.stderr)
            
            raise Exception("Service temporarily unavailable. Please try again in a moment. If the problem persists, please contact support.")
    
    def list_models(self, provider: str = 'openai') -> List[str]:
        """
        List available models for a provider.
        
        Note: Vercel AI Gateway supports many models. This returns common ones.
        Check https://vercel.com/docs/ai-gateway/models-and-providers for full list.
        """
        # Return models based on provider (without 'provider/' prefix in model name)
        # The gateway will add the prefix automatically
        if provider == 'openai':
            return [
                'gpt-4o-mini',
                'gpt-4o',
                'gpt-4-turbo',
                'gpt-3.5-turbo'
            ]
        elif provider == 'anthropic':
            return [
                'claude-3-5-sonnet-20241022',
                'claude-3-5-haiku-20241022',
                'claude-3-opus-20240229',
                'claude-3-sonnet-20240229',
                'claude-3-haiku-20240307'
            ]
        elif provider == 'google':
            return [
                'gemini-3-pro-preview',
                'gemini-3-pro-image',
                'gemini-3-flash',
                'gemini-2.5-pro',
                'gemini-2.5-flash',
                'gemini-2.5-flash-lite',
                'gemini-2.5-flash-preview-09-2025',
                'gemini-2.5-flash-image',
                'gemini-2.5-flash-image-preview',
                'gemini-2.5-flash-lite-preview-09-2025',
                'gemini-2.0-flash',
                'gemini-2.0-flash-lite',
                'gemini-1.5-flash'
                # Note: gemini-1.5-pro may not be available in all gateway setups
            ]
            ]
        elif provider == 'grok':
            return [
                'grok-beta',
                'grok-2'
            ]
        else:
            return []

