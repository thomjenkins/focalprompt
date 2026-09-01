# FocalPrompt MCP server

FocalPrompt exposes three research tools over the [Model Context Protocol](https://modelcontextprotocol.io/) (stdio). Install optional dependencies first:

```bash
pip install focalprompt[mcp]
```

Start the server manually (stdio):

```bash
focalprompt mcp
```

Or point your MCP client at the `focalprompt` CLI with `args: ["mcp"]`.

## Credentials

Uses the same inference resolution as the CLI and web UI:

| Variable | Purpose |
|----------|---------|
| `AI_GATEWAY_API_KEY` | Preferred — Vercel AI Gateway |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / … | Direct provider keys |
| `FOCALPROMPT_BACKEND` | `vercel_gateway`, `direct`, `openai_compatible`, `ollama` |
| `FOCALPROMPT_BASE_URL` | OpenAI-compatible local endpoint (e.g. Ollama) |

## Tools

| Tool | Lens | Description |
|------|------|-------------|
| `extract_foci` | — | Detect foci with verified spans (fast, iterative) |
| `report_focus` | A | Model self-report of focus on one completion — **not** attention weights |
| `ablation_analysis` | B | Perturbation sensitivity + BH-FDR (slow, many API calls) |

## Client configuration

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "focalprompt": {
      "command": "focalprompt",
      "args": ["mcp"],
      "env": {
        "AI_GATEWAY_API_KEY": "your-key-here"
      }
    }
  }
}
```

### Cursor

In **Cursor Settings → MCP**, add a server:

```json
{
  "command": "focalprompt",
  "args": ["mcp"],
  "env": {
    "AI_GATEWAY_API_KEY": "your-key-here"
  }
}
```

### Claude Code

In your project's MCP settings (or `~/.claude/settings.json`):

```json
{
  "mcpServers": {
    "focalprompt": {
      "command": "focalprompt",
      "args": ["mcp"],
      "env": {
        "AI_GATEWAY_API_KEY": "your-key-here"
      }
    }
  }
}
```

Use a virtualenv path for `command` if `focalprompt` is not on your global `PATH`, e.g. `/path/to/venv/bin/focalprompt`.

## Cost and interpretation

**Cost:** `ablation_analysis` runs many chat completions (baseline plus ablated samples for every focus) and embedding calls on **your** API key. It can take minutes and consume significant tokens. `extract_foci` and `report_focus` each use a small number of calls.

**Interpretation:** Lens A (`report_focus`) is the model's stated allocation over foci for one output — self-report, not transformer attention. Lens B (`ablation_analysis`) measures whether removing each focus shifts behaviour in embedding space (permutation test with FDR-adjusted *q*-values and observed effect sizes in `influence_scores`). A **non-significant** ablation does **not** mean that text is safe to delete; short structural instructions can matter greatly while barely moving embeddings. Neither lens measures correctness, quality, or safety.

Long ablation runs emit MCP **logging** notifications while work continues so clients are not left silent.
