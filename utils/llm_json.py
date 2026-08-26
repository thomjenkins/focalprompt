#!/usr/bin/env python3
"""Parse JSON from LLM chat responses (plain or markdown-fenced)."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

# Models often re-echo long prompt spans into JSON and hit the output cap
# mid-string. Strip complete or truncated prompt_section fields before parse.
_PROMPT_SECTION_FIELD_RE = re.compile(
    r',?\s*"prompt_section"\s*:\s*"(?:\\.|[^"\\])*(?:"|$)',
    re.DOTALL,
)

_FOCUS_OBJECT_RE = re.compile(
    r'\{\s*"focus"\s*:\s*"(?P<focus>(?:\\.|[^"\\])*)"\s*,'
    r'(?:[^}]*?"score"\s*:\s*(?P<score>-?\d+(?:\.\d+)?)[^}]*?)'
    r'(?:[^}]*?"explanation"\s*:\s*"(?P<explanation>(?:\\.|[^"\\])*)")?'
    r'[^}]*\}',
    re.DOTALL,
)


def strip_prompt_section_fields(text: str) -> str:
    """Remove prompt_section key/values, including truncated mid-string values."""
    if not text:
        return text
    cleaned = _PROMPT_SECTION_FIELD_RE.sub('', text)
    # Clean up dangling commas left by removals: { , "focus" or , }
    cleaned = re.sub(r'\{\s*,', '{', cleaned)
    cleaned = re.sub(r',\s*,', ',', cleaned)
    cleaned = re.sub(r',\s*([}\]])', r'\1', cleaned)
    return cleaned


def _unescape_json_string(value: str) -> str:
    try:
        return json.loads(f'"{value}"')
    except json.JSONDecodeError:
        return value.replace('\\"', '"').replace('\\n', '\n')


def recover_assessment_foci(text: str) -> Optional[Dict[str, Any]]:
    """
    Best-effort recovery when assessment JSON was truncated.

    Returns a dict with foci (and optional overall_summary) if at least one
    complete focus+score object can be salvaged; otherwise None.
    """
    if not text:
        return None
    cleaned = strip_prompt_section_fields(text)
    foci: List[Dict[str, Any]] = []
    for match in _FOCUS_OBJECT_RE.finditer(cleaned):
        score_raw = match.group('score')
        if score_raw is None:
            continue
        item: Dict[str, Any] = {
            'focus': _unescape_json_string(match.group('focus')),
            'score': float(score_raw),
        }
        expl = match.group('explanation')
        if expl is not None:
            item['explanation'] = _unescape_json_string(expl)
        foci.append(item)
    if not foci:
        return None
    summary = None
    sm = re.search(
        r'"overall_summary"\s*:\s*"(?P<summary>(?:\\.|[^"\\])*)"',
        cleaned,
        re.DOTALL,
    )
    if sm:
        summary = _unescape_json_string(sm.group('summary'))
    out: Dict[str, Any] = {'foci': foci}
    if summary:
        out['overall_summary'] = summary
    return out


def parse_llm_json(content: str) -> Any:
    """
    Parse a JSON object/array from model output.

    Models often wrap JSON in ```json fences even when response_format
    requests json_object. Bare json.loads then fails with
    ``Expecting value: line 1 column 1``.
    """
    text = (content or '').strip()
    if not text:
        raise ValueError('Empty response from LLM')

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fenced = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text, re.IGNORECASE)
    if fenced:
        inner = fenced.group(1).strip()
        try:
            return json.loads(inner)
        except json.JSONDecodeError:
            text = inner

    # Strip echoed prompt_section fields (complete or truncated) then retry.
    stripped = strip_prompt_section_fields(text)
    if stripped != text:
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            start = stripped.find('{')
            end = stripped.rfind('}')
            if start >= 0 and end > start:
                try:
                    return json.loads(stripped[start : end + 1])
                except json.JSONDecodeError:
                    pass

    start = text.find('{')
    end = text.rfind('}')
    if start >= 0 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    start = text.find('[')
    end = text.rfind(']')
    if start >= 0 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    recovered = recover_assessment_foci(text)
    if recovered is not None:
        return recovered

    hint = ''
    stripped_tail = text.rstrip()
    if stripped_tail.count('{') > stripped_tail.count('}') or stripped_tail.count('[') > stripped_tail.count(']'):
        hint = (
            ' Response looks truncated (unbalanced braces). '
            'Retry, or use fewer/shorter foci so the model can finish the JSON.'
        )
    elif stripped_tail.endswith(('"', ',', ':')) or '"prompt_section"' in text[:400]:
        hint = (
            ' Response looks incomplete or mid-string. '
            'Focus assessment no longer requires echoing full prompt spans; retry.'
        )
    raise ValueError(
        f'LLM did not return valid JSON.{hint} Response: {text[:200]}...'
    )


def parse_assessment_json(content: str) -> Dict[str, Any]:
    """Parse assess-focus JSON; tolerate truncated prompt_section echo."""
    result = parse_llm_json(content)
    if not isinstance(result, dict):
        raise ValueError('Assessment JSON must be an object')
    if 'foci' not in result or not isinstance(result.get('foci'), list):
        raise ValueError('Assessment JSON missing foci array')
    # Drop any residual prompt_section keys the model still emitted.
    for item in result['foci']:
        if isinstance(item, dict):
            item.pop('prompt_section', None)
    return result
