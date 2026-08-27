#!/usr/bin/env python3
"""Tests for baseline stability diagnostics."""

import numpy as np
import pytest

from utils.baseline_stability import (
    HEURISTIC_BETWEEN_WITHIN_MULTIMODAL,
    HEURISTIC_P95_TO_MEDIAN_VARIABLE,
    attach_signal_to_noise,
    classify_baseline_stability,
    compute_baseline_stability,
    pairwise_cosine_distances,
    signal_to_noise_ratio,
)


def test_pairwise_empty_for_single_sample():
    emb = np.ones((1, 3))
    assert pairwise_cosine_distances(emb).size == 0


def test_stable_tight_cluster():
    rng = np.random.default_rng(0)
    emb = np.ones((10, 4)) + rng.normal(0, 0.01, (10, 4))
    result = compute_baseline_stability(emb)
    assert result['n_baseline'] == 10
    assert result['mean_pairwise_cosine_distance'] is not None
    assert result['median_pairwise_cosine_distance'] is not None
    assert result['p95_pairwise_cosine_distance'] is not None
    assert result['mean_distance_from_centroid'] is not None
    assert result['p95_distance_from_centroid'] is not None
    assert result['classification']['label'] == 'stable_baseline'
    assert result['disclaimer']
    assert isinstance(result['warnings'], list)


def test_variable_baseline_when_heavy_tail_ratio():
    # One outlier far from a tight cluster → high p95/median with non-tiny median
    cluster = np.tile(np.array([1.0, 0.0, 0.0]), (8, 1))
    cluster += np.random.default_rng(1).normal(0, 0.05, cluster.shape)
    outlier = np.array([[0.0, 1.0, 0.0]])
    emb = np.vstack([cluster, outlier])
    result = compute_baseline_stability(emb)
    assert result['classification']['p95_to_median_pairwise_ratio'] is not None
    # Label is either variable or multimodal; both are non-stable advisories
    assert result['classification']['label'] in (
        'variable_baseline',
        'potentially_multimodal_baseline',
    )
    assert result['classification']['heuristic_p95_to_median_variable'] == HEURISTIC_P95_TO_MEDIAN_VARIABLE


def test_multimodal_advisory_two_modes():
    a = np.zeros((5, 4))
    a[:, 0] = 1.0
    b = np.zeros((5, 4))
    b[:, 1] = 1.0
    result = compute_baseline_stability(np.vstack([a, b]))
    multi = result['multimodality']
    assert multi['advisory_only'] is True
    assert multi['potentially_multimodal'] is True
    assert multi['heuristic_threshold'] == HEURISTIC_BETWEEN_WITHIN_MULTIMODAL
    assert result['classification']['label'] == 'potentially_multimodal_baseline'
    assert result['warnings']


def test_signal_to_noise_descriptive_only():
    assert signal_to_noise_ratio(0.2, 0.1) == pytest.approx(2.0)
    assert signal_to_noise_ratio(0.2, None) is None
    stability = {
        'mean_distance_from_centroid': 0.05,
        'mean_pairwise_cosine_distance': 0.04,
    }
    rows = attach_signal_to_noise(
        [{'focus': 'A', 't_obs': 0.2}, {'focus': 'B', 'influence': 0.01}],
        stability,
    )
    assert rows[0]['signal_to_noise'] == pytest.approx(4.0)
    assert 'not a significance' in rows[0]['signal_to_noise_definition'].lower()
    assert rows[1]['signal_to_noise_note']  # below heuristic


def test_score_from_samples_includes_baseline_stability():
    from unittest.mock import Mock
    from services.ablation_service import AblationService
    from services.embedding_service import EmbeddingService

    prompt = (
        'You are a veterinary triage assistant.\n\n'
        'Always cite the source of any medical claim.'
    )
    foci = [
        {'focus': 'Role', 'prompt_section': 'You are a veterinary triage assistant.', 'is_dynamic': False},
        {'focus': 'Cite', 'prompt_section': 'Always cite the source of any medical claim.', 'is_dynamic': False},
    ]
    provider = Mock()
    emb = Mock(spec=EmbeddingService)
    rng = np.random.default_rng(2)

    def _embed(texts):
        return [rng.normal(0, 1, 6) for _ in texts], len(texts)

    emb.batch_embeddings_with_usage.side_effect = _embed
    svc = AblationService(provider, 'gpt-4o-mini', embedding_service=emb, provider_name='openai')
    result = svc.score_from_samples(
        prompt,
        foci,
        ['b1', 'b2', 'b3', 'b4'],
        {0: ['a1', 'a2'], 1: ['c1', 'c2']},
        n_permutations=40,
        permutation_seed=0,
        temperature=0.7,
    )
    assert 'baseline_stability' in result
    assert 'classification' in result['baseline_stability']
    assert 'signal_to_noise' in result['influence_scores'][0]
    # Backwards-compatible core fields
    assert 'influence_scores' in result
    assert 'significance_method' in result
    assert result['significance_method'] == 'permutation_bh'
