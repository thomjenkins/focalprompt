#!/usr/bin/env python3
"""Tests for per-focus ablation stability analysis."""

from __future__ import annotations

import json

import numpy as np
import pytest

from utils.ablation_stability import (
    HEURISTIC_RATIO_MORE_STABLE,
    HEURISTIC_RATIO_MORE_VARIABLE,
    build_stability_scatter_points,
    build_stability_summary,
    categorical_entropy,
    compare_behavioral_outcomes,
    compute_ablation_stability,
    compute_dispersion_metrics,
    interpret_dispersion_ratio,
    summarize_behavioral_outcomes,
)
from utils.baseline_stability import compute_baseline_stability


def _cluster(n: int, center, noise: float = 0.02, seed: int = 0):
    rng = np.random.default_rng(seed)
    return np.tile(np.asarray(center, dtype=float), (n, 1)) + rng.normal(
        0, noise, (n, len(center))
    )


def test_compute_dispersion_metrics_pairwise_and_centroid():
    emb = _cluster(5, [1.0, 0.0, 0.0], noise=0.05, seed=1)
    metrics = compute_dispersion_metrics(emb)
    assert metrics['n_samples'] == 5
    assert metrics['mean_pairwise_distance'] is not None
    assert metrics['median_pairwise_distance'] is not None
    assert metrics['p95_pairwise_distance'] is not None
    assert metrics['mean_centroid_distance'] is not None
    assert metrics['p95_centroid_distance'] is not None


def test_single_sample_dispersion_metrics_have_null_pairwise():
    emb = np.ones((1, 4))
    metrics = compute_dispersion_metrics(emb)
    assert metrics['n_samples'] == 1
    assert metrics['mean_pairwise_distance'] is None
    assert metrics['mean_centroid_distance'] == pytest.approx(0.0, abs=1e-6)


def test_ablation_stability_ratios_and_deltas_vs_baseline():
    base = _cluster(10, [1.0, 0.0, 0.0], noise=0.03, seed=2)
    ablated = _cluster(5, [1.0, 0.0, 0.0], noise=0.01, seed=3)
    baseline_stability = compute_baseline_stability(base)
    stab = compute_ablation_stability(
        ablated,
        baseline_stability,
        n_ablated_configured=5,
        t_obs=0.15,
        standardized_effect=1.2,
    )
    assert stab['n_samples'] == 5
    assert stab['mean_pairwise_noise_delta'] is not None
    assert stab['centroid_noise_delta'] is not None
    assert stab['mean_pairwise_noise_ratio'] is not None
    assert stab['mean_pairwise_noise_ratio'] < 1.0
    assert stab['mean_pairwise_noise_ratio_status'] == 'ok'
    assert 'more stable' in (stab['dispersion_ratio_interpretation'] or '').lower()


def test_zero_baseline_dispersion_ratio_is_null_with_warning():
    base = np.ones((5, 3))
    ablated = _cluster(5, [1.0, 0.0, 0.0], noise=0.05, seed=4)
    baseline_stability = compute_baseline_stability(base)
    stab = compute_ablation_stability(ablated, baseline_stability, n_ablated_configured=5)
    assert stab['mean_pairwise_noise_ratio'] is None
    assert stab['mean_pairwise_noise_ratio_status'] == 'baseline_near_zero'
    assert stab['dispersion_ratio_warnings']


def test_near_zero_baseline_handled_safely():
    base = _cluster(5, [1.0, 0.0, 0.0], noise=1e-8, seed=5)
    ablated = _cluster(5, [1.0, 0.0, 0.0], noise=0.05, seed=6)
    baseline_stability = compute_baseline_stability(base)
    stab = compute_ablation_stability(ablated, baseline_stability)
    assert stab['mean_pairwise_noise_ratio'] is None or stab['mean_pairwise_noise_ratio_status'] in (
        'baseline_near_zero',
        'ok',
    )


def test_n5_sample_size_warning():
    emb = _cluster(5, [1.0, 0.0, 0.0], noise=0.04, seed=7)
    baseline_stability = compute_baseline_stability(emb)
    stab = compute_ablation_stability(emb, baseline_stability, n_ablated_configured=5)
    assert stab['sample_size_warning'] is True
    assert 'only 5 sample' in (stab['sample_size_note'] or '').lower()


def test_multimodality_insufficient_samples_for_small_n():
    emb = _cluster(3, [1.0, 0.0, 0.0], seed=8)
    baseline_stability = compute_baseline_stability(emb)
    stab = compute_ablation_stability(emb, baseline_stability, n_ablated_configured=3)
    assert stab['multimodality']['status'] == 'insufficient_samples'


def test_judge_outcome_entropy_and_delta():
    base_j = [
        {'classification': 'COMPLIES'},
        {'classification': 'VIOLATES'},
        {'classification': 'COMPLIES'},
        {'classification': 'VIOLATES'},
    ]
    abl_j = [
        {'classification': 'COMPLIES'},
        {'classification': 'COMPLIES'},
        {'classification': 'COMPLIES'},
        {'classification': 'VIOLATES'},
    ]
    base = summarize_behavioral_outcomes(base_j)
    assert base['counts']['COMPLIES'] == 2
    assert base['outcome_entropy_bits'] == pytest.approx(1.0, abs=1e-6)
    cmp = compare_behavioral_outcomes(base_j, abl_j)
    assert cmp['outcome_entropy_delta_bits'] is not None
    assert cmp['outcome_entropy_delta_bits'] < 0


def test_interpret_dispersion_ratio_copy():
    assert 'more stable' in interpret_dispersion_ratio(0.5).lower()
    assert 'more variable' in interpret_dispersion_ratio(1.5).lower()
    assert 'similar' in interpret_dispersion_ratio(1.0).lower()


def test_build_stability_scatter_and_summary():
    influence = [
        {
            'focus': 'A',
            'focus_index': 0,
            'attributable': True,
            't_obs': 0.3,
            'standardized_effect': 3.0,
            'normalized_influence': 40.0,
            'q_value': 0.01,
            'ablation_stability': {
                'n_samples': 5,
                'mean_pairwise_distance': 0.02,
                'baseline_mean_pairwise_distance': 0.04,
                'mean_pairwise_noise_ratio': 0.5,
            },
        },
        {
            'focus': 'B',
            'focus_index': 1,
            'attributable': True,
            't_obs': 0.05,
            'standardized_effect': 0.4,
            'normalized_influence': 20.0,
            'ablation_stability': {
                'n_samples': 5,
                'mean_pairwise_distance': 0.08,
                'baseline_mean_pairwise_distance': 0.04,
                'mean_pairwise_noise_ratio': 2.0,
            },
        },
    ]
    scatter = build_stability_scatter_points(influence)
    assert len(scatter) == 2
    assert scatter[0]['y_reference_line'] == 1.0
    summary = build_stability_summary(influence)
    assert summary['most_stabilizing_after_ablation'][0]['focus'] == 'A'
    assert summary['most_destabilizing_after_ablation'][0]['focus'] == 'B'


def test_legacy_export_without_ablation_stability_still_loads():
    legacy = {
        'baseline_stability': {'n_baseline': 10},
        'influence_scores': [{'focus': 'X', 't_obs': 0.1, 'attributable': True}],
    }
    blob = json.dumps(legacy)
    loaded = json.loads(blob)
    assert 'ablation_stability' not in loaded['influence_scores'][0]
    assert loaded['baseline_stability']['n_baseline'] == 10


def test_mean_vs_variance_effect_heuristics():
    emb = _cluster(5, [1.0, 0.0, 0.0], noise=0.02, seed=9)
    baseline_stability = compute_baseline_stability(_cluster(10, [1.0, 0.0, 0.0], seed=10))
    stab = compute_ablation_stability(
        emb,
        baseline_stability,
        t_obs=0.4,
        standardized_effect=3.5,
    )
    mv = stab['mean_vs_variance_effect']
    assert mv['semantic_shift_level'] == 'high'
    assert mv['advisory_only'] is True
    assert mv['summary']


def test_categorical_entropy_uniform():
    ent = categorical_entropy({'COMPLIES': 1, 'VIOLATES': 1, 'AMBIGUOUS': 1})
    assert ent == pytest.approx(np.log2(3), rel=1e-6)
