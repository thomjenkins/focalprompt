#!/usr/bin/env python3
"""
Per-sample reported-focus dynamics (self-reported weight vectors).

These are LLM-judged focus weight distributions over generated outputs —
not model attention weights and not mechanistic interpretability.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
import math

DISCLAIMER = (
    'These are self-reported focus weights from an LLM judge over each sample. '
    'They are not model attention weights and not mechanistic interpretability.'
)


AssessFn = Callable[[str, str, List[Dict[str, Any]]], Dict[str, Any]]


def _focus_names(foci: Sequence[Mapping[str, Any]]) -> List[str]:
    names: List[str] = []
    for f in foci:
        name = (f.get('focus') or f.get('name') or '').strip()
        if name:
            names.append(name)
    return names


def weight_vector_from_assessment(
    assessment: Mapping[str, Any],
    focus_names: Sequence[str],
) -> Dict[str, float]:
    """Map assess_focus result → {focus: score} for the requested names."""
    by_name: Dict[str, float] = {n: 0.0 for n in focus_names}
    for item in assessment.get('foci') or []:
        name = (item.get('focus') or '').strip()
        if name in by_name:
            try:
                by_name[name] = float(item.get('score') or 0.0)
            except (TypeError, ValueError):
                by_name[name] = 0.0
    total = sum(by_name.values())
    if total > 0 and abs(total - 100.0) > 0.5:
        by_name = {k: (v / total) * 100.0 for k, v in by_name.items()}
    return by_name


def summarize_numeric(values: Sequence[float]) -> Dict[str, Optional[float]]:
    vals = [float(v) for v in values]
    if not vals:
        return {
            'n': 0,
            'mean': None,
            'median': None,
            'sd': None,
            'min': None,
            'max': None,
            'range': None,
        }
    mean = sum(vals) / len(vals)
    ordered = sorted(vals)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        median = ordered[mid]
    else:
        median = 0.5 * (ordered[mid - 1] + ordered[mid])
    if len(vals) > 1:
        var = sum((v - mean) ** 2 for v in vals) / (len(vals) - 1)
        sd = math.sqrt(var)
    else:
        sd = 0.0
    lo, hi = ordered[0], ordered[-1]
    return {
        'n': len(vals),
        'mean': float(mean),
        'median': float(median),
        'sd': float(sd),
        'min': float(lo),
        'max': float(hi),
        'range': float(hi - lo),
    }


def mean_weight_vector(vectors: Sequence[Mapping[str, float]], focus_names: Sequence[str]) -> Dict[str, float]:
    if not vectors:
        return {n: 0.0 for n in focus_names}
    out: Dict[str, float] = {}
    for name in focus_names:
        vals = [float(v.get(name, 0.0)) for v in vectors]
        out[name] = sum(vals) / len(vals)
    return out


def jensen_shannon_divergence(
    p: Mapping[str, float],
    q: Mapping[str, float],
    focus_names: Sequence[str],
) -> float:
    """JS divergence on discrete focus-weight distributions (bits, base 2)."""

    def _probs(vec: Mapping[str, float]) -> List[float]:
        raw = [max(float(vec.get(n, 0.0)), 0.0) for n in focus_names]
        s = sum(raw)
        if s <= 0:
            return [1.0 / len(focus_names)] * len(focus_names)
        return [x / s for x in raw]

    if not focus_names:
        return 0.0
    P = _probs(p)
    Q = _probs(q)
    M = [0.5 * (a + b) for a, b in zip(P, Q)]

    def _kl(a: List[float], b: List[float]) -> float:
        total = 0.0
        for x, y in zip(a, b):
            if x <= 0:
                continue
            total += x * math.log2(x / max(y, 1e-15))
        return total

    return 0.5 * _kl(P, M) + 0.5 * _kl(Q, M)


def summarize_condition(
    samples: Sequence[Mapping[str, Any]],
    focus_names: Sequence[str],
) -> Dict[str, Any]:
    vectors = [s['weights'] for s in samples if isinstance(s.get('weights'), dict)]
    per_focus = {
        name: summarize_numeric([float(v.get(name, 0.0)) for v in vectors])
        for name in focus_names
    }
    return {
        'n_samples': len(samples),
        'n_scored': len(vectors),
        'mean_weights': mean_weight_vector(vectors, focus_names),
        'per_focus': per_focus,
        'samples': list(samples),
    }


def delta_weight_vectors(
    baseline_mean: Mapping[str, float],
    ablated_mean: Mapping[str, float],
    focus_names: Sequence[str],
) -> Dict[str, float]:
    return {
        name: float(ablated_mean.get(name, 0.0)) - float(baseline_mean.get(name, 0.0))
        for name in focus_names
    }


def associate_with_behavior_labels(
    samples: Sequence[Mapping[str, Any]],
    focus_name: str,
    label_key: str = 'behavior_label',
) -> Dict[str, Any]:
    """
    Optional association: mean reported weight for ``focus_name`` by behavior label.

    Labels are user-supplied (e.g. refused_dog_appointment=true/false). Descriptive only.
    """
    buckets: Dict[str, List[float]] = {}
    for sample in samples:
        label = sample.get(label_key)
        if label is None:
            continue
        weights = sample.get('weights') or {}
        try:
            w = float(weights.get(focus_name, 0.0))
        except (TypeError, ValueError):
            continue
        buckets.setdefault(str(label), []).append(w)
    return {
        'focus': focus_name,
        'label_key': label_key,
        'by_label': {k: summarize_numeric(v) for k, v in buckets.items()},
        'note': (
            'Descriptive association between self-reported focus weight and '
            'user-defined behaviour labels — not causal proof.'
        ),
    }


def build_reported_focus_dynamics(
    *,
    prompt: str,
    foci: Sequence[Mapping[str, Any]],
    baseline_outputs: Sequence[str],
    ablated_outputs: Mapping[Any, Sequence[str]],
    assess_fn: AssessFn,
    behavior_labels: Optional[Mapping[str, Sequence[Any]]] = None,
    association_focus: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run reported-focus assessment on every baseline and ablated sample.

    ``ablated_outputs`` maps focus_index → list of texts (same as score_from_samples).
    ``behavior_labels`` optional: {'baseline': [...], 'focus:0': [...], ...}
    """
    focus_list = [dict(f) for f in foci]
    names = _focus_names(focus_list)
    behavior_labels = behavior_labels or {}

    def _assess_many(
        texts: Sequence[str],
        condition: str,
        labels: Optional[Sequence[Any]] = None,
    ) -> List[Dict[str, Any]]:
        samples: List[Dict[str, Any]] = []
        for i, text in enumerate(texts):
            assessment = assess_fn(prompt, str(text), focus_list)
            weights = weight_vector_from_assessment(assessment, names)
            row: Dict[str, Any] = {
                'sample_index': i,
                'condition': condition,
                'output': str(text),
                'weights': weights,
                'overall_summary': assessment.get('overall_summary')
                or assessment.get('overall_summary'),
                'explanations': {
                    (item.get('focus') or ''): (item.get('explanation') or '')
                    for item in (assessment.get('foci') or [])
                },
            }
            if labels is not None and i < len(labels):
                row['behavior_label'] = labels[i]
            samples.append(row)
        return samples

    baseline_samples = _assess_many(
        baseline_outputs,
        'baseline',
        behavior_labels.get('baseline'),
    )
    baseline_summary = summarize_condition(baseline_samples, names)

    ablation_blocks: List[Dict[str, Any]] = []
    for key, texts in sorted(
        ((int(k), list(v)) for k, v in (ablated_outputs or {}).items()),
        key=lambda kv: kv[0],
    ):
        focus_name = names[key] if 0 <= key < len(names) else f'focus_{key}'
        # Prefer focus name from foci list by index
        if 0 <= key < len(focus_list):
            focus_name = (focus_list[key].get('focus') or focus_name).strip()
        label_key = f'focus:{key}'
        samples = _assess_many(texts, f'ablate:{focus_name}', behavior_labels.get(label_key))
        summary = summarize_condition(samples, names)
        delta = delta_weight_vectors(
            baseline_summary['mean_weights'],
            summary['mean_weights'],
            names,
        )
        js = jensen_shannon_divergence(
            baseline_summary['mean_weights'],
            summary['mean_weights'],
            names,
        )
        block: Dict[str, Any] = {
            'focus_index': key,
            'focus': focus_name,
            'summary': summary,
            'delta_vs_baseline_mean_weights': delta,
            'js_divergence_vs_baseline_mean': js,
        }
        if association_focus:
            block['behavior_association'] = associate_with_behavior_labels(
                baseline_samples + samples,
                association_focus,
            )
        ablation_blocks.append(block)

    return {
        'disclaimer': DISCLAIMER,
        'focus_names': names,
        'baseline': baseline_summary,
        'ablations': ablation_blocks,
        'optional_behavior_labels_supported': True,
    }
