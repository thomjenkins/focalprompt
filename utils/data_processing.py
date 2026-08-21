#!/usr/bin/env python3
"""
Data processing utilities for batch aggregation.

Normalized influence convention (canonical, matches AblationService.score_from_samples):
  * ``normalized_influence`` is in **percentage points** on [0, 100].
  * Across attributable foci in a single pair, values sum to 100.
  * Reported-focus assessment scores also sum to ~100 points per pair.

Missing-focus policy for aggregation:
  * If a focus is absent or non-attributable in a pair, that pair is **excluded**
    from that focus's denominator (not imputed as zero).
"""

from __future__ import annotations

import numpy as np
from typing import Dict, List, Tuple


# Canonical scale for ablation normalized_influence and batch share aggregates.
NORMALIZED_INFLUENCE_PERCENTAGE_SCALE = 100.0


def _as_percentage_shares(
    focus_values: Dict[str, float],
    chat_value: float = 0.0,
    *,
    has_chat: bool = False,
) -> Tuple[Dict[str, float], float]:
    """
    Coerce per-pair shares onto the 0–100 percentage-point scale.

    Accepts legacy fractional payloads (sum ≈ 1) and modern percentage payloads
    (sum ≈ 100). Always returns percentages that sum to 100 when any mass exists.
    """
    total = sum(focus_values.values()) + (chat_value if has_chat else 0.0)
    if total <= 0:
        n = len(focus_values) + (1 if has_chat else 0)
        if n == 0:
            return {}, 0.0
        share = NORMALIZED_INFLUENCE_PERCENTAGE_SCALE / n
        return {name: share for name in focus_values}, (share if has_chat else 0.0)

    # Legacy 0–1 fractions (with tolerance for float noise).
    if 0.5 <= total <= 1.5:
        scale = NORMALIZED_INFLUENCE_PERCENTAGE_SCALE / total
    # Already percentage points (or close); renormalize gently to exact 100.
    elif 50.0 <= total <= 150.0:
        scale = NORMALIZED_INFLUENCE_PERCENTAGE_SCALE / total
    else:
        # Unknown scale: treat values as raw masses and renormalize to 100.
        scale = NORMALIZED_INFLUENCE_PERCENTAGE_SCALE / total

    focus_pct = {name: float(v) * scale for name, v in focus_values.items()}
    chat_pct = float(chat_value) * scale if has_chat else 0.0
    return focus_pct, chat_pct


def _per_pair_normalized_from_result(result: Dict) -> Tuple[Dict[str, float], float]:
    """
    Return (focus_name -> percentage share, chat percentage share) for one pair.

    Only foci present in ``influence_scores`` with an ``influence`` field are
    included. Absent foci are omitted (excluded from later denominators).
    """
    influence_scores = result.get('influence_scores', {}) or {}
    scored = {
        name: data for name, data in influence_scores.items()
        if isinstance(data, dict) and 'influence' in data
    }
    chat_influence = result.get('chat_content_influence') or {}
    has_chat = isinstance(chat_influence, dict) and 'influence' in chat_influence
    chat_raw = float(chat_influence.get('influence', 0.0)) if has_chat else 0.0

    all_have_norm = (
        scored
        and all('normalized_influence' in d for d in scored.values())
        and (not has_chat or 'normalized_influence' in chat_influence)
    )
    if all_have_norm:
        focus_vals = {
            name: float(d['normalized_influence']) for name, d in scored.items()
        }
        chat_val = float(chat_influence['normalized_influence']) if has_chat else 0.0
        return _as_percentage_shares(focus_vals, chat_val, has_chat=has_chat)

    focus_vals = {
        name: float(d.get('influence', 0.0)) for name, d in scored.items()
    }
    return _as_percentage_shares(focus_vals, chat_raw, has_chat=has_chat)


def calculate_statistics_from_results(pair_results: List[Dict]) -> Dict:
    """
    Aggregate pair-level ablation results.

    Primary metrics are **normalized percentage shares** (0–100; attributable
    foci sum to 100 within each pair), averaged across pairs where the focus
    appears. A focus missing from a pair does **not** contribute a zero — that
    pair is omitted from the focus's sample.

    Raw embedding-shift stats (``influence`` / T_obs) are retained as
    ``mean_raw`` / ``variance_raw`` / etc.
    """
    all_focus_influences: Dict[str, List[float]] = {}
    all_focus_shares: Dict[str, List[float]] = {}
    all_chat_influences: List[float] = []
    all_chat_shares: List[float] = []

    for result in pair_results:
        if not result.get('success', False):
            continue

        influence_scores = result.get('influence_scores', {}) or {}
        for focus_name, influence_data in influence_scores.items():
            if not isinstance(influence_data, dict) or 'influence' not in influence_data:
                continue
            all_focus_influences.setdefault(focus_name, []).append(
                float(influence_data.get('influence', 0.0))
            )

        chat_influence = result.get('chat_content_influence') or {}
        if isinstance(chat_influence, dict) and 'influence' in chat_influence:
            all_chat_influences.append(float(chat_influence['influence']))

        focus_norm, chat_norm = _per_pair_normalized_from_result(result)
        for focus_name, share in focus_norm.items():
            all_focus_shares.setdefault(focus_name, []).append(share)
        if isinstance(chat_influence, dict) and 'influence' in chat_influence:
            all_chat_shares.append(chat_norm)

    def _stats(values: List[float]):
        if len(values) == 0:
            return None
        arr = np.array(values, dtype=float)
        return {
            'mean': float(np.mean(arr)),
            'variance': float(np.var(arr)),
            'std_dev': float(np.std(arr)),
            'min': float(np.min(arr)),
            'max': float(np.max(arr)),
            'n_pairs': int(len(values)),
        }

    statistics: Dict[str, Dict] = {}
    for focus_name in sorted(set(all_focus_shares.keys()) | set(all_focus_influences.keys())):
        share_vals = all_focus_shares.get(focus_name, [])
        raw_vals = all_focus_influences.get(focus_name, [])
        if len(share_vals) == 0:
            continue
        st = _stats(share_vals)
        if not st:
            continue
        statistics[focus_name] = st
        if len(raw_vals) > 0:
            raw_st = _stats(raw_vals)
            if raw_st:
                statistics[focus_name].update({
                    'mean_raw': raw_st['mean'],
                    'variance_raw': raw_st['variance'],
                    'std_dev_raw': raw_st['std_dev'],
                    'min_raw': raw_st['min'],
                    'max_raw': raw_st['max'],
                })

    if len(all_chat_shares) > 0:
        st = _stats(all_chat_shares)
        if st:
            statistics['chat_content'] = st
            if len(all_chat_influences) == len(all_chat_shares):
                raw_st = _stats(all_chat_influences)
                if raw_st:
                    statistics['chat_content'].update({
                        'mean_raw': raw_st['mean'],
                        'variance_raw': raw_st['variance'],
                        'std_dev_raw': raw_st['std_dev'],
                        'min_raw': raw_st['min'],
                        'max_raw': raw_st['max'],
                    })

    return statistics


def calculate_focus_distribution_statistics(pair_results: List[Dict]) -> Dict:
    """
    Aggregate LLM-assessed focus scores (each pair sums to ~100 points) across batch pairs.

    A focus absent from a pair's assessment is excluded from that focus's
    denominator (not treated as zero).
    """
    by_focus: Dict[str, List[float]] = {}
    for result in pair_results:
        if not result.get('success'):
            continue
        fd = result.get('focus_distribution_assessment')
        if not fd:
            continue
        for item in fd.get('foci', []):
            name = item.get('focus', '')
            if not name:
                continue
            score = float(item.get('score', 0))
            by_focus.setdefault(name, []).append(score)

    statistics: Dict[str, Dict] = {}
    for name, scores in sorted(by_focus.items()):
        if not scores:
            continue
        arr = np.array(scores, dtype=float)
        statistics[name] = {
            'mean': float(np.mean(arr)),
            'variance': float(np.var(arr)),
            'std_dev': float(np.std(arr)),
            'min': float(np.min(arr)),
            'max': float(np.max(arr)),
            'n_pairs': len(scores),
        }
    return statistics
