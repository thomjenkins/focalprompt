#!/usr/bin/env python3
"""
LLM Provider Abstraction Layer

Supports multiple LLM providers with a unified interface:
- OpenAI
- Anthropic (Claude)
- Google (Gemini)
- Grok (X/Twitter)
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
import json


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        response_format: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Generate a chat completion.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model name to use
            temperature: Sampling temperature
            response_format: Optional response format specification
            
        Returns:
            Dict with 'content' (str) and 'usage' (dict with token counts)
        """
        pass
    
    @abstractmethod
    def list_models(self) -> List[str]:
        """List available models for this provider."""
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI provider implementation."""
    
    def __init__(self, api_key: str):
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=api_key)
        except ImportError:
            raise ImportError("openai package not installed. Install with: pip install openai")
    
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        response_format: Optional[Dict] = None
    ) -> Dict[str, Any]:
        kwargs = {
            'model': model,
            'messages': messages,
            'temperature': temperature
        }
        
        if response_format:
            kwargs['response_format'] = response_format
        
        response = self.client.chat.completions.create(**kwargs)
        
        return {
            'content': response.choices[0].message.content,
            'usage': {
                'prompt_tokens': response.usage.prompt_tokens,
                'completion_tokens': response.usage.completion_tokens,
                'total_tokens': response.usage.total_tokens
            }
        }
    
    def list_models(self) -> List[str]:
        return [
            'gpt-4o-mini',
            'gpt-4o',
            'gpt-4-turbo',
            'gpt-3.5-turbo'
        ]


class AnthropicProvider(LLMProvider):
    """Anthropic (Claude) provider implementation."""
    
    def __init__(self, api_key: str):
        try:
            from anthropic import Anthropic
            self.client = Anthropic(api_key=api_key)
        except ImportError:
            raise ImportError("anthropic package not installed. Install with: pip install anthropic")
    
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        response_format: Optional[Dict] = None
    ) -> Dict[str, Any]:
        # Convert messages format (Anthropic uses different format)
        # Anthropic expects system message separately and messages array
        system_message = None
        anthropic_messages = []
        
        for msg in messages:
            if msg['role'] == 'system':
                system_message = msg['content']
            else:
                # Anthropic uses 'assistant' and 'user' roles
                role = msg['role'] if msg['role'] in ['user', 'assistant'] else 'user'
                anthropic_messages.append({
                    'role': role,
                    'content': msg['content']
                })
        
        kwargs = {
            'model': model,
            'messages': anthropic_messages,
            'temperature': temperature,
            'max_tokens': 4096
        }
        
        if system_message:
            kwargs['system'] = system_message
        
        # Handle response format (JSON mode)
        if response_format and response_format.get('type') == 'json_object':
            # Anthropic supports JSON mode via system message
            if system_message:
                kwargs['system'] = system_message + "\n\nRespond in valid JSON format only."
            else:
                kwargs['system'] = "Respond in valid JSON format only."
        
        response = self.client.messages.create(**kwargs)
        
        # Extract content (Anthropic returns content as a list)
        content = ""
        if response.content:
            if isinstance(response.content[0], dict):
                content = response.content[0].get('text', '')
            else:
                content = str(response.content[0])
        
        return {
            'content': content,
            'usage': {
                'prompt_tokens': response.usage.input_tokens,
                'completion_tokens': response.usage.output_tokens,
                'total_tokens': response.usage.input_tokens + response.usage.output_tokens
            }
        }
    
    def list_models(self) -> List[str]:
        return [
            'claude-3-5-sonnet-20241022',
            'claude-3-5-haiku-20241022',
            'claude-3-opus-20240229',
            'claude-3-sonnet-20240229',
            'claude-3-haiku-20240307'
        ]


class GoogleProvider(LLMProvider):
    """Google (Gemini) provider implementation."""
    
    def __init__(self, api_key: str):
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            self.genai = genai
        except ImportError:
            raise ImportError("google-generativeai package not installed. Install with: pip install google-generativeai")
    
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        response_format: Optional[Dict] = None
    ) -> Dict[str, Any]:
        # Convert messages format for Gemini
        # Gemini uses a different message format
        chat = self.genai.GenerativeModel(model).start_chat(history=[])
        
        # Process messages
        last_user_message = None
        for msg in messages:
            if msg['role'] == 'user':
                last_user_message = msg['content']
            elif msg['role'] == 'assistant':
                # Add to history
                if last_user_message:
                    chat.history.append({
                        'role': 'user',
                        'parts': [last_user_message]
                    })
                    chat.history.append({
                        'role': 'model',
                        'parts': [msg['content']]
                    })
                    last_user_message = None
        
        # Generate response
        generation_config = {
            'temperature': temperature,
        }
        
        if response_format and response_format.get('type') == 'json_object':
            generation_config['response_mime_type'] = 'application/json'
        
        if last_user_message:
            response = chat.send_message(last_user_message, generation_config=generation_config)
        else:
            # Use the last user message from messages list
            user_messages = [m['content'] for m in messages if m['role'] == 'user']
            if user_messages:
                response = chat.send_message(user_messages[-1], generation_config=generation_config)
            else:
                raise ValueError("No user message found in messages")
        
        # Extract content
        content = response.text
        
        # Estimate token usage (Gemini doesn't provide exact counts in free tier)
        # Rough estimate: 1 token ≈ 4 characters
        prompt_chars = sum(len(m['content']) for m in messages)
        response_chars = len(content)
        
        return {
            'content': content,
            'usage': {
                'prompt_tokens': int(prompt_chars / 4),
                'completion_tokens': int(response_chars / 4),
                'total_tokens': int((prompt_chars + response_chars) / 4)
            }
        }
    
    def list_models(self) -> List[str]:
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
            'gemini-1.5-pro',
            'gemini-1.5-flash'
        ]


class GrokProvider(LLMProvider):
    """Grok (X/Twitter) provider implementation."""
    
    def __init__(self, api_key: str):
        try:
            from openai import OpenAI
            # Grok uses OpenAI-compatible API
            self.client = OpenAI(
                api_key=api_key,
                base_url="https://api.x.ai/v1"
            )
        except ImportError:
            raise ImportError("openai package not installed. Install with: pip install openai")
    
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        response_format: Optional[Dict] = None
    ) -> Dict[str, Any]:
        kwargs = {
            'model': model,
            'messages': messages,
            'temperature': temperature
        }
        
        if response_format:
            kwargs['response_format'] = response_format
        
        response = self.client.chat.completions.create(**kwargs)
        
        return {
            'content': response.choices[0].message.content,
            'usage': {
                'prompt_tokens': response.usage.prompt_tokens,
                'completion_tokens': response.usage.completion_tokens,
                'total_tokens': response.usage.total_tokens
            }
        }
    
    def list_models(self) -> List[str]:
        return [
            'grok-beta',
            'grok-2'
        ]


def get_provider(provider_name: str, api_key: str) -> LLMProvider:
    """
    Factory function to get a provider instance.
    
    Args:
        provider_name: Name of the provider ('openai', 'anthropic', 'google', 'grok')
        api_key: API key for the provider
        
    Returns:
        LLMProvider instance
    """
    providers = {
        'openai': OpenAIProvider,
        'anthropic': AnthropicProvider,
        'google': GoogleProvider,
        'grok': GrokProvider
    }
    
    provider_class = providers.get(provider_name.lower())
    if not provider_class:
        raise ValueError(f"Unknown provider: {provider_name}. Supported: {', '.join(providers.keys())}")
    
    return provider_class(api_key)


def get_provider_models(provider_name: str) -> List[str]:
    """Get list of available models for a provider (without API key)."""
    # Return default models without instantiating provider
    model_lists = {
        'openai': ['gpt-4o-mini', 'gpt-4o', 'gpt-4-turbo', 'gpt-3.5-turbo'],
        'anthropic': ['claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022', 'claude-3-opus-20240229', 'claude-3-sonnet-20240229', 'claude-3-haiku-20240307'],
        'google': ['gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-pro'],
        'grok': ['grok-beta', 'grok-2']
    }
    
    return model_lists.get(provider_name.lower(), [])


# Default models for each provider
defaultModels = {
    'openai': 'gpt-4o-mini',
    'anthropic': 'claude-3-5-sonnet-20241022',
    'google': 'gemini-1.5-pro',
    'grok': 'grok-beta'
}

