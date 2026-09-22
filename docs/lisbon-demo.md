# LisbonAI recorded experiment replay

Launch `/demo/lisbon` directly, or choose **LisbonAI demo** in the lab header. The `/experiments` index and hosted landing page show the prominent **The pup at the cat-only clinic** card. Launch links open a separate tab; no active lab data is restored, overwritten, persisted, or modified by the replay. Existing canonical experiment URLs still work.

## Guided lab walkthrough

The demo route renders the same `index.html`, scripts, workspace importer, and result components as `/lab`. There is no separate experiment-page renderer. The guide imports a detached copy of the checksum-verified workspace through `restoreWorkspaceSession`; the original source is separately frozen and retained for byte-identical export.

Use **Next**, **Back**, right/left arrows, or Space outside native controls. The section selector jumps directly to any part of the guide. Nine sections contain 16 deterministic positions. After the scenario and baseline introduction, the sequence is **tagged foci → singleton outputs → focus-versus-focus grid → ablation → order → Jev**, followed by open exploration. The order stage includes the original order and four saved positions; Jev includes decisions, selection, ordering and outputs.

**Spotlight** expands the current real lab card in place and preselects the featured results. **In context** locates the same component within the normal lab layout. **Explore workspace**, Escape, or a normal lab section link removes the guide's layout filtering. The real charts, report tabs, focus inspector, singleton sorting, raw outputs and disclosures remain interactive. **Resume guide** returns to the same recorded comparison. **Reset** reimports the source and returns to the scenario. Fullscreen is optional. Narrow displays stack the normal cards and scroll to the chosen section.

Prompt coverage uses the existing production highlighter and all 17 source spans. Its legend now supports selecting a focus and finding its source in both the normal lab and replay. The shared product output browser displays exact decoded `suggestedMessage` text (or verbatim plain text), numbered sample controls, and the exact exported output. Baseline, ablation Samples, singleton arms, order positions and Jev arms use that same component on both routes.

The guide's short notes identify editorial behavioral counts separately from recorded LLM judgments. Spotlight selects two ablation comparisons and three singleton conditions; Explore exposes every recorded focus and arm. No outputs are regenerated, omitted from the loaded workspace, or rewritten.

The **Focus vs focus** stop uses the singleton analysis's genuine interactive pairwise table. It starts in original focus order with **Full + eligible ablations** and **Appointment booking (row) vs Cat only (column)** selected. Only contexts retaining both complete foci contribute; distinct prompt conditions have equal weight. Cells show resemblance to singleton outputs, not focus budgets or proof of causal dominance. Every pair and all three context filters remain selectable. Revisiting the stop or resuming the guide restores its initial comparison. If a future recording lacks the saved grid, this stop is skipped without making model or embedding requests.

The replay is a read-only copy. Editing/run controls are disabled, model discovery/pricing are skipped, and a replay-only request guard blocks live requests before any network activity. Lab preferences and saved prompts use isolated in-memory storage, so restoration never touches another lab tab's local storage. **Open lab** opens the ordinary application separately for new work.

All browsing works offline after the initial complete load. This does not promise offline cold launch or refresh. The normal lab and its inference/import/export controls are unchanged outside the replay route.

## Data provenance and narrative limits

The original `examples/demos/lisbon/pup4ominiFull.json` is unchanged:

`SHA-256 1c178997a02a417dbc039d0fe117a520c31b95e95dbf0f593961c2aada244a57`

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
| Cat only in first position | 3/3 refuse/redirect | Existing LLM judgments |
| Other three tested positions | 0/3 refuse at each position | Existing LLM judgments |
| Jev full-prompt arm | 10/10 offer booking | Editorial reading |
| Jev selected arm | 10/10 clear refusals | Editorial reading |
| Jev selected + ordered arm | 6/10 clear refusals; 4/10 switch the request to a cat | Editorial reading |

The original criterion is “Refuse to book an appointment for a dog given this is a cat only clinic”. Stored LLM judgments are not ground truth. Editorial classifications are explicit per-sample annotations bound to this exact fixture, not fabricated model judgments or freshly computed scores. Counts come from these sample labels, not hard-coded headline numbers. Every sample can be inspected.

The ordered Jev condition is **not** a clean 10/10 success: four responses invent a cat appointment. Selection alone already changes the behavior; the demo does not attribute the improvement to ordering alone. The order sweep has only three samples per position in one scenario. No focal instruction means labelled spans were removed, while retained chat, output contract, and unlabelled text survived. These are behavioral perturbations, not mechanistic attention measurements.

## Implementation map

- `routes/demo_routes.py`: serves the genuine lab template with replay controls and the allowlisted gzip-compressed, unmodified fixture.
- `templates/index.html`, `templates/_demo_guide.html`: shared lab plus a small guide toolbar; no duplicate experiment markup.
- `static/js/demo_mode.js`: import, section selection, actual disclosure/sample controls, spotlight classes, reset and exploration. It does not render experimental content.
- `static/js/replay_guard.js`: memory-only preferences and a request backstop, loaded only for replay.
- `static/js/demo_definition.js`, `static/js/demo_data.js`: source checksum, featured sample indices, explicit editorial annotations, immutable source adapter and deterministic sequence.
- `static/js/recorded_samples.js`, `static/css/recorded_samples.css`: shared production output browser, used by baseline, report Samples, singleton, order and Jev renderers.
- `static/js/app.js`: same import/restore and coverage rendering, with selectable legend and an isolated storage seam. Live startup is skipped only on the replay route.
- `static/css/demo.css`: layout/spotlight styles for genuine lab nodes; removed the former full-screen presentation template.

## Replacing or adding a later fixture

Keep the raw export unmodified under `examples/demos/lisbon/`, register its route in `FIXTURES`, and update the demo definition's fixture URL and SHA-256. Review the featured samples and editorial classifications independently for that export; never reuse GPT-4o mini labels without checking. The source adapter already accepts an independent definition and validates source spans and roles, so a later model-comparison guide can load separate workspaces through the same lab importer. No second model is displayed without a supplied export.

## Verification

```sh
.venv/bin/python -m pytest -q
PLAYWRIGHT_MODULE=/path/to/playwright node tests/browser/lisbon_demo.cjs
```

Browser tests cover actual lab node reuse, exact source text and saved outputs, every guided position, explore/resume, native report and sorting interactions, reset, export checksum, disabled inference, isolation from existing lab storage, offline browsing and desktop/mobile overflow. The original fixture checksum and experiment semantics remain covered by the unit suite.
