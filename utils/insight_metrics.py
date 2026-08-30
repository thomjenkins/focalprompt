#!/usr/bin/env python3
"""
Deterministic interpretability metrics for experiment results.

Thresholds live here so archetype labels, status bands, and insight cards stay
inspectable and tunable. Browser logic mirrors these constants in
static/js/insight_metrics.js.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Thresholds (percentage points unless noted)
# ---------------------------------------------------------------------------

THRESHOLDS: Dict[str, float] = {
    'high_revealed': 12.0,
    'low_revealed': 10.0,
    'high_reported': 15.0,
    'low_reported': 8.0,
    'mismatch_gap': 12.0,
    'stabilizer_noise_delta': 0.08,
    'destabilizer_noise_delta': 0.08,
    'order_sensitive': 0.12,
    'concentration_high': 0.60,
    'concentration_medium': 0.40,
    'agreement_high': 0.70,
    'agreement_medium': 0.45,
    'stability_high_noise': 0.35,
    'stability_medium_noise': 0.20,
    'order_high': 0.20,
    'order_medium': 0.10,
}

ARCHETYPE_HELP = {
    'anchor': 'High revealed influence with moderate/high reported attention.',
    'hidden_driver': 'Low reported attention, high revealed behavioural influence.',
    'claimed_but_inert': 'High reported attention, low revealed influence.',
    'stabilizer': 'Removing this focus materially increases output noise.',
    'destabilizer': 'Removing this focus materially decreases output noise.',
    'order_sensitive': 'Behavioural effect depends on ordinal position.',
    'redundant': 'Persistently low reported attention and low revealed influence.',
}

ARCHETYPE_LABELS = {
    'anchor': 'Anchor',
    'hidden_driver': 'Hidden driver',
    'claimed_but_inert': 'Claimed but inert',
    'stabilizer': 'Stabilizer',
    'destabilizer': 'Destabilizer',
    'order_sensitive': 'Order-sensitive',
    'redundant': 'Redundant',
}


def _f(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_share(values: Sequence[float]) -> List[float]:
    """Normalize non-negative values to percentage points summing to ~100."""
    cleaned = [max(0.0, _f(v)) for v in values]
    total = sum(cleaned)
    if total <= 0:
        n = len(cleaned)
        return ([100.0 / n] * n) if n else []
    return [(v / total) * 100.0 for v in cleaned]


def reported_revealed_gap(reported: float, revealed: float) -> float:
    return _f(reported) - _f(revealed)


def classify_archetypes(
    *,
    reported: Optional[float],
    revealed: Optional[float],
    baseline_noise: Optional[float] = None,
    ablated_noise: Optional[float] = None,
    order_sensitivity: Optional[float] = None,
    thresholds: Optional[Mapping[str, float]] = None,
) -> List[str]:
    """Return zero or more archetype keys for a focus."""
    t = dict(THRESHOLDS)
    if thresholds:
        t.update(thresholds)

    labels: List[str] = []
    has_reported = reported is not None
    has_revealed = revealed is not None
    r = _f(reported) if has_reported else None
    v = _f(revealed) if has_revealed else None

    if has_reported and has_revealed and r is not None and v is not None:
        if v >= t['high_revealed'] and r >= t['low_reported']:
            labels.append('anchor')
        if r <= t['low_reported'] and v >= t['high_revealed']:
            labels.append('hidden_driver')
        if r >= t['high_reported'] and v <= t['low_revealed']:
            labels.append('claimed_but_inert')
        if r <= t['low_reported'] and v <= t['low_revealed']:
            labels.append('redundant')

    if baseline_noise is not None and ablated_noise is not None:
        delta = _f(ablated_noise) - _f(baseline_noise)
        if delta >= t['stabilizer_noise_delta']:
            labels.append('stabilizer')
        if (-delta) >= t['destabilizer_noise_delta']:
            labels.append('destabilizer')

    if order_sensitivity is not None and abs(_f(order_sensitivity)) >= t['order_sensitive']:
        labels.append('order_sensitive')

    seen = set()
    out: List[str] = []
    for lab in labels:
        if lab not in seen:
            seen.add(lab)
            out.append(lab)
    return out


def band_from_thresholds(
    value: float,
    *,
    high_at: float,
    medium_at: float,
    higher_is_stronger: bool = True,
) -> str:
    """Map a continuous metric to Low / Medium / High."""
    v = _f(value)
    if higher_is_stronger:
        if v >= high_at:
            return 'High'
        if v >= medium_at:
            return 'Medium'
        return 'Low'
    if v >= high_at:
        return 'Low'
    if v >= medium_at:
        return 'Medium'
    return 'High'


def status_strip(
    *,
    top3_revealed_share: Optional[float] = None,
    mean_abs_gap: Optional[float] = None,
    baseline_noise: Optional[float] = None,
    mean_order_sensitivity: Optional[float] = None,
    thresholds: Optional[Mapping[str, float]] = None,
) -> Dict[str, Dict[str, str]]:
    """Multi-dimensional summary statuses (not a single prompt score)."""
    t = dict(THRESHOLDS)
    if thresholds:
        t.update(thresholds)

    out: Dict[str, Dict[str, str]] = {}

    if top3_revealed_share is not None:
        share = _f(top3_revealed_share)
        if share > 1.0:
            share = share / 100.0
        out['influence_concentration'] = {
            'level': band_from_thresholds(
                share,
                high_at=t['concentration_high'],
                medium_at=t['concentration_medium'],
            ),
            'help': (
                'Share of total revealed influence held by the top three foci. '
                f'High ≥ {t["concentration_high"]:.0%}, Medium ≥ {t["concentration_medium"]:.0%}.'
            ),
        }

    if mean_abs_gap is not None:
        agreement = max(0.0, min(1.0, 1.0 - (_f(mean_abs_gap) / 100.0)))
        out['reported_revealed_agreement'] = {
            'level': band_from_thresholds(
                agreement,
                high_at=t['agreement_high'],
                medium_at=t['agreement_medium'],
            ),
            'help': (
                'Agreement between reported-focus scores and revealed influence shares. '
                'Derived from mean absolute gap (percentage points).'
            ),
        }

    if baseline_noise is not None:
        out['baseline_stability'] = {
            'level': band_from_thresholds(
                _f(baseline_noise),
                high_at=t['stability_high_noise'],
                medium_at=t['stability_medium_noise'],
                higher_is_stronger=False,
            ),
            'help': (
                'Inverse of baseline sample dispersion. Higher noise ⇒ lower stability. '
                f'Low stability when noise ≥ {t["stability_high_noise"]}.'
            ),
        }

    if mean_order_sensitivity is not None:
        out['order_sensitivity'] = {
            'level': band_from_thresholds(
                abs(_f(mean_order_sensitivity)),
                high_at=t['order_high'],
                medium_at=t['order_medium'],
            ),
            'help': (
                'Mean absolute order-sensitivity across foci when order/shuffle '
                'analysis is available.'
            ),
        }

    return out


def select_insight_cards(
    foci: Sequence[Mapping[str, Any]],
    *,
    max_cards: int = 4,
    thresholds: Optional[Mapping[str, float]] = None,
) -> List[Dict[str, Any]]:
    """Pick up to max_cards high-value insight cards from focus rows."""
    t = dict(THRESHOLDS)
    if thresholds:
        t.update(thresholds)

    candidates: List[Tuple[float, Dict[str, Any]]] = []

    for row in foci:
        name = str(row.get('name') or row.get('focus') or '').strip()
        if not name:
            continue
        reported = row.get('reported')
        revealed = row.get('revealed')
        gap = row.get('gap')
        if gap is None and reported is not None and revealed is not None:
            gap = reported_revealed_gap(_f(reported), _f(revealed))
        archetypes = list(row.get('archetypes') or [])
        if not archetypes:
            archetypes = classify_archetypes(
                reported=reported,
                revealed=revealed,
                baseline_noise=row.get('baseline_noise'),
                ablated_noise=row.get('ablated_noise'),
                order_sensitivity=row.get('order_sensitivity'),
                thresholds=t,
            )

        def add(kind: str, priority: float, interpretation: str, numbers: Dict[str, Any]) -> None:
            candidates.append((
                priority,
                {
                    'kind': kind,
                    'focus': name,
                    'interpretation': interpretation,
                    'numbers': numbers,
                },
            ))

        if 'hidden_driver' in archetypes and revealed is not None:
            add(
                'hidden_driver',
                100.0 + _f(revealed),
                'Low reported attention but strong behavioural influence when removed.',
                {'reported': reported, 'revealed': revealed, 'gap': gap},
            )
        if 'claimed_but_inert' in archetypes and reported is not None:
            add(
                'claimed_but_inert',
                90.0 + _f(reported),
                'High reported attention with little revealed behavioural influence.',
                {'reported': reported, 'revealed': revealed, 'gap': gap},
            )
        if gap is not None and abs(_f(gap)) >= t['mismatch_gap']:
            add(
                'mismatch',
                80.0 + abs(_f(gap)),
                'Large reported-vs-revealed disagreement for this focus.',
                {'reported': reported, 'revealed': revealed, 'gap': gap},
            )
        if 'stabilizer' in archetypes:
            bn = row.get('baseline_noise')
            an = row.get('ablated_noise')
            add(
                'stabilizer',
                70.0 + (_f(an) - _f(bn)),
                'Removing this focus increases output noise — likely a stabilizer.',
                {'baseline_noise': bn, 'ablated_noise': an},
            )
        if 'destabilizer' in archetypes:
            bn = row.get('baseline_noise')
            an = row.get('ablated_noise')
            add(
                'destabilizer',
                70.0 + (_f(bn) - _f(an)),
                'Removing this focus decreases output noise — likely a destabilizer.',
                {'baseline_noise': bn, 'ablated_noise': an},
            )
        if 'order_sensitive' in archetypes:
            os_ = row.get('order_sensitivity')
            add(
                'order_sensitive',
                60.0 + abs(_f(os_)),
                'Behavioural effect depends on where this focus sits in the prompt.',
                {'order_sensitivity': os_},
            )
        if 'redundant' in archetypes:
            add(
                'redundant',
                40.0,
                'Low reported attention and low revealed influence — often inert.',
                {'reported': reported, 'revealed': revealed},
            )

    candidates.sort(key=lambda x: -x[0])
    selected: List[Dict[str, Any]] = []
    used_kinds: set = set()
    used_foci: set = set()
    for _, card in candidates:
        if len(selected) >= max_cards:
            break
        if card['kind'] in used_kinds:
            continue
        if card['focus'] in used_foci:
            continue
        selected.append(card)
        used_kinds.add(card['kind'])
        used_foci.add(card['focus'])
    return selected


def overview_headline(
    foci: Sequence[Mapping[str, Any]],
    *,
    thresholds: Optional[Mapping[str, float]] = None,
) -> str:
    """Deterministic one–two sentence summary for Overview."""
    t = dict(THRESHOLDS)
    if thresholds:
        t.update(thresholds)

    rows = [dict(r) for r in foci if str(r.get('name') or r.get('focus') or '').strip()]
    if not rows:
        return 'No focus-level results are available for this run yet.'

    for row in rows:
        if row.get('gap') is None and row.get('reported') is not None and row.get('revealed') is not None:
            row['gap'] = reported_revealed_gap(_f(row['reported']), _f(row['revealed']))

    n = len(rows)
    revealed_vals = [_f(r.get('revealed')) for r in rows]
    ranked = sorted(zip(revealed_vals, rows), key=lambda x: -x[0])
    top_k = min(3, n)
    top_share = sum(v for v, _ in ranked[:top_k]) if revealed_vals else 0.0
    gaps = [abs(_f(r.get('gap'))) for r in rows if r.get('gap') is not None]
    mean_gap = (sum(gaps) / len(gaps)) if gaps else None

    parts: List[str] = []
    if mean_gap is not None and mean_gap >= t['mismatch_gap']:
        parts.append(
            "The model's reported focus differs materially from its strongest behavioural drivers."
        )
    elif mean_gap is not None:
        parts.append('Reported focus and revealed influence are broadly aligned for this run.')
    else:
        parts.append(
            'Revealed behavioural influence is available; reported-focus scores were not paired for every focus.'
        )
    if top_share > 0:
        parts.append(
            f'{top_k} of {n} prompt sections account for {top_share:.0f}% of revealed influence.'
        )
    return ' '.join(parts)


def next_experiment_suggestions(
    foci: Sequence[Mapping[str, Any]],
    status: Mapping[str, Mapping[str, str]],
) -> List[str]:
    """Evidence-based next tests — framed as experiments, not fixes."""
    suggestions: List[str] = []
    by_kind: Dict[str, List[str]] = {}
    for row in foci:
        name = str(row.get('name') or row.get('focus') or '').strip()
        for lab in row.get('archetypes') or []:
            by_kind.setdefault(str(lab), []).append(name)

    if by_kind.get('claimed_but_inert'):
        focus = by_kind['claimed_but_inert'][0]
        suggestions.append(
            f'Test shortening or relocating “{focus}” (claimed but inert) and re-measure revealed influence.'
        )
    if by_kind.get('hidden_driver'):
        focus = by_kind['hidden_driver'][0]
        suggestions.append(
            f'Try moving hidden driver “{focus}” earlier in the prompt and compare order sensitivity.'
        )
    if not by_kind.get('claimed_but_inert') and not by_kind.get('hidden_driver'):
        gaps = []
        for row in foci:
            name = str(row.get('name') or row.get('focus') or '').strip()
            if name and row.get('gap') is not None:
                gaps.append((abs(_f(row.get('gap'))), name, _f(row.get('gap'))))
        if gaps:
            gaps.sort(reverse=True)
            _, name, signed = gaps[0]
            if signed > 0:
                suggestions.append(
                    f'Test whether “{name}” is over-claimed: high reported attention vs lower revealed influence.'
                )
            else:
                suggestions.append(
                    f'Test elevating “{name}”: low reported attention vs higher revealed influence.'
                )
    if by_kind.get('destabilizer'):
        focus = by_kind['destabilizer'][0]
        suggestions.append(
            f'Rewrite destabilizing section “{focus}” while preserving its information; re-check baseline noise.'
        )
    if (status.get('baseline_stability') or {}).get('level') == 'Low':
        suggestions.append(
            'Increase baseline sample count — current baseline dispersion is high relative to the signal.'
        )
    if (status.get('order_sensitivity') or {}).get('level') in ('High', 'Medium'):
        suggestions.append(
            'Run or expand focus-order / shuffle analysis to confirm positional effects before rewriting.'
        )
    if (status.get('reported_revealed_agreement') or {}).get('level') == 'Low':
        suggestions.append(
            'Compare two models on the same prompt to see whether reported/revealed disagreement is model-specific.'
        )

    out: List[str] = []
    for s in suggestions:
        if s not in out:
            out.append(s)
        if len(out) >= 4:
            break
    return out


def build_focus_rows(
    *,
    influence_scores: Sequence[Mapping[str, Any]],
    assessment_foci: Optional[Sequence[Mapping[str, Any]]] = None,
    baseline_noise: Optional[float] = None,
    order_by_focus: Optional[Mapping[str, float]] = None,
    thresholds: Optional[Mapping[str, float]] = None,
) -> List[Dict[str, Any]]:
    """Merge ablation influence with optional reported-focus scores."""
    t = dict(THRESHOLDS)
    if thresholds:
        t.update(thresholds)

    reported_by: Dict[str, float] = {}
    for f in assessment_foci or []:
        name = str(f.get('focus') or f.get('name') or '').strip()
        if name and f.get('score') is not None:
            reported_by[name.lower()] = _f(f.get('score'))

    raw_revealed: List[float] = []
    names: List[str] = []
    meta: List[Mapping[str, Any]] = []
    for item in influence_scores:
        name = str(item.get('focus') or item.get('focus_name') or '').strip()
        if not name:
            continue
        if item.get('attributable') is False:
            continue
        ni = item.get('normalized_influence')
        if ni is None:
            ni = item.get('influence') or item.get('t_obs') or 0.0
        raw_revealed.append(_f(ni))
        names.append(name)
        meta.append(item)

    total = sum(raw_revealed)
    if total <= 0:
        shares = normalize_share(raw_revealed)
    elif 80.0 <= total <= 120.0:
        shares = list(raw_revealed)
    else:
        shares = normalize_share(raw_revealed)

    rows: List[Dict[str, Any]] = []
    for name, share, item in zip(names, shares, meta):
        reported = reported_by.get(name.lower())
        ablated_noise = None
        stab = item.get('ablation_stability') or item.get('stability') or {}
        if isinstance(stab, Mapping):
            ablated_noise = stab.get('mean_pairwise_cosine_distance')
            if ablated_noise is None:
                ablated_noise = stab.get('dispersion')
        order_s = None
        if order_by_focus:
            order_s = order_by_focus.get(name)
            if order_s is None:
                order_s = order_by_focus.get(name.lower())
        gap = None if reported is None else reported_revealed_gap(reported, share)
        archetypes = classify_archetypes(
            reported=reported,
            revealed=share,
            baseline_noise=baseline_noise,
            ablated_noise=_f(ablated_noise) if ablated_noise is not None else None,
            order_sensitivity=_f(order_s) if order_s is not None else None,
            thresholds=t,
        )
        rows.append({
            'name': name,
            'focus': name,
            'reported': reported,
            'revealed': share,
            'gap': gap,
            'baseline_noise': baseline_noise,
            'ablated_noise': _f(ablated_noise) if ablated_noise is not None else None,
            'order_sensitivity': _f(order_s) if order_s is not None else None,
            'archetypes': archetypes,
            'prompt_section': item.get('prompt_section') or item.get('focus_text') or '',
            'source': item,
        })
    return rows
