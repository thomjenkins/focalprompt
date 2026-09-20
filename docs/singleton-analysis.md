# Baseline + singleton focus analysis

Step 9 adds a separate, resumable experiment:

**No foci → each focus individually → all foci → each focus removed.**

Label exact source spans in step 1, choose the generation model and sampling
settings in steps 2–3/5, and select **Run analysis**. Prediction and retrospective
assessment are optional for this mode. Existing full-prompt and ablation results
remain unchanged. Each row's details show all four prompts and their outputs.
Workspace export/import includes partial samples and completed results; completed
runs also use the existing checkpoint service. **Download results** exports the
complete result JSON, including the execution plan and sample provenance.

## Exact prompt construction

The shared `utils/focus_variants.py` composer serves both Jev and this mode. It
copies source intervals rather than reconstructing instructions or matching text
by name. It retains message roles/order, all Retain content, named inputs, the
output contract and unlabelled text (including residual whitespace). A fully
removed Analyse message is omitted. A request that would have no user message
fails validation before generation; no substitute prompt or fabricated output
is inserted.

- **Full:** the original scenario.
- **No-focus:** delete the union of every labelled focus span.
- **Singleton i:** preserve the complete spans of focus i and all unlabelled text;
  delete text covered only by other foci.
- **Leave-one-out i:** call the unchanged `ablate_scenario` implementation, deleting
  focus i's complete spans, including shared text.

For overlapping foci, a singleton can contain text shared with an excluded focus.
Its result lists those focus indices and the UI warns about this. Conversely,
leave-one-out can remove text used by a different focus. These are interventions
on source text, not a guarantee that a semantic concept occurs in only one place.
Multi-span and multi-message foci, retained conversation history and output
contracts are preserved. All foci must have verified spans for this mode.

## Sampling and reuse

Full and no-focus conditions use the configured baseline count; singleton and
leave-one-out conditions use the configured ablated count. Defaults are 10/5 at
0.7. Every condition uses the baseline generation model and existing
`/api/ablation-sample` → `AblationService` → `complete_scenario` execution path.
Provider-specific handling of temperature, roles and output contracts is unchanged.

A deterministic hash of each exact scenario defines a sample pool within this
experiment's model/temperature context. Identical variants share a pool sized to
the largest requested count and take its ordered prefix. They are not independent
replications. For two disjoint foci, singleton A is the same prompt as removing B,
so those outputs are generated once. For N distinct foci, the upper bound is
`2 × n_baseline + 2 × N × n_ablated` calls; the plan shows the reduced count.

Matching saved full and leave-one-out samples are reused only when their scenario,
focus identities/spans, model/provider, temperature and relevant count match.
There is no global generation cache: separate stochastic draws within a pool are
preserved, and **New run** starts a new experiment while still allowing exact
existing full/ablation evidence to be reused. To resample that evidence, regenerate
it in the main workflow first.

Unique conditions are randomly interleaved by sampling round, with the schedule
saved for resumption. Six workers use the existing sampling/retry path and settle
in-flight calls before returning an error. Successful samples survive interruption,
export/import and scoring failures. Scoring does not resample. Lost responses or
failed retries can still incur provider usage. Only received new-call usage is
counted; reused samples are labelled. Embeddings are cached by exact output text
within each score request and batched through the existing embedding service.

## Metrics

Let `d(A,B)` be the existing cosine distance between mean output embeddings.
Here each `Y` is a sample set, rather than a single representative output. Every
result includes both the first output for convenience and the complete arrays.

| Metric | Formula | Meaning |
|---|---|---|
| Influence | `d(Y_i,Y_0)` | Shift caused by introducing one focus into the no-focus prompt |
| Normalized influence | `d(Y_i,Y_0) / d(Y_full,Y_0)` | Shift relative to the full/no-focus contrast; may exceed 1 |
| Raw singleton/full distance | `d(Y_i,Y_full)` | Remaining distance from the full-prompt behavior |
| Sufficiency | `1 - d(Y_i,Y_full) / d(Y_full,Y_0)` | Progress toward full behavior; negative values are retained |
| Necessity | `d(Y_-i,Y_full)` | Existing leave-one-out shift |

The new normalized influence is a **ratio**, not the legacy ablation
`normalized_influence` percentage share. The old field remains unchanged inside
`necessity_comparison` and `necessity_analysis` for compatibility.

Influence gets a separate permutation-test/BH family across singleton/no-focus
comparisons. Necessity calls the original ablation scorer, retaining its raw
statistics, p/q-values, noise diagnostics and definition. Sufficiency and the
normalized influence ratio are descriptive; they do not have significance tests
or confidence intervals. The optional `permutation_seed` makes scoring repeatable
for fixed embeddings and outputs; it is not a model-generation seed.

### Low behavioral contrast

The numerical floor is `1e-6`, consistent with existing near-zero dispersion
handling. When both full and no-focus sets have at least two outputs, the threshold
is the larger of that floor and the 95th percentile of the existing permutation
null for their centroid distance. The rule and actual threshold are exported.

If the observed contrast is at or below this threshold,
`low_behavioral_contrast=true`, both normalized metrics are `null`, and the UI
explains why. Raw comparisons are retained. This is a conservative normalization
guard against numerical or sampling noise, **not proof that the two conditions are
equivalent**. At one output per condition only the numerical guard is available;
there is no useful sampling-noise estimate. Small samples and multimodal output
sets limit the interpretation of centroid-based summaries.

High singleton sufficiency with low necessity may suggest redundancy. Low
singleton sufficiency with strong necessity may suggest reliance on other foci.
These are evidence patterns, not automatic causal labels. Full/no-focus,
singleton and leave-one-out arms do not uniquely identify all pairwise or
higher-order interactions; that requires additional factorial interventions.
None of these metrics measures internal attention or task quality.

## API and result structure

1. `POST /api/singleton-plan`: `scenario`, `foci`, `n_baseline`, `n_ablated`,
   `temperature`, optional named `inputs`. Returns a bound scenario, exact
   `variants` and de-duplicated `pools`; no inference is used.
2. `POST /api/ablation-sample`: existing body plus `kind` = `baseline`, `no_focus`,
   `singleton` or `ablated`; singleton/ablated require `focus_index`. Use the bound
   scenario from the plan. New kinds use the scenario API; legacy prompt sampling
   is unchanged.
3. `POST /api/singleton-score`: bound `scenario`, original `foci`, the same sampling
   settings and `samples` keyed by pool ID. Each sample contains nonempty `content`
   and may include `scenario`, `usage` and `reused_from`. All pools must be complete;
   supplied scenario metadata must match. Optional `n_permutations`, `alpha` and
   `permutation_seed` use the existing scoring conventions.

The `singleton-focus-v1` result includes `context`, `plan`, `samples`, all four
`arms`, `full_outputs`, `no_focus_outputs`, `full_no_focus_distance`,
`low_behavioral_contrast`, `contrast_threshold`, `focus_results`,
`necessity_analysis`, evaluator metadata, counts and costs. Per-focus rows include
identity/spans, singleton/leave-one-out outputs, influence and necessity
comparisons, normalized influence, sufficiency and raw singleton/full distance.

See [the two-focus example](../examples/singleton/two-focus-analysis.json).
It uses invented outputs and hand-specified embeddings to illustrate the formulas,
not measured model performance. Its full/no-focus distance is 1:

| Focus | Influence | Normalized influence | Sufficiency | Necessity |
|---|---:|---:|---:|---:|
| Accuracy | 1 | 1 | 1 | 2 |
| Brevity | 1 | 1 | -1 | 0 |

The negative sufficiency means the singleton embedding is farther from the full
condition than the no-focus embedding in this deliberately constructed example.
