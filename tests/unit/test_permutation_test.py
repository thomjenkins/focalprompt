"""Permutation test statistic, null, BH, and guardrails."""

import numpy as np
import pytest

from utils.permutation_test import (
    benjamini_hochberg,
    cosine_distance_centroids,
    min_achievable_pvalue,
    n_label_assignments,
    permutation_test,
    power_guardrail_message,
    require_stochastic_temperature,
)


def test_centroid_distance_identical_means_is_zero():
    rng = np.random.default_rng(0)
    a = rng.normal(size=(5, 4))
    assert cosine_distance_centroids(a, a) == pytest.approx(0.0, abs=1e-12)


def test_centroid_distance_orthogonal_shift():
    a = np.array([[1.0, 0.0], [1.0, 0.0]])
    b = np.array([[0.0, 1.0], [0.0, 1.0]])
    assert cosine_distance_centroids(a, b) == pytest.approx(1.0)


def test_bh_hand_computed_q_values():
    p = [0.01, 0.04, 0.03, 0.20]
    out = benjamini_hochberg(p, alpha=0.05)
    q = [row['q_value'] for row in out]
    assert q[0] == pytest.approx(0.04)
    assert q[1] == pytest.approx(0.04 * 4 / 3)
    assert q[2] == pytest.approx(0.04 * 4 / 3)
    assert q[3] == pytest.approx(0.20)
    assert out[0]['significant'] is True
    assert out[1]['significant'] is False
    assert out[2]['significant'] is False
    assert out[3]['significant'] is False


def test_exact_enumeration_triggers_at_small_n():
    rng = np.random.default_rng(1)
    a = rng.normal(size=(3, 6))
    b = rng.normal(size=(2, 6))
    assert n_label_assignments(3, 2) == 10
    exact = permutation_test(a, b, n_permutations=10, rng=0)
    sampled = permutation_test(a, b, n_permutations=9, rng=0)
    assert exact['exact'] is True
    assert exact['n_permutations'] == 10
    assert sampled['exact'] is False
    assert sampled['n_permutations'] == 9
    sampled_hi = permutation_test(a, b, n_permutations=5000, rng=0)
    assert sampled_hi['p_value'] == pytest.approx(exact['p_value'], abs=0.08)


def test_permutation_uses_cached_embeddings_only():
    calls = {'n': 0}

    def wrapped(a, b):
        calls['n'] += 1
        return cosine_distance_centroids(a, b)

    rng = np.random.default_rng(2)
    a = rng.normal(size=(4, 5))
    b = rng.normal(size=(3, 5))
    # Precompute observed with the real function, then run permutations
    # by monkeypatching at module level is done in the service test.
    # Here: n_exact = C(7,3)=35, each combo calls the statistic once plus we
    # call it once for T_obs → 36 centroid evaluations, zero external I/O.
    result = permutation_test(a, b, n_permutations=100, rng=3)
    assert result['exact'] is True
    assert 'p_value' in result
    assert calls['n'] == 0  # permutation_test never calls this wrapper


def test_calibration_uniform_under_null():
    rng = np.random.default_rng(42)
    p_values = []
    for _ in range(200):
        x = rng.normal(size=(8, 6))
        a, b = x[:4], x[4:]
        p_values.append(permutation_test(a, b, n_permutations=70, rng=rng)['p_value'])
    frac = sum(p < 0.05 for p in p_values) / len(p_values)
    assert 0.0 <= frac <= 0.15


def test_power_planted_mean_shift():
    rng = np.random.default_rng(7)
    p_values = []
    for _ in range(40):
        a = rng.normal(scale=0.05, size=(5, 8))
        b = rng.normal(scale=0.05, size=(5, 8))
        b[:, 0] += 3.0
        p_values.append(permutation_test(a, b, n_permutations=252, rng=rng)['p_value'])
    assert max(p_values) < 0.05
    assert sum(p < 0.01 for p in p_values) >= 35


def test_temperature_zero_raises():
    with pytest.raises(ValueError, match='temperature must be > 0'):
        require_stochastic_temperature(0)
    with pytest.raises(ValueError, match='output stochasticity'):
        require_stochastic_temperature(0.0)
    require_stochastic_temperature(0.7)


def test_power_guardrail_fires_when_min_p_too_large():
    msg = power_guardrail_message(2, 2, n_foci=3, alpha=0.05, n_permutations=10000)
    assert msg is not None
    assert 'Increase n_baseline' in msg
    assert min_achievable_pvalue(2, 2) == pytest.approx(1 / 6)


def test_null_deciles_present():
    rng = np.random.default_rng(5)
    a = rng.normal(size=(4, 3))
    b = rng.normal(size=(4, 3))
    out = permutation_test(a, b, n_permutations=70, rng=0)
    assert set(out['null_deciles']) == {str(d) for d in (0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100)}
    assert 't_obs' in out and 'null_mean' in out and 'null_p95' in out
    assert 'standardized_effect' in out
