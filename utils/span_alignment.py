#!/usr/bin/env python3
"""Align LLM-quoted prompt_section strings to exact offsets in the original prompt."""

from typing import Dict, List, Optional, Tuple

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

    # Strip trailing normalised space
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


def align_quote(prompt: str, quote: str) -> Optional[Tuple[int, int]]:
    """
    Locate `quote` in `prompt`.

    1. Exact substring.
    2. Whitespace-normalised match (quote folding + collapsed whitespace),
       mapped back to original offsets.
    3. Same as (1)–(2) after stripping trailing punctuation from the quote.

    After a hit, include immediately following trailing punctuation when it
    sits at a token/sentence boundary (truncation).
    """
    if quote is None:
        return None
    quote = str(quote)
    if not quote:
        return None

    found = _find_exact(prompt, quote) or _find_ws_norm(prompt, quote)
    if found:
        return _extend_trailing_punct(prompt, found[0], found[1])

    stripped = _strip_trailing_punct(quote.rstrip())
    if stripped and stripped != quote:
        found = _find_exact(prompt, stripped) or _find_ws_norm(prompt, stripped)
        if found:
            return _extend_trailing_punct(prompt, found[0], found[1])

    return None


def verify_focus(prompt: str, focus: Dict) -> Dict:
    """Copy a focus dict and set verified / char_start / char_end from alignment."""
    out = dict(focus)
    existing_start = out.get('char_start')
    existing_end = out.get('char_end')
    if (
        isinstance(existing_start, int)
        and isinstance(existing_end, int)
        and 0 <= existing_start < existing_end <= len(prompt)
    ):
        out['verified'] = True
        out['char_start'] = existing_start
        out['char_end'] = existing_end
        return out

    span = align_quote(prompt, out.get('prompt_section') or '')
    if span is None:
        out['verified'] = False
        out['char_start'] = None
        out['char_end'] = None
        return out

    out['verified'] = True
    out['char_start'] = span[0]
    out['char_end'] = span[1]
    return out


def verify_foci(prompt: str, foci: List[Dict]) -> List[Dict]:
    return [verify_focus(prompt, f) for f in (foci or [])]


def spans_overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    """Half-open intervals. Adjacent spans do not overlap."""
    return a_start < b_end and b_start < a_end


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
