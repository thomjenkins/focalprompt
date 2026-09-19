# Jev dynamic focus experiment

The separate lab experiment uses `typesafe-ai/jev` to decide which verified focus
spans apply to the current retained user input. A generative model then samples
responses to the constructed prompts. Existing prospective, retrospective and
ablation results are not changed.

## Protocol `jev-focus-v1`

1. Snapshot the complete ordered scenario, exact focus spans, inclusion threshold,
   generation model, temperature and sample count. Require a nonempty retained user
   message and a verified span for every focus (up to 60 foci).
2. Send the complete scenario, retained user messages and focus catalog to Jev.
   Ask one independent Boolean question per focus in a shared request. Include
   applicable background constraints as well as instructions directly relevant to
   the user request. No new outputs, prospective allocations or retrospective
   judgments are supplied. Include when `P(include) >= threshold` (default 0.5).
   These probabilities are **not** a normalized focus budget or measured attention.
3. Optionally ask Jev to choose the next focus from remaining candidates, repeating
   until each message's selected movable foci have been ordered. Each choice sees
   the full context, selected set and previous ordering prefix. The last candidate
   occupies the last slot without an inference call. This is a sequential decision
   heuristic, not a guarantee of a globally optimal ordering.
4. Compose exact original source text. Remove only text covered by excluded foci
   and not by any selected focus. Preserve unlabelled text, retained messages,
   roles, message order and the output contract. Overlapping and multi-span foci
   cannot move. Movable, non-overlapping single spans can only exchange slots
   within the same message. Excluded text shared with an included focus survives;
   the UI explicitly reports these cases. Removing a focus may therefore not fully
   remove its semantics. Users can improve span labels and inspect the exact result.
5. Generate independent samples for the full scenario, selected foci in source
   order, and optionally the same selected set in Jev's order. Use the same model,
   requested temperature and count for all arms. Randomize arm order within each
   sampling round, store the schedule, and resume only missing outputs. Provider
   restrictions on sampling parameters still apply. No assumed seed pairing or
   reuse of previous baseline outputs occurs.

The selection is held fixed across outputs in one experiment. This measures
generation variability conditional on a single selection, not the variability of
Jev decisions. For generalization, run separate experiments on representative
retained inputs and evaluate task quality against criteria specified in advance.
Threshold tuning requires labelled examples and held-out validation. High model
probabilities do not establish calibrated accuracy in a new domain. Fewer prompt
characters or different responses do not by themselves establish better quality.

Each experiment preserves the exact selection/ordering requests, typed answers,
Gateway usage, provider metadata, applied orders, prompts, sampling schedule and
received outputs in workspace export/import. Jev provides no prose explanation;
FocalPrompt does not invent one. Failures never become uniform scores or forced
selections. Transport failures retry up to twice, which may duplicate an upstream
call whose response was lost; only successfully received outputs count as samples.

## Gateway integration

Jev has model type `evaluation`; `/api/models` returns evaluation models separately
from chat models. The dedicated experiment uses Jev automatically, while its model
picker chooses the model generating responses.

Vercel documents evaluation as AI SDK-only, not OpenAI-compatible. FocalPrompt's
Python adapter implements the **experimental evaluation v4 wire contract** used
by the public AI SDK (`/v4/ai/evaluation-model`, protocol `0.0.1`, model/specification
headers). Keep it isolated and live-smoke-test it when the upstream protocol changes.
No chat fallback, text parsing, temperature or max-token setting is used for Jev.
The server's `AI_GATEWAY_API_KEY` and standard Gateway routing settings are used. Credentials
and response headers are excluded from experiment exports and upstream error bodies
are not exposed or logged by this adapter.

As verified September 18, 2026, Gateway lists $0.042 per million input tokens and
$0 for output. Pricing and promotional credits can change; the UI links to current
pricing rather than promising free inference. Generation incurs its model's charges.

Primary references:

- https://vercel.com/docs/ai-gateway/modalities/evaluation
- https://vercel.com/ai-gateway/models/jev
- https://github.com/vercel/ai/blob/main/packages/gateway/src/gateway-evaluation-model.ts
- https://github.com/vercel/ai/blob/main/packages/gateway/src/gateway-provider.ts
