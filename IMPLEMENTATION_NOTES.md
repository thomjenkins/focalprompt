# Implementation notes: subtractive ablation

This pass implements strategy (a) from `CONFOUND_AUDIT.md`: strict span deletion on the original prompt. Dynamic slots are excluded from attribution, not filled.

## What changed

- **`utils/span_alignment.py` (new).** Aligns `prompt_section` to `[char_start, char_end)` in the original prompt (exact, then whitespace-normalised with quote folding). `verify_foci` / `classify_foci_for_ablation` set `verified`, `attributable`, `reason`, and `overlap_with`. `delete_span` removes that half-open interval and optionally collapses a doubled blank line *at the join only*.
- **`services/assessment_service.py` `detect_foci`.** After the LLM returns foci, every quote is aligned. Unaligned foci are `verified: false` with null offsets. They are never treated as spans.
- **`AblationService.run_ablation` and `BatchAnalysisService.process_single_pair`.** Reconstruction via `build_prompt_with_dynamic_foci` is gone. Ablated prompt is `original[:start] + original[end:]` (plus the boundary collapse rule). `ablated_prompt` is stored on each attributable result. Baseline and ablations all send the original prompt or a strict deletion of it.
- **`build_prompt_with_dynamic_foci`.** Still used by agent-builder routes. The post-replace re-join that revived `{{CHAT_CONTENT}}` is fixed: substitutions are kept; chat is appended only when the template had no chat placeholder.
- **`utils/data_processing.py`.** Pair share normalisation no longer invents a chat arm when `chat_content_influence` is absent.

## What was deleted

- Reconstruction, string-replace fallback, last-focus chat/RAG concat, and reuse-original no-op in `ablation_service.py` and `batch_analysis_service.py`.
- Batch chat-ablation path (`prompt.replace(chat_content, …)` plus `chat_content_influence`).
- `app_old.py` (unused legacy reconstruction).

## Decisions not specified in the task

1. **Alignment order.** Exact substring first; then whitespace collapse + curly/straight quote folding, mapped back to original offsets; then the same after stripping trailing `.!?,;:…` from the quote. After a hit, trailing punctuation in the original is included only if it is followed by end-of-string or whitespace (so `v1` does not swallow `.2` in `v1.2`). Duplicate quotes use the **first** occurrence.
2. **Existing offsets.** If a focus already has in-range `char_start`/`char_end`, those offsets are trusted and not re-searched. Otherwise alignment runs from `prompt_section`. Invalid offsets are not accepted; alignment is retried from the quote.
3. **`reason` strings.** Unaligned: `unverified`. Dynamic: `dynamic_slot` (as specified). Overlap: `overlap`, with `overlap_with` listing the other focus names. Adjacent half-open spans do not overlap; identical spans do (both refused).
4. **Boundary collapse.** Both sides of the join must contribute at least one newline and the joined newline count must be ≥ 3; the join is then a single blank line (`\n\n`). Other blank lines are left alone. A mid-line deletion that produces a single `\n\n` is **not** collapsed.
5. **Empty remainder.** The LLM is still called with `content: ""`. `prompt_empty: true` is set. Influence is still scored (a real intervention).
6. **Scores.** `influence_scores` contains only attributable foci. Dynamic / unverified / overlapping foci appear in `ablation_results` (and `foci_list`) with flags and **no** similarity/influence. Normalisation is over attributable foci only.
7. **`inputs` on `run_ablation`.** Still accepted for API compatibility and ignored. Filling chat/RAG is out of scope.
8. **Batch-wide noise.** Still computed once from pair 0’s prompt (now unstripped). Per-pair noise floors were not added.
9. **`chat_content_influence`.** Omitted from pair results rather than returned as zeros. Aggregate stats no longer emit a `chat_content` series unless a legacy result still has that field.
10. **Retry helper.** Ablation LLM retries were pulled into `_complete` so empty-prompt calls share the same retry path. Behaviour is unchanged aside from the prompt string.

## Out of scope (subtractive pass)

- Matched-scaffold / dynamic-slot attribution (strategy (c)).
- `app.py.backup`.

---

# Permutation test (significance)

This pass **replaces** the previous significance rule (pairwise cosine similarities among baseline samples; threshold `mean − 2×std`; one ablated-vs-baseline similarity compared to that threshold). That rule mixed a one-sample distance with a within-baseline noise floor and had no valid p-value or multiple-testing control.

## Statistical definitions

**Null hypothesis (per attributable focus).** Deleting the focus span does not change the distribution of model outputs. Equivalently, the `n_baseline` embeddings of the original prompt and the `n_ablated` embeddings of the ablated prompt are exchangeable: any split of the pooled embeddings into groups of those sizes is as likely as the true labels.

**Test statistic.** Let \(\bar e_B\) and \(\bar e_A\) be the means of the baseline and ablated embedding vectors.  
\(T = 1 - \cos(\bar e_B, \bar e_A)\)  
(cosine *distance* between centroids). Larger \(T\) means the two clouds are farther apart. The same function is used for the observed split and for every permuted split.

**Permutation scheme.** Pool the \(n_B + n_A\) embeddings. Each permutation reassigns labels while preserving group sizes and recomputes \(T\).  
- If \(\binom{n_B+n_A}{n_A}\) is at most the permutation budget (default 10 000), **every** assignment is enumerated (`exact: true`). The p-value is \(\#\{T_\pi \ge T_{\mathrm{obs}}\}/N\), identity included (so \(p \ge 1/N\)).  
- Otherwise **Monte Carlo**: \(B\) random assignments,  
  \(p = (1 + \#\{T_{\mathrm{perm}} \ge T_{\mathrm{obs}}\})/(1+B)\).  
The RNG seed, if provided, affects **only** these shuffles, never generation.

**Multiple testing.** Raw p-values for **attributable** foci only (not `verified: false`, `dynamic_slot`, or `overlap`) are converted to Benjamini–Hochberg q-values.  
**`is_significant` now means \(q < \alpha\)** (default \(\alpha = 0.05\)).

**Effect size (descriptive).** For each focus we also report \(T_{\mathrm{obs}}\), the null mean, the null 95th percentile, \((T_{\mathrm{obs}} - \mathrm{mean}(T_{\mathrm{null}}))/\mathrm{sd}(T_{\mathrm{null}})\), and null **deciles** (not the full permutation list). Normalized influence shares are \(T_{\mathrm{obs}}\) renormalised to 100% across attributable foci; they are not the test.

**Power guardrail.** The smallest possible p is \(1/N\) (exact) or \(1/(1+B)\) (Monte Carlo). If that exceeds \(\alpha / n_{\mathrm{foci}}\), results include `power_warning` telling the user to increase samples.

**Why the noise floor was replaced.** Pairwise similarities among baseline repeats describe *within-prompt* stochasticity. Comparing a *single* ablated output to that floor is not a test of “this deletion shifted the output distribution,” has no Type I error control, and does not account for testing many foci. The permutation test uses the same sampling design on both arms and a null that matches the claim.

## Sampling defaults

- `n_baseline = 10`, `n_ablated = 5`, `n_permutations = 10000`, `alpha = 0.05`, `temperature = 0.7`.
- Temperature **must** be \(> 0\); otherwise a clear error is raised.
- Baseline samples are drawn once per experiment (per pair in batch) and reused across foci.
- Legacy `num_samples` is treated as `n_baseline` if sent.

## Schema changes (not backward compatible)

| Removed | Replacement |
|---|---|
| `noise_threshold`, `baseline_variance`, `baseline_std`, `baseline_mean_similarity` | permutation fields on each attributable score |
| `noise_metrics` / batch-wide noise generation | per-pair (or single-run) permutation test |
| `is_significant` = similarity < noise floor | `is_significant` = BH \(q < \alpha\) |
| `influence` = \(1 - \cos\) of **one** pair of embeddings | `influence` = \(T_{\mathrm{obs}}\) (centroid cosine distance) |
| `similarity` of one pair | `similarity` = \(1 - T_{\mathrm{obs}}\) |

Kept: `is_significant`, `influence`, `similarity`, `normalized_influence`, `ablated_prompt`, `ablated_output` (first of `n_ablated` samples). Added: `p_value`, `q_value`, `t_obs`, `exact`, `null_*`, `null_deciles`, `standardized_effect`, `ablated_outputs`, `baseline_outputs`, `power_warning`, `significance_method: "permutation_bh"`.

Batch: BH is **per pair** (each pair is an experiment). Pair `i` uses RNG seed `permutation_seed + i` when a seed is set, so pairs do not share one shuffle stream.

## Decisions not specified

1. Exact p-value uses \(k/N\) over all splits including the observed labelling, not the Monte Carlo \(+1\) formula.
2. Zero-norm centroids → \(T = 1\). Zero null SD → standardized effect \(0\) if \(T\) equals the null mean, otherwise \(\infty\).
3. Comparisons \(T_{\mathrm{perm}} \ge T_{\mathrm{obs}}\) use a \(10^{-12}\) tolerance.
4. Frontend shows p, q, and BH significance; the old “within noise” copy is gone.

---

# Results presentation (copy and rendering)

This pass changes **user-facing copy and HTML only**. Permutation, ablation, and tagging logic are unchanged.

## User-facing strings that changed

Canonical source: `utils/results_copy.py` (`COPY`), injected into `templates/index.html` as `window.FOCALPROMPT_COPY`. `static/js/results_copy.js` renders from that payload and does not duplicate the prose.

| Location | Previous framing | New copy |
|---|---|---|
| Every results view (top) | Ablation as contribution / influence ranking | `DEFINITION`: FocalPrompt detects whether removing each focus shifts the model's behaviour in semantic embedding space. It does not measure correctness, quality, or safety, and it does not tell you what to delete. |
| Significant focus (primary) | “✓ Significant” plus influence % | `VERDICT_SIGNIFICANT`: Removing this focus measurably changed the model's behaviour. Then `(q = {q}, effect size = {z, 1 decimal})` and a band: small (z < 2), moderate (2–5), large (z > 5), e.g. `large effect (z = 8.3)`. |
| Non-significant focus (primary) | “Not significant” / previously “Within Noise” | `VERDICT_NOT_SIGNIFICANT`: No behavioural change detected beyond sampling variation at this sample size. Then `(q = {q})`. |
| Non-significant caution (always visible) | Absent, or implied “low influence ⇒ unused” | `NON_SIGNIFICANT_CAUTION`: Undetected here does not mean removable: short structural instructions (output formats, escalation rules, guardrails) can matter greatly while barely shifting output embeddings. |
| Near-threshold (α < q ≤ 2α) | Absent | `NEAR_THRESHOLD_HINT`: Near the threshold. Rerun with more ablated samples to resolve. |
| `verified: false` / `reason: unverified` | Blank or a zero | `EXCLUDED_UNVERIFIED`: Couldn't locate this focus verbatim in your prompt, so it wasn't tested. The tagger may have paraphrased it. |
| `reason: dynamic_slot` | Blank / chat treated as a scored arm | `EXCLUDED_DYNAMIC_SLOT`: This focus is a runtime slot (chat, retrieved context), not text in your prompt, so subtractive testing doesn't apply in this version. |
| `reason: overlap` | Blank or ill-defined score | `EXCLUDED_OVERLAP` plus `Overlaps with: {names}.` |
| `prompt_empty: true` | Unremarked | `PROMPT_EMPTY_NOTE`: Ablating this focus left an empty prompt. Results reflect the model with no instructions at all. |
| Power banner (when backend `power_warning` is present) | Raw backend sentence about min p vs α/n_foci | `POWER_BANNER_TEMPLATE`: With {n_baseline} baseline and {n_ablated} ablated samples, the smallest possible p-value is {min_p}. After correction across {n_foci} foci, real effects may be undetectable. Increase samples to resolve. `min_p` is computed in the presentation layer from the same `min_achievable_pvalue` helper; statistics are not changed. |
| Methods | Short numbered list + “Key Insight” that treated share % as importance | Expandable **How this works** (`METHODS_PANEL`): both-arm sampling, centroid cosine distance, permutation null (exact at small n), p-value, BH / q < 0.05, embedding blindness, leave-one-out conditionality, locality. |
| `templates/index.html` documentation + ablation intro | 20× “noise” measurement; tip to drop foci below background noise | Sensitivity framing; same `DEFINITION`; non-significant ≠ unused. |
| Batch results heading | “Ablation influence (embedding-based shares)” | “Descriptive T_obs shares across pairs”; per-pair verdict cards; excluded foci first-class. |
| Batch progress | “Calculating noise…” | “Sampling baseline outputs…” |
| CSV export header | `ABLATION (embedding shares)` | `ABLATION (descriptive T_obs shares; not a test)` |
| `README.md` | 100-point attention assessor overview | Sensitivity prototype, what it does not do, quickstart, methods summary, research-prototype status (< 150 lines). |
| `services/optimization_service.py` summary fed to the rewriter | “Influence scores (how much removing each focus affects output)” | T_obs / p / q with the non-significant caution. Normalized share % omitted from that summary so it is not treated as importance. |

q on the primary card uses three significant figures (`format_q_value`). Raw `t_obs`, `p_value`, `q_value`, and null deciles stay in **Statistical detail**, not on the primary card.

## Old framing that survives deliberately

1. **JSON field `influence`.** Still `T_obs` (centroid cosine distance) for schema compatibility. It is not labelled as an “influence score” in the UI. Documented in `models/analysis_models.py`.
2. **`normalized_influence` / batch mean-share table.** Still computed by the backend. The UI labels it as a descriptive renormalisation of T_obs, not a test and not a ranking of what to keep.
3. **`IMPLEMENTATION_NOTES.md` permutation section.** Keeps “noise floor” when describing *why the previous rule was replaced*. That is methods history, not product copy.
4. **`CONFOUND_AUDIT.md`.** Untracked audit of the old reconstruction pipeline; left as a historical record. It still uses the old claim language because it is describing that claim.
5. **Agent Builder / optimization `removal` recommendation type.** That tab rewrites prompts; it is not the ablation results view. Labels were not turned into ablation verdicts. The ablation summary piped into it now uses sensitivity language so the rewriter is less likely to treat T_obs as a delete-score.
6. **`window.removeFocus` and “Clear All”.** UI actions that delete a *tag* from the tagging list, not a recommendation about model behaviour.
7. **Backend `power_warning` string.** Still generated by `power_guardrail_message` for logs/API. The UI substitutes `POWER_BANNER_TEMPLATE` whenever that field is present, rather than showing the backend sentence.

## Decisions

- q format on the card: `.3g`. min_p on the banner: `.6g` (same as the permutation helper).
- Effect-size bands: small if \|z\| < 2, moderate if 2 ≤ \|z\| ≤ 5, large if \|z\| > 5. Infinite standardised effect is treated as large.
- Excluded-state precedence: `dynamic_slot`, then `overlap`, then `verified: false` / `unverified`. Unknown `attributable: false` uses the unverified sentence rather than a blank.
- Power banner n_foci is the number of tested (attributable / scored) foci, matching BH.
- Near-threshold uses α < q ≤ 2α on non-significant cards only.

---

# Experiment configuration (controls and live preview)

UI + persistence only. The permutation test, BH rule, and ablation deletion are unchanged. `power_guardrail_message` now wraps a pure `power_guardrail()` dict so the API warning and the configuration preview cannot disagree.

## New user-facing strings (`utils/experiment_config.py`)

| Control | Copy |
|---|---|
| Temperature help (always) | Use the temperature your prompt runs at in production. Results describe the model's behaviour at this temperature only. |
| Temperature ≥ 1.0 | High temperature widens normal output variation, so subtle effects need more samples to detect. |
| Temperature ≤ 0 (reject) | Existing `require_stochastic_temperature` text: Permutation test requires output stochasticity: temperature must be > 0 (got {t}). … |
| Cost, foci unknown | This experiment will make {n_baseline} + {n_ablated} × n_foci model calls. |
| Cost, foci tagged | This experiment will make {n_baseline + n_ablated × n_attributable} model calls. |
| Suggestion chip | suggested for this temperature |
| Suggestion tooltip | A heuristic starting point. If results warn about power or sit near the threshold, increase ablated samples. |
| Power ok | This design can detect effects at your significance level |
| Power fail | With {n_foci} foci, this design cannot reach significance after correction. Increase samples. |
| Exact disclosure | Significance: exact test ({n_assignments} enumerated group assignments) |
| Sampled disclosure | Significance: 10,000 sampled permutations (p-value margin ~±{se}) |
| Results header | Run at temperature {t}, {n_baseline}+{n_ablated} samples per focus, {exact\|sampled} test. |

## Behaviour

- Temperature default 0.7, intended range 0.1–2.0 step 0.1. ≤ 0 is rejected client-side with the same explanation as the server.
- n_baseline default 10 (5–50); n_ablated default 5 (3–25). Permutation count is not editable (10 000).
- Suggestion: t ≤ 1.0 → 10/5; t > 1.0 → 15/8. Click applies; hover/focus shows the tooltip. Heuristic, not a guarantee.
- Preview attributable count = tagged foci that are not `is_dynamic`. Overlap/unverified still cost a call in the preview if they are tagged as static; the run may then exclude them. Documented so it is not silent.
- Live power line uses `power_guardrail` (`min_p <= alpha/n_foci`). Hidden until at least one non-dynamic focus is tagged.
- Results and checkpoints already stored n_baseline, n_ablated, temperature; this pass adds experiment-level `test_type` (`exact` \| `sampled`) and renders the header.

## Deliberate leftovers

- Backend `power_warning` sentence is still the longer API string. The results banner and the config preview use their own copy, both driven by `power_guardrail()`.
- Monte Carlo SE is \(\sqrt{p(1-p)/B}\) at p = 0.05, B = 10 000 (≈ 0.002). It is a disclosure, not a confidence interval for a specific result.

