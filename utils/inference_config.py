#!/usr/bin/env python3
"""
BYO inference configuration.

Resolution order for chat backends:
1. Explicit request fields (backend, api_key, base_url)
2. FOCALPROMPT_BACKEND env
3. AI_GATEWAY_API_KEY → vercel_gateway (default when present)
4. Provider-specific env keys (OPENAI_API_KEY, ANTHROPIC_API_KEY, …)
5. FOCALPROMPT_BASE_URL / OPENAI_BASE_URL → openai_compatible

Credentials are never persisted remotely by this module.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Mapping, Optional, Tuple


PROVIDER_ENV_KEYS = {
    'openai': 'OPENAI_API_KEY',
    'anthropic': 'ANTHROPIC_API_KEY',
    'google': 'GOOGLE_API_KEY',
    'grok': 'XAI_API_KEY',
    'xai': 'XAI_API_KEY',
}

GATEWAY_BACKENDS = frozenset({'gateway', 'vercel_gateway', 'ai_gateway', 'vercel'})


def _strip(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def resolve_inference(
    data: Optional[Mapping[str, Any]] = None,
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Return a resolved inference config dict:

    {
      backend: 'vercel_gateway' | 'direct' | 'openai_compatible',
      provider: str,
      model: str | None,
      api_key: str | None,
      base_url: str | None,
    }
    """
    data = data or {}
    provider = _strip(provider) or _strip(data.get('provider')) or 'openai'
    provider = provider.lower()
    # Keep xai for Vercel AI Gateway (slug is xai/*, not grok/*).
    # Direct GrokProvider still uses 'grok' — remapped only on that path below.
    model = _strip(model) or _strip(data.get('model'))

    explicit_backend = _strip(data.get('backend')) or _strip(os.getenv('FOCALPROMPT_BACKEND'))
    if explicit_backend:
        explicit_backend = explicit_backend.lower()

    api_key = _strip(data.get('api_key'))
    base_url = _strip(data.get('base_url')) or _strip(
        os.getenv('FOCALPROMPT_BASE_URL')
    ) or _strip(os.getenv('OPENAI_BASE_URL'))

    gateway_key = _strip(os.getenv('AI_GATEWAY_API_KEY'))
    gateway_url = _strip(os.getenv('AI_GATEWAY_URL'))

    # Explicit openai-compatible
    if explicit_backend in ('openai_compatible', 'compatible', 'ollama', 'lmstudio', 'vllm', 'local'):
        key = api_key or _strip(os.getenv(PROVIDER_ENV_KEYS.get(provider, 'OPENAI_API_KEY'))) or 'ollama'
        if not base_url:
            if explicit_backend == 'ollama':
                base_url = 'http://127.0.0.1:11434/v1'
            else:
                raise ValueError(
                    'openai_compatible backend requires base_url or FOCALPROMPT_BASE_URL / OPENAI_BASE_URL'
                )
        return {
            'backend': 'openai_compatible',
            'provider': provider,
            'model': model,
            'api_key': key,
            'base_url': base_url.rstrip('/'),
        }

    # Explicit direct provider
    if explicit_backend in ('direct', 'provider') or (
        explicit_backend and explicit_backend not in GATEWAY_BACKENDS
        and explicit_backend not in ('openai_compatible',)
    ):
        if explicit_backend in ('direct', 'provider'):
            pass
        elif explicit_backend in PROVIDER_ENV_KEYS or explicit_backend == 'grok':
            provider = 'grok' if explicit_backend == 'xai' else explicit_backend
        # Direct SDK path uses GrokProvider registered as 'grok'.
        if provider == 'xai':
            provider = 'grok'
        key = api_key or _strip(os.getenv(PROVIDER_ENV_KEYS.get(provider, '')))
        if not key:
            raise ValueError(
                f'No API key for provider "{provider}". Set {PROVIDER_ENV_KEYS.get(provider, "API key")} '
                'or pass api_key in the request.'
            )
        return {
            'backend': 'direct',
            'provider': provider,
            'model': model,
            'api_key': key,
            'base_url': None,
        }

    # Default: Gateway when key present
    use_gateway = (
        explicit_backend in GATEWAY_BACKENDS
        or (explicit_backend is None and gateway_key)
    )
    if use_gateway:
        key = api_key or gateway_key
        if not key:
            raise ValueError(
                'AI_GATEWAY_API_KEY is not set. Provide your Vercel AI Gateway key in the environment, '
                'or set FOCALPROMPT_BACKEND=direct|openai_compatible with the appropriate credentials.'
            )
        # Gateway model ids are provider/model with xAI's slug = "xai".
        if provider == 'grok':
            provider = 'xai'
        return {
            'backend': 'vercel_gateway',
            'provider': provider,
            'model': model,
            'api_key': key,
            'base_url': (gateway_url or 'https://ai-gateway.vercel.sh/v1').rstrip('/'),
        }

    # Fallbacks without gateway
    if base_url:
        key = api_key or _strip(os.getenv(PROVIDER_ENV_KEYS.get(provider, 'OPENAI_API_KEY'))) or 'ollama'
        return {
            'backend': 'openai_compatible',
            'provider': provider,
            'model': model,
            'api_key': key,
            'base_url': base_url.rstrip('/'),
        }

    key = api_key or _strip(os.getenv(PROVIDER_ENV_KEYS.get(provider, '')))
    if key:
        return {
            'backend': 'direct',
            'provider': provider,
            'model': model,
            'api_key': key,
            'base_url': None,
        }

    raise ValueError(
        'No inference credentials found. Set AI_GATEWAY_API_KEY (recommended), '
        'or a provider key (OPENAI_API_KEY / ANTHROPIC_API_KEY / …), '
        'or FOCALPROMPT_BASE_URL for a local OpenAI-compatible endpoint.'
    )


def resolve_embedding_config(
    data: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Embeddings: prefer Gateway; else OpenAI-compatible / OpenAI key."""
    data = data or {}
    chat = resolve_inference(data)
    if chat['backend'] == 'vercel_gateway':
        return {
            'api_key': chat['api_key'],
            'base_url': chat['base_url'],
            'model': os.getenv('FOCALPROMPT_EMBEDDING_MODEL', 'openai/text-embedding-3-small'),
        }
    # Direct / compatible: use OpenAI embeddings endpoint shape
    embed_key = (
        _strip(data.get('embedding_api_key'))
        or _strip(os.getenv('OPENAI_API_KEY'))
        or chat['api_key']
    )
    embed_base = (
        _strip(data.get('embedding_base_url'))
        or _strip(os.getenv('FOCALPROMPT_EMBEDDING_BASE_URL'))
        or (chat['base_url'] if chat['backend'] == 'openai_compatible' else 'https://api.openai.com/v1')
    )
    model = os.getenv('FOCALPROMPT_EMBEDDING_MODEL', 'text-embedding-3-small')
    if chat['backend'] == 'vercel_gateway':
        model = 'openai/text-embedding-3-small'
    return {
        'api_key': embed_key,
        'base_url': (embed_base or 'https://api.openai.com/v1').rstrip('/'),
        'model': model,
    }
