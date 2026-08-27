#!/usr/bin/env python3
"""Align LLM-quoted prompt_section strings to exact offsets in the original prompt.

Ablation always deletes an exact contiguous span of the original prompt. The LLM
may propose a conceptual focus (and even paraphrase), but deterministic grounding
must recover the experimental span before a focus is verified.
"""

from __future__ import annotations

import re
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

# Fold curly / typographic quotes to ASCII so a straight-quote quote can match.
_QUOTE_FOLD = {
    '\u201c': '"',  # left double
    '\u201d': '"',  # right double
    '\u201e': '"',
    '\u00ab': '"',
    '\u00bb': '"',
    '\u2018': "'",  # left single
    '\u2019': "'",  # right single
    '\u201a': "'",
    '`': "'",
}

_TRAILING_PUNCT = frozenset('.!?,;:…')

# Token pattern for conservative formatting-only alignment.
_TOKEN_RE = re.compile(r'\w+|[^\w\s]', re.UNICODE)


def _fold_char(ch: str) -> str:
    return _QUOTE_FOLD.get(ch, ch)


def _build_ws_norm(text: str) -> Tuple[str, List[int], List[int]]:
    """
    Whitespace-normalise and fold quotes.

    Returns (normalized, orig_start_per_norm_char, orig_end_per_norm_char).
    Consecutive whitespace collapses to a single space. Leading/trailing
    whitespace in the normalised string is stripped.
    """
    norm_chars: List[str] = []
    orig_start: List[int] = []
    orig_end: List[int] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        folded = _fold_char(ch)
        if folded.isspace():
            run_start = i
            while i < n and _fold_char(text[i]).isspace():
                i += 1
            if norm_chars:
                orig_start.append(run_start)
                orig_end.append(i)
                norm_chars.append(' ')
            continue
        orig_start.append(i)
        orig_end.append(i + 1)
        norm_chars.append(folded)
        i += 1

    while norm_chars and norm_chars[-1] == ' ':
        norm_chars.pop()
        orig_start.pop()
        orig_end.pop()

    return ''.join(norm_chars), orig_start, orig_end


def _map_norm_span(
    orig_start: List[int],
    orig_end: List[int],
    ns: int,
    ne: int,
) -> Optional[Tuple[int, int]]:
    if ns < 0 or ne > len(orig_start) or ns >= ne:
        return None
    return orig_start[ns], orig_end[ne - 1]


def _find_exact(prompt: str, quote: str) -> Optional[Tuple[int, int]]:
    if not quote:
        return None
    idx = prompt.find(quote)
    if idx < 0:
        return None
    return idx, idx + len(quote)


def _find_all_exact(prompt: str, quote: str) -> List[Tuple[int, int]]:
    if not quote:
        return []
    out: List[Tuple[int, int]] = []
    start = 0
    while True:
        idx = prompt.find(quote, start)
        if idx < 0:
            break
        out.append((idx, idx + len(quote)))
        start = idx + 1
    return out


def _find_ws_norm(prompt: str, quote: str) -> Optional[Tuple[int, int]]:
    if not quote or not prompt:
        return None
    p_norm, p_start, p_end = _build_ws_norm(prompt)
    q_norm, _, _ = _build_ws_norm(quote)
    if not q_norm:
        return None
    ns = p_norm.find(q_norm)
    if ns < 0:
        return None
    return _map_norm_span(p_start, p_end, ns, ns + len(q_norm))


def _find_all_ws_norm(prompt: str, quote: str) -> List[Tuple[int, int]]:
    if not quote or not prompt:
        return []
    p_norm, p_start, p_end = _build_ws_norm(prompt)
    q_norm, _, _ = _build_ws_norm(quote)
    if not q_norm:
        return []
    out: List[Tuple[int, int]] = []
    start = 0
    while True:
        ns = p_norm.find(q_norm, start)
        if ns < 0:
            break
        mapped = _map_norm_span(p_start, p_end, ns, ns + len(q_norm))
        if mapped:
            out.append(mapped)
        start = ns + 1
    return out


def _strip_trailing_punct(text: str) -> str:
    i = len(text)
    while i > 0 and text[i - 1] in _TRAILING_PUNCT:
        i -= 1
    return text[:i]


def _extend_trailing_punct(prompt: str, start: int, end: int) -> Tuple[int, int]:
    """Include trailing punctuation after the match when it ends the token/sentence."""
    trial = end
    while trial < len(prompt) and prompt[trial] in _TRAILING_PUNCT:
        trial += 1
    if trial > end and (trial == len(prompt) or prompt[trial].isspace()):
        return start, trial
    return start, end


def _unique_or_none(spans: List[Tuple[int, int]]) -> Optional[Tuple[int, int]]:
    if len(spans) == 1:
        return spans[0]
    return None


def _locate_unique(prompt: str, quote: str) -> Tuple[Optional[Tuple[int, int]], str, bool]:
    """
    Locate quote in prompt.

    Returns (span_or_none, method, ambiguous).
    Distinguishes zero matches, unique match, and ambiguous multi-match.
    Does NOT treat literal backslash-n as a newline (or vice versa).
    """
    if quote is None:
        return None, '', False
    quote = str(quote)
    if not quote:
        return None, '', False

    exact = _find_all_exact(prompt, quote)
    if len(exact) > 1:
        return None, 'exact', True
    if len(exact) == 1:
        span = _extend_trailing_punct(prompt, exact[0][0], exact[0][1])
        return span, 'exact', False

    ws = _find_all_ws_norm(prompt, quote)
    if len(ws) > 1:
        return None, 'whitespace_normalized', True
    if len(ws) == 1:
        span = _extend_trailing_punct(prompt, ws[0][0], ws[0][1])
        return span, 'whitespace_normalized', False

    stripped = _strip_trailing_punct(quote.rstrip())
    if stripped and stripped != quote:
        exact = _find_all_exact(prompt, stripped)
        if len(exact) > 1:
            return None, 'exact_stripped_punct', True
        if len(exact) == 1:
            span = _extend_trailing_punct(prompt, exact[0][0], exact[0][1])
            return span, 'exact_stripped_punct', False
        ws = _find_all_ws_norm(prompt, stripped)
        if len(ws) > 1:
            return None, 'whitespace_normalized_stripped_punct', True
        if len(ws) == 1:
            span = _extend_trailing_punct(prompt, ws[0][0], ws[0][1])
            return span, 'whitespace_normalized_stripped_punct', False

    return None, '', False


def align_quote(prompt: str, quote: str) -> Optional[Tuple[int, int]]:
    """
    Locate `quote` in `prompt` (first unique hit).

    1. Exact substring (ambiguous multi-hit → None).
    2. Whitespace-normalised match (quote folding + collapsed whitespace).
    3. Same after stripping trailing punctuation from the quote.

    After a hit, include immediately following trailing punctuation when it
    sits at a token/sentence boundary (truncation).
    """
    span, _method, ambiguous = _locate_unique(prompt, quote)
    if ambiguous:
        return None
    return span


def _token_align_span(prompt: str, quote: str) -> Tuple[Optional[Tuple[int, int]], bool]:
    """
    Conservative token/sequence alignment for formatting-only discrepancies.

    Allows quote-fold and whitespace differences only. Requires an unambiguous
    contiguous mapping of all non-whitespace quote tokens onto the prompt.
    Returns (span, ambiguous).
    """
    if not quote or not prompt:
        return None, False

    q_tokens = [(m.group(0), m.start(), m.end()) for m in _TOKEN_RE.finditer(quote)]
    p_tokens = [(m.group(0), m.start(), m.end()) for m in _TOKEN_RE.finditer(prompt)]
    if not q_tokens or not p_tokens:
        return None, False

    q_folded = [_fold_char(t[0]) for t in q_tokens]
    p_folded = [_fold_char(t[0]) for t in p_tokens]
    qn = len(q_folded)
    pn = len(p_folded)
    if qn > pn:
        return None, False

    hits: List[Tuple[int, int]] = []
    for i in range(pn - qn + 1):
        if p_folded[i : i + qn] == q_folded:
            start = p_tokens[i][1]
            end = p_tokens[i + qn - 1][2]
            hits.append((start, end))

    if not hits:
        return None, False
    if len(hits) > 1:
        return None, True
    span = _extend_trailing_punct(prompt, hits[0][0], hits[0][1])
    return span, False


def _enclosing_line_span(prompt: str, start: int, end: int) -> Tuple[int, int]:
    left = prompt.rfind('\n', 0, start)
    right = prompt.find('\n', end)
    a = 0 if left < 0 else left + 1
    b = len(prompt) if right < 0 else right
    return a, b


def _enclosing_sentence_span(prompt: str, start: int, end: int) -> Tuple[int, int]:
    """Expand to nearest sentence/newline boundaries around [start, end)."""
    seps = set('.!?\n')
    a = start
    while a > 0 and prompt[a - 1] not in seps:
        a -= 1
    b = end
    while b < len(prompt) and prompt[b] not in seps:
        b += 1
    if b < len(prompt) and prompt[b] in '.!?':
        b += 1
    # Trim surrounding whitespace for a clean span.
    while a < b and prompt[a].isspace():
        a += 1
    while b > a and prompt[b - 1].isspace():
        b -= 1
    return a, b


def _expand_from_anchor(
    prompt: str,
    anchor: Tuple[int, int],
    proposed: str,
) -> Optional[Tuple[int, int]]:
    """
    Expand a unique evidence anchor using nearby original text.

    1. Unique whitespace/exact match of `proposed` that covers the anchor.
    2. Else the enclosing sentence/line containing the anchor, when larger than
       the anchor (proposal may be paraphrased; the recovered span is still
       exact original text).
    """
    a0, a1 = anchor
    if proposed:
        candidates = _find_all_ws_norm(prompt, proposed) + _find_all_exact(prompt, proposed)
        covering = [c for c in candidates if c[0] <= a0 and c[1] >= a1]
        # Deduplicate
        covering = list(dict.fromkeys(covering))
        if len(covering) == 1:
            return _extend_trailing_punct(prompt, covering[0][0], covering[0][1])

    for builder in (_enclosing_sentence_span, _enclosing_line_span):
        span = builder(prompt, a0, a1)
        if span[0] <= a0 and span[1] >= a1 and (span[1] - span[0]) > (a1 - a0):
            return span
    return None


def ground_focus_span(prompt: str, focus: Dict) -> Dict:
    """
    Deterministically ground a focus proposal to an exact contiguous prompt span.

    Matching order:
      1. exact / whitespace-normalized / punct-stripped match on prompt_section
      2. same on evidence_quote
      3. unique evidence_quote as anchor + optional expansion to proposed section
      4. conservative token alignment (formatting-only)

    If multiple plausible spans exist, the focus is left unverified (ambiguous).
    Never invents spans via unconstrained semantic similarity.
    """
    proposal = str(focus.get('prompt_section') or '')
    evidence = str(focus.get('evidence_quote') or focus.get('evidence') or '')
    original_proposal = proposal

    result = {
        'verified': False,
        'char_start': None,
        'char_end': None,
        'grounding_method': None,
        'grounding_confidence': 0.0,
        'grounding_failure': None,
        'original_proposal': original_proposal,
        'evidence_quote': evidence or None,
        'prompt_section': proposal,
    }

    # Trusted manual / prior offsets.
    existing_start = focus.get('char_start')
    existing_end = focus.get('char_end')
    if (
        isinstance(existing_start, int)
        and isinstance(existing_end, int)
        and 0 <= existing_start < existing_end <= len(prompt)
    ):
        result.update({
            'verified': True,
            'char_start': existing_start,
            'char_end': existing_end,
            'grounding_method': 'provided_offsets',
            'grounding_confidence': 1.0,
            'prompt_section': prompt[existing_start:existing_end],
            'grounding_failure': None,
        })
        return result

    # 1. Proposed prompt_section
    span, method, ambiguous = _locate_unique(prompt, proposal)
    if ambiguous and not evidence:
        result['grounding_failure'] = 'ambiguous_prompt_section'
        result['grounding_method'] = method or 'ambiguous'
        return result
    if span is not None and not ambiguous:
        result.update({
            'verified': True,
            'char_start': span[0],
            'char_end': span[1],
            'grounding_method': method,
            'grounding_confidence': 1.0 if method == 'exact' else 0.9,
            'prompt_section': prompt[span[0]:span[1]],
        })
        return result

    # 2–3. evidence_quote
    if evidence:
        espan, emethod, eamb = _locate_unique(prompt, evidence)
        if eamb:
            result['grounding_failure'] = 'ambiguous_evidence_quote'
            result['grounding_method'] = emethod or 'ambiguous'
            return result
        if espan is not None:
            expanded = _expand_from_anchor(prompt, espan, proposal) if proposal else None
            if expanded is not None and expanded != espan:
                result.update({
                    'verified': True,
                    'char_start': expanded[0],
                    'char_end': expanded[1],
                    'grounding_method': 'evidence_anchor_expanded',
                    'grounding_confidence': 0.8,
                    'prompt_section': prompt[expanded[0]:expanded[1]],
                })
                return result
            result.update({
                'verified': True,
                'char_start': espan[0],
                'char_end': espan[1],
                'grounding_method': f'evidence_{emethod}' if emethod else 'evidence_quote',
                'grounding_confidence': 0.85,
                'prompt_section': prompt[espan[0]:espan[1]],
            })
            return result

    # 4. Conservative token alignment on proposal, then evidence.
    for label, text, conf in (
        ('token_align_prompt_section', proposal, 0.7),
        ('token_align_evidence_quote', evidence, 0.65),
    ):
        if not text:
            continue
        tspan, tamb = _token_align_span(prompt, text)
        if tamb:
            result['grounding_failure'] = f'ambiguous_{label}'
            result['grounding_method'] = label
            return result
        if tspan is not None:
            result.update({
                'verified': True,
                'char_start': tspan[0],
                'char_end': tspan[1],
                'grounding_method': label,
                'grounding_confidence': conf,
                'prompt_section': prompt[tspan[0]:tspan[1]],
            })
            return result

    result['grounding_failure'] = 'no_unique_span'
    return result


def verify_focus(prompt: str, focus: Dict) -> Dict:
    """
    Copy a focus dict and ground it to an exact original span when possible.

    For verified foci, ``prompt_section`` is overwritten with
    ``prompt[char_start:char_end]`` so ablation always deletes source text.
    """
    out = dict(focus)
    grounded = ground_focus_span(prompt, out)
    out['verified'] = grounded['verified']
    out['char_start'] = grounded['char_start']
    out['char_end'] = grounded['char_end']
    out['grounding_method'] = grounded.get('grounding_method')
    out['grounding_confidence'] = grounded.get('grounding_confidence', 0.0)
    out['grounding_failure'] = grounded.get('grounding_failure')
    out['original_proposal'] = grounded.get('original_proposal')
    if grounded.get('evidence_quote') is not None:
        out['evidence_quote'] = grounded['evidence_quote']
    if grounded['verified']:
        out['prompt_section'] = grounded['prompt_section']
    return out


def verify_foci(prompt: str, foci: List[Dict]) -> List[Dict]:
    return [verify_focus(prompt, f) for f in (foci or [])]


def spans_overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    """Half-open intervals. Adjacent spans do not overlap."""
    return a_start < b_end and b_start < a_end


def compute_coverage_report(prompt: str, foci: List[Dict]) -> Dict:
    """
    Coverage of the prompt by verified static (non-dynamic) foci.

    Boilerplate and dynamic slots may legitimately remain uncovered; this report
    makes missing coverage visible without requiring 100%.
    """
    n = len(prompt)
    covered = [False] * n
    verified_static = []
    unverified = []
    overlaps = []
    dynamic = []

    grounded = verify_foci(prompt, foci) if foci and not all(
        'verified' in f for f in (foci or [])
    ) else [dict(f) for f in (foci or [])]

    # Prefer already-verified fields when present.
    items = []
    for f in (foci or []):
        item = dict(f)
        if 'verified' not in item:
            item = verify_focus(prompt, item)
        items.append(item)

    verified_spans: List[Tuple[int, int, str]] = []
    for item in items:
        name = item.get('focus') or ''
        if item.get('is_dynamic'):
            dynamic.append(name)
            continue
        if not item.get('verified'):
            unverified.append({
                'focus': name,
                'original_proposal': item.get('original_proposal') or item.get('prompt_section'),
                'evidence_quote': item.get('evidence_quote'),
                'grounding_failure': item.get('grounding_failure') or 'unverified',
            })
            continue
        start, end = item['char_start'], item['char_end']
        verified_static.append({
            'focus': name,
            'char_start': start,
            'char_end': end,
            'prompt_section': item.get('prompt_section'),
            'grounding_method': item.get('grounding_method'),
        })
        verified_spans.append((start, end, name))
        for i in range(start, end):
            covered[i] = True

    for i in range(len(verified_spans)):
        a0, a1, an = verified_spans[i]
        for j in range(i + 1, len(verified_spans)):
            b0, b1, bn = verified_spans[j]
            if spans_overlap(a0, a1, b0, b1):
                overlaps.append({'a': an, 'b': bn, 'a_span': [a0, a1], 'b_span': [b0, b1]})

    uncovered_spans: List[Dict] = []
    i = 0
    while i < n:
        if covered[i]:
            i += 1
            continue
        j = i + 1
        while j < n and not covered[j]:
            j += 1
        text = prompt[i:j]
        # Skip pure-whitespace microgaps in the uncovered list? Keep them for honesty.
        uncovered_spans.append({'char_start': i, 'char_end': j, 'text': text})
        i = j

    covered_chars = sum(1 for c in covered if c)
    pct = (100.0 * covered_chars / n) if n else 0.0
    return {
        'prompt_length': n,
        'covered_chars': covered_chars,
        'coverage_percent': round(pct, 2),
        'verified_static_foci': verified_static,
        'unverified_proposals': unverified,
        'overlaps': overlaps,
        'dynamic_foci': dynamic,
        'uncovered_spans': uncovered_spans,
    }


def collapse_deletion_boundary(left: str, right: str) -> Tuple[str, bool]:
    """
    If deletion joins blank lines from both sides, collapse that join to one blank line.

    Doubled blank lines means both sides contribute newlines and the join has 3+
    consecutive newlines. Unrelated blank lines elsewhere are left intact.
    """
    def trailing_newlines(s: str) -> int:
        n = 0
        for ch in reversed(s):
            if ch == '\n':
                n += 1
            else:
                break
        return n

    def leading_newlines(s: str) -> int:
        n = 0
        for ch in s:
            if ch == '\n':
                n += 1
            else:
                break
        return n

    t = trailing_newlines(left)
    l = leading_newlines(right)
    if t >= 1 and l >= 1 and (t + l) >= 3:
        return left.rstrip('\n') + '\n\n' + right.lstrip('\n'), True
    return left + right, False


def delete_span(prompt: str, start: int, end: int) -> Tuple[str, bool, bool]:
    """
    Strict subtractive deletion of prompt[start:end].

    Returns (ablated_prompt, prompt_empty, boundary_collapsed).
    """
    if start < 0 or end > len(prompt) or start > end:
        raise ValueError(f'Invalid span [{start}, {end}) for prompt of length {len(prompt)}')
    left = prompt[:start]
    right = prompt[end:]
    ablated, collapsed = collapse_deletion_boundary(left, right)
    return ablated, (not ablated.strip()), collapsed


def build_shuffled_remaining_prompt(
    prompt: str,
    classified: Sequence[Mapping[str, Any]],
    removed_index: int,
    *,
    shuffle_seed: Optional[int] = None,
    separator: str = '\n\n',
) -> Tuple[str, bool, List[str], List[str]]:
    """
    Remove one focus and reassemble the remaining attributable spans in shuffled order.

    Tests whether ablation significance is robust to structural hierarchy (section
    ordering) rather than only to strict subtractive deletion in document order.

    Returns (ablated_prompt, prompt_empty, document_order_names, shuffled_order_names).
    """
    import random

    if removed_index < 0 or removed_index >= len(classified):
        raise ValueError('removed_index out of range')
    removed = classified[removed_index]
    if not removed.get('attributable'):
        raise ValueError(
            f"Focus '{removed.get('focus')}' cannot be ablated ({removed.get('reason')})"
        )

    remaining: List[Tuple[str, str]] = []
    for i, focus in enumerate(classified):
        if i == removed_index or not focus.get('attributable'):
            continue
        start = int(focus['char_start'])
        end = int(focus['char_end'])
        text = prompt[start:end].strip()
        name = (focus.get('focus') or focus.get('focus_name') or f'Focus {i + 1}').strip()
        if text:
            remaining.append((name, text))

    document_order = [name for name, _ in remaining]
    if len(remaining) <= 1:
        shuffled_pairs = list(remaining)
    else:
        shuffled_pairs = list(remaining)
        rng = random.Random(shuffle_seed)
        rng.shuffle(shuffled_pairs)
    shuffled_order = [name for name, _ in shuffled_pairs]
    ablated = separator.join(text for _, text in shuffled_pairs).strip()
    return ablated, (not ablated), document_order, shuffled_order


def classify_foci_for_ablation(prompt: str, foci: List[Dict]) -> List[Dict]:
    """
    Verify spans, exclude dynamic foci, and refuse overlapping verified static foci.

    Each item is a copy of the input focus plus:
      verified, char_start, char_end, attributable, reason, overlap_with
    """
    classified = []
    for focus in foci or []:
        item = verify_focus(prompt, focus)
        item['overlap_with'] = []
        if item.get('is_dynamic'):
            item['attributable'] = False
            item['reason'] = 'dynamic_slot'
        elif not item.get('verified'):
            item['attributable'] = False
            item['reason'] = 'unverified'
        else:
            item['attributable'] = True
            item['reason'] = None
        classified.append(item)

    n = len(classified)
    for i in range(n):
        a = classified[i]
        if not a.get('verified') or a.get('is_dynamic'):
            continue
        for j in range(i + 1, n):
            b = classified[j]
            if not b.get('verified') or b.get('is_dynamic'):
                continue
            if spans_overlap(a['char_start'], a['char_end'], b['char_start'], b['char_end']):
                a_name = a.get('focus') or f'Focus {i + 1}'
                b_name = b.get('focus') or f'Focus {j + 1}'
                a['attributable'] = False
                a['reason'] = 'overlap'
                if b_name not in a['overlap_with']:
                    a['overlap_with'].append(b_name)
                b['attributable'] = False
                b['reason'] = 'overlap'
                if a_name not in b['overlap_with']:
                    b['overlap_with'].append(a_name)

    return classified
