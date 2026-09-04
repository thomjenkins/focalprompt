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

from utils.inference_scenario import ProviderCapabilityError


def _structured_schema(response_format: Optional[Dict]) -> Optional[Dict[str, Any]]:
    """Extract a JSON Schema from the OpenAI-compatible boundary shape."""
    if not response_format or response_format.get('type') != 'json_schema':
        return None
    config = response_format.get('json_schema')
    if not isinstance(config, dict) or not isinstance(config.get('schema'), dict):
        raise ProviderCapabilityError('Invalid json_schema response_format')
    return config['schema']


def _merge_conversation_roles(
    messages: List[Dict[str, str]],
) -> tuple[List[Dict[str, str]], List[Dict[str, Any]]]:
    """Merge consecutive equivalent roles for providers that require alternation."""
    merged: List[Dict[str, str]] = []
    records: List[Dict[str, Any]] = []
    for message in messages:
        role = message['role']
        if role == 'developer':
            role = 'system'
        item = {'role': role, 'content': message['content']}
        if merged and merged[-1]['role'] == role:
            records.append({'role': role, 'source_indices': [len(merged) - 1, len(merged)]})
            merged[-1]['content'] += '\n\n' + item['content']
        else:
            merged.append(item)
    return merged, records


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        response_format: Optional[Dict] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Generate a chat completion.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model name to use
            temperature: Sampling temperature
            response_format: Optional response format specification
            max_tokens: Optional completion token limit
            
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
        response_format: Optional[Dict] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        kwargs = {
            'model': model,
            'messages': messages,
            'temperature': temperature
        }
        
        if response_format:
            kwargs['response_format'] = response_format
        if max_tokens is not None:
            kwargs['max_tokens'] = max_tokens
        
        response = self.client.chat.completions.create(**kwargs)

        choice = response.choices[0]
        refusal = getattr(choice.message, 'refusal', None)
        
        return {
            'content': choice.message.content,
            'refusal': refusal,
            'finish_reason': getattr(choice, 'finish_reason', None),
            'provider_metadata': {
                'provider_translation': 'openai_chat',
                'role_merges': [],
            },
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
        response_format: Optional[Dict] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        # Anthropic exposes instructions separately and requires alternating
        # conversational roles. Preserve instruction block order exactly.
        instruction_blocks = [
            {'type': 'text', 'text': msg['content']}
            for msg in messages if msg['role'] in ('system', 'developer')
        ]
        conversation = [msg for msg in messages if msg['role'] not in ('system', 'developer')]
        anthropic_messages, role_merges = _merge_conversation_roles(conversation)
        
        kwargs = {
            'model': model,
            'messages': anthropic_messages,
            'temperature': temperature,
            'max_tokens': max_tokens or 4096
        }
        
        if instruction_blocks:
            kwargs['system'] = instruction_blocks

        schema = _structured_schema(response_format)
        if schema is not None:
            kwargs['output_config'] = {
                'format': {'type': 'json_schema', 'schema': schema}
            }
        
        # Handle response format (JSON mode)
        if response_format and response_format.get('type') == 'json_object':
            # Anthropic supports JSON mode via system message
            if instruction_blocks:
                kwargs['system'] = instruction_blocks + [
                    {'type': 'text', 'text': 'Respond in valid JSON format only.'}
                ]
            else:
                kwargs['system'] = "Respond in valid JSON format only."

        try:
            response = self.client.messages.create(**kwargs)
        except TypeError as exc:
            if schema is not None:
                raise ProviderCapabilityError(
                    'Installed Anthropic SDK cannot express required structured output; '
                    'upgrade to anthropic>=1.0'
                ) from exc
            raise
        
        # Extract content (Anthropic returns content as a list)
        content = ""
        if response.content:
            block = next(
                (part for part in response.content if getattr(part, 'type', None) == 'text'),
                response.content[0],
            )
            if isinstance(block, dict):
                content = block.get('text', '')
            else:
                content = getattr(block, 'text', str(block))
        
        return {
            'content': content,
            'finish_reason': getattr(response, 'stop_reason', None),
            'provider_metadata': {
                'provider_translation': 'anthropic_messages',
                'instruction_roles_merged': [
                    msg['role'] for msg in messages
                    if msg['role'] in ('system', 'developer')
                ],
                'role_merges': role_merges,
                'structured_output': 'output_config.format' if schema is not None else None,
            },
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
        response_format: Optional[Dict] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        instruction_blocks = [
            msg['content'] for msg in messages
            if msg['role'] in ('system', 'developer')
        ]
        conversation, role_merges = _merge_conversation_roles([
            msg for msg in messages if msg['role'] not in ('system', 'developer')
        ])
        system_instruction = '\n\n'.join(instruction_blocks) or None
        try:
            generative_model = self.genai.GenerativeModel(
                model,
                system_instruction=system_instruction,
            )
        except TypeError as exc:
            if system_instruction:
                raise ProviderCapabilityError(
                    'Installed Gemini SDK cannot preserve system/developer instructions'
                ) from exc
            generative_model = self.genai.GenerativeModel(model)

        if not conversation or conversation[-1]['role'] != 'user':
            raise ProviderCapabilityError(
                'Gemini generation requires the ordered conversation to end with a user message'
            )
        history = [
            {
                'role': 'model' if msg['role'] == 'assistant' else 'user',
                'parts': [msg['content']],
            }
            for msg in conversation[:-1]
        ]
        last_user_message = conversation[-1]['content']
        chat = generative_model.start_chat(history=history)
        
        # Generate response
        generation_config = {
            'temperature': temperature,
        }
        if max_tokens is not None:
            generation_config['max_output_tokens'] = max_tokens
        
        schema = _structured_schema(response_format)
        if schema is not None:
            generation_config['response_mime_type'] = 'application/json'
            generation_config['response_schema'] = schema
        elif response_format and response_format.get('type') == 'json_object':
            generation_config['response_mime_type'] = 'application/json'
        
        response = chat.send_message(last_user_message, generation_config=generation_config)
        
        # Extract content
        content = response.text
        
        # Estimate token usage (Gemini doesn't provide exact counts in free tier)
        # Rough estimate: 1 token ≈ 4 characters
        prompt_chars = sum(len(m['content']) for m in messages)
        response_chars = len(content)
        
        return {
            'content': content,
            'finish_reason': str(
                getattr((getattr(response, 'candidates', None) or [None])[0], 'finish_reason', '')
                or ''
            ),
            'provider_metadata': {
                'provider_translation': 'gemini_generate_content',
                'instruction_roles_merged': [
                    msg['role'] for msg in messages
                    if msg['role'] in ('system', 'developer')
                ],
                'role_merges': role_merges,
                'structured_output': 'response_schema' if schema is not None else None,
            },
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
        response_format: Optional[Dict] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        kwargs = {
            'model': model,
            'messages': messages,
            'temperature': temperature
        }
        
        if response_format:
            kwargs['response_format'] = response_format
        if max_tokens is not None:
            kwargs['max_tokens'] = max_tokens
        
        response = self.client.chat.completions.create(**kwargs)

        choice = response.choices[0]
        
        return {
            'content': choice.message.content,
            'refusal': getattr(choice.message, 'refusal', None),
            'finish_reason': getattr(choice, 'finish_reason', None),
            'provider_metadata': {
                'provider_translation': 'openai_compatible_chat',
                'role_merges': [],
            },
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


class OpenAICompatibleProvider(LLMProvider):
    """Any OpenAI-compatible HTTP endpoint (Ollama, LM Studio, vLLM, etc.)."""

    def __init__(self, api_key: str, base_url: str):
        try:
            from openai import OpenAI
        except ImportError:
            # Fall back to raw HTTP via requests (openai package optional for gateway path)
            self.client = None
            self.api_key = api_key
            self.base_url = base_url.rstrip('/')
            return
        self.client = OpenAI(api_key=api_key or 'ollama', base_url=base_url.rstrip('/'))
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        response_format: Optional[Dict] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        if self.client is not None:
            call_kw: Dict[str, Any] = {
                'model': model,
                'messages': messages,
                'temperature': temperature,
            }
            if response_format:
                call_kw['response_format'] = response_format
            if max_tokens is not None:
                call_kw['max_tokens'] = max_tokens
            response = self.client.chat.completions.create(**call_kw)
            choice = response.choices[0]
            return {
                'content': choice.message.content,
                'refusal': getattr(choice.message, 'refusal', None),
                'finish_reason': getattr(choice, 'finish_reason', None),
                'provider_metadata': {
                    'provider_translation': 'openai_compatible_chat',
                    'role_merges': [],
                },
                'usage': {
                    'prompt_tokens': getattr(response.usage, 'prompt_tokens', 0) or 0,
                    'completion_tokens': getattr(response.usage, 'completion_tokens', 0) or 0,
                    'total_tokens': getattr(response.usage, 'total_tokens', 0) or 0,
                },
            }
        import requests
        payload: Dict[str, Any] = {
            'model': model,
            'messages': messages,
            'temperature': temperature,
        }
        if response_format:
            payload['response_format'] = response_format
        if max_tokens is not None:
            payload['max_tokens'] = max_tokens
        headers = {
            'Authorization': f'Bearer {self.api_key or "ollama"}',
            'Content-Type': 'application/json',
        }
        r = requests.post(
            f'{self.base_url}/chat/completions',
            json=payload,
            headers=headers,
            timeout=120,
        )
        r.raise_for_status()
        data = r.json()
        usage = data.get('usage') or {}
        return {
            'content': data['choices'][0]['message']['content'],
            'refusal': data['choices'][0]['message'].get('refusal'),
            'finish_reason': data['choices'][0].get('finish_reason'),
            'provider_metadata': {
                'provider_translation': 'openai_compatible_chat',
                'role_merges': [],
            },
            'usage': {
                'prompt_tokens': usage.get('prompt_tokens', 0),
                'completion_tokens': usage.get('completion_tokens', 0),
                'total_tokens': usage.get('total_tokens', 0),
            },
        }

    def list_models(self) -> List[str]:
        return []


def get_provider(provider_name: str, api_key: str, base_url: Optional[str] = None) -> LLMProvider:
    """
    Factory function to get a provider instance.
    
    Args:
        provider_name: Name of the provider ('openai', 'anthropic', 'google', 'grok',
            'openai_compatible')
        api_key: API key for the provider
        base_url: Required for openai_compatible
        
    Returns:
        LLMProvider instance
    """
    name = provider_name.lower()
    if name in ('openai_compatible', 'compatible', 'ollama', 'lmstudio', 'vllm', 'local'):
        if not base_url:
            raise ValueError('openai_compatible provider requires base_url')
        return OpenAICompatibleProvider(api_key, base_url)

    providers = {
        'openai': OpenAIProvider,
        'anthropic': AnthropicProvider,
        'google': GoogleProvider,
        'grok': GrokProvider,
        'xai': GrokProvider,
    }
    
    provider_class = providers.get(name)
    if not provider_class:
        raise ValueError(f"Unknown provider: {provider_name}. Supported: {', '.join(list(providers) + ['openai_compatible'])}")
    
    return provider_class(api_key)


def get_provider_models(provider_name: str) -> List[str]:
    """Get list of available models for a provider (without API key)."""
    # Return default models without instantiating provider
    model_lists = {
        'openai': ['gpt-4o-mini', 'gpt-4o', 'gpt-4-turbo', 'gpt-3.5-turbo'],
        'anthropic': ['claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022', 'claude-3-opus-20240229', 'claude-3-sonnet-20240229', 'claude-3-haiku-20240307'],
        'google': ['gemini-3-pro-preview', 'gemini-3-pro-image', 'gemini-3-flash', 'gemini-2.5-pro', 'gemini-2.5-flash', 'gemini-2.5-flash-lite', 'gemini-2.5-flash-preview-09-2025', 'gemini-2.5-flash-image', 'gemini-2.5-flash-image-preview', 'gemini-2.5-flash-lite-preview-09-2025', 'gemini-2.0-flash', 'gemini-2.0-flash-lite', 'gemini-1.5-flash'],
        'grok': ['grok-beta', 'grok-2']
    }
    
    return model_lists.get(provider_name.lower(), [])


# Default models for each provider
defaultModels = {
    'openai': 'gpt-4o-mini',
    'anthropic': 'claude-3-5-sonnet-20241022',
    'google': 'gemini-2.5-flash',  # More commonly available than gemini-1.5-pro
    'grok': 'grok-beta'
}
