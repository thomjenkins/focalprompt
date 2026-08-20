# Local setup

## Install

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Credentials (BYO)

Create a `.env` in the project root (gitignored):

```bash
# Preferred — multi-model via Vercel AI Gateway
AI_GATEWAY_API_KEY=…

# Or direct provider
# OPENAI_API_KEY=…
# FOCALPROMPT_BACKEND=direct

# Or OpenAI-compatible local server
# FOCALPROMPT_BACKEND=openai_compatible
# FOCALPROMPT_BASE_URL=http://127.0.0.1:11434/v1
# OPENAI_API_KEY=ollama

# Optional Flask session signing (checkpoints UI only)
SECRET_KEY=dev-secret-change-me
```

See also [AI_GATEWAY_SETUP.md](AI_GATEWAY_SETUP.md).

## Run

```bash
python app_new.py
# http://127.0.0.1:5001
# or: focalprompt ui --port 5001
```

Local default: `/` is the analysis lab. `/experiments` serves precomputed demos. `/about` is the research landing page.

## Hosted demo flags (optional)

Only for a public site that should not open-endedly burn a maintainer key:

```bash
FOCALPROMPT_HOSTED_MODE=1
FOCALPROMPT_ALLOW_LIVE_INFERENCE=0
```

## Tests

```bash
pytest
```
