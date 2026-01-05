#!/usr/bin/env python3
"""
Data processing utilities.

Functions for processing CSV data, calculating statistics, etc.
"""

import numpy as np
from typing import Dict, List


def calculate_statistics_from_results(pair_results: List[Dict]) -> Dict:
    """
    Calculate statistics from pair results if they're missing from checkpoint.
    
    Args:
        pair_results: List of pair result dictionaries
        
    Returns:
        Dict with statistics for each focus
    """
    all_focus_influences = {}
    all_chat_influences = []
    
    for result in pair_results:
        if not result.get('success', False):
            continue
        
        # Collect focus influences
        influence_scores = result.get('influence_scores', {})
        for focus_name, influence_data in influence_scores.items():
            if focus_name not in all_focus_influences:
                all_focus_influences[focus_name] = []
            all_focus_influences[focus_name].append(influence_data.get('influence', 0.0))
        
        # Collect chat content influence
        chat_influence = result.get('chat_content_influence', {})
        if 'influence' in chat_influence:
            all_chat_influences.append(chat_influence['influence'])
    
    # Calculate statistics
    statistics = {}
    for focus_name, influences in all_focus_influences.items():
        if len(influences) > 0:
            statistics[focus_name] = {
                'mean': float(np.mean(influences)),
                'variance': float(np.var(influences)),
                'std_dev': float(np.std(influences)),
                'min': float(np.min(influences)),
                'max': float(np.max(influences))
            }
    
    if len(all_chat_influences) > 0:
        statistics['chat_content'] = {
            'mean': float(np.mean(all_chat_influences)),
            'variance': float(np.var(all_chat_influences)),
            'std_dev': float(np.std(all_chat_influences)),
            'min': float(np.min(all_chat_influences)),
            'max': float(np.max(all_chat_influences))
        }
    
    # Extract noise statistics from the first pair's noise_metrics (batch-wide calculation)
    if pair_results and len(pair_results) > 0:
        first_result = pair_results[0]
        if first_result.get('success', False):
            noise_metrics = first_result.get('noise_metrics', {})
            if noise_metrics and noise_metrics.get('is_batch_wide', False):
                # Extract noise statistics from the first pair (they're all the same for batch-wide)
                statistics['noise'] = {
                    'mean': noise_metrics.get('mean_similarity', 1.0),
                    'variance': noise_metrics.get('variance', 0.0),
                    'std_dev': noise_metrics.get('std_dev', 0.0),
                    'noise_threshold': noise_metrics.get('threshold'),
                    'num_samples': 20  # Default, could be stored in checkpoint if needed
                }
    
    return statistics


