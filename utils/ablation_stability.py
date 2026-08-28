#!/usr/bin/env python3
"""
Per-focus ablation-condition stability (dispersion) for LOO experiments.

Measures how variable outputs become when each focus is removed, compared to
unchanged baseline dispersion. Behavioural / distributional — not mechanistic
attention and not causal variance decomposition.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from utils.baseline_stability import (
    HEURISTIC_MIN_CLUSTER_SIZE,
    advisory_multimodality,
    compute_baseline_stability,
    distances_from_centroid,
    pairwise_cosine_distances,
)

VALID_CLASSIFICATIONS = ('COMPLIES', 'AMBIGUOUS', 'VIOLATES')

# Labeled heuristics — surfaced in JSON, not universal cutoffs.
NEAR_ZERO_BASELINE_DISPERSION = 1e-6
RECOMMENDED_MIN_ABLATION_SAMPLES = 10
DEFAULT_SAMPLE_SIZE_WARN_BELOW = 10
HEURISTIC_RATIO_MORE_STABLE = 0.85
HEURISTIC_RATIO_MORE_VARIABLE = 1.15
HEURISTIC_HIGH_SEMANTIC_Z = 2.0
HEURISTIC_MODERATE_SEMANTIC_Z = 0.5


def _as_2d(embeddings: Sequence[Sequence[float]] | np.ndarray) -> np.ndarray:
    arr = np.asarray(embeddings, dtype=float)
    if arr.ndim != 2 or arr.shape[0] < 1:
        raise ValueError('embeddings must be a non-empty 2-D array')
    return arr


def _mean(values: np.ndarray) -> Optional[float]:
    if values.size == 0:
        return None
    return float(np.mean(values))


def _median(values: np.ndarray) -> Optional[float]:
    if values.size == 0:
        return None
    return float(np.median(values))


def _percentile(values: np.ndarray, q: float) -> Optional[float]:
    if values.size == 0:
        return None
    return float(np.percentile(values, q))


def compute_dispersion_metrics(
    embeddings: Sequence[Sequence[float]] | np.ndarray,
) -> Dict[str, Any]:
    """Pairwise and centroid dispersion for one condition (baseline or ablated)."""
    arr = _as_2d(embeddings)
    pairwise = pairwise_cosine_distances(arr)
    from_centroid = distances_from_centroid(arr)
    return {
        'n_samples': int(arr.shape[0]),
        'mean_pairwise_distance': _mean(pairwise),
        'median_pairwise_distance': _median(pairwise),
        'p95_pairwise_distance': _percentile(pairwise, 95),
        'mean_centroid_distance': _mean(from_centroid),
        'p95_centroid_distance': _percentile(from_centroid, 95),
    }


def _safe_ratio(
    numerator: Optional[float],
    denominator: Optional[float],
    *,
    label: str,
) -> Tuple[Optional[float], str, Optional[str]]:
    if numerator is None or denominator is None:
        return None, 'missing_data', f'{label}: missing dispersion value.'
    if abs(float(denominator)) < NEAR_ZERO_BASELINE_DISPERSION:
        return (
            None,
            'baseline_near_zero',
            f'{label}: baseline dispersion near zero; ratio is not meaningful.',
        )
    return float(numerator) / float(denominator), 'ok', None


def interpret_dispersion_ratio(ratio: Optional[float]) -> Optional[str]:
    """Conservative UI copy for ablation/baseline dispersion ratio."""
    if ratio is None:
        return None
    if ratio < HEURISTIC_RATIO_MORE_STABLE:
        return 'Outputs were more stable after this focus was removed.'
    if ratio > HEURISTIC_RATIO_MORE_VARIABLE:
        return 'Outputs were more variable after this focus was removed.'
    return 'Output variability was similar to baseline.'


def ablated_multimodality_advisory(
    embeddings: Sequence[Sequence[float]] | np.ndarray,
) -> Dict[str, Any]:
    """Same PC1 advisory as baseline, with explicit insufficient-sample status."""
    arr = _as_2d(embeddings)
    n = int(arr.shape[0])
    if n < 2 * HEURISTIC_MIN_CLUSTER_SIZE:
        return {
            'status': 'insufficient_samples',
            'advisory_only': True,
            'potentially_multimodal': False,
            'n_samples': n,
            'method': 'pc1_median_split_between_within_ratio',
            'note': (
                f'Too few ablated samples ({n}) for the advisory multimodality check '
                f'(need at least {2 * HEURISTIC_MIN_CLUSTER_SIZE}).'
            ),
        }
    multi = advisory_multimodality(arr)
    multi['status'] = 'computed'
    return multi


def _semantic_shift_level(
    *,
    t_obs: Optional[float],
    standardized_effect: Optional[float],
) -> str:
    z = standardized_effect
    if z is not None and math.isfinite(float(z)):
        az = abs(float(z))
        if az >= HEURISTIC_HIGH_SEMANTIC_Z:
            return 'high'
        if az >= HEURISTIC_MODERATE_SEMANTIC_Z:
            return 'moderate'
        return 'low'
    if t_obs is not None and float(t_obs) > 0:
        return 'moderate'
    return 'low'


def describe_mean_vs_variance_effect(
    *,
    t_obs: Optional[float],
    standardized_effect: Optional[float],
    mean_pairwise_noise_ratio: Optional[float],
) -> Dict[str, Any]:
    """
    Descriptive pairing of semantic steering vs stability change.

    Not a hard scientific classification.
    """
    semantic = _semantic_shift_level(
        t_obs=t_obs, standardized_effect=standardized_effect
    )
    if mean_pairwise_noise_ratio is None:
        stability = 'unknown'
        summary = (
            'Semantic perturbation was measured; ablation/baseline dispersion ratio '
            'is not available for this focus.'
        )
    elif mean_pairwise_noise_ratio < HEURISTIC_RATIO_MORE_STABLE:
        stability = 'more_stable_after_ablation'
        if semantic == 'high':
            summary = (
                'Removing this focus affected both trajectory and output stability '
                '(high semantic shift with lower ablated dispersion).'
            )
        elif semantic == 'low':
            summary = (
                'Removing this focus made outputs more consistent despite limited '
                'average semantic movement.'
            )
        else:
            summary = (
                'Removing this focus made outputs more consistent; semantic shift was moderate.'
            )
    elif mean_pairwise_noise_ratio > HEURISTIC_RATIO_MORE_VARIABLE:
        stability = 'more_variable_after_ablation'
        if semantic == 'high':
            summary = (
                'Outputs shifted substantially and became more variable after removal.'
            )
        elif semantic == 'low':
            summary = (
                'Removing this focus made outputs less stable despite limited average '
                'semantic movement.'
            )
        else:
            summary = (
                'Removing this focus increased output variability with moderate semantic shift.'
            )
    else:
        stability = 'similar_to_baseline'
        if semantic == 'high':
            summary = (
                'Focus appears to steer behaviour without materially changing output '
                'variability.'
            )
        elif semantic == 'low':
            summary = 'Little detectable effect on semantic shift or output variability.'
        else:
            summary = (
                'Semantic shift was moderate while output variability stayed near baseline.'
            )

    return {
        'semantic_shift_level': semantic,
        'stability_effect': stability,
        'summary': summary,
        'heuristic_thresholds': {
            'ratio_more_stable_below': HEURISTIC_RATIO_MORE_STABLE,
            'ratio_more_variable_above': HEURISTIC_RATIO_MORE_VARIABLE,
            'high_semantic_z_at_least': HEURISTIC_HIGH_SEMANTIC_Z,
            'moderate_semantic_z_at_least': HEURISTIC_MODERATE_SEMANTIC_Z,
        },
        'advisory_only': True,
        'disclaimer': (
            'Descriptive summary only — not causal attribution of variance to this focus.'
        ),
    }


def categorical_entropy(counts: Mapping[str, int]) -> Optional[float]:
    """Shannon entropy (bits) of a categorical distribution."""
    total = sum(int(v) for v in counts.values())
    if total <= 0:
        return None
    ent = 0.0
    for c in counts.values():
        if c <= 0:
            continue
        p = c / total
        ent -= p * math.log2(p)
    return float(ent)


def summarize_behavioral_outcomes(
    judgments: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Counts, proportions, and entropy for COMPLIES/AMBIGUOUS/VIOLATES judgments."""
    counts = {k: 0 for k in VALID_CLASSIFICATIONS}
    for row in judgments or []:
        cls = str(row.get('classification') or 'AMBIGUOUS').upper()
        if cls not in counts:
            cls = 'AMBIGUOUS'
        counts[cls] += 1
    total = sum(counts.values())
    proportions = {
        k: (counts[k] / total if total else 0.0) for k in VALID_CLASSIFICATIONS
    }
    return {
        'n_samples': total,
        'counts': counts,
        'proportions': proportions,
        'outcome_entropy_bits': categorical_entropy(counts),
        'disclaimer': (
            'Task-specific behavioural outcome distribution from LLM criterion judge — '
            'complementary to embedding dispersion, not a replacement.'
        ),
    }


def compare_behavioral_outcomes(
    baseline_judgments: Sequence[Mapping[str, Any]],
    ablated_judgments: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    base = summarize_behavioral_outcomes(baseline_judgments)
    abl = summarize_behavioral_outcomes(ablated_judgments)
    base_ent = base.get('outcome_entropy_bits')
    abl_ent = abl.get('outcome_entropy_bits')
    delta = None
    if base_ent is not None and abl_ent is not None:
        delta = float(abl_ent) - float(base_ent)
    return {
        'baseline': base,
        'ablated': abl,
        'outcome_entropy_delta_bits': delta,
        'interpretation_note': (
            'Delta in outcome entropy compares categorical spread of criterion labels. '
            'Lower entropy can mean a more concentrated behavioural mode.'
        ),
    }


def compute_ablation_stability(
    ablated_embeddings: Sequence[Sequence[float]] | np.ndarray,
    baseline_stability: Mapping[str, Any],
    *,
    n_ablated_configured: Optional[int] = None,
    behavioral_outcome: Optional[Mapping[str, Any]] = None,
    t_obs: Optional[float] = None,
    standardized_effect: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Full per-focus ablation_stability payload.

    Compares ablated-condition dispersion to global baseline_stability.
    """
    metrics = compute_dispersion_metrics(ablated_embeddings)
    n = metrics['n_samples']
    base_mp = baseline_stability.get('mean_pairwise_cosine_distance')
    base_mc = baseline_stability.get('mean_distance_from_centroid')

    mp_ratio, mp_status, mp_note = _safe_ratio(
        metrics.get('mean_pairwise_distance'),
        base_mp,
        label='mean_pairwise_noise_ratio',
    )
    mc_ratio, mc_status, mc_note = _safe_ratio(
        metrics.get('mean_centroid_distance'),
        base_mc,
        label='centroid_noise_ratio',
    )

    mp_delta = None
    if metrics.get('mean_pairwise_distance') is not None and base_mp is not None:
        mp_delta = float(metrics['mean_pairwise_distance']) - float(base_mp)
    mc_delta = None
    if metrics.get('mean_centroid_distance') is not None and base_mc is not None:
        mc_delta = float(metrics['mean_centroid_distance']) - float(base_mc)

    ratio_warnings = [w for w in (mp_note, mc_note) if w]
    sample_size_warning = n < DEFAULT_SAMPLE_SIZE_WARN_BELOW
    sample_size_note = None
    if sample_size_warning:
        sample_size_note = (
            f'Ablation stability is estimated from only {n} sample(s). '
            'Dispersion ratios may be unstable; increase ablation sample count '
            f'({RECOMMENDED_MIN_ABLATION_SAMPLES}+ recommended) for stronger inference.'
        )

    multimodality = ablated_multimodality_advisory(ablated_embeddings)
    combined = describe_mean_vs_variance_effect(
        t_obs=t_obs,
        standardized_effect=standardized_effect,
        mean_pairwise_noise_ratio=mp_ratio,
    )

    payload: Dict[str, Any] = {
        **metrics,
        'baseline_mean_pairwise_distance': base_mp,
        'baseline_mean_centroid_distance': base_mc,
        'mean_pairwise_noise_ratio': mp_ratio,
        'centroid_noise_ratio': mc_ratio,
        'mean_pairwise_noise_ratio_status': mp_status,
        'centroid_noise_ratio_status': mc_status,
        'mean_pairwise_noise_delta': mp_delta,
        'centroid_noise_delta': mc_delta,
        'dispersion_ratio_interpretation': interpret_dispersion_ratio(mp_ratio),
        'dispersion_ratio_warnings': ratio_warnings,
        'sample_size_warning': sample_size_warning,
        'sample_size_note': sample_size_note,
        'recommended_min_samples': RECOMMENDED_MIN_ABLATION_SAMPLES,
        'n_ablated_configured': n_ablated_configured,
        'multimodality': multimodality,
        'mean_vs_variance_effect': combined,
        'terminology_note': (
            'Ablation stability describes within-condition output dispersion after '
            'removing this focus — not causal noise contribution or attention variance.'
        ),
        'inferential_dispersion_test': {
            'implemented': False,
            'note': (
                'Dispersion ratios and deltas are descriptive only in this version. '
                'Semantic perturbation p/q values do not test variance changes.'
            ),
        },
    }
    if behavioral_outcome is not None:
        payload['behavioral_outcome'] = behavioral_outcome
    return payload


def build_stability_scatter_points(
    influence_scores: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    """2-D scatter data: semantic shift (x) vs ablation/baseline dispersion ratio (y)."""
    points: List[Dict[str, Any]] = []
    for item in influence_scores or []:
        if not item.get('attributable', True):
            continue
        stab = item.get('ablation_stability') or {}
        sem = item.get('semantic_perturbation') or {}
        y = stab.get('mean_pairwise_noise_ratio')
        if y is None:
            y = stab.get('centroid_noise_ratio')
        points.append({
            'focus': item.get('focus') or item.get('focus_name'),
            'focus_index': item.get('focus_index'),
            'x_semantic_shift': item.get('t_obs'),
            'x_standardized_effect': item.get('standardized_effect'),
            'x_normalized_influence': item.get('normalized_influence'),
            'y_dispersion_ratio': y,
            'y_reference_line': 1.0,
            'q_value': item.get('q_value'),
            'p_value': item.get('p_value'),
            'is_significant': item.get('is_significant'),
            'baseline_mean_pairwise_distance': stab.get('baseline_mean_pairwise_distance'),
            'ablated_mean_pairwise_distance': stab.get('mean_pairwise_distance'),
            'baseline_mean_centroid_distance': stab.get('baseline_mean_centroid_distance'),
            'ablated_mean_centroid_distance': stab.get('mean_centroid_distance'),
            'n_ablated_samples': stab.get('n_samples'),
            'semantic_perturbation': sem,
            'ablation_stability': stab,
        })
    return points


def _rank_foci(
    items: Sequence[Mapping[str, Any]],
    key_fn,
    *,
    reverse: bool = True,
    limit: int = 3,
) -> List[Dict[str, Any]]:
    scored: List[Tuple[float, Dict[str, Any]]] = []
    for item in items:
        val = key_fn(item)
        if val is None:
            continue
        scored.append((float(val), item))
    scored.sort(key=lambda t: t[0], reverse=reverse)
    out = []
    for val, item in scored[:limit]:
        out.append({
            'focus': item.get('focus') or item.get('focus_name'),
            'focus_index': item.get('focus_index'),
            'value': val,
        })
    return out


def build_stability_summary(
    influence_scores: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Experiment-level descriptive rankings (wording: effect after ablation)."""
    rows = [dict(r) for r in influence_scores if r.get('attributable', True)]

    def stab(item):
        return (item.get('ablation_stability') or {}).get('mean_pairwise_noise_ratio')

    def semantic(item):
        return item.get('t_obs')

    def joint(item):
        s = stab(item)
        t = semantic(item)
        if s is None or t is None:
            return None
        return abs(float(t)) * abs(float(s) - 1.0)

    return {
        'most_stabilizing_after_ablation': _rank_foci(
            rows, stab, reverse=False
        ),
        'most_destabilizing_after_ablation': _rank_foci(rows, stab, reverse=True),
        'largest_semantic_shift': _rank_foci(rows, semantic, reverse=True),
        'largest_joint_shift_and_stability_change': _rank_foci(
            rows, joint, reverse=True
        ),
        'wording_note': (
            '"Most stabilizing after ablation" means ablated outputs became more stable, '
            'not that the removed focus was proven to cause baseline noise.'
        ),
        'disclaimer': (
            'Rankings are descriptive heuristics over this run — not causal attribution.'
        ),
    }


def attach_ablation_stability_to_results(
    ablation_results: List[Dict[str, Any]],
    influence_scores: List[Dict[str, Any]],
    baseline_stability: Mapping[str, Any],
    *,
    n_ablated: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    """
    Merge ablation_stability into parallel ablation_results / influence_scores lists.

    ``influence_scores`` must already include semantic enrichment fields where applicable.
    """
    by_index = {int(r['focus_index']): r for r in influence_scores if r.get('focus_index') is not None}
    new_ablation: List[Dict[str, Any]] = []
    new_influence: List[Dict[str, Any]] = []

    for row in ablation_results:
        r = dict(row)
        idx = r.get('focus_index')
        if r.get('attributable') and idx in by_index:
            inf = by_index[int(idx)]
            emb_key = '_ablation_embeddings'
            embeddings = r.pop(emb_key, None)
            if embeddings is not None:
                stab = compute_ablation_stability(
                    embeddings,
                    baseline_stability,
                    n_ablated_configured=n_ablated,
                    t_obs=inf.get('t_obs'),
                    standardized_effect=inf.get('standardized_effect'),
                    behavioral_outcome=inf.get('behavioral_outcome'),
                )
                r['ablation_stability'] = stab
                inf = dict(inf)
                inf['ablation_stability'] = stab
                by_index[int(idx)] = inf
        new_ablation.append(r)

    for inf in influence_scores:
        idx = inf.get('focus_index')
        merged = dict(by_index.get(int(idx), inf)) if idx is not None else dict(inf)
        merged.pop('_ablation_embeddings', None)
        new_influence.append(merged)

    summary = build_stability_summary(new_influence)
    scatter = build_stability_scatter_points(new_influence)
    experiment = {
        'stability_summary': summary,
        'stability_scatter': scatter,
        'interpretation_axes': {
            'x': 'Semantic perturbation (centroid cosine distance / standardized effect)',
            'y': 'Ablation-to-baseline mean pairwise dispersion ratio (y=1 unchanged)',
            'y_reference': 1.0,
            'note': (
                'Vertical distance from 1 is not statistical significance of a '
                'variance change.'
            ),
        },
    }
    return new_ablation, new_influence, experiment
