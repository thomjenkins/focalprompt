#!/usr/bin/env python3
"""
Vercel AI Gateway Provider

Wraps LLM providers to route through Vercel AI Gateway for unified access,
cost tracking, and rate limiting.
"""

import os
import requests
from typing import List, Dict, Any, Optional
from core.llm_providers import LLMProvider


class AIGatewayProvider(LLMProvider):
    """
    Vercel AI Gateway provider that routes requests through Vercel's gateway.
    
    This allows for:
    - Unified API access
    - Cost tracking and analytics
    - Rate limiting
    - Automatic failover
    """
    
    def __init__(self, gateway_api_key: str, base_url: str = None):
        """
        Initialize AI Gateway provider.
        
        Args:
            gateway_api_key: Vercel AI Gateway API key
            base_url: Optional custom gateway URL (defaults to Vercel's gateway)
        """
        self.gateway_api_key = gateway_api_key
        # Vercel AI Gateway endpoint
        # Note: Update this URL based on your Vercel AI Gateway configuration
        # Vercel AI Gateway typically uses: https://gateway.vercel.ai/v1
        # Or check your Vercel dashboard for the correct endpoint
        self.base_url = base_url or os.getenv("AI_GATEWAY_URL", "https://gateway.ai.cloudflare.com/v1")
        
        # Map provider names to gateway provider IDs
        self.provider_map = {
            'openai': 'openai',
            'anthropic': 'anthropic',
            'google': 'google',
            'grok': 'grok'
        }
    
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
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model name to use
            temperature: Sampling temperature
            response_format: Optional response format specification
            provider: Provider name ('openai', 'anthropic', 'google', 'grok')
            
        Returns:
            Dict with 'content' (str) and 'usage' (dict with token counts)
        """
        # Map provider to gateway provider ID
        gateway_provider = self.provider_map.get(provider, 'openai')
        
        # Build request payload based on provider
        if provider == 'openai':
            payload = {
                'model': model,
                'messages': messages,
                'temperature': temperature
            }
            if response_format:
                payload['response_format'] = response_format
            
            # Use OpenAI-compatible endpoint
            url = f"{self.base_url}/openai/chat/completions"
            
        elif provider == 'anthropic':
            # Anthropic uses different message format
            payload = {
                'model': model,
                'messages': messages,
                'temperature': temperature,
                'max_tokens': 4096  # Default max tokens
            }
            url = f"{self.base_url}/anthropic/messages"
            
        elif provider == 'google':
            # Google Gemini format
            payload = {
                'model': model,
                'contents': self._convert_messages_to_gemini(messages),
                'temperature': temperature
            }
            url = f"{self.base_url}/google/generateContent"
            
        else:
            # Default to OpenAI format for other providers
            payload = {
                'model': model,
                'messages': messages,
                'temperature': temperature
            }
            url = f"{self.base_url}/{gateway_provider}/chat/completions"
        
        # Make request to AI Gateway
        headers = {
            'Authorization': f'Bearer {self.gateway_api_key}',
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=60)
            response.raise_for_status()
            data = response.json()
            
            # Parse response based on provider
            if provider == 'openai' or provider == 'grok':
                return {
                    'content': data['choices'][0]['message']['content'],
                    'usage': {
                        'prompt_tokens': data.get('usage', {}).get('prompt_tokens', 0),
                        'completion_tokens': data.get('usage', {}).get('completion_tokens', 0),
                        'total_tokens': data.get('usage', {}).get('total_tokens', 0)
                    }
                }
            elif provider == 'anthropic':
                return {
                    'content': data['content'][0]['text'],
                    'usage': {
                        'prompt_tokens': data.get('usage', {}).get('input_tokens', 0),
                        'completion_tokens': data.get('usage', {}).get('output_tokens', 0),
                        'total_tokens': data.get('usage', {}).get('input_tokens', 0) + data.get('usage', {}).get('output_tokens', 0)
                    }
                }
            elif provider == 'google':
                return {
                    'content': data['candidates'][0]['content']['parts'][0]['text'],
                    'usage': {
                        'prompt_tokens': data.get('usageMetadata', {}).get('promptTokenCount', 0),
                        'completion_tokens': data.get('usageMetadata', {}).get('candidatesTokenCount', 0),
                        'total_tokens': data.get('usageMetadata', {}).get('totalTokenCount', 0)
                    }
                }
            else:
                # Fallback parsing
                return {
                    'content': str(data),
                    'usage': {
                        'prompt_tokens': 0,
                        'completion_tokens': 0,
                        'total_tokens': 0
                    }
                }
                
        except requests.exceptions.RequestException as e:
            raise Exception(f"AI Gateway request failed: {str(e)}")
    
    def _convert_messages_to_gemini(self, messages: List[Dict[str, str]]) -> List[Dict]:
        """Convert standard message format to Google Gemini format."""
        parts = []
        for msg in messages:
            role = msg['role']
            if role == 'system':
                # Gemini doesn't have system role, prepend to first user message
                continue
            elif role == 'user':
                parts.append({'role': 'user', 'parts': [{'text': msg['content']}]})
            elif role == 'assistant':
                parts.append({'role': 'model', 'parts': [{'text': msg['content']}]})
        return parts
    
    def list_models(self, provider: str = 'openai') -> List[str]:
        """List available models for a provider."""
        # Return models based on provider
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

