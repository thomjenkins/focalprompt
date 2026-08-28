#!/usr/bin/env python3
"""
Statistics for focus order / position sensitivity experiments.

Compares reordered-prompt outputs against an unchanged baseline sample set.
Ratios are descriptive — not p-values or significance claims.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

import numpy as np

from utils.baseline_stability import (
    compute_baseline_stability,
    distances_from_centroid,
    pairwise_cosine_distances,
    signal_to_noise_ratio,
)
from utils.permutation_test import cosine_distance_centroids, permutation_test


def _percentile(values: np.ndarray, q: float) -> Optional[float]:
    if values.size == 0:
        return None
    return float(np.percentile(values, q))


def compare_condition_to_baseline(
    baseline_embeddings: np.ndarray,
    condition_embeddings: np.ndarray,
    baseline_stability: Mapping[str, Any],
    *,
    n_permutations: int = 10_000,
    permutation_seed: Optional[int] = None,
) -> Dict[str, Any]:
    """Semantic displacement of a condition vs shared baseline + descriptive SNR."""
    base = np.asarray(baseline_embeddings, dtype=float)
    cond = np.asarray(condition_embeddings, dtype=float)
    t_obs = cosine_distance_centroids(base, cond)
    dispersion = baseline_stability.get('mean_distance_from_centroid')
    if dispersion is None:
        dispersion = baseline_stability.get('mean_pairwise_cosine_distance')
    snr = signal_to_noise_ratio(t_obs, dispersion)
    perm = permutation_test(
        base,
        cond,
        n_permutations=n_permutations,
        rng=permutation_seed,
    )
    cond_pairwise = pairwise_cosine_distances(cond)
    cond_from_centroid = distances_from_centroid(cond)
    return {
        't_obs': float(t_obs),
        'semantic_displacement': float(t_obs),
        'relative_to_baseline_noise': snr,
        'relative_to_baseline_noise_note': (
            'observed_centroid_cosine_distance / baseline_mean_distance_from_centroid; '
            'descriptive ratio — not a p-value or significance claim'
        ),
        'p_value': perm['p_value'],
        'permutation_test': {
            'exact': perm['exact'],
            'n_permutations': perm['n_permutations'],
            'null_mean': perm['null_mean'],
            'null_p95': perm['null_p95'],
            'standardized_effect': perm['standardized_effect'],
        },
        'condition_dispersion': {
            'mean_pairwise_cosine_distance': float(np.mean(cond_pairwise))
            if cond_pairwise.size
            else None,
            'median_pairwise_cosine_distance': float(np.median(cond_pairwise))
            if cond_pairwise.size
            else None,
            'p95_pairwise_cosine_distance': _percentile(cond_pairwise, 95),
            'mean_distance_from_centroid': float(np.mean(cond_from_centroid))
            if cond_from_centroid.size
            else None,
        },
    }


def summarize_global_order_experiment(
    permutation_results: Sequence[Mapping[str, Any]],
    baseline_stability: Mapping[str, Any],
) -> Dict[str, Any]:
    """Aggregate global order permutation statistics."""
    displacements = np.asarray(
        [float(r.get('semantic_displacement') or r.get('t_obs') or 0.0) for r in permutation_results],
        dtype=float,
    )
    ratios = [
        r.get('relative_to_baseline_noise')
        for r in permutation_results
        if r.get('relative_to_baseline_noise') is not None
    ]
    ratio_arr = np.asarray(ratios, dtype=float) if ratios else np.asarray([], dtype=float)
    baseline_disp = baseline_stability.get('mean_distance_from_centroid')
    summary: Dict[str, Any] = {
        'n_permutations': len(permutation_results),
        'baseline_stability': baseline_stability,
        'baseline_dispersion_reference': baseline_disp,
        'displacement': {
            'mean': float(np.mean(displacements)) if displacements.size else None,
            'median': float(np.median(displacements)) if displacements.size else None,
            'p95': _percentile(displacements, 95),
            'min': float(np.min(displacements)) if displacements.size else None,
            'max': float(np.max(displacements)) if displacements.size else None,
        },
        'relative_to_baseline_noise': {
            'mean': float(np.mean(ratio_arr)) if ratio_arr.size else None,
            'median': float(np.median(ratio_arr)) if ratio_arr.size else None,
            'p95': _percentile(ratio_arr, 95),
        },
        'interpretation_notes': [
            (
                'Global permutations change many focus positions simultaneously. '
                'Association between position and displacement is exploratory — not causal.'
            ),
            (
                'Order-noise ratios compare centroid displacement to baseline dispersion. '
                'They are not p-values.'
            ),
        ],
    }
    if ratio_arr.size and baseline_disp:
        med_ratio = float(np.median(ratio_arr))
        if med_ratio >= 1.0:
            summary['advisory_label'] = 'order_sensitive'
            summary['advisory_ui'] = (
                'Changing focus order introduced behavioural variation beyond typical '
                'baseline dispersion (descriptive median ratio ≥ 1).'
            )
        else:
            summary['advisory_label'] = 'order_effect_small_vs_baseline'
            summary['advisory_ui'] = (
                'Sampled order permutations showed displacement similar to or below '
                'baseline dispersion (descriptive median ratio < 1).'
            )
    return summary


def position_association_analysis(
    permutation_results: Sequence[Mapping[str, Any]],
    focus_name: str,
) -> Dict[str, Any]:
    """
    Exploratory association between a focus's slot position and displacement.

    NOT causal — global permutations move many foci at once.
    """
    rows: List[Dict[str, Any]] = []
    for row in permutation_results:
        positions = row.get('focus_positions') or {}
        if focus_name not in positions:
            continue
        rows.append({
            'position': int(positions[focus_name]),
            'displacement': float(row.get('semantic_displacement') or row.get('t_obs') or 0.0),
        })
    if len(rows) < 3:
        return {
            'focus': focus_name,
            'method': 'rank_correlation_exploratory',
            'n': len(rows),
            'note': 'Too few permutations for exploratory position association.',
            'advisory_only': True,
        }
    positions = np.asarray([r['position'] for r in rows], dtype=float)
    displacements = np.asarray([r['displacement'] for r in rows], dtype=float)
    # Spearman via rank correlation (no scipy dependency)
    pos_rank = positions.argsort().argsort().astype(float)
    disp_rank = displacements.argsort().argsort().astype(float)
    if np.std(pos_rank) < 1e-12 or np.std(disp_rank) < 1e-12:
        rho = 0.0
    else:
        rho = float(np.corrcoef(pos_rank, disp_rank)[0, 1])
    return {
        'focus': focus_name,
        'method': 'spearman_rank_correlation_exploratory',
        'n': len(rows),
        'rho': rho,
        'advisory_only': True,
        'note': (
            'Exploratory association from global permutations where many foci move '
            'simultaneously — not evidence that position alone caused displacement.'
        ),
        'samples': rows,
    }


def summarize_position_sweep(
    sweep_results: Sequence[Mapping[str, Any]],
    baseline_stability: Mapping[str, Any],
    focus_name: str,
) -> Dict[str, Any]:
    """Summarize controlled single-focus position sweep."""
    displacements = [
        float(r.get('semantic_displacement') or r.get('t_obs') or 0.0) for r in sweep_results
    ]
    arr = np.asarray(displacements, dtype=float)
    ratios = [
        r.get('relative_to_baseline_noise')
        for r in sweep_results
        if r.get('relative_to_baseline_noise') is not None
    ]
    ratio_arr = np.asarray(ratios, dtype=float) if ratios else np.asarray([], dtype=float)
    return {
        'focus': focus_name,
        'method': 'controlled_single_focus_position_sweep',
        'n_positions_tested': len(sweep_results),
        'baseline_stability': baseline_stability,
        'displacement_by_position': [
            {
                'slot_index': r.get('slot_index'),
                'ordered_focus_names': r.get('ordered_focus_names'),
                'semantic_displacement': r.get('semantic_displacement'),
                'relative_to_baseline_noise': r.get('relative_to_baseline_noise'),
            }
            for r in sweep_results
        ],
        'displacement': {
            'mean': float(np.mean(arr)) if arr.size else None,
            'median': float(np.median(arr)) if arr.size else None,
            'p95': _percentile(arr, 95),
        },
        'relative_to_baseline_noise': {
            'mean': float(np.mean(ratio_arr)) if ratio_arr.size else None,
            'median': float(np.median(ratio_arr)) if ratio_arr.size else None,
            'p95': _percentile(ratio_arr, 95),
        },
        'interpretation_note': (
            'Controlled positional intervention: only the selected focus moves; '
            'relative order of other movable foci is preserved. Stronger evidence '
            'about this focus than global permutation associations.'
        ),
    }


def behavioral_outcome_distribution(
    judgments: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Count COMPLIES / AMBIGUOUS / VIOLATES classifications."""
    counts: Dict[str, int] = {'COMPLIES': 0, 'AMBIGUOUS': 0, 'VIOLATES': 0, 'OTHER': 0}
    for row in judgments:
        label = str(row.get('classification') or row.get('label') or 'OTHER').upper()
        if label not in counts:
            counts['OTHER'] += 1
        else:
            counts[label] += 1
    total = sum(counts.values())
    return {
        'counts': counts,
        'n': total,
        'fractions': {k: (v / total if total else 0.0) for k, v in counts.items()},
    }


def compare_behavioral_distributions(
    baseline_judgments: Sequence[Mapping[str, Any]],
    condition_judgments: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """
    Descriptive comparison of categorical behavioural outcomes.

    Uses Fisher's exact test when sample sizes are small (2x3 table collapsed to
    complies vs not-complies if needed). Advisory — judge is not ground truth.
    """
    base_dist = behavioral_outcome_distribution(baseline_judgments)
    cond_dist = behavioral_outcome_distribution(condition_judgments)

    def _complies_rate(dist: Mapping[str, Any]) -> float:
        counts = dist.get('counts') or {}
        n = dist.get('n') or 0
        if not n:
            return 0.0
        return float(counts.get('COMPLIES', 0)) / float(n)

    result: Dict[str, Any] = {
        'baseline': base_dist,
        'condition': cond_dist,
        'baseline_complies_rate': _complies_rate(base_dist),
        'condition_complies_rate': _complies_rate(cond_dist),
        'advisory_only': True,
        'note': 'LLM behavioural criterion judgments are not ground truth.',
    }

    # Fisher exact on complies vs non-complies (2x2) when possible
    try:
        from math import comb

        def _binary_counts(judgments: Sequence[Mapping[str, Any]]) -> List[int]:
            complies = 0
            non = 0
            for row in judgments:
                label = str(row.get('classification') or '').upper()
                if label == 'COMPLIES':
                    complies += 1
                else:
                    non += 1
            return [complies, non]

        a = _binary_counts(baseline_judgments)
        b = _binary_counts(condition_judgments)
        if sum(a) >= 2 and sum(b) >= 2:

            def _hypergeom(a0, a1, b0, b1):
                n = a0 + a1
                m = b0 + b1
                # Fisher exact for 2x2: [[a0,a1],[b0,b1]]
                row1 = a0 + a1
                col1 = a0 + b0
                total = row1 + b0 + b1 - a0  # n + m? fix
                total = a0 + a1 + b0 + b1
                # enumerate
                p_obs = (
                    comb(col1, a0)
                    * comb(total - col1, a1)
                    / comb(total, row1)
                )
                pvals = []
                for x in range(max(0, col1 - b1), min(row1, col1) + 1):
                    y = row1 - x
                    z0 = col1 - x
                    z1 = b0 + b1 - z0
                    if y < 0 or z1 < 0:
                        continue
                    p = comb(col1, x) * comb(total - col1, y) / comb(total, row1)
                    if p <= p_obs + 1e-15:
                        pvals.append(p)
                result['fisher_exact_complies_vs_other'] = {
                    'table': {'baseline': a, 'condition': b},
                    'p_value_one_sided_greater_complies_in_condition': min(1.0, sum(pvals)),
                    'method': 'fisher_exact_2x2_complies_vs_other',
                }
    except Exception:
        pass

    return result


def focus_positions_from_assignment(
    template: Mapping[str, Any],
    assignment: Sequence[int],
) -> Dict[str, int]:
    """Map focus name → slot index for a given assignment."""
    names = list(template.get('movable_focus_names') or [])
    positions: Dict[str, int] = {}
    for slot_i, movable_i in enumerate(assignment):
        if 0 <= int(movable_i) < len(names):
            positions[names[int(movable_i)]] = int(slot_i)
    return positions
