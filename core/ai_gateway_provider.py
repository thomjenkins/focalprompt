#!/usr/bin/env python3
"""
Vercel AI Gateway Provider

Wraps LLM providers to route through Vercel AI Gateway for unified access,
cost tracking, and rate limiting.

Vercel AI Gateway provides OpenAI-compatible and Anthropic-compatible APIs.
See: https://vercel.com/docs/ai-gateway
"""

import os
from typing import List, Dict, Any, Optional
from core.llm_providers import LLMProvider


class AIGatewayProvider(LLMProvider):
    """
    Vercel AI Gateway provider that routes requests through Vercel's gateway.
    
    Vercel AI Gateway is OpenAI-compatible, so we can use the OpenAI SDK
    with a custom base_url. Models are specified as 'provider/model' format.
    
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
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai package not installed. Install with: pip install openai")
        
        self.gateway_api_key = gateway_api_key
        
        # Vercel AI Gateway endpoint (OpenAI-compatible)
        # Default: https://gateway.vercel.ai/v1
        # Can be overridden with AI_GATEWAY_URL environment variable
        self.base_url = base_url or os.getenv("AI_GATEWAY_URL", "https://gateway.vercel.ai/v1")
        
        # Initialize OpenAI client with gateway endpoint
        # Vercel AI Gateway uses OpenAI-compatible API
        self.client = OpenAI(
            api_key=gateway_api_key,
            base_url=self.base_url
        )
    
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
        
        # Build request using OpenAI SDK (gateway is OpenAI-compatible)
        kwargs = {
            'model': gateway_model,
            'messages': messages,
            'temperature': temperature
        }
        
        if response_format:
            kwargs['response_format'] = response_format
        
        try:
            # Use OpenAI SDK with gateway endpoint
            response = self.client.chat.completions.create(**kwargs)
            
            return {
                'content': response.choices[0].message.content,
                'usage': {
                    'prompt_tokens': response.usage.prompt_tokens,
                    'completion_tokens': response.usage.completion_tokens,
                    'total_tokens': response.usage.total_tokens
                }
            }
                
        except Exception as e:
            # Extract more detailed error information from OpenAI SDK exceptions
            error_msg = str(e)
            error_code = None
            error_details = {}
            
            # OpenAI SDK uses specific exception types (openai.APIError, openai.APIConnectionError, etc.)
            # Check for status_code attribute (most common)
            if hasattr(e, 'status_code'):
                error_code = e.status_code
            # Check for response object (OpenAI SDK v1+)
            elif hasattr(e, 'response'):
                if hasattr(e.response, 'status_code'):
                    error_code = e.response.status_code
                # Try to extract JSON error details
                if hasattr(e.response, 'json'):
                    try:
                        error_data = e.response.json()
                        if isinstance(error_data, dict):
                            error_details = error_data
                            # Format error data nicely
                            if 'error' in error_data:
                                if isinstance(error_data['error'], dict):
                                    error_msg = error_data['error'].get('message', str(error_data['error']))
                                else:
                                    error_msg = str(error_data['error'])
                            else:
                                error_msg = str(error_data)
                        else:
                            error_msg = str(error_data)
                    except:
                        pass
                # Also check for text response
                elif hasattr(e.response, 'text'):
                    try:
                        error_msg = e.response.text
                    except:
                        pass
            # Check for code attribute (some OpenAI exceptions use 'code')
            elif hasattr(e, 'code'):
                error_code = e.code
            
            # Log detailed error for debugging (server-side only)
            import sys
            print(f"AI Gateway Error (code {error_code}): {error_msg}", file=sys.stderr)
            print(f"Exception type: {type(e).__name__}", file=sys.stderr)
            print(f"Exception attributes: {[attr for attr in dir(e) if not attr.startswith('_')]}", file=sys.stderr)
            if error_details:
                print(f"Error details: {error_details}", file=sys.stderr)
            print(f"Gateway URL: {self.base_url}", file=sys.stderr)
            print(f"Model: {gateway_model} (provider={provider}, model={model})", file=sys.stderr)
            print(f"API Key (first 20 chars): {self.gateway_api_key[:20] if self.gateway_api_key else 'None'}...", file=sys.stderr)
            
            # Provide user-friendly error messages (no technical details)
            if error_code == 404:
                error_msg = "Service temporarily unavailable. Please try again in a moment. If the problem persists, please contact support."
            elif error_code == 401:
                error_msg = "Service temporarily unavailable. Please try again in a moment. If the problem persists, please contact support."
            elif error_code == 403:
                error_msg = "Service temporarily unavailable. Please try again in a moment. If the problem persists, please contact support."
            elif error_code == 429:
                error_msg = "Rate limit exceeded. Please wait a moment and try again."
            elif error_code == 500 or error_code == 502 or error_code == 503:
                error_msg = "Service temporarily unavailable. Please try again in a moment. If the problem persists, please contact support."
            else:
                # Generic error message for unknown errors
                error_msg = "Service temporarily unavailable. Please try again in a moment. If the problem persists, please contact support."
            
            raise Exception(error_msg)
    
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
                'gemini-1.5-pro',
                'gemini-1.5-flash',
                'gemini-pro'
            ]
        elif provider == 'grok':
            return [
                'grok-beta',
                'grok-2'
            ]
        else:
            return []

