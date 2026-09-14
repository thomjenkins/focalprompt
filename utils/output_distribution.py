"""Exploratory clustering of baseline outputs; never a significance test."""

import numpy as np

from utils.baseline_stability import compute_baseline_stability


def describe_output_distribution(embeddings):
    vectors = np.asarray(embeddings, dtype=float)
    if vectors.ndim != 2 or not vectors.shape[0] or not vectors.shape[1]:
        raise ValueError('Expected non-empty 2-D embeddings.')
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    if not np.isfinite(vectors).all() or (norms <= 0).any():
        raise ValueError('Embeddings must be finite, nonzero vectors.')
    unit = vectors / norms
    distances = np.clip(1 - unit @ unit.T, 0, 2)
    np.fill_diagonal(distances, 0)
    n = len(unit)
    groups = [[i] for i in range(n)]
    candidates = []
    # Average-link agglomeration is deterministic, permits uneven clusters and
    # explores >2 modes. Disallow singleton "modes" and tiny absolute separations.
    while len(groups) > 1:
        if 2 <= len(groups) <= min(5, n // 2) and min(map(len, groups)) >= 2:
            silhouettes = []
            within, between = [], []
            for group in groups:
                others = [g for g in groups if g is not group]
                for i in group:
                    a = float(np.mean([distances[i, j] for j in group if j != i]))
                    b = min(float(np.mean(distances[i, g])) for g in others)
                    within.append(a)
                    between.append(b)
                    silhouettes.append((b - a) / max(a, b, 1e-12))
            candidates.append({
                'groups': [g[:] for g in groups], 'k': len(groups),
                'silhouette': float(np.mean(silhouettes)),
                'mean_within_distance': float(np.mean(within)),
                'mean_nearest_between_distance': float(np.mean(between)),
            })
        _, a, b = min(
            (float(distances[np.ix_(groups[i], groups[j])].mean()), i, j)
            for i in range(len(groups)) for j in range(i + 1, len(groups))
        )
        groups[a] = sorted(groups[a] + groups[b])
        groups.pop(b)
    eligible = [c for c in candidates if c['silhouette'] >= 0.5
                and c['mean_nearest_between_distance'] - c['mean_within_distance'] >= 0.01
                and c['mean_nearest_between_distance'] >= 2 * c['mean_within_distance']]
    best = max(eligible, key=lambda c: (c['silhouette'], -c['k'])) if eligible else None
    groups = sorted(best['groups'], key=lambda g: g[0]) if best else [list(range(n))]
    clusters = []
    membership = [0] * n
    for cluster_id, group in enumerate(groups):
        medoid = min(group, key=lambda i: float(distances[i, group].mean()))
        clusters.append({'cluster_id': cluster_id, 'output_indices': group,
                         'size': len(group), 'representative_output_index': medoid})
        for i in group:
            membership[i] = cluster_id
    centered = unit - unit.mean(axis=0)
    u, singular, _vt = np.linalg.svd(centered, full_matrices=False)
    coordinates = np.zeros((n, 2))
    axes = min(2, len(singular))
    coordinates[:, :axes] = u[:, :axes] * singular[:axes]
    return {
        'baseline_stability': compute_baseline_stability(vectors),
        'output_distribution': {
            'method': 'average_link_cosine_silhouette', 'advisory_only': True,
            'label': ('insufficient_samples' if n < 4 else 'no_clear_multiple_modes') if not best
                     else ('potentially_bimodal' if len(groups) == 2 else 'potentially_multimodal'),
            'candidate_mode_count': len(groups) if best else None,
            'silhouette': best['silhouette'] if best else None,
            'thresholds': {'min_cluster_size': 2, 'min_silhouette': 0.5,
                           'min_between_within_gap': 0.01, 'min_between_within_ratio': 2,
                           'max_modes': min(5, n // 2)},
            'clusters': clusters, 'membership': membership,
            'pairwise_cosine_distances': distances.tolist(),
            'projection': {'method': 'PCA of normalized embeddings', 'coordinates': coordinates.tolist()},
            'note': ('Exploratory grouping of this finite sample, not proof of a number of modes. '
                     'No detected split does not establish unimodality. Inspect the outputs and distance matrix; '
                     'ten samples provide limited evidence. The 2-D view is a projection.'),
        },
    }
