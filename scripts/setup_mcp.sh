#!/usr/bin/env bash
# One-time setup: install FocalPrompt MCP and print Cursor config to paste.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> FocalPrompt MCP setup"
echo "    Repo: $ROOT"
echo

if [[ ! -f pyproject.toml ]]; then
  echo "ERROR: pyproject.toml not found here."
  echo
  echo "You are probably in the wrong folder. The git repo root contains"
  echo "pyproject.toml, app_new.py, routes/, scripts/, etc."
  echo
  echo "If your prompt shows 'focalprompt $', try:"
  echo "  cd .."
  echo "  ls pyproject.toml"
  echo "  bash scripts/setup_mcp.sh"
  exit 1
fi

_venv_ok() {
  [[ -x .venv/bin/pip ]] && [[ -x .venv/bin/python3 ]]
}

if [[ -d .venv ]] && ! _venv_ok; then
  echo "==> Removing broken .venv..."
  rm -rf .venv
fi

FP=""
if _venv_ok; then
  :
elif python3 -m venv .venv 2>/dev/null && _venv_ok; then
  echo "==> Created virtualenv (.venv)"
else
  echo "==> Could not create .venv (install python3-venv or use --user fallback)"
  echo "    Ubuntu/Debian: sudo apt install python3-venv"
  echo
  echo "==> Installing with pip --user instead..."
  python3 -m pip install -q -U pip
  python3 -m pip install -q -e ".[mcp]"
  FP="$(python3 -m pip show focalprompt 2>/dev/null | awk '/^Location:/{print $2}')"
  if [[ -x "${HOME}/.local/bin/focalprompt" ]]; then
    FP="${HOME}/.local/bin/focalprompt"
  else
    echo "Install failed: focalprompt command not found after pip install"
    exit 1
  fi
fi

if [[ -z "$FP" ]]; then
  echo "==> Installing focalprompt[mcp] into .venv..."
  .venv/bin/pip install -q -U pip
  .venv/bin/pip install -q -e ".[mcp]"
  FP=".venv/bin/focalprompt"
fi

if [[ ! -x "$FP" ]] && [[ "$FP" == .venv/bin/focalprompt ]]; then
  echo "Install failed: $ROOT/$FP not found"
  exit 1
fi

echo "==> Verifying CLI ($FP)..."
"$FP" --help | head -3
echo

# Optional: load .env for key hint
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env 2>/dev/null || true
  set +a
fi

KEY_LINE=""
if [[ -n "${AI_GATEWAY_API_KEY:-}" ]]; then
  KEY_LINE="\"AI_GATEWAY_API_KEY\": \"${AI_GATEWAY_API_KEY}\","
elif [[ -n "${OPENAI_API_KEY:-}" ]]; then
  KEY_LINE="\"OPENAI_API_KEY\": \"${OPENAI_API_KEY}\","
else
  KEY_LINE="\"AI_GATEWAY_API_KEY\": \"PASTE_YOUR_KEY_HERE\","
fi

# Resolve relative FP to absolute for Cursor config
if [[ "$FP" != /* ]]; then
  FP="$ROOT/$FP"
fi

echo "============================================================"
echo "DONE. Copy the block below into Cursor MCP settings."
echo "  Cursor → Settings → MCP → Add new global MCP server"
echo "  (Mac/Linux config file: ~/.cursor/mcp.json)"
echo "============================================================"
echo
cat <<EOF
{
  "mcpServers": {
    "focalprompt": {
      "command": "$FP",
      "args": ["mcp"],
      "env": {
        $KEY_LINE
        "FOCALPROMPT_BACKEND": "vercel_gateway"
      }
    }
  }
}
EOF
echo
echo "============================================================"
echo "Then: restart Cursor, open Agent chat, paste the experiment"
echo "prompt from docs/mcp.md or ask: 'Run extract_foci on ...'"
echo "============================================================"
