# Vercel AI Gateway (BYO)

Focal Prompt prefers the [Vercel AI Gateway](https://vercel.com/docs/ai-gateway) when `AI_GATEWAY_API_KEY` is set. Use **your** gateway key locally or in your own deployment — the open-source toolkit does not ship maintainer-funded inference.

## Setup

1. Create an AI Gateway in your Vercel project and copy an API key.
2. Export it (or put it in `.env`):

```bash
export AI_GATEWAY_API_KEY="…"
# optional override:
# export AI_GATEWAY_URL="https://ai-gateway.vercel.sh/v1"
```

3. Run the lab: `python app_new.py` or `focalprompt ui`.

## Alternatives

```bash
# Direct provider SDKs
export FOCALPROMPT_BACKEND=direct
export OPENAI_API_KEY="…"

# OpenAI-compatible (Ollama, LM Studio, vLLM, …)
export FOCALPROMPT_BACKEND=openai_compatible
export FOCALPROMPT_BASE_URL="http://127.0.0.1:11434/v1"
export OPENAI_API_KEY="ollama"
```

Resolution order is documented in `utils/inference_config.py`.

## Smoke test

Optional TypeScript helper under `demo/` (requires `pnpm` + a key). Not required for the Python toolkit.
