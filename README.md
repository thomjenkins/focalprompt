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

The Prompt Analysis lab follows five steps:

1. Label foci in Analyse messages, keeping user/chat messages as Retain.
2. Ask the baseline model for a prospective 100% focus budget and a short justification for every focus, using the full scenario before generating any outputs.
3. Sample **10 baseline outputs at temperature 0.7** by default (both configurable). Inspect baseline dispersion, pairwise distances, a similarity projection and possible bimodal/multimodal groupings.
4. Independently assess each output with the same model. Show every retrospective allocation, the equal-weight mean and sample standard deviation, and percentage-point differences from the prospective budget. Predictions are never included in generation or retrospective assessment requests.
5. Reuse those exact baseline outputs for ablation. Compare descriptive shares of observed shifts with both self-assessments, alongside the existing raw shifts, permutation tests, q-values and noise diagnostics. Continue with the existing reports, rewrites, order and quality tests.

Self-reports are not measured internal attention. Normalized ablation shifts are descriptive sensitivity shares, not a recovered attention budget; overlapping effects need not be additive. Output groups are exploratory (cosine average-link clustering, 2–5 candidate groups, minimum two samples per group, silhouette ≥ 0.5, between/within ratio ≥ 2 and distance gap ≥ 0.01). Ten samples cannot establish a true mode count; no detected split does not establish unimodality. The existing baseline-stability heuristic is also retained in the diagnostics payload.

Ablation requires the completed baseline outputs from step 3. Retrospective assessment (step 4) and baseline diagnostics may be unfinished or omitted. Completing retrospective assessment after ablation adds the focus comparison for the same saved baseline without resampling any outputs.

Changed scenario text, foci, model, baseline count or temperature starts a new experiment at step 2. Successful partial samples and retrospective assessments survive retries. Workspace exports preserve all five stages; ablation checkpoints and result exports include available assessments and the comparison when complete. Existing single-output APIs and batch workflows remain available.

Task Quality Evaluation uses the model recorded in the ablation run for self-assessment, with an optional second, different LLM. Both judges receive the same criteria, sampled outputs and original scenario (including retained chat and the output contract), in independent calls at assessment temperature 0.2. Neither sees the other judge's scores or is told which model generated an output. Scores, explanations, model identities, sampling metadata and costs remain separate in results and workspace exports; the comparison reports second-judge minus self-assessment score points. Retrying a failed judge preserves the successful judge when the task inputs and selection are unchanged. Self-assessment is a fresh evaluation by the same model, not access to its generation process; agreement between judges is not proof of correctness. Older saved single-judge results remain readable.

The browser prepares one shared stratified sample, then sends at most four outputs per HTTP request for each judge. Each returned batch is saved immediately and remains exportable while evaluation continues. Missing, invalid or ambiguously labelled scores make the run incomplete; they are never filled with zero. Retrying uses the original batches and keeps previously valid scores, including when resuming older dual-judge exports. New batches use short neutral output IDs (`task-quality-batches-v2`) to prevent label collisions; human-readable labels are restored in results. Workspace exports preserve the sampling plan, retained earlier results and each batch response or error, including protocol and cost metadata. A timeout may have incurred unreported provider usage. Rerunning a fully completed pair starts a fresh evaluation; changing task inputs also invalidates reuse.

Transport failures and temporary HTTP errors (408, 429, 500, 502, 503, 504) automatically retry the same batch at most twice, after 2 and 5 seconds. `Retry-After` can extend those waits up to 30 seconds. The interface shows the retry attempt and retains the completed scores; exported batch history records failed transport attempts. Authentication, model-selection, validation and invalid-success-response errors are not automatically retried, nor are missing or unfavourable scores. A lost response can still incur provider usage before its retry; only received usage and costs can be reported.

**CLI / Python**

```bash
focalprompt foci prompt.txt --model gpt-4o-mini
focalprompt analyze prompt.txt --completion out.txt -o result.json
focalprompt analyze --scenario examples/scenarios/veterinary.json --completion out.txt -o result.json
```

```python
from focalprompt import analyze
result = analyze("You are…", output="…", model="gpt-4o-mini")

# Ordered roles, retained inputs, and structured output are kept in every arm.
result = analyze(
    scenario="examples/scenarios/rag.json",
    inputs={"question": "When is the booster due?", "retrieved_context": "…"},
    output='{"answer":"…","citations":[]}',
)
```

## Ordered inference scenarios

A scenario is the canonical model-under-test request: versioned messages in role order, with each message marked `analyse` or `retain`. Foci use message-relative spans, named retained inputs are replaced per batch row, and an optional strict JSON Schema is forwarded and validated without downgrade. HTTP and Python calls accept exactly one of `scenario` or the legacy `prompt`; the CLI uses mutually exclusive `--scenario FILE`.

See [the scenario reference](docs/inference-scenarios.md), [the veterinary example](examples/scenarios/veterinary.json), and [the RAG example](examples/scenarios/rag.json). The HTTP schema is available at `/api/v1/openapi.json`.

## Precomputed experiment

Browse [examples/canonical](examples/canonical) or, with the server running, `/experiments`.

## Methods (summary)

Full practitioner text lives in `utils/results_copy.py` (in-app **How this works** panel).

- **Both arms sampled.** Baseline = the ordered scenario; each ablated arm clones it and deletes only one focus's verified Analyse spans.
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
3. Retained messages / named batch inputs excluded from ablation
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
