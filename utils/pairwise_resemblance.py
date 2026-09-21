"""Descriptive nearest-singleton comparisons in contexts retaining both foci."""
import numpy as np

from utils.focus_variants import overlaps

TOLERANCE = 1e-6


def summarize_conditions(conditions, i, j):
    # Equivalent prompts share draws. Use the longest available prefix once,
    # then weight each distinct prompt equally, irrespective of sample count.
    pools = {}
    for condition in conditions:
        previous = pools.get(condition['pool_id'])
        if previous is None or len(condition['distances']) > len(previous['distances']):
            pools[condition['pool_id']] = condition
    if not pools:
        return None
    scores = []
    for condition in pools.values():
        distances = np.asarray(condition['distances'], dtype=float)
        gap = distances[:, j] - distances[:, i]
        ties = np.abs(gap) <= TOLERANCE
        scores.append({
            'row_share': float(np.mean((gap > TOLERANCE) + ties * .5)),
            'tie_share': float(np.mean(ties)),
            'mean_gap': float(np.mean(gap)),
            'row_distance': float(np.mean(distances[:, i])),
            'column_distance': float(np.mean(distances[:, j])),
        })
    return {key: float(np.mean([s[key] for s in scores])) for key in scores[0]} | {
        'condition_count': len(pools),
        'output_count': sum(len(c['distances']) for c in pools.values()),
    }


def pairwise_resemblance(plan, arms, cache):
    foci = plan['foci']
    count = len(foci)
    references, valid, dispersion = [], [], []
    for i in range(count):
        vectors = cache.array(arms[f'singleton_{i}']['outputs'])
        centroid = vectors.mean(axis=0)
        norm = np.linalg.norm(centroid)
        valid.append(bool(norm > TOLERANCE))
        references.append(centroid / norm if valid[-1] else np.zeros_like(centroid))
        unit = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
        dispersion.append(float(np.mean(np.clip(1 - unit @ references[-1], 0, 2))) if valid[-1] else None)
    references = np.asarray(references)
    separations = np.clip(1 - references @ references.T, 0, 2)
    conditions = []
    for arm in arms.values():
        if arm['kind'] not in ('baseline', 'ablated'):
            continue
        deleted = arm.get('deleted_spans', [])
        intact = [i for i, focus in enumerate(foci)
                  if not any(overlaps(span, removed) for span in focus['spans'] for removed in deleted)]
        vectors = cache.array(arm['outputs'])
        unit = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
        distances = np.clip(1 - unit @ references.T, 0, 2).tolist()
        for row in distances:
            for i in range(count):
                if not valid[i]:
                    row[i] = None
        conditions.append({
            'id': arm['id'], 'pool_id': arm['pool_id'], 'kind': arm['kind'],
            'removed_focus_index': arm['focus_index'], 'intact_focus_indices': intact,
            'distances': distances,
        })
    pairs = []
    for i in range(count):
        for j in range(i + 1, count):
            reason = None
            if any(overlaps(a, b) for a in foci[i]['spans'] for b in foci[j]['spans']):
                reason = 'These foci share labelled source text; their singleton references are not isolated.'
            elif not (valid[i] and valid[j]):
                reason = 'A singleton centroid is numerically undefined.'
            elif separations[i, j] <= TOLERANCE:
                reason = 'The singleton centroids are numerically indistinguishable.'
            eligible = [c for c in conditions if i in c['intact_focus_indices'] and j in c['intact_focus_indices']]
            views = {
                'full': [c for c in eligible if c['kind'] == 'baseline'],
                'ablations': [c for c in eligible if c['kind'] == 'ablated'],
                'combined': eligible,
            }
            pairs.append({
                'row_index': i, 'column_index': j, 'unavailable_reason': reason,
                'singleton_distance': float(separations[i, j]) if valid[i] and valid[j] else None,
                'views': {view: None if reason else summarize_conditions(items, i, j) for view, items in views.items()},
            })
    return {
        'protocol': 'pairwise-singleton-resemblance-v1',
        'method': 'cosine_distance_from_each_output_to_each_singleton_embedding_centroid',
        'tie_tolerance': TOLERANCE,
        'weighting': 'equal_weight_per_distinct_prompt_pool; longest_sample_prefix_once',
        'singleton_dispersion': dispersion, 'conditions': conditions, 'pairs': pairs,
        'notes': [
            'Row share is the fraction closer to the row singleton, with half credit for numerical ties.',
            'Only full/leave-one-out conditions preserving every source span of both foci are eligible.',
            'Mean gap is column distance minus row distance; positive values favor the row singleton.',
            'Percentages are descriptive resemblance frequencies, not focus allocations, causal dominance or confidence.',
            'Singleton centroids and shares are sample estimates without confidence intervals; small samples and multiple output modes limit interpretation.',
            'High shares with tiny gaps can reflect slight differences. Inspect distances, singleton dispersion and actual outputs.',
        ],
    }
