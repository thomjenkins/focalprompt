# Focal Prompt

<p align="center">
  <img src="static/focalpromptlogo.png" alt="Focal Prompt" width="420" />
</p>

Open-source research toolkit for studying how AI systems **allocate attention** and **respond to their informational environment** — the behavioural ecology of language models.

Focal Prompt decomposes a prompt into *foci*, then compares:

| Lens | Name | What it measures |
|------|------|------------------|
| **A** | Reported focus | Model self-assessment of how a *single completion* attended to each focus (**not** transformer attention weights) |
| **B** | Perturbation sensitivity | Whether *deleting* each verified span shifts outputs in embedding space (permutation test + Benjamini–Hochberg FDR) |
| **C** | Reported vs revealed | Side-by-side comparison of A and B on the same foci |

It does **not** score correctness, quality, or safety, and a non-significant ablation is not a licence to delete text.

## Status

Research toolkit + public methodology demo. Schema fields such as `influence` remain for compatibility; they are the observed centroid distance \(T_{\mathrm{obs}}\), not a standalone importance score.

## Install

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# optional editable install for the CLI:
pip install -e .
```

## Credentials (BYO)

Inference is **never** assumed to be paid by the maintainers.

Preferred (multi-model via [Vercel AI Gateway](https://vercel.com/docs/ai-gateway)):

```bash
export AI_GATEWAY_API_KEY="…"
```

Direct providers:

```bash
export OPENAI_API_KEY="…"       # or ANTHROPIC_API_KEY / GOOGLE_API_KEY / XAI_API_KEY
export FOCALPROMPT_BACKEND=direct   # optional; Gateway is used automatically when AI_GATEWAY_API_KEY is set
```

OpenAI-compatible local servers (Ollama, LM Studio, vLLM, …):

```bash
export FOCALPROMPT_BACKEND=openai_compatible
export FOCALPROMPT_BASE_URL="http://127.0.0.1:11434/v1"
export OPENAI_API_KEY="ollama"   # if required by the server
```

## Quickstart

**Web UI**

```bash
python app_new.py
# or: focalprompt ui --port 5001
```

Open `http://127.0.0.1:5001` (local toolkit). On a hosted deploy with `FOCALPROMPT_HOSTED_MODE=1`, `/` is the research landing page and `/lab` is the analysis UI.

**CLI / Python**

```bash
focalprompt foci prompt.txt --model gpt-4o-mini
focalprompt analyze prompt.txt --completion out.txt -o result.json
```

```python
from focalprompt import analyze
result = analyze("You are…", output="…", model="gpt-4o-mini")
```

## Precomputed experiment

Browse [examples/canonical](examples/canonical) or, with the server running, `/experiments`.

## Methods (summary)

Full practitioner text lives in `utils/results_copy.py` (in-app **How this works** panel).

- **Both arms sampled.** Baseline = original prompt; ablated = prompt with one verified span deleted.
- **Statistic.** Cosine distance between embedding centroids (\(T_{\mathrm{obs}}\)).
- **Null.** Exact or Monte Carlo permutation of group labels.
- **Correction.** Benjamini–Hochberg q-values; significant means \(q < \alpha\) (default 0.05).
- **Limits.** Embeddings can miss structural change; leave-one-out is conditional on the surrounding prompt; results are local to model and decoding settings.

See [docs/methodology/IMPLEMENTATION_NOTES.md](docs/methodology/IMPLEMENTATION_NOTES.md).

## Hosted demo (`focalprompt.com`)

| Env | Effect |
|-----|--------|
| `FOCALPROMPT_HOSTED_MODE=1` | Landing at `/`; lab at `/lab` |
| `FOCALPROMPT_ALLOW_LIVE_INFERENCE=0` (default when hosted) | Analytical `/api/*` returns 503 — use `/experiments` |
| `FOCALPROMPT_ALLOW_LIVE_INFERENCE=1` | Optional capped live demo |
| `FOCALPROMPT_DEMO_RPM` / `FOCALPROMPT_DEMO_DAILY_BUDGET_USD` | Soft caps when live is on (see below) |
| `FOCALPROMPT_ALLOWED_ORIGINS` | Comma-separated browser origins for CORS when hosted (default `https://focalprompt.com`) |

**Spend and rate limits on hosted:** RPM and daily-budget counters are stored in **in-process memory**. On serverless each instance has its own counters; they reset on cold start and **do not aggregate** across instances. Treat them as best-effort per-instance caps, not a hard global ceiling. The **authoritative spend control** is the AI gateway budget limit on your gateway key.

## Regression checklist (analytical workflows)

Preserve all of these when changing code:

1. Auto-detect foci + span verify  
2. Manual add/edit/merge foci  
3. Dynamic focus detect / exclude from ablation  
4. Generate output  
5. Assess Focus (reported distribution)  
6. Rewrite / slider emphasis  
7. Ablation paced sample→score  
8. Ablation server monolith (`POST /api/ablation-analysis`)  
9. Results: significant / not / excluded / power  
10. Experiment config power/cost preview  
11. Batch CSV/manual + SSE + resume  
12. Batch focus-distribution aggregates  
13. Checkpoint list/load  
14. Model/provider switch (cross-model)  
15. Agent builder + batch agents  
16. Temperature ≤ 0 rejected  
17. Strict span deletion (no reconstruct)

```bash
pytest
```

## License

Apache-2.0 — see [LICENSE](LICENSE). Citation: [CITATION.cff](CITATION.cff).
