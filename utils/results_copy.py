#!/usr/bin/env python3
"""
User-facing copy and HTML rendering for ablation / permutation results.

FocalPrompt measures behavioural sensitivity, not usefulness. This module is
the source of truth for every results-view string. The browser reads the same
payload via Flask injection; do not duplicate prose in app.js.
"""

from __future__ import annotations

import html
import math
from typing import Any, Dict, List, Mapping, Optional, Sequence

from utils.permutation_test import (
    DEFAULT_ALPHA,
    DEFAULT_N_PERMUTATIONS,
    min_achievable_pvalue,
    design_test_type,
)
from utils.experiment_config import format_run_header

# ---------------------------------------------------------------------------
# Canonical copy. Tests assert these strings character-for-character.
# ---------------------------------------------------------------------------

DEFINITION = (
    "FocalPrompt detects whether removing each focus shifts the model's "
    "behaviour in semantic embedding space. It does not measure correctness, "
    "quality, or safety, and it does not tell you what to delete."
)

VERDICT_SIGNIFICANT = (
    "Removing this focus measurably changed the model's behaviour."
)

VERDICT_NOT_SIGNIFICANT = (
    "No behavioural change detected beyond sampling variation at this sample size."
)

NON_SIGNIFICANT_CAUTION = (
    "Undetected here does not mean removable: short structural instructions "
    "(output formats, escalation rules, guardrails) can matter greatly while "
    "barely shifting output embeddings."
)

EXCLUDED_UNVERIFIED = (
    "Couldn't uniquely ground this focus to an exact span of your prompt, so it "
    "wasn't tested. Repair the span manually or re-detect with a clearer "
    "evidence quote."
)

EXCLUDED_DYNAMIC_SLOT = (
    "This focus is a runtime slot (chat, retrieved context), not text in your "
    "prompt, so subtractive testing doesn't apply in this version."
)

EXCLUDED_OVERLAP = (
    "This focus overlaps another focus's text, so removing it alone isn't well "
    "defined. Refine the foci to separate them."
)

PROMPT_EMPTY_NOTE = (
    "Ablating this focus left an empty prompt. Results reflect the model with "
    "no instructions at all."
)

NEAR_THRESHOLD_HINT = (
    "Near the threshold. Rerun with more ablated samples to resolve."
)

POWER_BANNER_TEMPLATE = (
    "With {n_baseline} baseline and {n_ablated} ablated samples, the smallest "
    "possible p-value is {min_p}. After correction across {n_foci} foci, real "
    "effects may be undetectable. Increase samples to resolve."
)

METHODS_PANEL_TITLE = "How this works"

METHODS_PANEL = """FocalPrompt tests whether deleting a focus from your prompt changes the model's behaviour, as seen in semantic embedding space. It does not score whether that focus is useful, correct, or safe, and a non-significant result is not a licence to delete the text.

Repeated sampling of both arms. The original prompt is sampled several times (the baseline). For each focus that can be located as a contiguous span in that prompt, the span is deleted and the remaining prompt is sampled several times (the ablated arm). Both arms use the same model and the same temperature. Temperature is kept above zero so repeated samples of the same prompt are allowed to vary.

The statistic. Each sample is embedded. The observed statistic is the cosine distance between the centroid (mean vector) of the baseline embeddings and the centroid of the ablated embeddings. A larger distance means the two groups of outputs sit further apart. That distance is a shift in embedding space, not an importance score, and it is only meaningful when compared with the permutation null for the same samples.

The permutation null. Under the null, deleting the focus does not change the output distribution, so the baseline and ablated embeddings are interchangeable. The test reassigns the pooled embeddings into two groups of the original sizes and recomputes the distance. When the number of distinct assignments is small enough, every assignment is enumerated (an exact permutation test). Otherwise a Monte Carlo sample of assignments is used. The p-value is the share of those assignments whose distance is at least as large as the one you observed: how often a shift this large would appear if the group labels were meaningless.

What the p-value means. A small p-value means the observed shift would be unusual if deletion did nothing. It is not a measure of how much the focus matters, and it is not a recommendation to keep or drop the text.

Benjamini–Hochberg correction. Each experiment tests several foci at once. Raw p-values among the foci that were actually tested are converted to q-values with the Benjamini–Hochberg procedure, which controls the false discovery rate. q < 0.05 (the default α) means this focus is called significant after that correction: among the foci called significant, the expected fraction of false calls is at most 5%. It does not mean the remaining foci have no effect.

Known limitations. Embedding blindness: short structural instructions — output formats, escalation rules, guardrails — can change what the model does while barely moving output embeddings. A non-significant result is a failure to detect a shift at this sample size, not evidence that the text is inert. Leave-one-out conditionality: each focus is deleted while the rest of the prompt stays. Redundant instructions can mask each other (deleting one copy may not shift behaviour if another remains). Interacting instructions can be misattributed (the measured shift is the effect of deleting this span in this surrounding prompt, not an isolated effect of the idea). Locality: results hold for this model, this temperature, and this surrounding prompt only. They do not automatically generalise to other models, decoding settings, or prompt revisions."""


MULTI_LENS_EXPLAINER = (
    "Embedding similarity captures semantic change. Qualitative review can detect "
    "structural, procedural, stylistic, or compliance changes that embeddings may miss. "
    "The LLM judge is not ground truth; it is an independent difference lens."
)

LENS_SEMANTIC_TITLE = "Semantic perturbation"
LENS_LLM_TITLE = "LLM behavioral difference"
LENS_HUMAN_TITLE = "Human-observed difference"
REVIEW_BEHAVIORAL_DIFFERENCE = "Review behavioral difference"

SHUFFLE_ROBUSTNESS_TITLE = "Shuffle-order robustness check"
SHUFFLE_ROBUSTNESS_EXPLAINER = (
    "Re-run ablation for this focus only, reassembling the remaining focus spans "
    "in a shuffled order while keeping residual prompt text (including dynamic chat). "
    "Tests whether significance survives a different structural hierarchy. "
    "Reuses your original baseline samples; p-value is uncorrected."
)
SHUFFLE_ROBUSTNESS_BUTTON = "Re-test with shuffled remaining order"
SHUFFLE_ROBUSTNESS_ORDER_UNCHANGED = (
    "Only one remaining focus — order unchanged (same as subtractive content)."
)

BASELINE_STABILITY_TITLE = "Baseline stability / noise"
BASELINE_STABILITY_DISCLAIMER = (
    "Describes dispersion among full-prompt samples only. Not a significance test "
    "and does not replace the permutation results below. Classification uses labeled heuristics."
)
REPORTED_FOCUS_DYNAMICS_TITLE = "Per-sample reported-focus dynamics"
REPORTED_FOCUS_DYNAMICS_DISCLAIMER = (
    "Self-reported focus weights from an LLM judge on each sample — not model attention "
    "weights and not mechanistic interpretability."
)
REPORTED_FOCUS_DYNAMICS_BUTTON = "Run per-sample reported-focus dynamics"

COPY = {
    'DEFINITION': DEFINITION,
    'MULTI_LENS_EXPLAINER': MULTI_LENS_EXPLAINER,
    'LENS_SEMANTIC_TITLE': LENS_SEMANTIC_TITLE,
    'LENS_LLM_TITLE': LENS_LLM_TITLE,
    'LENS_HUMAN_TITLE': LENS_HUMAN_TITLE,
    'REVIEW_BEHAVIORAL_DIFFERENCE': REVIEW_BEHAVIORAL_DIFFERENCE,
    'SHUFFLE_ROBUSTNESS_TITLE': SHUFFLE_ROBUSTNESS_TITLE,
    'SHUFFLE_ROBUSTNESS_EXPLAINER': SHUFFLE_ROBUSTNESS_EXPLAINER,
    'SHUFFLE_ROBUSTNESS_BUTTON': SHUFFLE_ROBUSTNESS_BUTTON,
    'SHUFFLE_ROBUSTNESS_ORDER_UNCHANGED': SHUFFLE_ROBUSTNESS_ORDER_UNCHANGED,
    'BASELINE_STABILITY_TITLE': BASELINE_STABILITY_TITLE,
    'BASELINE_STABILITY_DISCLAIMER': BASELINE_STABILITY_DISCLAIMER,
    'REPORTED_FOCUS_DYNAMICS_TITLE': REPORTED_FOCUS_DYNAMICS_TITLE,
    'REPORTED_FOCUS_DYNAMICS_DISCLAIMER': REPORTED_FOCUS_DYNAMICS_DISCLAIMER,
    'REPORTED_FOCUS_DYNAMICS_BUTTON': REPORTED_FOCUS_DYNAMICS_BUTTON,
    'VERDICT_SIGNIFICANT': VERDICT_SIGNIFICANT,
    'VERDICT_NOT_SIGNIFICANT': VERDICT_NOT_SIGNIFICANT,
    'NON_SIGNIFICANT_CAUTION': NON_SIGNIFICANT_CAUTION,
    'EXCLUDED_UNVERIFIED': EXCLUDED_UNVERIFIED,
    'EXCLUDED_DYNAMIC_SLOT': EXCLUDED_DYNAMIC_SLOT,
    'EXCLUDED_OVERLAP': EXCLUDED_OVERLAP,
    'PROMPT_EMPTY_NOTE': PROMPT_EMPTY_NOTE,
    'NEAR_THRESHOLD_HINT': NEAR_THRESHOLD_HINT,
    'POWER_BANNER_TEMPLATE': POWER_BANNER_TEMPLATE,
    'METHODS_PANEL_TITLE': METHODS_PANEL_TITLE,
    'METHODS_PANEL': METHODS_PANEL,
}


def format_q_value(q_value: Optional[float]) -> str:
    """Compact q for the primary card. Three significant figures."""
    if q_value is None:
        return 'n/a'
    q = float(q_value)
    if math.isnan(q):
        return 'n/a'
    if q == 0:
        return '0'
    return f'{q:.3g}'


def format_effect_size(standardized_effect: Optional[float]) -> str:
    """One decimal place, as specified for the primary card."""
    if standardized_effect is None:
        return 'n/a'
    z = float(standardized_effect)
    if math.isnan(z):
        return 'n/a'
    if math.isinf(z):
        return 'inf'
    return f'{z:.1f}'


def effect_size_band(standardized_effect: Optional[float]) -> Optional[str]:
    """small (< 2), moderate (2–5 inclusive), large (> 5)."""
    if standardized_effect is None:
        return None
    z = float(standardized_effect)
    if math.isnan(z):
        return None
    abs_z = abs(z) if math.isfinite(z) else float('inf')
    if abs_z > 5:
        return 'large'
    if abs_z >= 2:
        return 'moderate'
    return 'small'


def effect_size_qualifier(standardized_effect: Optional[float]) -> Optional[str]:
    """e.g. 'large effect (z = 8.3)'."""
    band = effect_size_band(standardized_effect)
    if band is None:
        return None
    z_txt = format_effect_size(standardized_effect)
    return f'{band} effect (z = {z_txt})'


def significant_stats_line(q_value: Optional[float], standardized_effect: Optional[float]) -> str:
    q_txt = format_q_value(q_value)
    z_txt = format_effect_size(standardized_effect)
    return f'(q = {q_txt}, effect size = {z_txt})'


def not_significant_stats_line(q_value: Optional[float]) -> str:
    return f'(q = {format_q_value(q_value)})'


def format_power_banner(
    n_baseline: int,
    n_ablated: int,
    n_foci: int,
    min_p: Optional[float] = None,
    n_permutations: int = DEFAULT_N_PERMUTATIONS,
) -> str:
    if min_p is None:
        min_p = min_achievable_pvalue(int(n_baseline), int(n_ablated), int(n_permutations))
    return POWER_BANNER_TEMPLATE.format(
        n_baseline=int(n_baseline),
        n_ablated=int(n_ablated),
        min_p=f'{float(min_p):.6g}',
        n_foci=int(n_foci),
    )


def format_overlap_names(overlap_with: Optional[Sequence[Any]]) -> str:
    if not overlap_with:
        return ''
    names = []
    for item in overlap_with:
        if isinstance(item, Mapping):
            name = item.get('focus') or item.get('focus_name') or item.get('name')
            if name:
                names.append(str(name))
        elif item:
            names.append(str(item))
    return '; '.join(names)


def excluded_explanation(focus: Mapping[str, Any]) -> Optional[str]:
    """Plain-language reason a focus was not tested, or None if it was tested."""
    reason = focus.get('reason')
    verified = focus.get('verified')
    attributable = focus.get('attributable')

    if reason == 'dynamic_slot':
        return EXCLUDED_DYNAMIC_SLOT
    if reason == 'overlap':
        names = format_overlap_names(focus.get('overlap_with'))
        if names:
            return f'{EXCLUDED_OVERLAP} Overlaps with: {names}.'
        return EXCLUDED_OVERLAP
    if verified is False or reason == 'unverified':
        return EXCLUDED_UNVERIFIED
    if attributable is False:
        # Unknown exclusion: still explain rather than show a blank or a zero.
        return EXCLUDED_UNVERIFIED
    return None


def is_near_threshold(q_value: Optional[float], alpha: float = DEFAULT_ALPHA) -> bool:
    if q_value is None:
        return False
    q = float(q_value)
    if math.isnan(q):
        return False
    return alpha < q <= (2.0 * alpha)


def _focus_name(item: Mapping[str, Any], fallback: str = 'Untitled focus') -> str:
    return str(item.get('focus') or item.get('focus_name') or fallback)


def _as_score_list(influence_scores: Any) -> List[Mapping[str, Any]]:
    if not influence_scores:
        return []
    if isinstance(influence_scores, Mapping):
        rows = []
        for name, payload in influence_scores.items():
            row = dict(payload) if isinstance(payload, Mapping) else {'value': payload}
            row.setdefault('focus', name)
            rows.append(row)
        return rows
    return list(influence_scores)


def collect_focus_records(data: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Merge ablation_results with influence_scores, preserving focus order."""
    ablation = list(data.get('ablation_results') or [])
    scores = _as_score_list(data.get('influence_scores'))
    scores_by_name = {_focus_name(s, str(i)): dict(s) for i, s in enumerate(scores)}
    records: List[Dict[str, Any]] = []
    seen = set()
    for i, row in enumerate(ablation):
        name = _focus_name(row, f'Focus {i + 1}')
        merged = dict(row)
        extra = scores_by_name.get(name)
        if extra:
            merged.update(extra)
            merged['focus'] = name
        records.append(merged)
        seen.add(name)
    for i, score in enumerate(scores):
        name = _focus_name(score, f'Focus {i + 1}')
        if name not in seen:
            records.append(dict(score))
            seen.add(name)
    return records


def n_foci_tested(data: Mapping[str, Any]) -> int:
    scores = _as_score_list(data.get('influence_scores'))
    if scores:
        return len(scores)
    return sum(1 for r in collect_focus_records(data) if r.get('attributable') and excluded_explanation(r) is None)


def should_show_power_banner(data: Mapping[str, Any]) -> bool:
    return bool(data.get('power_warning'))


def _esc(text: Any) -> str:
    # Body text: keep apostrophes so user-facing copy matches the spec byte-for-byte in HTML.
    return html.escape('' if text is None else str(text), quote=False)


def _p_txt(value: Any) -> str:
    if value is None:
        return 'n/a'
    try:
        return f'{float(value):.6g}'
    except (TypeError, ValueError):
        return _esc(value)


def _null_deciles_html(deciles: Any) -> str:
    if not deciles:
        return '<p>No null deciles reported.</p>'
    if isinstance(deciles, Mapping):
        items = sorted(deciles.items(), key=lambda kv: float(kv[0]) if str(kv[0]).replace('.', '', 1).isdigit() else str(kv[0]))
        rows = ''.join(
            f'<tr><th>{_esc(k)}</th><td>{_p_txt(v)}</td></tr>' for k, v in items
        )
        return f'<table class="null-deciles"><tbody>{rows}</tbody></table>'
    return f'<pre>{_esc(deciles)}</pre>'


def render_statistical_detail(focus: Mapping[str, Any]) -> str:
    t_obs = focus.get('t_obs', focus.get('influence'))
    parts = [
        '<details class="focus-verdict-details">',
        '<summary>Statistical detail</summary>',
        '<dl class="focus-stat-list">',
        f'<dt>t_obs</dt><dd>{_p_txt(t_obs)}</dd>',
        f'<dt>p_value</dt><dd>{_p_txt(focus.get("p_value"))}</dd>',
        f'<dt>q_value</dt><dd>{_p_txt(focus.get("q_value"))}</dd>',
        '</dl>',
        '<p class="focus-stat-label">Null deciles</p>',
        _null_deciles_html(focus.get('null_deciles')),
        '</details>',
    ]
    return ''.join(parts)


def _difference_band(score) -> str:
    try:
        s = int(score)
    except (TypeError, ValueError):
        return 'not assessed'
    if s <= 0:
        return 'None'
    if s <= 2:
        return 'Weak'
    if s <= 3:
        return 'Moderate'
    return 'Strong'


def render_evidence_lenses(focus: Mapping[str, Any]) -> str:
    """Render independent semantic / LLM / human difference lenses (not quality)."""
    sem = focus.get('semantic_perturbation') or {}
    llm = focus.get('llm_behavioral_difference') or {}
    hum = focus.get('human_behavioral_difference') or {}
    rec = focus.get('review_recommendation') or {}

    sig = sem.get('is_significant', focus.get('is_significant'))
    q = sem.get('q_value', focus.get('q_value'))
    q_txt = format_q_value(q)
    if sig is True:
        sem_line = f'Detectable semantic perturbation (q = {q_txt})'
    elif sig is False:
        sem_line = f'No detectable semantic perturbation (q = {q_txt})'
    else:
        sem_line = 'Semantic perturbation not assessed'

    llm_status = llm.get('status') or 'not_run'
    if llm_status == 'complete':
        band = _difference_band(llm.get('overall_difference_score'))
        dims = llm.get('dimensions') or {}
        dim_bits = []
        for key in ('structure_format', 'instruction_compliance', 'content'):
            if key in dims and dims[key]:
                dim_bits.append(f"{key.replace('_', ' ')}: {dims[key]}/5")
        llm_line = band
        if dim_bits:
            llm_line += ' — ' + '; '.join(dim_bits)
        if llm.get('summary'):
            llm_line += '. ' + str(llm.get('summary'))
        llm_line = _esc(llm_line)
    elif llm_status == 'failed':
        llm_line = _esc(f"Failed: {llm.get('error') or 'judge error'}")
    else:
        llm_line = 'Not run'

    hum_status = hum.get('status') or 'not_run'
    if hum_status == 'complete':
        mat = hum.get('material_behavioral_difference')
        band = _difference_band(hum.get('overall_difference_score'))
        if mat is True:
            hum_line = f'Difference confirmed ({band})'
        elif mat is False:
            hum_line = f'No material difference ({band})'
        else:
            hum_line = f'Uncertain ({band})'
        if hum.get('notes'):
            hum_line += '. ' + str(hum.get('notes'))
        hum_line = _esc(hum_line)
    elif hum_status == 'pending':
        hum_line = 'Pending human review'
    else:
        hum_line = 'Not run'

    focus_key = _esc(str(focus.get('focus') or focus.get('focus_name') or ''))
    recommend = ''
    if rec.get('review_recommended'):
        reasons = ', '.join(str(r) for r in (rec.get('reasons') or []))
        recommend = (
            '<p class="review-recommended">Review recommended'
            + (f' ({_esc(reasons)})' if reasons else '')
            + ' — advisory only.</p>'
        )

    return (
        f'<div class="evidence-lenses" data-focus="{focus_key}">'
        f'<p class="multi-lens-explainer">{_esc(MULTI_LENS_EXPLAINER)}</p>'
        f'<div class="lens-row"><strong>{_esc(LENS_SEMANTIC_TITLE)}:</strong> {_esc(sem_line)}</div>'
        f'<div class="lens-row"><strong>{_esc(LENS_LLM_TITLE)}:</strong> {llm_line}</div>'
        f'<div class="lens-row"><strong>{_esc(LENS_HUMAN_TITLE)}:</strong> {hum_line}</div>'
        f'{recommend}'
        f'<div class="behavioral-review-actions">'
        f'<button type="button" class="btn btn-outline btn-review-llm-diff" data-focus="{focus_key}">'
        f'{_esc(REVIEW_BEHAVIORAL_DIFFERENCE)} (LLM)</button> '
        f'<button type="button" class="btn btn-outline btn-review-human-diff" data-focus="{focus_key}">'
        f'Record human difference review</button>'
        f'</div></div>'
    )



def render_focus_card(focus: Mapping[str, Any], alpha: float = DEFAULT_ALPHA) -> str:
    name = _focus_name(focus)
    excluded = excluded_explanation(focus)
    prompt_empty = bool(focus.get('prompt_empty'))
    classes = ['focus-verdict-card']

    body: List[str] = [f'<h4 class="focus-verdict-name">{_esc(name)}</h4>']

    if excluded:
        classes.append('excluded')
        body.append(f'<p class="focus-verdict-primary">{_esc(excluded)}</p>')
    elif focus.get('is_significant') is True:
        classes.append('significant')
        z = focus.get('standardized_effect')
        body.append(f'<p class="focus-verdict-primary">{_esc(VERDICT_SIGNIFICANT)}</p>')
        body.append(
            f'<p class="focus-verdict-stats">{_esc(significant_stats_line(focus.get("q_value"), z))}</p>'
        )
        qualifier = effect_size_qualifier(z)
        if qualifier:
            body.append(f'<p class="focus-effect-qualifier">{_esc(qualifier)}</p>')
        if prompt_empty:
            body.append(f'<p class="focus-prompt-empty">{_esc(PROMPT_EMPTY_NOTE)}</p>')
        body.append(render_statistical_detail(focus))
    else:
        classes.append('not-significant')
        body.append(f'<p class="focus-verdict-primary">{_esc(VERDICT_NOT_SIGNIFICANT)}</p>')
        body.append(
            f'<p class="focus-verdict-stats">{_esc(not_significant_stats_line(focus.get("q_value")))}</p>'
        )
        body.append(f'<p class="focus-verdict-caution">{_esc(NON_SIGNIFICANT_CAUTION)}</p>')
        if is_near_threshold(focus.get('q_value'), alpha=alpha):
            body.append(f'<p class="focus-near-threshold">{_esc(NEAR_THRESHOLD_HINT)}</p>')
        if prompt_empty:
            body.append(f'<p class="focus-prompt-empty">{_esc(PROMPT_EMPTY_NOTE)}</p>')
        body.append(render_statistical_detail(focus))

    if not excluded:
        body.append(render_evidence_lenses(focus))

    return f'<article class="{" ".join(classes)}">{"".join(body)}</article>'


def render_definition() -> str:
    return (
        f'<p class="results-definition">{_esc(DEFINITION)}</p>'
    )


def render_methods_panel() -> str:
    paragraphs = [p.strip() for p in METHODS_PANEL.split('\n\n') if p.strip()]
    inner = ''.join(f'<p>{_esc(p)}</p>' for p in paragraphs)
    return (
        '<details class="methods-panel">'
        f'<summary>{_esc(METHODS_PANEL_TITLE)}</summary>'
        f'<div class="methods-panel-body">{inner}</div>'
        '</details>'
    )


def render_power_banner_html(data: Mapping[str, Any]) -> str:
    if not should_show_power_banner(data):
        return ''
    n_baseline = int(data.get('n_baseline') or data.get('num_baseline_samples') or 10)
    n_ablated = int(data.get('n_ablated') or 5)
    n_perm = int(data.get('n_permutations') or DEFAULT_N_PERMUTATIONS)
    n_foci = n_foci_tested(data)
    text = format_power_banner(
        n_baseline, n_ablated, n_foci, n_permutations=n_perm
    )
    return f'<div class="results-power-banner" role="status">{_esc(text)}</div>'


def render_run_header(data: Mapping[str, Any]) -> str:
    n_baseline = int(data.get('n_baseline') or data.get('num_baseline_samples') or 10)
    n_ablated = int(data.get('n_ablated') or 5)
    n_perm = int(data.get('n_permutations') or DEFAULT_N_PERMUTATIONS)
    temperature = data.get('temperature')
    if temperature is None:
        temperature = 0.7
    test_type = data.get('test_type') or design_test_type(n_baseline, n_ablated, n_perm)
    text = format_run_header(temperature, n_baseline, n_ablated, test_type)
    return f'<p class="results-run-header">{_esc(text)}</p>'


def render_ablation_results_html(data: Mapping[str, Any]) -> str:
    """Full results view HTML (definition, banner, cards, methods, extras)."""
    alpha = float(data.get('alpha') if data.get('alpha') is not None else DEFAULT_ALPHA)
    parts = [
        '<div class="ablation-summary">',
        '<h3>Behavioural sensitivity</h3>',
        render_definition(),
        render_run_header(data),
        '</div>',
        render_power_banner_html(data),
    ]
    records = collect_focus_records(data)
    parts.append('<div class="focus-verdict-list">')
    for rec in records:
        parts.append(render_focus_card(rec, alpha=alpha))
    parts.append('</div>')
    parts.append(render_methods_panel())

    if data.get('baseline_output') or data.get('baseline_outputs') or data.get('ablation_results'):
        parts.append('<div class="ablation-outputs-section">')
        parts.append(
            '<button id="toggle-all-outputs" class="btn btn-outline" type="button">'
            'Show sampled outputs</button>'
        )
        parts.append('<div id="all-outputs-container" class="hidden">')
        baselines = list(data.get('baseline_outputs') or [])
        if not baselines and data.get('baseline_output'):
            baselines = [data.get('baseline_output')]
        if baselines:
            n = len(baselines)
            label = 'sample' if n == 1 else 'samples'
            parts.append(
                '<div class="output-comparison-item">'
                f'<h4>Baseline outputs (full prompt, {n} {label})</h4>'
            )
            for idx, text in enumerate(baselines):
                parts.append(
                    '<div class="output-text" style="margin-top:8px">'
                    f'<strong>Sample {idx + 1}</strong>'
                    f'<pre style="white-space:pre-wrap;margin:4px 0 0">{_esc(text)}</pre>'
                    '</div>'
                )
            parts.append('</div>')
        for rec in records:
            outputs = rec.get('ablated_outputs') or (
                [rec['ablated_output']] if rec.get('ablated_output') else []
            )
            if not outputs:
                continue
            parts.append(
                '<div class="output-comparison-item">'
                f'<h4>Ablated outputs: {_esc(_focus_name(rec))} ({len(outputs)})</h4>'
            )
            for idx, text in enumerate(outputs):
                parts.append(
                    '<div class="output-text" style="margin-top:8px">'
                    f'<strong>Sample {idx + 1}</strong>'
                    f'<pre style="white-space:pre-wrap;margin:4px 0 0">{_esc(text)}</pre>'
                    '</div>'
                )
            parts.append('</div>')
        parts.append('</div></div>')

    if data.get('cost_breakdown'):
        cost = data['cost_breakdown']
        parts.append('<div class="cost-breakdown">')
        parts.append('<h4>Cost breakdown</h4>')
        chat = cost.get('chat_completions') or {}
        emb = cost.get('embeddings') or {}
        parts.append(
            f'<p>Chat completions: ${float(chat.get("cost") or 0):.4f}. '
            f'Embeddings: ${float(emb.get("cost") or 0):.4f}. '
            f'Total: ${float(cost.get("total_cost") or 0):.4f}'
            f' (model: {_esc(cost.get("model") or "unknown")}).</p>'
        )
        parts.append('</div>')

    parts.append(
        '<div class="ablation-download">'
        '<button id="download-ablation-results" class="btn btn-primary" type="button">'
        'Download all results (JSON)</button></div>'
    )
    return ''.join(parts)


def user_facing_text_blobs() -> List[str]:
    """Every canonical user-facing string, for forbidden-phrase scans."""
    return list(COPY.values())
