#!/usr/bin/env python3
"""Shared request helpers for analytical routes (no SaaS/billing)."""

from typing import Any, Dict, Optional, Tuple

from flask import request

from utils.model_provider import resolve_model_and_provider


def request_inference_fields(data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Fields passed through to AssessorFactory / resolve_inference."""
    data = data if data is not None else (request.json or {})
    model = data.get('model', 'gpt-4o-mini')
    provider = data.get('provider', 'openai')
    model, provider = resolve_model_and_provider(model, provider)
    out = {
        'model': model,
        'provider': provider,
        'backend': data.get('backend'),
        'base_url': data.get('base_url'),
        'api_key': data.get('api_key'),
    }
    return {k: v for k, v in out.items() if v is not None}


def get_api_key_and_model(data: Optional[Dict[str, Any]] = None) -> Tuple[Optional[str], str, str]:
    """Legacy tuple (api_key, model, provider) for existing call sites."""
    fields = request_inference_fields(data)
    return fields.get('api_key'), fields['model'], fields['provider']
