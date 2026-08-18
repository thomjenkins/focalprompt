# FocalPrompt

FocalPrompt is a research prototype that measures **behavioural sensitivity**: whether deleting a tagged span of a prompt (a *focus*) shifts a language model's outputs in semantic embedding space. It samples the original prompt and each ablated prompt, compares the two clouds of embeddings with a permutation test, and reports which deletions produced a detectable shift after false-discovery-rate correction.

## What it does not do

FocalPrompt detects whether removing each focus shifts the model's behaviour in semantic embedding space. It does not measure correctness, quality, or safety, and it does not tell you what to delete. A non-significant result means no shift was detected at this sample size — not that the text is inert, and not a recommendation. Short structural instructions (output formats, escalation rules, guardrails) can matter a great deal while barely moving embeddings.

## Status

Research prototype. Results hold for the model, temperature, and surrounding prompt you actually ran. Schema fields such as `influence` remain for compatibility; they are the observed centroid distance \(T_{\mathrm{obs}}\), not a standalone importance score.

## Quickstart

```bash
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
export OPENAI_API_KEY="your-key"   # or AI_GATEWAY_API_KEY
python app_new.py
```

Open `http://127.0.0.1:5000`.

1. Paste a prompt and tag it into foci (auto-detect or manual). Aim for span-accurate coverage of the original text.
2. Optionally generate or paste an output and run **Assess Focus** (attention scoring; separate from sensitivity).
3. Run **Ablation Analysis**. Defaults: 10 baseline samples, 5 ablated samples per tested focus, temperature 0.7, Benjamini–Hochberg \(\alpha = 0.05\).

Batch analysis repeats the same per-pair experiment. Dynamic slots (chat, retrieved context) are reported as excluded, not tested.

## Methods (summary)

Full practitioner write-up is in the in-app **How this works** panel on every results view (same text as `utils/results_copy.py`).

- **Both arms are sampled.** Baseline = original prompt; ablated = that prompt with one verified span deleted.
- **Statistic.** Cosine distance between the two embedding centroids.
- **Null.** Permute group labels (exact enumeration when the split count is small); the p-value is how often a distance at least this large appears by chance.
- **Correction.** Benjamini–Hochberg q-values across tested foci. **Significant** means \(q < 0.05\): a detectable behavioural shift after correction, not a recommendation.
- **Limits.** Embeddings can miss structural change; leave-one-out can mask redundant text or misattribute interactions; results are local to this model and prompt.

See `IMPLEMENTATION_NOTES.md` for statistical definitions and schema.

## Environment

Set `OPENAI_API_KEY` or `AI_GATEWAY_API_KEY`. Optional: `SECRET_KEY` for sessions.
