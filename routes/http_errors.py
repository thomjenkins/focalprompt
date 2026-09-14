"""Safe JSON responses for route and upstream-provider failures."""

from __future__ import annotations

import sys
import traceback
import re
from typing import Any, Dict, Optional, Tuple

from flask import jsonify


_PUBLIC_PROVIDER_EXCEPTIONS = {
    'APIConnectionError',
    'APIError',
    'APIStatusError',
    'APITimeoutError',
    'AuthenticationError',
    'BadRequestError',
    'ConflictError',
    'NotFoundError',
    'PermissionDeniedError',
    'ProviderCapabilityError',
    'RateLimitError',
    'StructuredOutputError',
    'UnprocessableEntityError',
}


def _redact_provider_message(message: str) -> str:
    """Keep actionable upstream text while removing common credential shapes."""
    message = re.sub(r'(?i)\bbearer\s+[^\s,;]+', 'Bearer [redacted]', message)
    message = re.sub(r'\bsk-[A-Za-z0-9_-]{8,}\b', '[redacted API key]', message)
    message = re.sub(
        r'(?i)(api[_ -]?key\s*[:=]\s*)[^\s,;]+',
        r'\1[redacted]',
        message,
    )
    message = ' '.join(message.split())
    return message[:600]


def _provider_error_details(exc: BaseException) -> Optional[Dict[str, Any]]:
    """Extract a safe, structured error from supported provider SDK failures."""
    class_name = type(exc).__name__
    module_name = type(exc).__module__.split('.', 1)[0]
    response = getattr(exc, 'response', None)
    status = getattr(exc, 'status_code', None) or getattr(response, 'status_code', None)
    body = getattr(exc, 'body', None)
    if not isinstance(body, dict) and response is not None:
        try:
            body = response.json()
        except Exception:
            body = None

    error = body.get('error', body) if isinstance(body, dict) else {}
    if not isinstance(error, dict):
        error = {}
    provider_type = error.get('type') or getattr(exc, 'type', None)
    provider_code = error.get('code') or getattr(exc, 'code', None)
    param = error.get('param') or getattr(exc, 'param', None)
    is_provider_error = (
        class_name in _PUBLIC_PROVIDER_EXCEPTIONS
        or module_name in {'openai', 'anthropic'}
        or provider_type in {'invalid_request_error', 'authentication_error'}
    )
    if not is_provider_error:
        return None

    message = error.get('message') or getattr(exc, 'message', None) or str(exc)
    message = _redact_provider_message(str(message or 'Provider request failed'))
    if not message:
        message = 'Provider request failed'

    if class_name == 'RateLimitError' or status == 429:
        http_status = 429
    elif class_name == 'AuthenticationError' or status == 401:
        http_status = 401
    elif class_name == 'PermissionDeniedError' or status == 403:
        http_status = 403
    elif class_name in {'APIConnectionError'}:
        http_status = 503
    elif class_name in {'APITimeoutError'}:
        http_status = 504
    elif status in {400, 404, 409, 422} or class_name in {
        'ProviderCapabilityError', 'StructuredOutputError'
    }:
        http_status = 422
    else:
        http_status = 502

    metadata = {
        key: value
        for key, value in {
            'type': provider_type or class_name,
            'code': provider_code,
            'param': param,
            'status': status,
        }.items()
        if value is not None
    }
    return {'message': message, 'metadata': metadata, 'status': http_status}


def internal_error(
    code: str,
    exc: BaseException,
    *,
    extra: Optional[Dict[str, Any]] = None,
) -> Tuple[Any, int]:
    """Log server-side and expose only recognized, sanitized provider errors."""
    traceback.print_exc(file=sys.stderr)
    print(f'Route error [{code}]: {exc}', file=sys.stderr)
    provider_error = _provider_error_details(exc)
    if provider_error is not None:
        body = {
            'error': provider_error['message'],
            'code': 'provider_request_error',
            'route_code': code,
            'provider_error': provider_error['metadata'],
        }
        if extra:
            body.update(extra)
        return jsonify(body), provider_error['status']

    body: Dict[str, Any] = {'error': 'internal error', 'code': code}
    if extra:
        body.update(extra)
    return jsonify(body), 500
