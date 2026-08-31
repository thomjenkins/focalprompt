"""Tests for multi-span / overlapping focus helpers."""

import pytest

from utils.focus_spans import (
    affected_overlapping_foci,
    compute_coverage_metrics,
    delete_focus_spans,
    delete_spans,
    focus_span_tuples,
    is_order_movable,
    normalize_focus,
    overlap_matrix,
    pairwise_overlap,
)
from utils.span_alignment import classify_foci_for_ablation, compute_coverage_report


def test_legacy_single_span_migrates_to_spans():
    focus = {'focus': 'Role', 'char_start': 0, 'char_end': 5, 'prompt_section': 'Hello'}
    nf = normalize_focus(focus, prompt='Hello world')
    assert len(nf['spans']) == 1
    assert nf['spans'][0]['char_start'] == 0
    assert nf['spans'][0]['char_end'] == 5
    assert nf['char_start'] == 0
    assert nf['is_multi_span'] is False
    assert nf['is_contiguous'] is True


def test_multi_span_non_contiguous():
    prompt = 'AAAAABBBBBCCCCC'
    focus = {
        'focus': 'Policy',
        'spans': [
            {'char_start': 0, 'char_end': 5},
            {'char_start': 10, 'char_end': 15},
        ],
    }
    nf = normalize_focus(focus, prompt=prompt)
    assert nf['is_multi_span'] is True
    assert nf['is_contiguous'] is False
    assert nf['total_span_length'] == 10
    assert nf['unique_span_length'] == 10
    assert '…' in nf['prompt_section']


def test_duplicate_same_focus_span_deduped():
    focus = {
        'focus': 'X',
        'spans': [
            {'char_start': 0, 'char_end': 3},
            {'char_start': 0, 'char_end': 3},
            {'char_start': 5, 'char_end': 8},
        ],
    }
    nf = normalize_focus(focus, prompt='0123456789')
    assert nf['span_count'] == 2


def test_identical_spans_across_foci_ok():
    prompt = 'Hello world'
    a = normalize_focus({'focus': 'A', 'char_start': 0, 'char_end': 5}, prompt=prompt)
    b = normalize_focus({'focus': 'B', 'char_start': 0, 'char_end': 5}, prompt=prompt)
    info = pairwise_overlap(a, b)
    assert info['relation'] == 'identical'
    assert info['jaccard'] == 1.0


def test_invalid_offsets_raise():
    with pytest.raises(ValueError):
        normalize_focus(
            {'focus': 'Bad', 'spans': [{'char_start': 5, 'char_end': 2}]},
            prompt='Hello',
            require_bounds=True,
        )
    with pytest.raises(ValueError):
        normalize_focus(
            {'focus': 'Bad', 'spans': [{'char_start': 0, 'char_end': 99}]},
            prompt='Hello',
            require_bounds=True,
        )


def test_unique_coverage_and_density_over_100():
    prompt = 'X' * 1000
    foci = [
        {'focus': 'A', 'char_start': 0, 'char_end': 500, 'verified': True},
        {'focus': 'B', 'char_start': 250, 'char_end': 750, 'verified': True},
    ]
    m = compute_coverage_metrics(prompt, foci)
    assert m['unique_coverage_percent'] == 75.0
    assert m['focus_density_percent'] == 100.0
    foci.append({'focus': 'C', 'char_start': 250, 'char_end': 500, 'verified': True})
    m2 = compute_coverage_metrics(prompt, foci)
    assert m2['unique_coverage_percent'] == 75.0
    assert m2['focus_density_percent'] == 125.0
    assert m2['depth_percent']['three_plus'] > 0


def test_delete_noncontiguous_preserves_middle():
    prompt = 'AAAAABBBBBCCCCC'
    focus = {
        'focus': 'Policy',
        'spans': [{'char_start': 0, 'char_end': 5}, {'char_start': 10, 'char_end': 15}],
    }
    ablated, empty, _, ranges = delete_focus_spans(prompt, focus)
    assert ablated == 'BBBBB'
    assert empty is False
    assert ranges == [(0, 5), (10, 15)]


def test_delete_spans_descending_safety():
    prompt = '0123456789'
    ablated, _, _, ranges = delete_spans(prompt, [(1, 3), (7, 9), (1, 3)])
    assert ranges == [(1, 3), (7, 9)]
    assert ablated == '034569'


def test_affected_overlapping_foci_metadata():
    prompt = 'AAAAABBBBBCCCCC'
    a = normalize_focus({'focus': 'A', 'char_start': 0, 'char_end': 10}, prompt=prompt)
    b = normalize_focus({'focus': 'B', 'char_start': 5, 'char_end': 15}, prompt=prompt)
    affected = affected_overlapping_foci(a, [a, b])
    assert len(affected) == 1
    assert affected[0]['focus'] == 'B'
    assert affected[0]['overlap_removed_pct'] == 50.0


def test_nested_containment_relation():
    prompt = '0123456789'
    parent = normalize_focus({'focus': 'Parent', 'char_start': 0, 'char_end': 10}, prompt=prompt)
    child = normalize_focus({'focus': 'Child', 'char_start': 2, 'char_end': 5}, prompt=prompt)
    info = pairwise_overlap(parent, child)
    assert info['a_contains_b'] is True
    assert info['overlap_pct_of_b'] == 100.0


def test_order_movable_requires_contiguous():
    prompt = 'AAAAABBBBBCCCCC'
    contiguous = normalize_focus({'focus': 'C', 'char_start': 0, 'char_end': 5, 'verified': True}, prompt=prompt)
    multi = normalize_focus({
        'focus': 'M',
        'verified': True,
        'spans': [{'char_start': 0, 'char_end': 5}, {'char_start': 10, 'char_end': 15}],
    }, prompt=prompt)
    assert is_order_movable(contiguous) is True
    assert is_order_movable(multi) is False


def test_coverage_report_includes_density():
    prompt = 'AAAAABBBBBCCCCC'
    foci = [
        {'focus': 'A', 'prompt_section': 'AAAAABBBBB'},
        {'focus': 'B', 'prompt_section': 'BBBBBCCCCC'},
    ]
    rep = compute_coverage_report(prompt, foci)
    assert rep['unique_coverage_percent'] == 100.0
    assert rep['focus_density_percent'] == pytest.approx(133.33, abs=0.01)
    assert rep['coverage_percent'] == rep['unique_coverage_percent']
    assert rep['overlap_matrix']


def test_text_snapshot_mismatch_raises():
    with pytest.raises(ValueError):
        normalize_focus(
            {'focus': 'X', 'spans': [{'char_start': 0, 'char_end': 5, 'text': 'NOPE!'}]},
            prompt='AAAAABBBBB',
            require_bounds=True,
        )
