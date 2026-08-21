"""Deterministic focus span grounding for auto-detect."""

from __future__ import annotations

from pathlib import Path

import pytest

from utils.span_alignment import (
    classify_foci_for_ablation,
    compute_coverage_report,
    ground_focus_span,
    verify_focus,
    verify_foci,
)

FIXTURES = Path(__file__).resolve().parents[1] / 'fixtures' / 'focus_grounding'


def _load(name: str) -> str:
    return (FIXTURES / name).read_text()


def test_exact_quoted_prose():
    prompt = 'Always cite the source of any medical claim.'
    g = ground_focus_span(prompt, {
        'focus': 'Cite',
        'prompt_section': 'Always cite the source of any medical claim.',
    })
    assert g['verified'] is True
    assert g['grounding_method'] == 'exact'
    assert g['prompt_section'] == prompt[g['char_start']:g['char_end']]
    assert g['prompt_section'] == prompt


def test_literal_backslash_n_in_prompt():
    prompt = _load('json_code_prompt.txt')
    quote = 'Escape newlines as \\n inside string values.'
    assert '\\n' in quote and '\n' not in quote[len('Escape'):]  # two-char escape in quote
    g = ground_focus_span(prompt, {'focus': 'Escape', 'prompt_section': quote})
    assert g['verified'] is True
    assert g['prompt_section'] == prompt[g['char_start']:g['char_end']]
    assert '\\n' in g['prompt_section']
    assert '\n' not in g['prompt_section'].replace('\\n', '')  # no raw newline inside the span text beyond...
    # The span itself should contain backslash + n, not a newline between "as " and " inside"
    assert 'as \\n inside' in g['prompt_section']


def test_real_newline_does_not_match_literal_backslash_n():
    prompt = 'Use \\n between fields.'  # backslash-n
    g = ground_focus_span(prompt, {
        'focus': 'Wrong',
        'prompt_section': 'Use \n between fields.',  # real newline
    })
    assert g['verified'] is False


def test_json_code_snippet_exact():
    prompt = _load('json_code_prompt.txt')
    section = '{\n  "status": "ok|error",\n  "items": [],\n  "message": ""\n}'
    g = ground_focus_span(prompt, {'focus': 'Schema', 'prompt_section': section})
    assert g['verified'] is True
    assert g['prompt_section'] == prompt[g['char_start']:g['char_end']]
    assert '"status"' in g['prompt_section']


def test_curly_vs_straight_quotes():
    prompt = _load('curly_quotes_prompt.txt')
    g = ground_focus_span(prompt, {
        'focus': 'Quote rule',
        'prompt_section': 'He said "ship it" yesterday.',
    })
    assert g['verified'] is True
    assert '\u201c' in g['prompt_section'] and '\u201d' in g['prompt_section']
    assert g['prompt_section'] == prompt[g['char_start']:g['char_end']]


def test_repeated_identical_phrase_is_ambiguous():
    prompt = _load('repeated_phrase_prompt.txt')
    g = ground_focus_span(prompt, {
        'focus': 'Caution',
        'prompt_section': 'Caution.',
    })
    assert g['verified'] is False
    assert g['grounding_failure'] == 'ambiguous_prompt_section'


def test_whitespace_normalized_span():
    prompt = 'Always  cite   the source.'
    g = ground_focus_span(prompt, {
        'focus': 'Cite',
        'prompt_section': 'Always cite the source.',
    })
    assert g['verified'] is True
    assert g['prompt_section'] == 'Always  cite   the source.'
    assert g['prompt_section'] == prompt[g['char_start']:g['char_end']]


def test_paraphrase_plus_unique_verbatim_anchor():
    prompt = _load('vet_triage_prompt.txt')
    g = ground_focus_span(prompt, {
        'focus': 'JSON output',
        'prompt_section': 'Output a JSON object containing urgency and next steps',
        'evidence_quote': 'Respond in JSON with keys: urgency, differentials, next_steps.',
    })
    assert g['verified'] is True
    assert 'Respond in JSON with keys' in g['prompt_section']
    assert g['prompt_section'] == prompt[g['char_start']:g['char_end']]
    assert g['original_proposal'].startswith('Output a JSON')


def test_evidence_expands_to_larger_unique_section():
    prompt = 'RULES\nAlways cite sources for medical claims.\nEND'
    g = ground_focus_span(prompt, {
        'focus': 'Cite',
        'prompt_section': 'Require citations for any medical statements.',
        'evidence_quote': 'cite sources',
    })
    assert g['verified'] is True
    assert g['prompt_section'] == 'Always cite sources for medical claims.'
    assert g['grounding_method'] == 'evidence_anchor_expanded'



def test_overlapping_proposed_foci_refused_for_ablation():
    prompt = 'The quick brown fox jumps.'
    foci = verify_foci(prompt, [
        {'focus': 'A', 'prompt_section': 'The quick brown fox'},
        {'focus': 'B', 'prompt_section': 'brown fox jumps.'},
    ])
    assert all(f['verified'] for f in foci)
    classified = classify_foci_for_ablation(prompt, foci)
    assert classified[0]['reason'] == 'overlap'
    assert classified[1]['reason'] == 'overlap'
    assert classified[0]['attributable'] is False


def test_source_substring_replacement_after_grounding():
    prompt = 'Alpha instruction here.'
    out = verify_focus(prompt, {
        'focus': 'Alpha',
        'prompt_section': 'Alpha   instruction here.',
    })
    assert out['verified'] is True
    assert out['prompt_section'] == 'Alpha instruction here.'
    assert out['prompt_section'] == prompt[out['char_start']:out['char_end']]
    assert out['original_proposal'] == 'Alpha   instruction here.'


def test_ungroundable_excluded_from_ablation():
    prompt = 'Keep this sentence.'
    classified = classify_foci_for_ablation(prompt, [
        {'focus': 'Ghost', 'prompt_section': 'a paraphrase that never appears'},
    ])
    assert classified[0]['verified'] is False
    assert classified[0]['attributable'] is False
    assert classified[0]['reason'] == 'unverified'


def test_every_verified_focus_substring_identity():
    prompt = _load('vet_triage_prompt.txt')
    proposals = [
        {'focus': 'Role', 'prompt_section': 'You are a veterinary triage assistant.'},
        {'focus': 'Cite', 'prompt_section': 'Always cite the source of any medical claim.'},
        {
            'focus': 'JSON',
            'prompt_section': 'please emit json',
            'evidence_quote': 'Respond in JSON with keys: urgency, differentials, next_steps.',
        },
        {'focus': 'Bleed', 'prompt_section': 'If the owner describes bleeding, escalate immediately.'},
    ]
    out = verify_foci(prompt, proposals)
    verified = [f for f in out if f['verified']]
    assert len(verified) == 4
    for f in verified:
        assert f['prompt_section'] == prompt[f['char_start']:f['char_end']]


def test_coverage_report_exposes_uncovered_and_unverified():
    prompt = _load('vet_triage_prompt.txt')
    report = compute_coverage_report(prompt, [
        {'focus': 'Role', 'prompt_section': 'You are a veterinary triage assistant.'},
        {'focus': 'Ghost', 'prompt_section': 'not present anywhere'},
    ])
    assert report['coverage_percent'] > 0
    assert report['coverage_percent'] < 100
    assert any(u['focus'] == 'Ghost' for u in report['unverified_proposals'])
    assert report['uncovered_spans']


@pytest.mark.parametrize('fixture_name', [
    'json_code_prompt.txt',
    'curly_quotes_prompt.txt',
    'mixed_newline_prompt.txt',
    'vet_triage_prompt.txt',
])
def test_regression_fixtures_load(fixture_name):
    text = _load(fixture_name)
    assert len(text) > 20
