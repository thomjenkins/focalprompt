# Resumable focus-order sensitivity

The lab plans the experiment first, then requests each generated output separately (two concurrent requests at most). Optional behavioural judgments are requested one output at a time. Scoring receives the saved outputs and judgments, batches their embeddings, and applies the existing statistical engine without calling a generation or judge model.

This prevents the entire permutation and position-sweep experiment from sharing one serverless request timeout. An individual provider request can still fail; transport, rate-limit, and temporary server failures use bounded retries. Received samples and judgments are retained. **Resume order analysis** finishes missing work. **Stop after current requests** keeps outputs already in flight. **New run** starts another experiment; changed prompts, foci, baselines, models, or settings cannot be mixed into a resumed run.

Workspace exports include `prompt_analysis.focus_order.run_state`: the original context, deterministic condition plan, received samples, judgments, progress/error, and completed result. Import restores this state. Older exports containing only `focus_order.results` still render normally. Keep the tab open while running; export the workspace to preserve partial work across a reload or another device.

The lab calls these endpoints under `/api/focus-order-sensitivity/`:

- `plan`: validates and reconstructs the exact scenarios without inference.
- `sample`: generates one output for one planned permutation or position.
- `judge`: judges one saved output against the configured criterion.
- `score`: requires all samples and, when enabled, all judgments; performs embedding/statistical comparisons only.

Message roles, retained input, exact instruction text, structured output contracts, generation temperature, condition sample counts, and baseline reuse follow the original experiment. Global permutations and position-sweep conditions retain separate independent sample sets even when two conditions contain identical prompts. The legacy single-request endpoint remains available for direct API/CLI compatibility; the lab no longer uses it. Same-origin browser requests to that endpoint receive HTTP 409 JSON with code `order_client_upgrade_required`, before any model calls. Export the existing workspace, reload the lab, then import it to use the resumable workflow. Already-open tabs are never automatically reloaded or cleared.

JavaScript and CSS links use content fingerprints so a new page cannot reuse code from an older release based on the serverless bundle's normalized modification dates. A raw `Unexpected token ... is not valid JSON` popup without the saved-work/resume message identifies the old browser handler. The new handler translates plain-text timeout/error pages into actionable errors, retries transient failures, and retains completed samples.

Validation includes Astra request routing and structured contracts, plan determinism, statistical parity with the original engine, one-call generation/judging, incomplete-score rejection, retry and Stop behavior, model/context mismatch protection, and browser export/import/resume after a simulated gateway timeout.
