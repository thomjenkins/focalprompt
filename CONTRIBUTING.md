# Contributing to Focal Prompt

Thanks for helping improve this research toolkit.

## Principles

1. **Preserve analytical methodology.** Subtractive span ablation, centroid cosine distance \(T_{\mathrm{obs}}\), exact/MC permutation tests, and Benjamini–Hochberg FDR are protected behaviour. Refactor around them; do not “simplify” them without tests and discussion.
2. **BYO inference.** Do not reintroduce maintainer-funded or account-credit inference into the default open-source path.
3. **Epistemic clarity.** Assess Focus is behavioural self-report, not transformer attention. Keep that distinction in UI and docs.
4. **No SaaS regressions.** Avoid re-adding Stripe, credits, login, or product API-key minting unless explicitly scoped as a separate hosted product.

## Development

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e ".[dev]"
pytest
```

Set `AI_GATEWAY_API_KEY` (preferred) or a direct provider key for live smoke tests.

## Pull requests

- Prefer small PRs with a clear “why”.
- Add or update unit tests for statistical and span-alignment changes before moving code.
- Run `pytest` and note any checklist workflows you manually verified (see README regression list).

## Code of conduct

Be respectful. Assume scientific good faith. Do not submit malware or credential-harvesting changes.
