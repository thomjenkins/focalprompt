#!/usr/bin/env python3
"""
Baseline embedding stability / noise diagnostics for leave-one-focus-out ablation.

These metrics describe dispersion among full-prompt (baseline) samples only.
They do not replace the permutation test and are not themselves statistical
significance. Any classification thresholds below are labeled heuristics.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

import numpy as np

# Labeled heuristics — not universal scientific cutoffs. Surfaced in JSON so
# callers can ignore or replace them.
HEURISTIC_P95_TO_MEDIAN_VARIABLE = 2.0
# Ignore p95/median when median is numerically tiny (ratio is unstable near 0).
HEURISTIC_MIN_MEDIAN_PAIRWISE_FOR_VARIABLE = 1e-4
HEURISTIC_BETWEEN_WITHIN_MULTIMODAL = 2.0
HEURISTIC_MIN_CLUSTER_SIZE = 2
HEURISTIC_SNR_LOW = 1.0

DISCLAIMER = (
    'Baseline stability describes dispersion among full-prompt samples only. '
    'It does not replace the permutation test and is not itself statistical '
    'significance. Classification labels use clearly marked heuristics.'
)

VARIABLE_BASELINE_WARNING = (
    'Full-prompt outputs show substantial baseline variation. Failure to detect '
    'an ablation effect may reflect low attribution power rather than absence '
    'of influence.'
)

MULTIMODAL_WARNING = (
    'Baseline embeddings look potentially multimodal (advisory only). '
    'A single centroid distance may mix distinct response modes; interpret '
    'non-significant ablation results with extra caution.'
)


def _as_2d(embeddings: Sequence[Sequence[float]] | np.ndarray) -> np.ndarray:
    arr = np.asarray(embeddings, dtype=float)
    if arr.ndim != 2:
        raise ValueError('embeddings must be a 2-D array of shape (n_samples, dim)')
    if arr.shape[0] < 1:
        raise ValueError('need at least one embedding')
    return arr


def cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    """1 - cosine similarity; 1.0 if either vector has zero norm."""
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 1.0
    sim = float(np.dot(a, b) / (na * nb))
    sim = max(-1.0, min(1.0, sim))
    return 1.0 - sim


def pairwise_cosine_distances(embeddings: np.ndarray) -> np.ndarray:
    """Upper-triangle pairwise cosine distances (length C(n,2))."""
    n = embeddings.shape[0]
    if n < 2:
        return np.asarray([], dtype=float)
    out: List[float] = []
    for i in range(n):
        for j in range(i + 1, n):
            out.append(cosine_distance(embeddings[i], embeddings[j]))
    return np.asarray(out, dtype=float)


def distances_from_centroid(embeddings: np.ndarray) -> np.ndarray:
    centroid = embeddings.mean(axis=0)
    return np.asarray(
        [cosine_distance(row, centroid) for row in embeddings],
        dtype=float,
    )


def _percentile(values: np.ndarray, q: float) -> Optional[float]:
    if values.size == 0:
        return None
    return float(np.percentile(values, q))


def _mean(values: np.ndarray) -> Optional[float]:
    if values.size == 0:
        return None
    return float(np.mean(values))


def _median(values: np.ndarray) -> Optional[float]:
    if values.size == 0:
        return None
    return float(np.median(values))


def advisory_multimodality(embeddings: np.ndarray) -> Dict[str, Any]:
    """
    Conservative 2-mode check on the first principal component.

    Split PC1 scores at the median. Report between/within centroid cosine
    distance ratio. Flag only when both sides have at least
    HEURISTIC_MIN_CLUSTER_SIZE points and the ratio exceeds
    HEURISTIC_BETWEEN_WITHIN_MULTIMODAL. Advisory — not ground truth.
    """
    n = embeddings.shape[0]
    result: Dict[str, Any] = {
        'method': 'pc1_median_split_between_within_ratio',
        'advisory_only': True,
        'potentially_multimodal': False,
        'n_samples': n,
        'cluster_sizes': None,
        'between_centroid_cosine_distance': None,
        'within_mean_cosine_distance': None,
        'between_within_ratio': None,
        'heuristic_threshold': HEURISTIC_BETWEEN_WITHIN_MULTIMODAL,
        'heuristic_min_cluster_size': HEURISTIC_MIN_CLUSTER_SIZE,
        'note': (
            'Conservative PC1 median-split diagnostic. A positive flag is advisory '
            'evidence of possible distinct response modes, not a definitive mixture model.'
        ),
    }
    if n < 2 * HEURISTIC_MIN_CLUSTER_SIZE:
        result['note'] = (
            'Too few baseline samples for the PC1 median-split multimodality check '
            f'(need at least {2 * HEURISTIC_MIN_CLUSTER_SIZE}).'
        )
        return result

    centered = embeddings - embeddings.mean(axis=0, keepdims=True)
    try:
        _u, _s, vt = np.linalg.svd(centered, full_matrices=False)
    except np.linalg.LinAlgError:
        result['note'] = 'SVD failed; multimodality check skipped.'
        return result
    if vt.shape[0] < 1:
        return result
    scores = centered @ vt[0]
    med = float(np.median(scores))
    mask_hi = scores >= med
    if int(mask_hi.sum()) == 0 or int((~mask_hi).sum()) == 0:
        order = np.argsort(scores)
        half = n // 2
        mask_hi = np.zeros(n, dtype=bool)
        mask_hi[order[half:]] = True
    size_a = int((~mask_hi).sum())
    size_b = int(mask_hi.sum())
    result['cluster_sizes'] = [size_a, size_b]
    if size_a < HEURISTIC_MIN_CLUSTER_SIZE or size_b < HEURISTIC_MIN_CLUSTER_SIZE:
        result['note'] = (
            'PC1 median split produced a cluster smaller than '
            f'{HEURISTIC_MIN_CLUSTER_SIZE}; not flagged.'
        )
        return result

    group_a = embeddings[~mask_hi]
    group_b = embeddings[mask_hi]
    cent_a = group_a.mean(axis=0)
    cent_b = group_b.mean(axis=0)
    between = cosine_distance(cent_a, cent_b)
    within_a = float(np.mean([cosine_distance(row, cent_a) for row in group_a]))
    within_b = float(np.mean([cosine_distance(row, cent_b) for row in group_b]))
    within = max(within_a, within_b, 1e-12)
    ratio = between / within
    result['between_centroid_cosine_distance'] = float(between)
    result['within_mean_cosine_distance'] = float(within)
    result['between_within_ratio'] = float(ratio)
    result['potentially_multimodal'] = bool(ratio >= HEURISTIC_BETWEEN_WITHIN_MULTIMODAL)
    return result


def classify_baseline_stability(
    pairwise: np.ndarray,
    from_centroid: np.ndarray,
    multimodality: Mapping[str, Any],
) -> Dict[str, Any]:
    """
    Relative / heuristic labels for UI — not statistical conclusions.

    Priority:
      1. potentially multimodal (advisory)
      2. variable baseline (p95/median pairwise heuristic)
      3. stable baseline (otherwise, when enough pairs exist)
    """
    median_pw = _median(pairwise)
    p95_pw = _percentile(pairwise, 95)
    ratio = None
    if median_pw is not None and median_pw > 1e-12 and p95_pw is not None:
        ratio = float(p95_pw / median_pw)

    potentially_multimodal = bool(multimodality.get('potentially_multimodal'))
    variable = bool(
        ratio is not None
        and ratio >= HEURISTIC_P95_TO_MEDIAN_VARIABLE
        and median_pw is not None
        and median_pw >= HEURISTIC_MIN_MEDIAN_PAIRWISE_FOR_VARIABLE
    )

    if potentially_multimodal:
        label = 'potentially_multimodal_baseline'
        ui_label = 'Potentially multimodal baseline'
        warning = MULTIMODAL_WARNING
    elif variable:
        label = 'variable_baseline'
        ui_label = 'Variable baseline / attribution may be underpowered'
        warning = VARIABLE_BASELINE_WARNING
    elif pairwise.size >= 1:
        label = 'stable_baseline'
        ui_label = 'Stable baseline'
        warning = None
    else:
        label = 'insufficient_samples'
        ui_label = 'Insufficient baseline samples'
        warning = None

    return {
        'label': label,
        'ui_label': ui_label,
        'warning': warning,
        'p95_to_median_pairwise_ratio': ratio,
        'heuristic_p95_to_median_variable': HEURISTIC_P95_TO_MEDIAN_VARIABLE,
        'heuristic_min_median_pairwise_for_variable': HEURISTIC_MIN_MEDIAN_PAIRWISE_FOR_VARIABLE,
        'heuristics_are_labeled_not_universal': True,
        'mean_distance_from_centroid': _mean(from_centroid),
        'median_pairwise_cosine_distance': median_pw,
    }


def compute_baseline_stability(
    embeddings: Sequence[Sequence[float]] | np.ndarray,
) -> Dict[str, Any]:
    """Full baseline_stability payload for experiment JSON."""
    arr = _as_2d(embeddings)
    pairwise = pairwise_cosine_distances(arr)
    from_centroid = distances_from_centroid(arr)
    multi = advisory_multimodality(arr)
    classification = classify_baseline_stability(pairwise, from_centroid, multi)

    return {
        'n_baseline': int(arr.shape[0]),
        'embedding_dim': int(arr.shape[1]),
        'mean_pairwise_cosine_distance': _mean(pairwise),
        'median_pairwise_cosine_distance': _median(pairwise),
        'p95_pairwise_cosine_distance': _percentile(pairwise, 95),
        'mean_distance_from_centroid': _mean(from_centroid),
        'p95_distance_from_centroid': _percentile(from_centroid, 95),
        'multimodality': multi,
        'classification': classification,
        'disclaimer': DISCLAIMER,
        'warnings': [w for w in (classification.get('warning'),) if w],
    }


def signal_to_noise_ratio(
    observed_shift: float,
    baseline_dispersion: Optional[float],
    *,
    eps: float = 1e-12,
) -> Optional[float]:
    """
    Descriptive ratio: ablation centroid shift / baseline dispersion.

    Not a p-value and not a significance claim. ``None`` if dispersion unknown.
    """
    if baseline_dispersion is None:
        return None
    return float(observed_shift) / max(float(baseline_dispersion), eps)


def attach_signal_to_noise(
    influence_items: Sequence[Mapping[str, Any]],
    baseline_stability: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    """Copy influence rows with descriptive signal_to_noise fields added."""
    dispersion = baseline_stability.get('mean_distance_from_centroid')
    if dispersion is None:
        dispersion = baseline_stability.get('mean_pairwise_cosine_distance')
    out: List[Dict[str, Any]] = []
    for item in influence_items:
        row = dict(item)
        t_obs = row.get('t_obs')
        if t_obs is None:
            t_obs = row.get('influence')
        snr = signal_to_noise_ratio(float(t_obs or 0.0), dispersion)
        row['signal_to_noise'] = snr
        row['signal_to_noise_definition'] = (
            'observed_centroid_cosine_distance / baseline_mean_distance_from_centroid; '
            'descriptive only — not a significance test'
        )
        row['signal_to_noise_baseline_dispersion'] = dispersion
        if snr is not None and snr < HEURISTIC_SNR_LOW:
            row['signal_to_noise_note'] = (
                f'Descriptive SNR ({snr:.3f}) is below the labeled heuristic '
                f'{HEURISTIC_SNR_LOW}: observed shift is small relative to baseline '
                'dispersion. This is not a statistical conclusion.'
            )
        else:
            row['signal_to_noise_note'] = None
        out.append(row)
    return out
