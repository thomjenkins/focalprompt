#!/usr/bin/env python3
"""
Assessor factory — BYO inference with Vercel AI Gateway as the preferred default.

When AI_GATEWAY_API_KEY is set (and backend is not forced elsewhere), chat goes
through AIGatewayProvider. Direct provider SDKs and OpenAI-compatible local
endpoints are also supported via utils.inference_config.resolve_inference.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from core.focal_assessor import FocalAssessor
from core.ai_gateway_provider import AIGatewayProvider
from core.llm_providers import get_provider, defaultModels
from utils.inference_config import resolve_inference
from utils.model_provider import resolve_model_and_provider


class AssessorFactory:
    """Factory for creating FocalAssessor instances from BYO credentials."""

    def __init__(self):
        self._assessor = None
        self._cache_key = None

    def get_assessor(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        backend: Optional[str] = None,
        base_url: Optional[str] = None,
        data: Optional[Mapping[str, Any]] = None,
    ) -> FocalAssessor:
        payload = dict(data or {})
        if api_key is not None:
            payload['api_key'] = api_key
        if backend is not None:
            payload['backend'] = backend
        if base_url is not None:
            payload['base_url'] = base_url
        if model is not None:
            payload['model'] = model
        if provider is not None:
            payload['provider'] = provider

        model_in = payload.get('model') or model or 'gpt-4o-mini'
        provider_in = payload.get('provider') or provider or 'openai'
        model_in, provider_in = resolve_model_and_provider(model_in, provider_in)
        payload['model'] = model_in
        payload['provider'] = provider_in

        cfg = resolve_inference(payload, provider=provider_in, model=model_in)
        model_name = cfg['model'] or defaultModels.get(cfg['provider'], 'gpt-4o-mini')
        cache_key = (
            cfg['backend'],
            cfg['provider'],
            model_name,
            cfg.get('base_url'),
            (cfg.get('api_key') or '')[:8],
        )
        if self._assessor is None or self._cache_key != cache_key:
            if cfg['backend'] == 'vercel_gateway':
                provider_instance = AIGatewayProvider(
                    cfg['api_key'],
                    base_url=cfg.get('base_url'),
                )
                provider_name = cfg['provider']
            elif cfg['backend'] == 'openai_compatible':
                provider_instance = get_provider(
                    'openai_compatible',
                    cfg['api_key'],
                    base_url=cfg['base_url'],
                )
                provider_name = cfg['provider']
            else:
                provider_instance = get_provider(cfg['provider'], cfg['api_key'])
                provider_name = cfg['provider']

            self._assessor = FocalAssessor(
                provider_instance=provider_instance,
                model=model_name,
                provider=provider_name,
            )
            self._cache_key = cache_key
        return self._assessor

    def clear_cache(self):
        self._assessor = None
        self._cache_key = None


_assessor_factory = AssessorFactory()


def get_assessor(
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    provider: Optional[str] = None,
    backend: Optional[str] = None,
    base_url: Optional[str] = None,
    data: Optional[Mapping[str, Any]] = None,
) -> FocalAssessor:
    return _assessor_factory.get_assessor(
        api_key=api_key,
        model=model,
        provider=provider,
        backend=backend,
        base_url=base_url,
        data=data,
    )


def clear_assessor_cache():
    _assessor_factory.clear_cache()
