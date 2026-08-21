"""Exact-copy coverage for results presentation. No statistics."""

from pathlib import Path

import pytest

from utils.permutation_test import min_achievable_pvalue
from utils.experiment_config import format_run_header
from utils.results_copy import (
    COPY,
    DEFINITION,
    EXCLUDED_DYNAMIC_SLOT,
    EXCLUDED_OVERLAP,
    EXCLUDED_UNVERIFIED,
    METHODS_PANEL,
    METHODS_PANEL_TITLE,
    NEAR_THRESHOLD_HINT,
    NON_SIGNIFICANT_CAUTION,
    PROMPT_EMPTY_NOTE,
    VERDICT_NOT_SIGNIFICANT,
    VERDICT_SIGNIFICANT,
    collect_focus_records,
    effect_size_qualifier,
    excluded_explanation,
    format_power_banner,
    format_q_value,
    render_ablation_results_html,
    render_focus_card,
    render_power_banner_html,
)

FORBIDDEN_USER_FACING_PHRASES = (
    'noise floor',
    'safe to remove',
)

REPO = Path(__file__).resolve().parents[2]

USER_FACING_PATHS = [
    REPO / 'README.md',
    REPO / 'utils' / 'results_copy.py',
    REPO / 'utils' / 'experiment_config.py',
    REPO / 'static' / 'js' / 'results_copy.js',
    REPO / 'static' / 'js' / 'experiment_config.js',
    REPO / 'static' / 'js' / 'app.js',
    REPO / 'templates' / 'index.html',
    REPO / 'services' / 'optimization_service.py',
]


def _significant_focus(**overrides):
    row = {
        'focus': 'Citation style',
        'verified': True,
        'attributable': True,
        'is_significant': True,
        'q_value': 0.0012,
        'p_value': 0.0004,
        't_obs': 0.21,
        'standardized_effect': 8.3,
        'null_deciles': {'0': 0.01, '50': 0.04, '100': 0.09},
        'prompt_empty': False,
    }
    row.update(overrides)
    return row


def _nonsig_focus(**overrides):
    row = {
        'focus': 'Tone',
        'verified': True,
        'attributable': True,
        'is_significant': False,
        'q_value': 0.41,
        'p_value': 0.22,
        't_obs': 0.03,
        'standardized_effect': 0.4,
        'null_deciles': {'50': 0.02},
        'prompt_empty': False,
    }
    row.update(overrides)
    return row


def test_copy_constants_are_exact():
    assert DEFINITION == (
        "FocalPrompt detects whether removing each focus shifts the model's "
        "behaviour in semantic embedding space. It does not measure correctness, "
        "quality, or safety, and it does not tell you what to delete."
    )
    assert VERDICT_SIGNIFICANT == (
        "Removing this focus measurably changed the model's behaviour."
    )
    assert VERDICT_NOT_SIGNIFICANT == (
        "No behavioural change detected beyond sampling variation at this sample size."
    )
    assert NON_SIGNIFICANT_CAUTION == (
        "Undetected here does not mean removable: short structural instructions "
        "(output formats, escalation rules, guardrails) can matter greatly while "
        "barely shifting output embeddings."
    )
    assert EXCLUDED_UNVERIFIED == (
        "Couldn't uniquely ground this focus to an exact span of your prompt, so it "
        "wasn't tested. Repair the span manually or re-detect with a clearer "
        "evidence quote."
    )
    assert EXCLUDED_DYNAMIC_SLOT == (
        "This focus is a runtime slot (chat, retrieved context), not text in your "
        "prompt, so subtractive testing doesn't apply in this version."
    )
    assert EXCLUDED_OVERLAP == (
        "This focus overlaps another focus's text, so removing it alone isn't well "
        "defined. Refine the foci to separate them."
    )
    assert NEAR_THRESHOLD_HINT == (
        "Near the threshold. Rerun with more ablated samples to resolve."
    )
    assert METHODS_PANEL_TITLE == "How this works"
    assert "repeated sampling" in METHODS_PANEL.lower()
    assert "centroid" in METHODS_PANEL.lower()
    assert "permutation" in METHODS_PANEL.lower()
    assert "p-value" in METHODS_PANEL.lower()
    assert "benjamini" in METHODS_PANEL.lower()
    assert "q < 0.05" in METHODS_PANEL
    assert "embedding blindness" in METHODS_PANEL.lower()
    assert "leave-one-out" in METHODS_PANEL.lower()
    assert "locality" in METHODS_PANEL.lower()


def test_effect_size_qualifier_bands():
    assert effect_size_qualifier(8.3) == "large effect (z = 8.3)"
    assert effect_size_qualifier(1.9) == "small effect (z = 1.9)"
    assert effect_size_qualifier(2.0) == "moderate effect (z = 2.0)"
    assert effect_size_qualifier(5.0) == "moderate effect (z = 5.0)"
    assert effect_size_qualifier(5.1) == "large effect (z = 5.1)"


def test_significant_verdict_card_copy():
    html = render_focus_card(_significant_focus())
    assert VERDICT_SIGNIFICANT in html
    assert f"(q = {format_q_value(0.0012)}, effect size = 8.3)" in html
    assert "large effect (z = 8.3)" in html
    assert NON_SIGNIFICANT_CAUTION not in html
    assert "t_obs" in html
    assert "p_value" in html
    assert "q_value" in html
    assert "Null deciles" in html
    assert "focus-verdict-details" in html
    assert html.index(VERDICT_SIGNIFICANT) < html.index("Statistical detail")
    assert html.index(VERDICT_SIGNIFICANT) < html.index("t_obs")


def test_not_significant_verdict_and_visible_caution():
    html = render_focus_card(_nonsig_focus())
    assert VERDICT_NOT_SIGNIFICANT in html
    assert f"(q = {format_q_value(0.41)})" in html
    assert NON_SIGNIFICANT_CAUTION in html
    assert "focus-verdict-caution" in html
    # Caution is outside the expandable detail block.
    caution_at = html.index(NON_SIGNIFICANT_CAUTION)
    details_at = html.index("Statistical detail")
    assert caution_at < details_at
    assert NEAR_THRESHOLD_HINT not in html


def test_near_threshold_hint():
    html = render_focus_card(_nonsig_focus(q_value=0.07), alpha=0.05)
    assert NEAR_THRESHOLD_HINT in html
    html_sig = render_focus_card(_significant_focus(q_value=0.01), alpha=0.05)
    assert NEAR_THRESHOLD_HINT not in html_sig


def test_excluded_unverified_copy():
    html = render_focus_card({
        'focus': 'Paraphrased block',
        'verified': False,
        'attributable': False,
        'reason': 'unverified',
    })
    assert EXCLUDED_UNVERIFIED in html
    assert VERDICT_SIGNIFICANT not in html
    assert VERDICT_NOT_SIGNIFICANT not in html
    assert '0.0' not in html


def test_excluded_dynamic_slot_copy():
    html = render_focus_card({
        'focus': 'Chat turn',
        'verified': False,
        'attributable': False,
        'reason': 'dynamic_slot',
        'is_dynamic': True,
    })
    assert EXCLUDED_DYNAMIC_SLOT in html


def test_excluded_overlap_names_the_other_focus():
    html = render_focus_card({
        'focus': 'Style A',
        'verified': True,
        'attributable': False,
        'reason': 'overlap',
        'overlap_with': ['Style B'],
    })
    assert EXCLUDED_OVERLAP in html
    assert "Overlaps with: Style B." in html


def test_prompt_empty_note_on_tested_focus():
    html = render_focus_card(_significant_focus(prompt_empty=True))
    assert PROMPT_EMPTY_NOTE in html
    html_ns = render_focus_card(_nonsig_focus(prompt_empty=True))
    assert PROMPT_EMPTY_NOTE in html_ns


def test_power_banner_exact_copy():
    n_baseline, n_ablated, n_foci = 10, 5, 8
    min_p = min_achievable_pvalue(n_baseline, n_ablated, 10000)
    expected = (
        f"With {n_baseline} baseline and {n_ablated} ablated samples, the smallest "
        f"possible p-value is {min_p:.6g}. After correction across {n_foci} foci, real "
        "effects may be undetectable. Increase samples to resolve."
    )
    assert format_power_banner(n_baseline, n_ablated, n_foci) == expected
    html = render_power_banner_html({
        'power_warning': 'backend present',
        'n_baseline': n_baseline,
        'n_ablated': n_ablated,
        'n_permutations': 10000,
        'influence_scores': [{'focus': f'f{i}'} for i in range(n_foci)],
    })
    assert expected in html
    assert render_power_banner_html({'n_baseline': 10, 'n_ablated': 5}) == ''


def test_full_results_view_has_definition_methods_and_states():
    data = {
        'alpha': 0.05,
        'n_baseline': 10,
        'n_ablated': 5,
        'power_warning': 'present',
        'baseline_output': 'hello',
        'influence_scores': [
            _significant_focus(),
            _nonsig_focus(),
        ],
        'ablation_results': [
            _significant_focus(),
            _nonsig_focus(),
            {
                'focus': 'Chat',
                'verified': False,
                'attributable': False,
                'reason': 'dynamic_slot',
            },
            {
                'focus': 'Missing',
                'verified': False,
                'attributable': False,
                'reason': 'unverified',
            },
            {
                'focus': 'Overlap A',
                'verified': True,
                'attributable': False,
                'reason': 'overlap',
                'overlap_with': ['Overlap B'],
            },
        ],
    }
    html = render_ablation_results_html(data)
    assert html.index(DEFINITION) < html.index(VERDICT_SIGNIFICANT)
    assert DEFINITION in html
    assert format_run_header(0.7, 10, 5, 'exact') in html or 'samples per focus' in html
    assert METHODS_PANEL_TITLE in html
    import html as html_lib
    for paragraph in METHODS_PANEL.split('\n\n'):
        assert html_lib.escape(paragraph.strip(), quote=False) in html
    assert VERDICT_SIGNIFICANT in html
    assert VERDICT_NOT_SIGNIFICANT in html
    assert NON_SIGNIFICANT_CAUTION in html
    assert EXCLUDED_DYNAMIC_SLOT in html
    assert EXCLUDED_UNVERIFIED in html
    assert EXCLUDED_OVERLAP in html
    assert "Overlaps with: Overlap B." in html
    assert format_power_banner(10, 5, 2) in html
    assert 'How this works' in html


def test_collect_focus_records_keeps_excluded():
    data = {
        'ablation_results': [
            {'focus': 'A', 'attributable': False, 'reason': 'dynamic_slot'},
            {'focus': 'B', 'attributable': True, 'verified': True},
        ],
        'influence_scores': [
            {'focus': 'B', 'is_significant': True, 'q_value': 0.01, 't_obs': 0.2},
        ],
    }
    records = collect_focus_records(data)
    assert [r['focus'] for r in records] == ['A', 'B']
    assert excluded_explanation(records[0]) == EXCLUDED_DYNAMIC_SLOT
    assert records[1]['is_significant'] is True


def test_no_user_facing_string_contains_forbidden_phrases():
    hits = []
    for path in USER_FACING_PATHS:
        text = path.read_text(encoding='utf-8').lower()
        for phrase in FORBIDDEN_USER_FACING_PHRASES:
            if phrase in text:
                hits.append(f'{path.relative_to(REPO)}: {phrase!r}')
    assert hits == [], 'Forbidden phrasing in user-facing files:\n' + '\n'.join(hits)

    for value in COPY.values():
        lowered = value.lower()
        for phrase in FORBIDDEN_USER_FACING_PHRASES:
            assert phrase not in lowered, phrase


def test_injected_copy_payload_matches_module():
    """Flask injects COPY; JS must not ship a second prose source."""
    js = (REPO / 'static' / 'js' / 'results_copy.js').read_text(encoding='utf-8')
    assert 'FOCALPROMPT_COPY' in js
    assert VERDICT_SIGNIFICANT not in js
    assert NON_SIGNIFICANT_CAUTION not in js
    assert EXCLUDED_UNVERIFIED not in js
    assert DEFINITION not in js
