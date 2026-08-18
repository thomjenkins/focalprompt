#!/usr/bin/env python3
"""
Permutation test for subtractive ablation significance.

Null: the n_baseline and n_ablated embeddings for a focus are exchangeable
(no systematic shift from deleting the span). Statistic: cosine distance
between group centroids. One-sided: larger T means more separation.
"""

from __future__ import annotations

from itertools import combinations
from math import comb, sqrt
from typing import Dict, List, Optional, Sequence, Union

import numpy as np

DEFAULT_N_PERMUTATIONS = 10_000
DEFAULT_ALPHA = 0.05
DECILES = (0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100)


def cosine_distance_centroids(
    baseline_embeddings: np.ndarray,
    ablated_embeddings: np.ndarray,
) -> float:
    """
    T = 1 - cosine(mean(baseline), mean(ablated)).

    Pure function of two embedding arrays; used for observed and permuted values.
    Zero-norm centroids yield T = 1 (maximum distance).
    """
    a = np.asarray(baseline_embeddings, dtype=float)
    b = np.asarray(ablated_embeddings, dtype=float)
    if a.ndim != 2 or b.ndim != 2:
        raise ValueError('Embeddings must be 2-D arrays of shape (n_samples, dim).')
    if a.shape[0] < 1 or b.shape[0] < 1:
        raise ValueError('Each arm needs at least one embedding.')
    mu_a = a.mean(axis=0)
    mu_b = b.mean(axis=0)
    na = np.linalg.norm(mu_a)
    nb = np.linalg.norm(mu_b)
    if na == 0.0 or nb == 0.0:
        return 1.0
    sim = float(np.dot(mu_a, mu_b) / (na * nb))
    sim = max(-1.0, min(1.0, sim))
    return 1.0 - sim


def n_label_assignments(n_baseline: int, n_ablated: int) -> int:
    """Number of distinct ways to split pooled embeddings into the original group sizes."""
    n = n_baseline + n_ablated
    if n_baseline < 0 or n_ablated < 0 or n == 0:
        return 0
    return comb(n, n_ablated)


def min_achievable_pvalue(
    n_baseline: int,
    n_ablated: int,
    n_permutations: int = DEFAULT_N_PERMUTATIONS,
) -> float:
    """Smallest p the configured design can report."""
    n_exact = n_label_assignments(n_baseline, n_ablated)
    if n_exact == 0:
        return 1.0
    if n_exact <= n_permutations:
        return 1.0 / n_exact
    return 1.0 / (1.0 + n_permutations)


def _null_summary(stats: np.ndarray) -> Dict:
    stats = np.asarray(stats, dtype=float)
    return {
        'mean': float(np.mean(stats)),
        'std': float(np.std(stats, ddof=1)) if stats.size > 1 else 0.0,
        'p95': float(np.percentile(stats, 95)),
        'deciles': {
            str(d): float(np.percentile(stats, d)) for d in DECILES
        },
    }


def permutation_test(
    baseline_embeddings: np.ndarray,
    ablated_embeddings: np.ndarray,
    n_permutations: int = DEFAULT_N_PERMUTATIONS,
    rng: Optional[Union[int, np.random.Generator]] = None,
) -> Dict:
    """
    One-sided permutation test of centroid cosine distance.

    Monte Carlo p-value: (1 + #{T_perm >= T_obs}) / (1 + n_permutations).
    Exact enumeration (when C(n, k) <= n_permutations): p = #{T >= T_obs} / N
    over all label assignments of the original sizes, identity included.
    """
    A = np.asarray(baseline_embeddings, dtype=float)
    B = np.asarray(ablated_embeddings, dtype=float)
    t_obs = cosine_distance_centroids(A, B)
    n0, n1 = A.shape[0], B.shape[0]
    pooled = np.vstack([A, B])
    n = n0 + n1
    n_exact = n_label_assignments(n0, n1)
    exact = n_exact <= n_permutations

    if exact:
        stats = np.empty(n_exact, dtype=float)
        for i, ablated_idx in enumerate(combinations(range(n), n1)):
            mask = np.zeros(n, dtype=bool)
            mask[list(ablated_idx)] = True
            stats[i] = cosine_distance_centroids(pooled[~mask], pooled[mask])
        count_ge = int(np.sum(stats >= t_obs - 1e-12))
        p_value = count_ge / float(n_exact)
        n_done = n_exact
    else:
        generator = (
            rng if isinstance(rng, np.random.Generator)
            else np.random.default_rng(rng)
        )
        stats = np.empty(n_permutations, dtype=float)
        for i in range(n_permutations):
            order = generator.permutation(n)
            stats[i] = cosine_distance_centroids(
                pooled[order[:n0]], pooled[order[n0:]]
            )
        count_ge = int(np.sum(stats >= t_obs - 1e-12))
        p_value = (1.0 + count_ge) / (1.0 + n_permutations)
        n_done = n_permutations

    summary = _null_summary(stats)
    std = summary['std']
    if std == 0.0:
        standardized = 0.0 if abs(t_obs - summary['mean']) < 1e-15 else float('inf')
    else:
        standardized = (t_obs - summary['mean']) / std

    return {
        't_obs': float(t_obs),
        'p_value': float(p_value),
        'exact': bool(exact),
        'n_permutations': int(n_done),
        'null_mean': summary['mean'],
        'null_std': std,
        'null_p95': summary['p95'],
        'null_deciles': summary['deciles'],
        'standardized_effect': float(standardized),
    }


def benjamini_hochberg(
    p_values: Sequence[float],
    alpha: float = DEFAULT_ALPHA,
) -> List[Dict]:
    """
    BH q-values and significance flags.

    q is the BH-adjusted p-value (step-up, reversed cumulative min).
    significant = q < alpha.
    """
    m = len(p_values)
    if m == 0:
        return []
    p = np.asarray(p_values, dtype=float)
    order = np.argsort(p)
    q = np.empty(m, dtype=float)
    prev = 1.0
    for rank in range(m, 0, -1):
        idx = order[rank - 1]
        q_raw = min(1.0, p[idx] * m / rank)
        prev = min(prev, q_raw)
        q[idx] = prev
    return [
        {
            'p_value': float(p[i]),
            'q_value': float(q[i]),
            'significant': bool(q[i] < alpha),
        }
        for i in range(m)
    ]


def uses_exact_enumeration(
    n_baseline: int,
    n_ablated: int,
    n_permutations: int = DEFAULT_N_PERMUTATIONS,
) -> bool:
    """True when every label assignment fits in the permutation budget."""
    n_exact = n_label_assignments(n_baseline, n_ablated)
    return n_exact > 0 and n_exact <= n_permutations


def design_test_type(
    n_baseline: int,
    n_ablated: int,
    n_permutations: int = DEFAULT_N_PERMUTATIONS,
) -> str:
    """'exact' or 'sampled' — the experiment-level permutation regime."""
    return 'exact' if uses_exact_enumeration(n_baseline, n_ablated, n_permutations) else 'sampled'


def monte_carlo_pvalue_se(
    p: float = 0.05,
    n_permutations: int = DEFAULT_N_PERMUTATIONS,
) -> float:
    """Binomial standard error of a Monte Carlo p-value, evaluated at p."""
    if n_permutations <= 0:
        return 1.0
    return sqrt(float(p) * (1.0 - float(p)) / float(n_permutations))


def power_guardrail(
    n_baseline: int,
    n_ablated: int,
    n_foci: int,
    alpha: float = DEFAULT_ALPHA,
    n_permutations: int = DEFAULT_N_PERMUTATIONS,
) -> Dict:
    """
    Whether this sampling design can produce a p-value small enough to pass
    a Bonferroni-scale stand-in for BH (min p <= alpha / n_foci).

    Used by the API warning and the live configuration preview so they cannot
    disagree. Does not change the permutation test itself.
    """
    n_baseline = int(n_baseline)
    n_ablated = int(n_ablated)
    n_foci = int(n_foci)
    n_permutations = int(n_permutations)
    min_p = min_achievable_pvalue(n_baseline, n_ablated, n_permutations)
    n_assignments = n_label_assignments(n_baseline, n_ablated)
    exact = uses_exact_enumeration(n_baseline, n_ablated, n_permutations)
    if n_foci <= 0:
        return {
            'min_p': min_p,
            'threshold': None,
            'can_reach_significance': None,
            'n_foci': n_foci,
            'n_baseline': n_baseline,
            'n_ablated': n_ablated,
            'n_permutations': n_permutations,
            'alpha': float(alpha),
            'exact': exact,
            'n_assignments': n_assignments,
            'test_type': 'exact' if exact else 'sampled',
        }
    threshold = float(alpha) / n_foci
    can_reach = min_p <= threshold
    return {
        'min_p': min_p,
        'threshold': threshold,
        'can_reach_significance': can_reach,
        'n_foci': n_foci,
        'n_baseline': n_baseline,
        'n_ablated': n_ablated,
        'n_permutations': n_permutations,
        'alpha': float(alpha),
        'exact': exact,
        'n_assignments': n_assignments,
        'test_type': 'exact' if exact else 'sampled',
    }


def power_guardrail_message(
    n_baseline: int,
    n_ablated: int,
    n_foci: int,
    alpha: float = DEFAULT_ALPHA,
    n_permutations: int = DEFAULT_N_PERMUTATIONS,
) -> Optional[str]:
    """Warn if the design cannot reject at alpha after Bonferroni-scale n_foci."""
    info = power_guardrail(
        n_baseline, n_ablated, n_foci, alpha=alpha, n_permutations=n_permutations
    )
    if info['can_reach_significance'] is not False:
        return None
    min_p = info['min_p']
    threshold = info['threshold']
    regime = (
        'exact enumeration' if info['exact'] else f'{n_permutations} permutations'
    )
    return (
        f"Minimum achievable p-value is {min_p:.6g} with n_baseline={n_baseline}, "
        f"n_ablated={n_ablated} "
        f"({regime}). "
        f"That exceeds alpha/n_foci = {alpha}/{n_foci} = {threshold:.6g}, so even a perfect "
        f"separation may not be declared significant after multiple-testing correction. "
        f"Increase n_baseline and/or n_ablated."
    )


def stochastic_temperature_message(temperature) -> str:
    return (
        "Permutation test requires output stochasticity: temperature must be > 0 "
        f"(got {temperature}). Repeated samples of the same prompt must be allowed "
        "to vary; set temperature above 0."
    )


def require_stochastic_temperature(temperature: float) -> None:
    if temperature is None or temperature <= 0:
        raise ValueError(stochastic_temperature_message(temperature))
