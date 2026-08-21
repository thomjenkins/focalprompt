"""Aggregation statistics for batch results."""

from __future__ import annotations

import pytest

from utils.data_processing import (
    NORMALIZED_INFLUENCE_PERCENTAGE_SCALE,
    calculate_focus_distribution_statistics,
    calculate_statistics_from_results,
)


def _pair(success=True, scores=None, assessment=None):
    out = {'success': success}
    if scores is not None:
        out['influence_scores'] = scores
    if assessment is not None:
        out['focus_distribution_assessment'] = assessment
    return out


def test_scale_constant_is_100():
    assert NORMALIZED_INFLUENCE_PERCENTAGE_SCALE == 100.0


def test_one_pair_percentage_norms():
    results = [
        _pair(scores={
            'A': {'influence': 0.2, 'normalized_influence': 40.0},
            'B': {'influence': 0.3, 'normalized_influence': 60.0},
        })
    ]
    stats = calculate_statistics_from_results(results)
    assert stats['A']['mean'] == pytest.approx(40.0)
    assert stats['B']['mean'] == pytest.approx(60.0)
    assert stats['A']['n_pairs'] == 1
    assert stats['A']['mean_raw'] == pytest.approx(0.2)


def test_multiple_pairs_mean_share():
    results = [
        _pair(scores={
            'A': {'influence': 1.0, 'normalized_influence': 25.0},
            'B': {'influence': 3.0, 'normalized_influence': 75.0},
        }),
        _pair(scores={
            'A': {'influence': 1.0, 'normalized_influence': 50.0},
            'B': {'influence': 1.0, 'normalized_influence': 50.0},
        }),
    ]
    stats = calculate_statistics_from_results(results)
    assert stats['A']['mean'] == pytest.approx(37.5)
    assert stats['B']['mean'] == pytest.approx(62.5)
    assert stats['A']['n_pairs'] == 2


def test_failed_pairs_ignored():
    results = [
        _pair(success=False, scores={'A': {'influence': 9, 'normalized_influence': 100}}),
        _pair(scores={'A': {'influence': 1.0, 'normalized_influence': 100.0}}),
    ]
    stats = calculate_statistics_from_results(results)
    assert stats['A']['mean'] == pytest.approx(100.0)
    assert stats['A']['n_pairs'] == 1


def test_missing_focus_excluded_from_denominator_not_zero():
    results = [
        _pair(scores={'A': {'influence': 1.0, 'normalized_influence': 100.0}}),
        _pair(scores={
            'A': {'influence': 1.0, 'normalized_influence': 40.0},
            'B': {'influence': 1.5, 'normalized_influence': 60.0},
        }),
    ]
    stats = calculate_statistics_from_results(results)
    assert stats['A']['n_pairs'] == 2
    assert stats['A']['mean'] == pytest.approx(70.0)
    assert stats['B']['n_pairs'] == 1
    assert stats['B']['mean'] == pytest.approx(60.0)


def test_legacy_fractional_normalized_coerced_to_percent():
    results = [
        _pair(scores={
            'A': {'influence': 0.2, 'normalized_influence': 0.25},
            'B': {'influence': 0.6, 'normalized_influence': 0.75},
        })
    ]
    stats = calculate_statistics_from_results(results)
    assert stats['A']['mean'] == pytest.approx(25.0)
    assert stats['B']['mean'] == pytest.approx(75.0)


def test_legacy_payload_without_normalized_recomputed_as_percent():
    results = [
        _pair(scores={
            'A': {'influence': 1.0},
            'B': {'influence': 3.0},
        })
    ]
    stats = calculate_statistics_from_results(results)
    assert stats['A']['mean'] == pytest.approx(25.0)
    assert stats['B']['mean'] == pytest.approx(75.0)


def test_zero_raw_influence_equal_percent_fallback():
    results = [
        _pair(scores={
            'A': {'influence': 0.0},
            'B': {'influence': 0.0},
        })
    ]
    stats = calculate_statistics_from_results(results)
    assert stats['A']['mean'] == pytest.approx(50.0)
    assert stats['B']['mean'] == pytest.approx(50.0)


def test_no_attributable_foci():
    assert calculate_statistics_from_results([_pair(scores={})]) == {}
    assert calculate_statistics_from_results([_pair(success=False)]) == {}


def test_focus_distribution_statistics_excludes_missing():
    results = [
        _pair(assessment={'foci': [
            {'focus': 'A', 'score': 80},
            {'focus': 'B', 'score': 20},
        ]}),
        _pair(assessment={'foci': [
            {'focus': 'A', 'score': 60},
        ]}),
        _pair(success=False, assessment={'foci': [{'focus': 'A', 'score': 1}]}),
    ]
    stats = calculate_focus_distribution_statistics(results)
    assert stats['A']['mean'] == pytest.approx(70.0)
    assert stats['A']['n_pairs'] == 2
    assert stats['B']['mean'] == pytest.approx(20.0)
    assert stats['B']['n_pairs'] == 1
