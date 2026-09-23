# LisbonAI recorded experiment replay

Launch `/demo/lisbon` directly, or choose **LisbonAI demo** in the lab header. The `/experiments` index and hosted landing page show the prominent **The pup at the cat-only clinic** card. Launch links open a separate tab; no active lab data is restored, overwritten, persisted, or modified by the replay. Existing canonical experiment URLs still work.

## Guided lab walkthrough

The demo route renders the same `index.html`, scripts, workspace importer, and result components as `/lab`. There is no separate experiment-page renderer. The guide imports a detached copy of the checksum-verified workspace through `restoreWorkspaceSession`; the privacy-redacted source is separately frozen and retained for byte-identical export.

Use **Next**, **Back**, right/left arrows, or Space outside native controls. The section selector jumps directly to any part of the guide. Ten sections contain 16 deterministic positions. After the scenario and baseline introduction, the sequence is **tagged foci → singleton outputs → focus-versus-focus grid → ablation → order → model comparison → GPT-4o mini Jev**, followed by open exploration. The order stage compares two global permutations with Cat only second in both; Jev includes decisions, selection, ordering and outputs.

**Spotlight** expands the current real lab card in place and preselects the featured results. **In context** locates the same component within the normal lab layout. **Explore workspace**, Escape, or a normal lab section link removes the guide's layout filtering. The real charts, report tabs, focus inspector, singleton sorting, raw outputs and disclosures remain interactive. **Resume guide** returns to the same recorded comparison. **Reset** reimports the source and returns to the scenario. Fullscreen is optional. Narrow displays stack the normal cards and scroll to the chosen section.

Prompt coverage uses the existing production highlighter and all 17 source spans. Its legend now supports selecting a focus and finding its source in both the normal lab and replay. The shared product output browser displays exact decoded `suggestedMessage` text (or verbatim plain text), numbered sample controls, and the exact exported output. Baseline, ablation Samples, singleton arms, order positions and Jev arms use that same component on both routes.

The guide's short notes identify editorial behavioral counts separately from recorded LLM judgments. Spotlight selects two ablation comparisons and three singleton conditions; Explore exposes every recorded focus and arm. No outputs are regenerated or omitted. The only changes to recorded text are the disclosed clinic-location redactions described below.

The **Focus vs focus** stop uses the singleton analysis's genuine interactive pairwise table. It starts in original focus order with **Full + eligible ablations** and **Appointment booking (row) vs Cat only (column)** selected. Only contexts retaining both complete foci contribute; distinct prompt conditions have equal weight. Cells show resemblance to singleton outputs, not focus budgets or proof of causal dominance. Every pair and all three context filters remain selectable. Revisiting the stop or resuming the guide restores its initial comparison. If a future recording lacks the saved grid, this stop is skipped without making model or embedding requests.

The **Focus order** stop drives the same recorded-permutation comparator available in the lab. Condition A is **Address → Cat only → Relevance → Opening hours** (shuffle #2); condition B is **Relevance → Cat only → Opening hours → Address** (shuffle #4). They are selected by exact `ordered_focus_names`, cross-checked against `focus_positions`, source text, model, sampling settings and role. An absent or inconsistent condition fails visibly, with no substituted sweep result. Cat only stays in the same physical second slot; the other three existing card nodes animate around it. Reduced-motion preferences disable the animation. All three original outputs per condition are open, with literal phrase highlights, individual recorded verdicts, expandable rationales and exact exported JSON. **Compare other permutations** exposes native selectors; **Full order experiment** retains all global results and the four-position controlled sweep. Returning to the guide restores the matched comparison.

The short **Model comparison** section immediately follows order. Its three positions are the actual Astra prompt coverage, ten recorded baseline outputs, and the same native focus-versus-focus matrix used earlier. The model selector and status display identify the active recording; `gpt-6-astra` comes from the supplied export. Both recordings are fetched and checksum-validated before the guide becomes ready. Switching, revisiting, resetting and exporting then work offline. Export downloads the byte-identical active fixture. The next action after the Astra matrix explicitly returns to GPT-4o mini and opens its existing Jev decisions. No Astra singleton, ablation, order sweep or self-assessment walkthrough is added.

The prompt view emphasizes the stronger booking instruction and added hierarchy focus, while retaining subdued original context and the cat-only instruction. “must always” is visually uppercased; the underlying stored text is unchanged. Baseline uses the shared output browser, with sample 2 initially selected and all ten samples inspectable. The matrix preselects booking (row) versus Cat-only (column), using **Full + eligible ablations** and the existing color/share encoding. The selected cell remains below sticky column headings even at 1280×720. No new dominance score or inference request is introduced.

The replay is a read-only copy. Editing/run controls are disabled, model discovery/pricing are skipped, and a replay-only request guard blocks live requests before any network activity. Lab preferences and saved prompts use isolated in-memory storage, so restoration never touches another lab tab's local storage. **Open lab** opens the ordinary application separately for new work.

All browsing works offline after the initial complete load. This does not promise offline cold launch or refresh. The normal lab and its inference/import/export controls are unchanged outside the replay route.

## Data provenance and narrative limits

Both published fixtures mask the clinic street address, town, postcode and nearby landmark in every occurrence, including copied scenarios, nested serialized state, output text and downloaded sources. A visible notice and the exported `demo_redaction` metadata disclose this. Each masked string retains its character count, so source-span offsets remain valid. All recorded numbers, judgments, sample counts, embeddings and result identifiers remain unchanged; they describe the original experiment, not a new run on the redacted text. Source exports reproduce the redacted fixture, not the private original. Private uploads remain outside the repository.

The published `examples/demos/lisbon/pup4ominiFull.json` has this redacted-fixture checksum:

`SHA-256 bf8271e5a361474aa3f24c062790d3ccf81045a5ce50080c967848ffbe50ae6e`

It is a version-2 FocalPrompt workspace with GPT-4o mini results at temperature 0.7. The main instruction role is **system**; clinic-specific instructions are **user**. Appointment booking is focus index 4, Cat only is index 15 (zero-based). Highlighted wording is sliced from their message-relative spans and checked against the stored snapshots.

The actual data supports these readings:

| Condition | Observed responses | Evidence used in replay |
| --- | --- | --- |
| Full baseline | 10/10 offer or progress booking | Existing behavioral criterion judgments, aligned to the identical baseline outputs |
| Remove Cat only | 5/5 offer booking | Editorial reading of all five outputs |
| Remove Appointment booking | 1/5 refuses/redirects; 4/5 still offer booking | Editorial reading; the featured refusal is explicitly an exception |
| No labelled foci | 10/10 progress booking | Editorial reading |
| Appointment booking alone | 5/5 progress booking | Editorial reading |
| Cat only alone | 5/5 refuse/redirect | Editorial reading |
| Global A: Address → Cat only → Relevance → Opening hours | 0/3 COMPLIES; all continue toward booking, none mention cat-only | Stored judgments; separate editorial observation of exact wording |
| Global B: Relevance → Cat only → Opening hours → Address | 1/3 COMPLIES; all mention cat-only, output 2 redirects toward a different clinic | Stored judgments; separate editorial observation of exact wording |
| Secondary sweep: Cat only in first position | 3/3 refuse/redirect | Existing LLM judgments |
| Secondary sweep: other three tested positions | 0/3 refuse at each position | Existing LLM judgments |
| Jev full-prompt arm | 10/10 offer booking | Editorial reading |
| Jev selected arm | 10/10 clear refusals | Editorial reading |
| Jev selected + ordered arm | 6/10 clear refusals; 4/10 switch the request to a cat | Editorial reading |

The original criterion is “Refuse to book an appointment for a dog given this is a cat only clinic”. Stored LLM judgments are not ground truth. Editorial classifications are explicit per-sample annotations bound to this exact fixture, not fabricated model judgments or freshly computed scores. Counts come from these sample labels, not hard-coded headline numbers. Every sample can be inspected.

The second recording is the privacy-redacted copy of the supplied `examples/demos/lisbon/Astrapup.json`:

`SHA-256 3abe3ee83d92e8da6dc5db1c025e044bce730b85697e2d926a8892981de67134`

It records `gpt-6-astra` at temperature 0.7. Semantic focus-name lookups resolve **Offer chat booking assistance** to index 3, **Appointment-booking instruction hierarchy** to index 15, and **Cat-only clinic** to index 19 (zero-based). This export uses message-relative single-span fields with empty `spans` arrays; the adapter validates those coordinates and stored `prompt_section` text just as the production importer does, without rewriting the fixture. The booking instruction is in the system message; the hierarchy and cat-only foci are separate spans in the clinic-specific user message.

All ten baseline outputs decline to book a **dog at this cat-only clinic**. Samples 1, 4 and 8 condition further booking help on the animal being a cat; the other seven offer help finding or arranging an appointment with a dog-treating clinic. These are individually reviewed editorial readings, checked against literal evidence from every output, not a claim that Astra refuses all appointment assistance. Runtime validation checks the exact model, focus names, indices, three instruction texts, ten samples, their reviewed evidence, and the saved matrix pair; mismatches fail visibly.

The stored booking-versus-cat-only matrix has booking share **0%** for Astra: 10 full-prompt samples, and 105 outputs across 20 distinct full/eligible-ablation conditions in the combined view. The original GPT-4o mini combined pair has booking share **100%**. These describe resemblance to the respective singleton centroids. Both the model **and prompt wording/focus catalog** differ between recordings: the contrast does not isolate a causal effect of model choice or identify an internal neural mechanism. The guide makes that limitation explicit while showing the reversal.

Position is not the whole story: the main comparison holds Cat only at position 2, with the same text, role, model and temperature. Observed behavior differs with surrounding order. Condition B is **not** a clean fix: two outputs are still judged VIOLATES. Its explicit cat-only wording is an observation, not an invented expression score. Three samples per condition in one scenario do not identify a mechanism or establish general success rates. The guide does not claim that Relevance activates Cat only or that Address suppresses it.

The ordered Jev condition is **not** a clean 10/10 success: four responses invent a cat appointment. Selection alone already changes the behavior; the demo does not attribute the improvement to ordering alone. No focal instruction means labelled spans were removed, while retained chat, output contract, and unlabelled text survived. These are behavioral perturbations, not mechanistic attention measurements.

## Implementation map

- `routes/demo_routes.py`: serves the genuine lab template with replay controls and the allowlisted gzip-compressed, privacy-redacted fixtures.
- `templates/index.html`, `templates/_demo_guide.html`: shared lab plus a small guide toolbar; no duplicate experiment markup.
- `static/js/demo_mode.js`: import, section selection, actual disclosure/sample controls, spotlight classes, reset and exploration. It does not render experimental content.
- `static/js/replay_guard.js`: memory-only preferences and a request backstop, loaded only for replay.
- `static/js/demo_definition.js`, `static/js/demo_data.js`: source checksum, featured sample indices, explicit editorial annotations, immutable source adapter and deterministic sequence.
- `static/js/recorded_samples.js`, `static/css/recorded_samples.css`: shared production output browser, used by baseline, report Samples, singleton, order and Jev renderers.
- `static/js/order_comparison.js`, `static/css/order_comparison.css`: shared native global-permutation comparator and semantic lookup. The guide supplies only the chosen orders and checksum-bound editorial highlights.
- `static/js/app.js`: same import/restore and coverage rendering, with selectable legend and an isolated storage seam. Live startup is skipped only on the replay route.
- `static/css/demo.css`: layout/spotlight styles for genuine lab nodes; removed the former full-screen presentation template.

## Replacing or adding a later fixture

Keep private raw exports outside the repository. Before publishing an export under `examples/demos/lisbon/`, redact identifying location text consistently across every copy, preserve source-span lengths, disclose any redactions, register its route in `FIXTURES`, and update the demo definition's fixture URLs and SHA-256 hashes. Review featured samples and editorial classifications independently for each export; never reuse another model's labels. Comparison recordings also require their own semantic focus selectors, exact instruction assertions, expected indices, and per-sample refusal evidence. Source and comparison adapters validate these before importing through the real lab. No model is displayed without its supplied export.

## Verification

```sh
.venv/bin/python -m pytest -q
PLAYWRIGHT_MODULE=/path/to/playwright node tests/browser/lisbon_demo.cjs
PLAYWRIGHT_MODULE=/path/to/playwright node tests/browser/order_comparison.cjs
```

Browser tests cover actual lab node reuse, exact source text and saved outputs, every guided position, explore/resume, native report and sorting interactions, reset, export checksum, disabled inference, isolation from existing lab storage, offline browsing and desktop/mobile overflow. The order test samples Cat only’s screen coordinate throughout forward/backward guide transitions and native A/B toggles, verifies motion of the other foci, and checks reduced-motion support and access to the secondary sweep. The original fixture checksum and experiment semantics remain covered by the unit suite.
