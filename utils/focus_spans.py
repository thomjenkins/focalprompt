#!/usr/bin/env python3
"""
Multi-span, overlapping focus model helpers.

A focus is a semantic/experimental unit with one or more prompt spans.
Spans may be non-contiguous within a focus; different foci may overlap.

Legacy single-span fields (char_start, char_end, prompt_section) remain as
derived compatibility views — spans[] is the source of truth once normalized.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

SpanTuple = Tuple[int, int]


def _new_id(prefix: str = 'sp') -> str:
    return f'{prefix}_{uuid.uuid4().hex[:10]}'


def _as_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def span_length(start: int, end: int) -> int:
    return max(0, end - start)


def validate_span_bounds(start: int, end: int, prompt_len: int) -> None:
    if start < 0 or end < 0 or start > end or end > prompt_len:
        raise ValueError(
            f'Invalid span [{start}, {end}) for prompt length {prompt_len}'
        )


def merge_intervals(spans: Sequence[SpanTuple]) -> List[SpanTuple]:
    """Union of half-open intervals (sorted, non-overlapping)."""
    cleaned = sorted(
        ((int(s), int(e)) for s, e in spans if e > s),
        key=lambda se: se[0],
    )
    if not cleaned:
        return []
    out: List[List[int]] = [[cleaned[0][0], cleaned[0][1]]]
    for s, e in cleaned[1:]:
        if s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return [(s, e) for s, e in out]


def intervals_intersection_length(a: Sequence[SpanTuple], b: Sequence[SpanTuple]) -> int:
    """Length of intersection of two interval unions."""
    au = merge_intervals(a)
    bu = merge_intervals(b)
    i = j = 0
    total = 0
    while i < len(au) and j < len(bu):
        a0, a1 = au[i]
        b0, b1 = bu[j]
        left = max(a0, b0)
        right = min(a1, b1)
        if left < right:
            total += right - left
        if a1 <= b1:
            i += 1
        else:
            j += 1
    return total


def intervals_contain(outer: Sequence[SpanTuple], inner: Sequence[SpanTuple]) -> bool:
    """True if every point in inner is covered by outer."""
    ou = merge_intervals(outer)
    iu = merge_intervals(inner)
    if not iu:
        return True
    if not ou:
        return False
    for i0, i1 in iu:
        covered = 0
        for o0, o1 in ou:
            left = max(i0, o0)
            right = min(i1, o1)
            if left < right:
                covered += right - left
        if covered < (i1 - i0):
            return False
    return True


def normalize_span_dict(
    span: Mapping[str, Any],
    *,
    prompt: Optional[str] = None,
    require_bounds: bool = False,
) -> Dict[str, Any]:
    """Normalize one FocusSpan dict."""
    start = _as_int(span.get('char_start', span.get('start')))
    end = _as_int(span.get('char_end', span.get('end')))
    if start is None or end is None:
        raise ValueError('Span requires char_start and char_end')
    if require_bounds and prompt is not None:
        validate_span_bounds(start, end, len(prompt))
    elif end < start:
        raise ValueError(f'Invalid span [{start}, {end})')

    out = dict(span)
    out['id'] = str(span.get('id') or _new_id())
    out['char_start'] = start
    out['char_end'] = end
    # Deprecated aliases kept for readability
    out['start'] = start
    out['end'] = end
    if prompt is not None and 0 <= start <= end <= len(prompt):
        text = prompt[start:end]
        snap = span.get('text') or span.get('text_snapshot')
        if snap is not None and str(snap) != text:
            raise ValueError(
                f'Span text snapshot does not match prompt[{start}:{end}]'
            )
        out['text'] = text
        out['text_snapshot'] = text
    elif span.get('text') is not None:
        out['text'] = str(span.get('text'))
        out['text_snapshot'] = out['text']
    return out


def extract_raw_spans(focus: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Pull span dicts from a focus in either legacy or multi-span form."""
    spans = focus.get('spans')
    if isinstance(spans, list) and spans:
        return [dict(s) for s in spans if isinstance(s, Mapping)]

    start = _as_int(focus.get('char_start', focus.get('start')))
    end = _as_int(focus.get('char_end', focus.get('end')))
    if start is not None and end is not None and end >= start:
        return [{
            'char_start': start,
            'char_end': end,
            'text': focus.get('prompt_section') or focus.get('text'),
            'grounding_method': focus.get('grounding_method'),
            'grounding_confidence': focus.get('grounding_confidence'),
            'id': focus.get('span_id') or _new_id(),
        }]
    return []


def dedupe_identical_spans(spans: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Drop exact duplicate ranges within one focus (keep first)."""
    seen = set()
    out: List[Dict[str, Any]] = []
    for span in spans:
        start = _as_int(span.get('char_start', span.get('start')))
        end = _as_int(span.get('char_end', span.get('end')))
        if start is None or end is None:
            continue
        key = (start, end)
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(span))
    return out


def normalize_focus(
    focus: Mapping[str, Any],
    *,
    prompt: Optional[str] = None,
    require_bounds: bool = False,
) -> Dict[str, Any]:
    """
    Normalize a focus so spans[] is the source of truth.

    Legacy char_start/char_end/prompt_section are re-derived for compatibility.
    """
    out = dict(focus)
    raw = extract_raw_spans(out)
    if not raw:
        # Unverified / ungrounded focus — keep as-is with empty spans
        out.setdefault('spans', [])
        out['id'] = str(out.get('id') or _new_id('fc'))
        out['span_count'] = 0
        out['is_contiguous'] = True
        out['is_multi_span'] = False
        out['total_span_length'] = 0
        out['unique_span_length'] = 0
        return out

    deduped = dedupe_identical_spans(raw)
    normalized: List[Dict[str, Any]] = []
    for span in deduped:
        normalized.append(
            normalize_span_dict(span, prompt=prompt, require_bounds=require_bounds)
        )
    normalized.sort(key=lambda s: (s['char_start'], s['char_end']))

    tuples = [(s['char_start'], s['char_end']) for s in normalized]
    unioned = merge_intervals(tuples)
    total_len = sum(span_length(s, e) for s, e in tuples)
    unique_len = sum(span_length(s, e) for s, e in unioned)

    out['id'] = str(out.get('id') or _new_id('fc'))
    out['spans'] = normalized
    out['span_count'] = len(normalized)
    out['is_multi_span'] = len(normalized) > 1
    # Contiguous iff the union is a single interval (abutting spans count as contiguous).
    out['is_contiguous'] = len(unioned) == 1
    out['total_span_length'] = total_len
    out['unique_span_length'] = unique_len

    # Legacy derived fields (deprecated as source of truth)
    if normalized:
        out['char_start'] = normalized[0]['char_start']
        out['char_end'] = normalized[-1]['char_end']
        if prompt is not None:
            texts = [prompt[s['char_start']:s['char_end']] for s in normalized]
            out['prompt_section'] = '\n…\n'.join(texts) if len(texts) > 1 else texts[0]
        elif out.get('prompt_section') is None and normalized[0].get('text'):
            texts = [str(s.get('text') or '') for s in normalized]
            out['prompt_section'] = '\n…\n'.join(texts) if len(texts) > 1 else texts[0]

    # Optional relationship fields passthrough
    if 'parent_focus_id' not in out:
        out['parent_focus_id'] = focus.get('parent_focus_id')
    if 'relationships' not in out:
        out['relationships'] = list(focus.get('relationships') or [])
    if 'provenance' not in out:
        method = focus.get('grounding_method') or focus.get('provenance')
        if method == 'manual_selection':
            out['provenance'] = 'manual'
        elif method:
            out['provenance'] = 'auto'
        else:
            out['provenance'] = focus.get('provenance') or 'unknown'

    return out


def spans_overlap_or_adjacent(a0: int, a1: int, b0: int, b1: int) -> bool:
    return a0 <= b1 and b0 <= a1


def spans_overlap(a0: int, a1: int, b0: int, b1: int) -> bool:
    """Half-open intervals. Adjacent spans do not overlap."""
    return a0 < b1 and b0 < a1


def focus_span_tuples(focus: Mapping[str, Any]) -> List[SpanTuple]:
    """Normalized (start, end) list for a focus (legacy-aware)."""
    nf = normalize_focus(focus)
    return [(s['char_start'], s['char_end']) for s in nf.get('spans') or []]


def focus_union_tuples(focus: Mapping[str, Any]) -> List[SpanTuple]:
    return merge_intervals(focus_span_tuples(focus))


def delete_spans(
    prompt: str,
    spans: Sequence[SpanTuple],
    *,
    collapse_boundary: bool = True,
) -> Tuple[str, bool, bool, List[SpanTuple]]:
    """
    Remove multiple half-open ranges from prompt, preserving intervening text.

    Spans are unioned first (same-focus internal overlap), then deleted in
    descending start order to avoid offset drift.

    Returns (ablated_prompt, prompt_empty, any_boundary_collapsed, ablated_ranges).
    """
    from utils.span_alignment import collapse_deletion_boundary

    if not prompt and not spans:
        return '', True, False, []

    unioned = merge_intervals([(int(s), int(e)) for s, e in spans])
    for s, e in unioned:
        validate_span_bounds(s, e, len(prompt))

    collapsed_any = False
    # Build by walking forward and skipping unioned ranges (avoids offset drift)
    parts: List[str] = []
    cursor = 0
    for s, e in unioned:
        if cursor < s:
            parts.append(prompt[cursor:s])
        cursor = e
    if cursor < len(prompt):
        parts.append(prompt[cursor:])

    if not collapse_boundary or len(parts) <= 1:
        ablated = ''.join(parts)
        return ablated, (not ablated.strip()), False, unioned

    # Collapse doubled blank lines only at deletion joins
    ablated = parts[0] if parts else ''
    for piece in parts[1:]:
        ablated, collapsed = collapse_deletion_boundary(ablated, piece)
        collapsed_any = collapsed_any or collapsed
    return ablated, (not ablated.strip()), collapsed_any, unioned


def delete_focus_spans(
    prompt: str,
    focus: Mapping[str, Any],
) -> Tuple[str, bool, bool, List[SpanTuple]]:
    """Ablate all spans belonging to one focus."""
    return delete_spans(prompt, focus_span_tuples(focus))


def coverage_depth_map(prompt_len: int, foci: Sequence[Mapping[str, Any]]) -> List[int]:
    """Per-character focus membership count (static verified spans only when flagged)."""
    depth = [0] * prompt_len
    for focus in foci:
        if focus.get('is_dynamic'):
            continue
        if 'verified' in focus and not focus.get('verified'):
            continue
        for s, e in focus_union_tuples(focus):
            s2 = max(0, min(prompt_len, s))
            e2 = max(0, min(prompt_len, e))
            for i in range(s2, e2):
                depth[i] += 1
    return depth


def compute_coverage_metrics(
    prompt: str,
    foci: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """
    Unique coverage (≤100%) and focus density (may exceed 100%).

    Unique coverage = union(all focus spans) / prompt length
    Focus density = sum(span lengths including overlaps) / prompt length
    """
    n = len(prompt or '')
    if n == 0:
        return {
            'prompt_length': 0,
            'unique_coverage_percent': 0.0,
            'focus_density_percent': 0.0,
            'covered_chars_unique': 0,
            'covered_chars_total': 0,
            'coverage_percent': 0.0,  # legacy alias = unique
            'depth_histogram': {'uncovered': 0, 'once': 0, 'twice': 0, 'three_plus': 0},
            'depth_percent': {'uncovered': 0.0, 'once': 0.0, 'twice': 0.0, 'three_plus': 0.0},
        }

    static: List[Mapping[str, Any]] = []
    for f in foci or []:
        if f.get('is_dynamic'):
            continue
        if 'verified' in f and not f.get('verified'):
            continue
        # Include if has usable spans
        if focus_span_tuples(f):
            static.append(f)

    depth = coverage_depth_map(n, static)
    unique = sum(1 for d in depth if d > 0)
    total = sum(d for d in depth)
    hist = {
        'uncovered': sum(1 for d in depth if d == 0),
        'once': sum(1 for d in depth if d == 1),
        'twice': sum(1 for d in depth if d == 2),
        'three_plus': sum(1 for d in depth if d >= 3),
    }
    unique_pct = round(100.0 * unique / n, 2)
    density_pct = round(100.0 * total / n, 2)
    return {
        'prompt_length': n,
        'unique_coverage_percent': unique_pct,
        'focus_density_percent': density_pct,
        'covered_chars_unique': unique,
        'covered_chars_total': total,
        'coverage_percent': unique_pct,  # backwards-compatible alias
        'depth_histogram': hist,
        'depth_percent': {
            k: round(100.0 * v / n, 2) for k, v in hist.items()
        },
    }


def pairwise_overlap(
    focus_a: Mapping[str, Any],
    focus_b: Mapping[str, Any],
) -> Dict[str, Any]:
    """Directional overlap statistics between two foci (union-of-spans)."""
    a = focus_union_tuples(focus_a)
    b = focus_union_tuples(focus_b)
    inter = intervals_intersection_length(a, b)
    len_a = sum(span_length(s, e) for s, e in a) or 0
    len_b = sum(span_length(s, e) for s, e in b) or 0
    union = len_a + len_b - inter
    pct_of_a = round(100.0 * inter / len_a, 2) if len_a else 0.0
    pct_of_b = round(100.0 * inter / len_b, 2) if len_b else 0.0
    jaccard = round(inter / union, 4) if union else 0.0
    if inter <= 0:
        relation = 'disjoint'
    elif intervals_contain(a, b) and intervals_contain(b, a):
        relation = 'identical'
    elif intervals_contain(a, b):
        relation = 'a_contains_b'
    elif intervals_contain(b, a):
        relation = 'b_contains_a'
    else:
        relation = 'partial'
    return {
        'a_id': focus_a.get('id'),
        'b_id': focus_b.get('id'),
        'a_name': focus_a.get('focus') or focus_a.get('name'),
        'b_name': focus_b.get('focus') or focus_b.get('name'),
        'intersection_length': inter,
        'overlap_pct_of_a': pct_of_a,
        'overlap_pct_of_b': pct_of_b,
        'jaccard': jaccard,
        'relation': relation,
        'a_contains_b': relation in ('a_contains_b', 'identical'),
        'b_contains_a': relation in ('b_contains_a', 'identical'),
    }


def overlap_matrix(foci: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """All unordered pairs with non-zero intersection (plus relation metadata)."""
    items = [normalize_focus(f) for f in (foci or [])]
    pairs: List[Dict[str, Any]] = []
    for i in range(len(items)):
        if items[i].get('is_dynamic'):
            continue
        for j in range(i + 1, len(items)):
            if items[j].get('is_dynamic'):
                continue
            info = pairwise_overlap(items[i], items[j])
            if info['intersection_length'] > 0:
                pairs.append(info)
    return pairs


def affected_overlapping_foci(
    ablated_focus: Mapping[str, Any],
    all_foci: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    """
    When ablating one focus, report how much of each other focus was also removed.
    """
    removed = focus_union_tuples(ablated_focus)
    ablated_name = ablated_focus.get('focus') or ablated_focus.get('name')
    ablated_id = ablated_focus.get('id')
    out: List[Dict[str, Any]] = []
    for other in all_foci or []:
        other_id = other.get('id')
        other_name = other.get('focus') or other.get('name')
        if other_id and ablated_id and other_id == ablated_id:
            continue
        if other_name == ablated_name and not other_id:
            continue
        if other.get('is_dynamic'):
            continue
        other_union = focus_union_tuples(other)
        if not other_union:
            continue
        inter = intervals_intersection_length(removed, other_union)
        if inter <= 0:
            continue
        other_len = sum(span_length(s, e) for s, e in other_union) or 1
        pct = round(100.0 * inter / other_len, 2)
        out.append({
            'focus_id': other_id,
            'focus': other_name,
            'overlap_removed_pct': pct,
            'overlap_removed_chars': inter,
            'focus_unique_chars': other_len,
        })
    out.sort(key=lambda r: -r['overlap_removed_pct'])
    return out


def is_order_movable(focus: Mapping[str, Any]) -> bool:
    """
    Contiguous foci (single union region) may be positionally moved.
    Non-contiguous multi-span semantic foci are not movable as one block.
    """
    nf = normalize_focus(focus)
    if nf.get('is_dynamic'):
        return False
    if 'verified' in nf and not nf.get('verified'):
        return False
    if not nf.get('spans'):
        return False
    return bool(nf.get('is_contiguous'))


def normalize_foci(
    foci: Sequence[Mapping[str, Any]],
    *,
    prompt: Optional[str] = None,
) -> List[Dict[str, Any]]:
    return [normalize_focus(f, prompt=prompt) for f in (foci or [])]
