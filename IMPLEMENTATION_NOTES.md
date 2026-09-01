<<<<<<< HEAD
<<<<<<< HEAD
# Checkpoint path-traversal hardening — implementation notes

Decisions not fully specified by the task brief:

## Validator shape

- One module-level function `validate_checkpoint_identifiers(session_id, checkpoint_type)`
  validates **both** arguments. Charset check uses `re.fullmatch` on
  `^[A-Za-z0-9_-]{1,64}$` (equivalent to the requested pattern).
- `checkpoint_type` is then checked against `ALLOWED_CHECKPOINT_TYPES`
  (`frozenset`), a whitelist taken from the existing `get_checkpoint_path`
  docstring / `prefix_map`: `batch_analysis`, `batch_agents`,
  `single_ablation`, `single_assessment`.
- Error messages are fixed strings (`Invalid session_id`,
  `Invalid checkpoint_type`, `Invalid checkpoint path`) and never interpolate
  the rejected input.

## Where validation runs

- **Primary gate:** `get_checkpoint_path`, so save / load / delete are covered
  without duplicating checks at each call site.
- **`list_checkpoints`:** validates `checkpoint_type` before scanning the
  directory by calling the same validator with a dummy legal `session_id`
  (`"_"`). Previously an unknown type fell back to the `batch_analysis_`
  prefix via `dict.get(..., 'batch_analysis_')`; that fallback is removed so
  unknown types raise instead of silently listing the wrong files.
- Filenames whose derived `session_id` fails validation are **skipped** during
  listing (not raised), so a stray file on disk cannot break the list API.

## Path containment

- After `os.path.join`, both the base directory and the candidate path are
  `Path(...).resolve()`’d and checked with `Path.is_relative_to` (Python 3.12).
- The returned path is the resolved absolute path. Callers previously received
  the joined (possibly relative) string; resolved form is equivalent for open /
  rename / unlink and closes TOCTOU-style symlink tricks on the parent dir.
- When `self.checkpoint_dir is None`, the dummy base remains `/tmp`, and the
  same containment check runs against `/tmp`.

## Routes

- `/api/get-checkpoint` and `/api/list-checkpoints` catch `ValueError` **before**
  the generic `Exception` handler and return **400** with
  `{"error": "invalid session_id or type"}` — never the exception text, never
  500 for validation failures.
- Empty `session_id` on get-checkpoint still returns the pre-existing
  `session_id required` 400 (checked before the service is called).

## Out of scope / unchanged

- No changes to other modules, checkpoint payload schema, or atomic write
  behaviour.
- Internally generated session ids (`%Y%m%d_%H%M%S`, UUID hex/hyphen forms)
  already match the charset; no generator changes required.
- URL-encoding: Flask decodes query args before application code runs, so
  `..%2Fx` arrives as `../x` and fails the charset check. Tests cover both the
  decoded form and a request that uses `%2F` in the query string.
=======
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
>>>>>>> fc6c491 (Fix degenerate standardized_effect JSON and sanitize non-finite floats)
=======
# Hosted deployment hardening — implementation notes

## 1. Client IP (`resolve_client_ip`)

- **Hosted only trusts forward headers.** When `FOCALPROMPT_HOSTED_MODE=1`, order is `x-vercel-forwarded-for` (case variants), then `X-Forwarded-For` / `x-forwarded-for`. Otherwise only `request.remote_addr` is used so local/dev clients cannot spoof rate-limit keys.
- **Comma-separated lists:** `_first_header_value()` takes the substring before the first comma and strips whitespace (covers multi-hop proxy chains).
- **Fallback:** `request.remote_addr or 'unknown'` when hosted headers are absent.

## 2. Honest guard documentation

- Module docstring in `utils/hosted_mode.py` and the README hosted table state plainly that RPM/daily budget counters are in-process, per-instance on serverless, reset on cold start, and do not aggregate. No KV or external store was added; gateway key budget remains the authoritative spend cap.

## 3. CORS

- `hosted_cors_origins()` returns `None` when not hosted → `app_new.py` calls `CORS(app)` (unrestricted, local dev).
- When hosted, returns a list from `FOCALPROMPT_ALLOWED_ORIGINS` (default `https://focalprompt.com`) → `CORS(app, origins=...)`.
- Helper lives in `hosted_mode.py` (not `app_new.py`) so CORS policy is testable without reloading the Flask app at import time.

## 4. Secret key

- **Branch taken:** searched the codebase for Flask `session` usage (`session[`, `from flask import session`, etc.) — **none found**.
- **Action:** removed `app.secret_key` assignment from `app_new.py` entirely. No `RuntimeError` for missing `SECRET_KEY` because sessions are unused.

## 5. Gateway key logging

- Debug path in `core/ai_gateway_provider.py` logs only the last four characters as `…abcd` (Unicode ellipsis + suffix), never a prefix of the key.

## 6. Route 500 responses (`routes/http_errors.py`)

- New helper `internal_error(code, exc, extra=...)` prints full traceback + exception to stderr, returns `{'error': 'internal error', 'code': <stable_route_code>}`.
- **400-level responses unchanged** (intentional validation/user feedback).
- **Intentional non-exception 500s kept** in `agent_routes.py` (empty/missing chat content in constructed prompt).
- **Ablation rate limits:** `RateLimitError` and string-heuristic 429 paths unchanged; only generic exception branches use `internal_error`.
- **SSE streams:** out of scope — still emit `str(e)` in event payloads (only JSON 500 handlers were swept).
- **Extra fields preserved** where the client contract expects them: e.g. `pricing_gateway_models` adds `models: {}`, `source: 'error'`; `behavioral_llm_judge` adds `status: 'failed'`; `batch_test_api_key` adds `valid: False`; `batch_parse_csv` adds empty `errors`/`pairs`.

### Stable error codes (500)

| Code | Route |
|------|-------|
| `batch_parse_csv` | POST `/api/parse-batch-csv` |
| `batch_list_checkpoints` | GET `/api/list-checkpoints` |
| `batch_get_checkpoint` | GET `/api/get-checkpoint` |
| `batch_aggregate` | POST `/api/batch-aggregate` |
| `batch_test_api_key` | POST `/api/test-api-key` (outer handler) |
| `assessment_detect_foci_parse` | POST `/api/detect-foci` (LLM JSON parse) |
| `assessment_detect_foci` | POST `/api/detect-foci` |
| `assessment_detect_dynamic_foci` | POST `/api/detect-dynamic-foci` |
| `assessment_assess` | POST `/api/assess` |
| `assessment_generate_output` | POST `/api/generate-output` |
| `assessment_rewrite_prompt` | POST `/api/rewrite-prompt` |
| `assessment_build_agent_prompt` | POST `/api/build-agent-prompt-from-inputs` |
| `ablation_analysis` | POST `/api/ablation-analysis` |
| `ablation_sample` | POST `/api/ablation-sample` |
| `ablation_refine_stability` | POST `/api/ablation-refine-stability` |
| `ablation_behavioral_outcome_dispersion` | POST `/api/ablation-behavioral-outcome-dispersion` |
| `ablation_score` | POST `/api/ablation-score` |
| `ablation_shuffle_robustness` | POST `/api/ablation-shuffle-robustness` |
| `ablation_reported_focus_dynamics` | POST `/api/ablation-reported-focus-dynamics` |
| `agent_assess_chat_foci` | POST `/api/assess-chat-foci` |
| `agent_build_prompt` | POST `/api/build-agent-prompt` |
| `agent_generate_response` | POST `/api/generate-agent-response` |
| `pricing_estimate` | POST `/api/pricing/estimate` |
| `pricing_models` | GET `/api/pricing/models` |
| `pricing_gateway_models` | GET `/api/models` |
| `behavioral_llm_judge` | POST `/api/behavioral-difference/llm-judge` |
| `behavioral_human_review` | POST `/api/behavioral-difference/human-review` |
| `evaluation_outputs_quality` | POST `/api/evaluate-outputs-quality` |
| `order_sensitivity_run` | POST `/api/focus-order-sensitivity` |
| `optimization_analyze_prompt` | POST `/api/analyze-prompt-optimization` |

## 7. Tests

- `tests/unit/test_hosted_and_experiments.py`: `resolve_client_ip` (local vs hosted, comma lists), `hosted_cors_origins` branches, pricing estimate 500 leak check via monkeypatched `CostCalculator.calculate_cost`.
>>>>>>> 6793c7f (Harden hosted deployment: client IP, CORS, error sanitization)
