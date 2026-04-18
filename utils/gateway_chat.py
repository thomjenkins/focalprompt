"""
AI Gateway chat_completion wrapper.

AIGatewayProvider.chat_completion defaults provider=openai; callers must pass the
correct slug (e.g. xai) or the gateway builds the wrong model id and requests fail.
"""

import inspect
from typing import Any, Dict, List


def chat_completion(
    provider,
    model: str,
    provider_name: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.7,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Call provider.chat_completion, adding provider= when the backend supports it."""
    call_kw: Dict[str, Any] = {
        'model': model,
        'messages': messages,
        'temperature': temperature,
        **kwargs,
    }
    if hasattr(provider, 'chat_completion'):
        sig = inspect.signature(provider.chat_completion)
        if 'provider' in sig.parameters:
            call_kw['provider'] = provider_name
    return provider.chat_completion(**call_kw)
