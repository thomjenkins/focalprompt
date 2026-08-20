# FocalPrompt confound audit: reconstruction artefacts in ablation

**Date:** 18 August 2026  
**Scope:** Read-only audit of prompt reconstruction after focus ablation. No code was changed.  
**Claim under test:** If removing a focus shifts model outputs beyond a stochastic noise floor (embedding cosine distance vs repeated runs of the unmodified prompt), that focus is influential.

**Verdict:** The claim is not currently identified. Ablated prompts are not the original prompt minus a span. They are **reassembled through an agent-builder template** that injects headers, focus-name tags, priority labels, optional chat scaffolding, and (for dynamic foci) leftover placeholders. **Baseline and noise-floor runs never enter that pipeline.** Measured divergence therefore mixes (a) deletion of the focus with (b) addition of reconstruction artefacts.

---

## 1. Reconstruction code paths

All live ablation reconstruction goes through one function: `build_prompt_with_dynamic_foci` in `utils/prompt_builder.py`. Callers force remaining foci to `weight=1.0` and `chat_weight=0.5`. Baseline / noise runs pass the original `prompt` string (or a chat-stripped variant) straight to the LLM.

`app_old.py` contains older reconstruction (string replace, line-filter by focus name, `\n\n`.join of remaining `prompt_section`s). Nothing in the current app imports it. It is historical only.

### 1.1 Shared reconstructor

| Item | Location |
|------|----------|
| Function | `build_prompt_with_dynamic_foci` |
| File | `utils/prompt_builder.py` |
| Lines | 38–141 |
| Artefact sources | 75–89 (always-on in ablation: `## Primary Instructions` + `### {focus_name}`); 91–121 (medium/low headers; unused in ablation because weight is forced to 1.0); 123–130 (placeholder replace); 132–139 (chat-weight append **overwrites** the replaced string) |

### 1.2 Single-run ablation (website + `/api/ablation-analysis`)

| Step | File | Function | Lines | What it does |
|------|------|----------|-------|----------------|
| HTTP entry | `routes/ablation_routes.py` | `ablation_analysis` | 38–86 | Passes `prompt`, `foci`, `inputs` (frontend often omits `inputs`) into `AblationService.run_ablation` |
| **Baseline / noise** | `services/ablation_service.py` | `AblationService.run_ablation` | 72–121, especially **86–92** | `num_samples` completions of **`[{"role":"user","content": prompt}]`** — original prompt, **no reconstruction** |
| Remaining-foci filter | same | same | 126–132 | Drops the focus whose `focus` name matches |
| **Primary reconstruction** | same | same | **134–146** | Remaining foci rewritten with `weight: 1.0`, then `build_prompt_with_dynamic_foci(..., chat_weight=0.5)` |
| Dead fallback | same | same | 148–154 | `prompt.replace(focus_section, '')` + strip blank lines. **Does not run** when remaining foci exist: weight 1.0 always yields at least the Primary Instructions header |
| Last-focus branch | same | same | 155–163 | If no remaining foci: concatenate `chat_content` + `rag_context`, else **reuse the original `prompt` (no-op ablation)** |
| Ablated LLM call | same | same | 175–179 | Completions of **`ablated_prompt`**, not `prompt` |
| Frontend | `static/js/app.js` | ablation click handler | 2538–2569 | POSTs `prompt`, `foci`, `num_samples`; **does not send `inputs`** |

Persisted results (`ablation_results` at 207–212) store `ablated_output` and `prompt_section`, **not** `ablated_prompt`. The confound is invisible in checkpoints.

### 1.3 Batch analysis (per pair)

| Step | File | Function | Lines | What it does |
|------|------|----------|-------|----------------|
| Pair **baseline** | `services/batch_analysis_service.py` | `process_single_pair` | **88–99** | LLM on pair `prompt` — **no reconstruction** |
| **Primary reconstruction** | same | same | **137–154** | Identical to single-run: remaining foci, `weight=1.0`, `build_prompt_with_dynamic_foci(..., chat_weight=0.5)` |
| Dead fallback | same | same | 156–162 | Same string-replace + blank-line strip |
| Last-focus branch | same | same | 163–171 | Same chat/rag concat or original prompt |
| Ablated LLM call | same | same | 173–178 | Completions of reconstructed `ablated_prompt` |
| Chat “ablation” | same | same | **202–210** | `prompt.replace(chat_content, '')` then strip blank lines. **Different pipeline** from focus ablation |

### 1.4 Batch noise floor (once per job)

| Step | File | Function | Lines | What it does |
|------|------|----------|-------|----------------|
| Noise prompt | `services/batch_analysis_service.py` | `stream_batch_analysis` | **320–349** | First pair’s `prompt`; if `chat_content` is a substring, **strip it** and drop blank lines (332–335). Then `num_samples` completions of that **system-only** string. **No reconstruction** |

This is a **third** prompt family: not the pair baseline, not the reconstructed ablation arm.

### 1.5 Related, not ablation

`routes/agent_routes.py` `build_agent_prompt` (75–108) and `routes/assessment_routes.py` `build_agent_prompt` call the same builder for **agent construction**. That is the intended use of the template. Ablation reused it.

Focus tagging (`services/assessment_service.py` `detect_foci`, ~60–84) asks the LLM to quote `prompt_section` as “exact text from the prompt.” There is **no span check** that the quote is a substring of `prompt`. Reconstruction uses those quotes, not character offsets into the original.

---

## 2. Concrete before / after examples

Examples were produced by executing the **current** `build_prompt_with_dynamic_foci` and the same remaining-foci / `weight=1.0` / `chat_weight=0.5` logic as `AblationService.run_ablation` (lines 132–163). No production code was edited.

### 2.1 Path A — primary reconstruction (typical single-run)

Website ablation sends no `inputs`. Remaining foci ≥ 1. This is the default path.

**Original prompt (baseline and noise floor):**

```
You are a veterinary triage assistant.

Always cite the source of any medical claim.

Respond in JSON with keys: urgency, differentials, next_steps.

If the owner mentions breathing difficulty, escalate immediately.
```

Foci (as `prompt_section` quotes):

1. Role as veterinary triage assistant → `You are a veterinary triage assistant.`
2. Citation requirement → `Always cite the source of any medical claim.`
3. JSON output format → `Respond in JSON with keys: urgency, differentials, next_steps.`
4. Breathing-difficulty escalation → `If the owner mentions breathing difficulty, escalate immediately.`

**Ablated prompt after removing “Citation requirement”:**

```
## Primary Instructions (High Priority)

### Role as veterinary triage assistant
You are a veterinary triage assistant.

### JSON output format
Respond in JSON with keys: urgency, differentials, next_steps.

### Breathing-difficulty escalation
If the owner mentions breathing difficulty, escalate immediately.
```

**Diff (text in the ablated prompt that is not in the original):**

```diff
+ ## Primary Instructions (High Priority)
+
+ ### Role as veterinary triage assistant
  You are a veterinary triage assistant.
-
- Always cite the source of any medical claim.
-
+ ### JSON output format
  Respond in JSON with keys: urgency, differentials, next_steps.
-
+ ### Breathing-difficulty escalation
  If the owner mentions breathing difficulty, escalate immediately.
```

Confound artefacts (lines with no counterpart in the original):

- `## Primary Instructions (High Priority)`
- `### Role as veterinary triage assistant`
- `### JSON output format`
- `### Breathing-difficulty escalation`

Also lost: original blank-line rhythm; the citation sentence. The lost sentence is the intended intervention. The four headers are not.

### 2.2 Path B — string-replace fallback (dead in live ablation)

If this branch ran (`ablation_service.py` 148–152), deleting the citation span and stripping empty lines would yield:

```
You are a veterinary triage assistant.
Respond in JSON with keys: urgency, differentials, next_steps.
If the owner mentions breathing difficulty, escalate immediately.
```

Artefacts: none added. Side effect: **all blank lines removed**, so the ablated prompt is denser than baseline even under “subtractive” fallback. This path does not run for remaining_foci > 0 because reconstruction is never empty.

### 2.3 Path C — last remaining focus (`remaining_foci == []`)

Single focus, empty `inputs`: **ablated prompt = original prompt**. Influence of that focus is ~0 by construction (same input as baseline).

With `inputs = {chat_content: "My dog is coughing.", rag_context: "Guideline excerpt"}`:

```
My dog is coughing.
Guideline excerpt
```

The original prompt is discarded entirely. Divergence vs baseline is dominated by **replacing the prompt with dynamic payloads**, not by deleting one span.

### 2.4 Path D — batch pair with `chat_content` (non-dynamic foci)

Pair baseline uses the original (or original + chat already in `prompt`). Reconstruction with `inputs.chat_content = "My dog has been coughing for 3 days."` after removing the citation focus:

```
## Primary Instructions (High Priority)

### Role as veterinary triage assistant
You are a veterinary triage assistant.

### JSON output format
Respond in JSON with keys: urgency, differentials, next_steps.

### Breathing-difficulty escalation
If the owner mentions breathing difficulty, escalate immediately.

## Current Chat Context (Weight: 0.50)

My dog has been coughing for 3 days.
```

**Added vs original:** all Path A headers, plus:

- `## Current Chat Context (Weight: 0.50)`
- The chat string, if it was not already in the original prompt (batch pairs often keep chat only in `inputs`, while pair `prompt` is the system prompt)

### 2.5 Path E — remaining dynamic `chat` focus (placeholder overwrite bug)

Foci include `{focus: "Live chat", prompt_section: "Consider the current conversation.", is_dynamic: True, dynamic_type: "chat"}`. Remove a *different* focus. `chat_content = "Owner: my cat is lethargic"`.

**Ablated prompt (actual output of the builder):**

```
## Primary Instructions (High Priority)

### Live chat
Consider the current conversation.

{{CHAT_CONTENT}}

### JSON format
Respond in JSON with keys: urgency, differentials, next_steps.

## Current Chat Context (Weight: 0.50)

Owner: my cat is lethargic
```

**Added vs original:**

- Priority / `###` headers (as in Path A)
- `Consider the current conversation.` if that sentence was not in the original
- Literal `{{CHAT_CONTENT}}` (placeholder **not** substituted in the returned string)
- `## Current Chat Context (Weight: 0.50)` and the chat body (chat appears once as scaffold, while the token remains)

Mechanism: lines 127–130 replace placeholders on `constructed_prompt`, then lines 134–139 see that `{{CHAT_CONTENT}}` is gone, append chat to **`prompt_parts` (still unreplaced)**, and **reassign** `constructed_prompt = '\n'.join(prompt_parts)`. The substitution is discarded. Comment on 132–133 (“if no chat focus”) does not match the condition (`'{{CHAT_CONTENT}}' not in constructed_prompt` after replace).

### 2.6 Path F — ablate the dynamic chat focus itself

Remaining static foci still get Primary / `###` headers. Chat is **still injected** via `chat_weight=0.5` (`## Current Chat Context`). Removing a “chat” focus does not remove chat from the prompt if `inputs.chat_content` is set. The intervention is mis-specified.

### 2.7 Batch chat ablation (separate from foci)

`batch_analysis_service.py` 202–204: `prompt.replace(chat_content, '')` + drop blank lines. No builder headers. If `chat_content` is missing from `prompt` (chat only in `inputs`), replace is a no-op and “no-chat” equals the full prompt.

---

## 3. Artefact characterisation

| Artefact | Source | When it appears |
|----------|--------|-----------------|
| `## Primary Instructions (High Priority)` | Template join, `prompt_builder.py` 78 | **Every** focus ablation with ≥1 remaining focus. Ablation sets `weight=1.0` (threshold `> 0.7`) |
| `### {focus_name}` | Template, lines 84, 100, 116 | **Every** remaining focus, all types. LLM focus **names** (not original wording) become headings |
| `## Secondary Instructions (Medium Priority)` / `## Context (Low Priority)` | Lines 94, 110 | **Not** in current ablation (weights forced to 1.0). Would fire if weights were left as assessment scores |
| Extra newlines | Parts already start with `\n` then `'\n'.join` (123) | All builder reconstructions |
| `## Current Chat Context (Weight: 0.50)` + chat body | Lines 134–139; ablation passes `chat_weight=0.5` | Any reconstruction with non-empty `inputs.chat_content` (batch typical; **not** default website single-run) |
| Literal `{{CHAT_CONTENT}}` (and analogously other placeholders if the same overwrite applied after a failed remaining-placeholder check) | Dynamic branch 85–87 / 101–103 / 117–119, then overwrite 139 | Remaining **dynamic chat** foci + non-empty chat: placeholder survives in the returned string |
| Dynamic `prompt_section` plus payload | Builder inserts quoted section **and** placeholder/payload | Dynamic foci (`chat` / `rag` / `tools` / `other`) |
| Blank-line deletion | Fallback 152; batch chat 204; batch noise 335 | Fallback (dead for main path); chat ablation; batch noise — **not** on pair/single baseline |
| Full original reused | Last-focus 163 / 171 | Sole focus, empty inputs: **no deletion** |
| Prompt replaced by chat+rag only | Last-focus 157–161 / 165–169 | Sole focus with dynamic inputs |

**Focus-type dependence**

- **Static foci, empty inputs (default website):** Path A only — priority header + one `###` name per remaining focus. Universal for that path.
- **Any reconstruction with `chat_content`:** additional chat scaffold; dynamic chat remaining → leftover `{{CHAT_CONTENT}}` and duplicated chat channel.
- **Ablating the last focus:** either no-op or discard-the-prompt, not span deletion.
- **`prompt_section` vs original:** tagging does not verify quotes. Reconstruction can insert **paraphrases** the original never contained (connective / summarised “section” text). That is LLM-assisted content, not a template join.

**What is *not* the original prompt:** remaining `prompt_section`s are concatenated in **foci-list order**, wrapped in a new outline. Original order, separators, and untagged glue (e.g. “Always…”, wrapping sentences that were not quoted) are dropped. Ablation is **reconstructive**, not subtractive.

---

## 4. Do baseline / noise use the same reconstruction pipeline?

**No. They bypass it.** This is the core confound.

| Arm | Prompt sent to the model | Reconstruction? |
|-----|--------------------------|-----------------|
| Single-run baseline (all `num_samples`) | Original `prompt` | **No** (`ablation_service.py` 86–92) |
| Single-run ablated | `build_prompt_with_dynamic_foci(...)` | **Yes** (145–146) |
| Batch pair baseline | Pair `prompt` | **No** (93–98) |
| Batch pair ablated | Same builder as single-run | **Yes** (154) |
| Batch noise floor | First pair `prompt` **minus** `chat_content` if present, blank lines stripped | **No** (328–349) — and **not even the same string** as pair baseline |
| Batch “no chat” control | `prompt.replace(chat_content)` + strip blanks | **No** builder; not matched to reconstructed focus arms |

Noise methodology: pairwise cosine similarities among embeddings of repeated **baseline** outputs; threshold `mean - 2*std` (`ablation_service.py` 221–240). Ablated similarity is compared to that threshold (278–281). The noise distribution is **output stochasticity of the original prompt**. Ablated outputs are generated from a **different prompt class** (templated agent prompt). Crossing the threshold can mean “template + deletion changed the output,” not “this focus exceeded original-prompt noise.”

Batch is worse: significance uses a noise floor from a **chat-stripped system prompt**, compared to ablated outputs from **reconstructed remaining foci ± chat scaffold**, against a pair baseline from the **full pair prompt**. Three prompt families, one threshold.

---

## 5. Fix strategies

### (a) Strict subtractive ablation

**Intervention:** Ablated prompt = original text with the focus **span deleted verbatim**. Nothing added. No headers, no `###` names, no chat-weight block.

**Requirements:** Align each `prompt_section` to offsets in `prompt` (exact match, then fuzzy: whitespace, quote truncation). Overlaps: define a rule (delete union, or refuse overlapping foci). Glue/whitespace: delete the span only; do not strip unrelated blank lines (unlike current fallback).

**Implementation cost:** Medium. Alignment + tests + UI for failed alignment. Dynamic slots that are **not** in `prompt` need a separate rule (see (c)), not this path.

**Statistical validity:** High for the stated estimand (effect of removing that text from **this** prompt). Baseline and noise already use that prompt; arms become matched except for the deletion.

**Noise floor:** Unchanged in method; it becomes a valid control for the ablation arm. Same temperature / sample count still apply.

**Limitations:** If foci are not true spans, you cannot ablate them this way without lying. Empty remaining document (delete everything) is a real intervention, unlike today’s silent no-op.

### (b) Run baseline through the same reconstruction pipeline

**Intervention:** Baseline and all noise samples use `build_prompt_with_dynamic_foci` on **all** foci (same `weight=1.0`, same `chat_weight`). Ablation drops one focus and calls the same function.

**Implementation cost:** Low. One helper; pass reconstructed-full into the existing sample loop. Still fix the placeholder overwrite (139) or (b) copies that bug into the control arm (better than one-sided, still wrong for dynamic chat).

**Statistical validity:** Medium at best. Constant scaffold (shared `## Primary Instructions`) can cancel in a difference-in-differences sense **only if** effects are additive in embedding space — they are not guaranteed to be. Scaffold **still changes with which focus is removed** (one fewer `###` heading and section). Estimand becomes “omit a block from a reconstructed agent prompt,” **not** “remove a span from the user’s prompt.” For a tool that attributes the **user’s** prompt, that is a different question.

**Noise floor:** Must be recomputed on the **fully reconstructed** prompt. Using original-prompt noise with reconstructed baseline+ablation would still mismatch. Reconstructing noise but not pair baseline (batch) would leave batch inconsistent.

**Does not fix:** last-focus no-op; chat-weight still adding chat when “ablating chat”; paraphrase `prompt_section`s.

### (c) Matched-scaffold control

**Intervention:** For each focus *i*, **treatment** = reconstructed remaining foci (current ablated prompt). **Control** = identical template (same headers, same `###` names for remaining foci, same chat/RAG slots) **plus** focus *i*’s content in a fixed slot — or a length-matched **shuffled / noise string** in that slot if the goal is to isolate semantic content vs structure.

A minimal matched pair:

- Control: builder(all foci)  
- Treatment: builder(all except *i*)

That is (b). A stronger control holds the **outline constant** (every `###` heading remains) and only zeros or scrambles the body of *i*.

**Implementation cost:** High. Need a control prompt per focus, extra LLM + embedding calls (doubles ablation compute), and a clear estimand in the UI.

**Statistical validity:** High **if** the scientific object is the reconstructed agent prompt (product: “which focus in the assembled agent matters?”). For “which span in the user’s pasted prompt matters?”, this answers the wrong question unless the user’s prompt *is* that template.

**Noise floor:** Draw repeats from the **control** prompt for that comparison (per-focus controls ⇒ per-focus or pooled reconstructed-full noise). Do not use original-prompt noise.

---

## 6. Recommendation (causal validity, not convenience)

**Recommend (a) strict subtractive ablation as the primary estimator** for FocalPrompt’s published claim.

The claim is about **foci as parts of the user’s prompt**, compared to **noise from that same prompt**. Identification requires: (1) the only systematic difference between baseline and ablated inputs is absence of that span; (2) the noise distribution is from the same input family as both arms. Today (1) and (2) fail. (a) restores both without assuming embeddings subtract template effects.

**(b) is not sufficient** to rescue the current claim. It is a cheap bias reduction for an **agent-reconstruction** estimand and still leaves focus-dependent headings, the chat-weight bug, and a changed object of inference. Use (b) only as an interim guardrail if reconstruction must stay for dynamic fills, and **recompute noise on the reconstructed-full prompt** — and say in the UI that scores are for the assembled agent, not the raw prompt.

**(c)** is the right design **for dynamic slots** that do not exist as verbatim spans (chat/RAG injected at runtime). Those foci were never subtractive in the original string. For them, a matched-scaffold or slot-empty vs slot-filled contrast is the honest experiment. Mixing (c) for dynamic foci with (a) for verified static spans is coherent; using the agent template for **all** foci is not.

**Do not** treat the dead `replace(prompt_section)` fallback as (a): it strips blank lines and never runs. Implementing (a) needs span alignment, persistence of `ablated_prompt` in results, and noise remaining on the original prompt.

Until then, influence scores and `is_significant` vs `noise_threshold` should not be described as isolating focus deletion from reconstruction artefacts.
