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
import time
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
        
        # Make direct HTTP request to gateway with retry logic
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
        
        # Retry configuration
        # NOTE: Vercel serverless function limits:
        # - Free: 10 seconds
        # - Pro: 60 seconds  
        # - Enterprise: 300 seconds (5 minutes)
        # - Fluid Compute: up to 14 minutes on paid plans
        # 
        # IMPORTANT: We don't retry on timeouts to avoid wasting tokens.
        # If a request times out, it may have already consumed tokens.
        # Only retry on connection errors (which don't consume tokens).
        max_retries = 2  # Retry only for connection errors (not timeouts)
        base_timeout = 120  # Increased base timeout to 120 seconds for slow models
        retry_delays = [2, 5]  # Exponential backoff delays in seconds
        
        for attempt in range(max_retries):
            try:
                # Increase timeout for retries (some models are slower)
                timeout = base_timeout + (attempt * 30)  # 120s, 150s, 180s
                
                if attempt > 0:
                    import sys
                    print(f"Retry attempt {attempt + 1}/{max_retries} for {gateway_model} (timeout: {timeout}s)", file=sys.stderr)
                    time.sleep(retry_delays[attempt - 1])
                
                response = requests.post(url, json=payload, headers=headers, timeout=timeout, stream=False)
                
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
                
            except requests.exceptions.Timeout as e:
                import sys
                # CRITICAL: Don't retry on timeout - wastes tokens!
                # If a request times out, it may have already consumed tokens.
                # Retrying would charge us again for the same work.
                print(f"AI Gateway Timeout Error: Request timed out after {timeout}s", file=sys.stderr)
                print(f"Exception type: {type(e).__name__}", file=sys.stderr)
                print(f"Gateway URL: {self.base_url}", file=sys.stderr)
                print(f"Model: {gateway_model} (provider={provider}, model={model})", file=sys.stderr)
                print(f"Note: Not retrying to avoid wasting tokens. The model may be too slow for this task.", file=sys.stderr)
                raise Exception("Request timed out. The model may be too slow for this task. Consider using a faster model, using streaming, or breaking the task into smaller chunks.")
                    
            except requests.exceptions.ConnectionError as e:
                import sys
                if attempt < max_retries - 1:
                    print(f"Connection error (attempt {attempt + 1}/{max_retries}), will retry...", file=sys.stderr)
                    continue
                else:
                    print(f"AI Gateway Connection Error: {str(e)}", file=sys.stderr)
                    print(f"Gateway URL: {self.base_url}", file=sys.stderr)
                    print(f"Model: {gateway_model} (provider={provider}, model={model})", file=sys.stderr)
                    raise Exception("Connection error. Please check your internet connection and try again.")
                    
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
                    raise Exception(user_error_msg)
                elif error_code == 401:
                    user_error_msg = "Service temporarily unavailable. Please try again in a moment. If the problem persists, please contact support."
                    raise Exception(user_error_msg)
                elif error_code == 403:
                    user_error_msg = "Service temporarily unavailable. Please try again in a moment. If the problem persists, please contact support."
                    raise Exception(user_error_msg)
                elif error_code == 429:
                    # Retry on rate limits with exponential backoff
                    if attempt < max_retries - 1:
                        import sys
                        wait_time = 2 * (2 ** attempt)
                        print(f"Rate limit exceeded (attempt {attempt + 1}/{max_retries}), waiting {wait_time}s before retry...", file=sys.stderr)
                        time.sleep(wait_time)
                        continue
                    raise Exception(
                        "Rate limit exceeded. Please wait a few minutes and try again."
                    )
                elif error_code == 500 or error_code == 502 or error_code == 503:
                    # Retry on server errors
                    if attempt < max_retries - 1:
                        import sys
                        print(f"Server error {error_code} (attempt {attempt + 1}/{max_retries}), will retry...", file=sys.stderr)
                        continue
                    user_error_msg = "Service temporarily unavailable. Please try again in a moment. If the problem persists, please contact support."
                    raise Exception(user_error_msg)
                else:
                    user_error_msg = "Service temporarily unavailable. Please try again in a moment. If the problem persists, please contact support."
                    raise Exception(user_error_msg)
                    
            except requests.exceptions.RequestException as e:
                # Other network or connection errors (not timeout/connection/HTTP)
                import sys
                if attempt < max_retries - 1:
                    print(f"Network error (attempt {attempt + 1}/{max_retries}), will retry...", file=sys.stderr)
                    continue
                else:
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
        raise Exception(
            "Failed to get a model response. Check model/provider selection, rate limits, and try again."
        )

    def fetch_models_from_gateway(self) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch all available models from the AI Gateway API.
        
        Returns:
            List of model dicts with 'id', 'provider', 'name', etc., or None if fetch fails
        """
        requests = _check_requests()
        url = f"{self.base_url}/models"
        headers = {
            'Authorization': f'Bearer {self.gateway_api_key}',
            'Content-Type': 'application/json'
        }
        
        # Add Vercel project context if available
        vercel_project_id = os.getenv('VERCEL_PROJECT_ID')
        if vercel_project_id:
            headers['X-Vercel-Project-ID'] = vercel_project_id
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # AI Gateway returns OpenAI-compatible format: {'object': 'list', 'data': [...]}
            if isinstance(data, dict) and 'data' in data:
                return data['data']
            elif isinstance(data, list):
                return data
            else:
                import sys
                print(f"Unexpected models API response format: {type(data)}", file=sys.stderr)
                return None
                
        except Exception as e:
            import sys
            print(f"Error fetching models from AI Gateway: {e}", file=sys.stderr)
            return None
    
    def list_models(self, provider: str = 'openai') -> List[str]:
        """
        List available models for a provider.
        
        First tries to fetch from AI Gateway API, falls back to hardcoded list.
        
        Args:
            provider: Provider name to filter models
            
        Returns:
            List of model names (without 'provider/' prefix)
        """
        # Try to fetch from gateway first
        all_models = self.fetch_models_from_gateway()
        
        if all_models:
            # Filter by provider and extract model names
            provider_models = []
            for model in all_models:
                model_id = model.get('id', '')
                # Model ID format is 'provider/model-name'
                if '/' in model_id:
                    model_provider, model_name = model_id.split('/', 1)
                    if model_provider.lower() == provider.lower():
                        provider_models.append(model_name)
            
            if provider_models:
                return sorted(provider_models)
        
        # Fallback to hardcoded list if API fetch fails
        import sys
        print(f"Using fallback model list for provider '{provider}'", file=sys.stderr)
        
        if provider == 'openai':
            return ['gpt-4o-mini', 'gpt-4o', 'gpt-4-turbo', 'gpt-3.5-turbo']
        elif provider == 'anthropic':
            return ['claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022', 'claude-3-opus-20240229', 'claude-3-sonnet-20240229', 'claude-3-haiku-20240307']
        elif provider == 'google':
            return ['gemini-2.5-flash', 'gemini-2.5-pro', 'gemini-3-flash', 'gemini-1.5-flash']
        elif provider == 'grok' or provider == 'xai':
            return ['grok-2', 'grok-3', 'grok-4']
        else:
            return []
    
    def list_all_models(self) -> List[Dict[str, Any]]:
        """
        List all available models from the gateway with full details.
        
        Returns:
            List of model dicts with full information (id, provider, name, pricing, etc.)
        """
        models = self.fetch_models_from_gateway()
        if models:
            return models
        
        # Fallback: return empty list if fetch fails
        return []

