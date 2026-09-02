#!/usr/bin/env bash
# One-time setup: install FocalPrompt MCP and print Cursor config to paste.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> FocalPrompt MCP setup"
echo "    Repo: $ROOT"
echo

if [[ ! -d .venv ]]; then
  echo "==> Creating virtualenv (.venv)..."
  python3 -m venv .venv || {
    echo
    echo "Could not create .venv. On Ubuntu/Debian run:"
    echo "  sudo apt install python3-venv"
    echo "Then run this script again."
    exit 1
  }
fi

echo "==> Installing focalprompt[mcp]..."
.venv/bin/pip install -q -U pip
.venv/bin/pip install -q -e ".[mcp]"

FP=".venv/bin/focalprompt"
if [[ ! -x "$FP" ]]; then
  echo "Install failed: $FP not found"
  exit 1
fi

echo "==> Verifying CLI..."
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

echo "============================================================"
echo "DONE. Copy the block below into Cursor MCP settings."
echo "  Cursor → Settings → MCP → Add new global MCP server"
echo "  (or edit ~/.cursor/mcp.json on Mac/Linux)"
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
