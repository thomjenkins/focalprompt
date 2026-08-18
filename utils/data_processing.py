#!/usr/bin/env python3
"""
Data processing utilities.

Functions for processing CSV data, calculating statistics, etc.
"""

import numpy as np
from typing import Dict, List


def _per_pair_normalized_from_result(result: Dict) -> tuple:
    """
    Return (focus_name -> normalized share, chat normalized share) for one pair.

    Chat attribution is out of scope; if chat_content_influence is absent, chat share is 0
    and shares are normalised over attributable foci only.
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
        focus_norm = {
            name: float(d['normalized_influence']) for name, d in scored.items()
        }
        chat_norm = float(chat_influence['normalized_influence']) if has_chat else 0.0
        return focus_norm, chat_norm
    
    raw_sum = sum(float(d.get('influence', 0.0)) for d in scored.values()) + chat_raw
    if raw_sum > 0:
        focus_norm = {
            name: float(d.get('influence', 0.0)) / raw_sum
            for name, d in scored.items()
        }
        chat_norm = chat_raw / raw_sum if has_chat else 0.0
        return focus_norm, chat_norm
    
    n = len(scored) + (1 if has_chat else 0)
    share = (1.0 / n) if n else 0.0
    focus_norm = {name: share for name in scored}
    chat_norm = share if has_chat else 0.0
    return focus_norm, chat_norm


def calculate_statistics_from_results(pair_results: List[Dict]) -> Dict:
    """
    Calculate statistics from pair results if they're missing from checkpoint.

    Primary metrics are **normalized shares** (per pair, foci + chat sum to 100%), averaged
    across pairs — comparable to single-run ablation's normalized influence.

    Raw embedding-shift stats (1 - similarity) are kept as mean_raw / variance_raw / etc.
    
    Args:
        pair_results: List of pair result dictionaries
        
    Returns:
        Dict with statistics for each focus
    """
    all_focus_influences = {}
    all_focus_shares = {}
    all_chat_influences = []
    all_chat_shares = []
    
    for result in pair_results:
        if not result.get('success', False):
            continue
        
        # Raw shift (1 - similarity) — not additive across foci
        influence_scores = result.get('influence_scores', {})
        for focus_name, influence_data in influence_scores.items():
            if focus_name not in all_focus_influences:
                all_focus_influences[focus_name] = []
            all_focus_influences[focus_name].append(influence_data.get('influence', 0.0))
        
        chat_influence = result.get('chat_content_influence') or {}
        if 'influence' in chat_influence:
            all_chat_influences.append(chat_influence['influence'])
        
        # Normalized shares (sum to 100% within each pair)
        focus_norm, chat_norm = _per_pair_normalized_from_result(result)
        for focus_name, share in focus_norm.items():
            if focus_name not in all_focus_shares:
                all_focus_shares[focus_name] = []
            all_focus_shares[focus_name].append(share)
        if result.get('chat_content_influence') and 'influence' in (result.get('chat_content_influence') or {}):
            all_chat_shares.append(chat_norm)
    
    def _stats(values):
        if len(values) == 0:
            return None
        arr = np.array(values, dtype=float)
        return {
            'mean': float(np.mean(arr)),
            'variance': float(np.var(arr)),
            'std_dev': float(np.std(arr)),
            'min': float(np.min(arr)),
            'max': float(np.max(arr))
        }
    
    # Calculate statistics — primary: share (normalized); raw shift kept as *_raw
    statistics = {}
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
                    'max_raw': raw_st['max']
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
                        'max_raw': raw_st['max']
                    })
    
    return statistics


def calculate_focus_distribution_statistics(pair_results: List[Dict]) -> Dict:
    """
    Aggregate LLM-assessed focus scores (each pair sums to ~100 points) across batch pairs.

    Returns per-focus mean / variance / min / max of those scores.
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
            if name not in by_focus:
                by_focus[name] = []
            by_focus[name].append(score)

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


