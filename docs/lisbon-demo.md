# LisbonAI recorded experiment replay

Launch `/demo/lisbon` directly, or choose **LisbonAI demo** in the lab header. The `/experiments` index and hosted landing page show the prominent **The pup at the cat-only clinic** card. Launch links open a separate tab; no active lab data is restored, overwritten, persisted, or modified by the replay. Existing canonical experiment URLs still work.

## Presenting

Wait for the first problem view: the complete workspace has then been loaded, checksum-verified, parsed, and frozen. All subsequent navigation, source inspection, and workspace download work without a network connection or API key. This guarantees offline operation of the loaded page, not an offline browser refresh or cold launch.

Use **Next**, **Previous**, right/left arrows, or Space. There are eight conceptual sections and 15 deterministic states, including each of four order-sweep positions and each stage of Jev composition. No timed autoplay, random sampling, or animation delays block the controls. Reset restores the first state and default featured samples. Escape closes an open detail panel first, then exits presentation mode to a local paused screen. Resume preserves the position; Reset starts over. Fullscreen is optional. Reduced-motion preferences disable animation.

Sample buttons show exact stored responses. **Inspect** opens the decoded `suggestedMessage`, the exact raw exported output, sample index, source path, and any stored judgment. Decoding JSON is the only display transformation: response wording, literal escape sequences, and placeholders remain unchanged. Source data exposes the full original scenario, message roles, output contract, and a byte-identical workspace download. Self-reports and embedding statistics are secondary disclosures.

Projector target sizes are 1920×1080 and 1280×720, without page or featured-response scrolling in the main walkthrough. Narrow screens use a stacked, scrollable layout.

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

- `routes/demo_routes.py`: isolated page and allowlisted fixture routes. Serves the original export with HTTP gzip (about 392 KB transferred) to stay below serverless response-size limits. The browser receives the complete unchanged JSON.
- `static/js/workspace_format.js`: existing workspace validation/v1 migration extracted for shared use by normal imports and the replay. It has no DOM or network effects.
- `static/js/demo_definition.js`: title, eight conceptual steps, focus names, featured sample indices, fixture checksum, and editorial per-sample labels. No copied prompts or outputs.
- `static/js/demo_data.js`: pure immutable adapters and deterministic navigation. Reads normal workspace fields (`focus_workflow`, `single_ablation`, `singleton_experiment`, `focus_order`, `jev_experiment`). Missing optional experiments are skipped.
- `static/js/demo_mode.js`: sparse presentation views, keyboard controls, detail panels, preload/checksum verification, and optional comparison loading. It calls no model or embedding endpoints.
- `templates/demo.html`, `static/css/demo.css`: separate stage layout and responsive styles; no third-party scripts or fonts.
- `templates/_demo_card.html`: shared entry card. Normal lab workflows and old direct experiment routes remain available.

## Adding a later GPT-5.6 comparison

1. Add the unmodified workspace export under `examples/demos/lisbon/` and calculate its SHA-256.
2. Add its file to `FIXTURES['lisbon']` in `routes/demo_routes.py`, using a new fixture ID.
3. Add a descriptor to `comparisonWorkspaces` in `demo_definition.js`:

```js
{
    id: 'gpt56',
    modelLabel: 'GPT-5.6 Sol',
    filename: 'your-export.json',
    url: '/demo/lisbon/workspaces/gpt56.json',
    sha256: 'the-actual-file-hash',
    presentation: {
        keyFoci: {booking: 'Appointment booking', cat: 'Cat only'},
        featured: {baseline: 0},
        annotations: {} // Add independently reviewed labels only for this export, if needed.
    }
}
```

The loader preloads all provided workspaces before the stage becomes ready. An optional comparison that fails loading/validation is omitted and reported in Source data. A comparison view is inserted before the ending for each loaded comparison: it shows each model's recorded baseline and exposes the exact focus wording and original roles. No GPT-4o mini editorial annotations are inherited by the second fixture. This avoids relabelling a strengthened system/developer instruction as if only the model changed. More elaborate comparison graphics can use the same independently prepared view data without restructuring the walkthrough.

To replace the primary fixture, update its descriptor/checksum and independently review the editorial labels/featured samples. Experimental words and outputs must stay in the workspace, not in the definition. A checksum mismatch stops replay before presentation.

## Verification

```sh
.venv/bin/python -m pytest -q
node --check static/js/demo_mode.js
node --check static/js/demo_data.js
```

Browser path (requires Playwright and a local FocalPrompt server):

```sh
PLAYWRIGHT_MODULE=/path/to/playwright node tests/browser/lisbon_demo.cjs
```

The browser test covers launch from the card, offline navigation through every state, exact rendered output text, source inspection, keyboard next/previous/reset/exit, fixture immutability, no inference calls, and projector-size clipping. The unit tests protect shared import validation/migration and the original workspace checksum, condition sample counts, roles, spans, actual orders, optional-result handling, and serverless gzip response.
