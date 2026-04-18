#!/usr/bin/env python3
"""
Normalize model id and provider for Vercel AI Gateway requests.

Clients sometimes send a mismatched provider (e.g. openai) with a model that belongs
to another provider (e.g. grok-4-fast-reasoning -> xai). The gateway expects
provider/model; we align provider with the model id when possible.
"""


def resolve_model_and_provider(model, provider):
    """
    Return (model_id_without_prefix, provider_slug) for get_assessor / AI Gateway.

    - If model is already "provider/model", split and use that provider (grok -> xai).
    - If model id implies another provider (grok-*, claude-*, gemini-*), override provider.
    """
    if model is None or (isinstance(model, str) and not str(model).strip()):
        model = "gpt-4o-mini"
    provider_in = provider
    provider = (provider_in or "openai").strip().lower() if provider_in else "openai"
    model = str(model).strip()

    # Combined gateway id: anthropic/claude-3-5-sonnet, xai/grok-4, etc.
    if "/" in model and not model.lower().startswith("ft:"):
        parts = model.split("/", 1)
        if len(parts) == 2 and parts[0] and parts[1]:
            pfx = parts[0].strip().lower()
            rest = parts[1].strip()
            if pfx == "grok":
                pfx = "xai"
            return rest, pfx

    ml = model.lower()
    if ml.startswith("grok-"):
        return model, "xai"
    if ml.startswith("claude"):
        return model, "anthropic"
    if ml.startswith("gemini"):
        return model, "google"

    return model, provider
