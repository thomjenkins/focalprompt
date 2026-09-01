# Permutation JSON safety — implementation notes

## Zero-variance `standardized_effect`

When the permutation null distribution has **zero variance** (`null_std == 0`) and the observed statistic differs from the null mean, the previous code returned `float('inf')`. Flask's default JSON encoder emits bare `Infinity`, which strict JSON parsers reject.

**Fix:** return `standardized_effect: null` and add `standardized_effect_note` with a plain explanation that the null was degenerate and a standardised z-score is undefined. The note string is defined once in `utils/permutation_test.py` as `STANDARDIZED_EFFECT_DEGENERATE_NOTE` and re-exported through `utils/results_copy.COPY` for the browser.

When `t_obs` equals the null mean under zero variance, `standardized_effect` remains `0.0` and no note is set.

## UI rendering

- **Python (`utils/results_copy.py`):** `format_effect_size` and `effect_size_band` treat non-finite floats as `n/a` / no band (no more `'inf'` label). `render_standardized_effect_note()` adds an inline caution with `title` tooltip on significant cards when the note field is present.
- **JavaScript (`static/js/results_copy.js`):** mirrors the same behaviour; copy text comes from `FOCALPROMPT_COPY`, not hardcoded in JS.

## Field propagation

`standardized_effect_note` is copied from `permutation_test()` output through `services/ablation_service.py` and `utils/order_sensitivity_stats.py` into API payloads so the results UI can display it.

## Source fixes for division-derived floats

- **`signal_to_noise_ratio`** (`utils/baseline_stability.py`): returns `None` when the ratio is non-finite instead of passing through `inf`/`nan`.

## Backstop sanitizer

`utils/json_safe.sanitize_non_finite()` recursively converts non-finite floats to `None`. Applied via `_analysis_json()` in `routes/ablation_routes.py` and `routes/order_sensitivity_routes.py` on successful analysis responses before `jsonify`. Error payloads (4xx/5xx) are not sanitized.

**Not audited exhaustively:** `insight_metrics` ratios already guard zero totals in `normalize_share()`; no `inf` sources found there. SSE streams and download JSON were out of scope.

## Tests

- `test_zero_variance_degenerate_standardized_effect` — `n_permutations=1` Monte Carlo case; asserts `None`, note, and `json.loads(..., parse_constant=...)` rejects `Infinity`/`NaN`.
- `tests/unit/test_json_safe.py` — sanitizer behaviour.
- `tests/unit/test_results_copy.py` — degenerate note rendered as `n/a` + inline caution.

## Reproducing the degenerate case

With `n_baseline=1`, `n_ablated=2`, and `n_permutations=1`, the null has a single sample (`null_std=0`). The observed statistic uses the original label assignment, which may differ from that lone permuted draw — triggering the undefined-effect branch. Example: `permutation_test(A, B, n_permutations=1, rng=0)` with `A.shape=(1,4)`, `B.shape=(2,4)` from `np.random.default_rng(0)`.
