#!/usr/bin/env python3
"""
Deterministic CSV parsing for Batch Analysis.

No LLM calls. Preserves field text exactly as decoded by the CSV reader
(critical for optional per-row ``prompt`` values used in span ablation).
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple


# Soft limits for the research UI (not an LLM concern).
MAX_CSV_BYTES = 20 * 1024 * 1024  # 20 MiB
MAX_CSV_ROWS = 10_000

# Case-insensitive header aliases → canonical input key
_INPUT_ALIASES: Sequence[Tuple[str, Tuple[str, ...]]] = (
    ('chat_content', ('chat_content', 'input', 'chat')),
    ('rag_context', ('rag_context', 'rag', 'context', 'retrieved_context')),
    ('tool_results', ('tool_results', 'tools', 'tool_outputs', 'function_results')),
    ('other_input', ('other_input', 'other', 'other_dynamic')),
)

_OUTPUT_ALIASES = ('output', 'suggested_message', 'response')
_PROMPT_ALIASES = ('prompt', 'system_prompt', 'full_prompt')


@dataclass
class BatchCsvParseResult:
    pairs: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    columns: Dict[str, Any] = field(default_factory=dict)
    missing_input_columns: List[str] = field(default_factory=list)
    unused_input_columns: List[str] = field(default_factory=list)


def _is_blank(value: Optional[str]) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == '')

def _has_unbalanced_quotes(text: str) -> bool:
    """Return True if CSV text ends inside an unclosed double-quoted field."""
    in_quotes = False
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == '"':
            if in_quotes and i + 1 < n and text[i + 1] == '"':
                i += 2
                continue
            in_quotes = not in_quotes
        i += 1
    return in_quotes




def _map_columns(fieldnames: Sequence[str]) -> Dict[str, Optional[str]]:
    lower = {f.lower().strip(): f for f in fieldnames if f is not None}
    mapping: Dict[str, Optional[str]] = {
        'chat_content': None,
        'rag_context': None,
        'tool_results': None,
        'other_input': None,
        'output': None,
        'prompt': None,
    }
    for canonical, aliases in _INPUT_ALIASES:
        for alias in aliases:
            if alias in lower:
                mapping[canonical] = lower[alias]
                break
    for alias in _OUTPUT_ALIASES:
        if alias in lower:
            mapping['output'] = lower[alias]
            break
    for alias in _PROMPT_ALIASES:
        if alias in lower:
            mapping['prompt'] = lower[alias]
            break
    return mapping


def _bind_named_columns(
    fieldnames: Sequence[str],
    expected: Sequence[str],
    skip: set,
) -> Tuple[Dict[str, str], List[str]]:
    """Bind header columns to configured input names.

    Exact header/name matches win, so case-distinct inputs (``Question`` and
    ``question``) bind separately. A case-insensitive fallback only applies when
    it is unambiguous on both sides: exactly one unbound configured name and
    exactly one remaining header for that lowercased key.
    """
    named_columns: Dict[str, str] = {}
    errors: List[str] = []
    expected_names = list(expected)

    candidates: List[Tuple[str, str]] = []
    for header in fieldnames:
        if header is None or header in skip:
            continue
        key = header.strip()
        if not key:
            continue
        candidates.append((header, key))

    exact_names = set(expected_names)
    remaining: List[Tuple[str, str]] = []
    for header, key in candidates:
        if key not in exact_names:
            remaining.append((header, key))
            continue
        if key in named_columns:
            errors.append(f'Duplicate input column: {key}')
            return {}, errors
        named_columns[key] = header

    headers_by_lower: Dict[str, List[str]] = {}
    for _header, key in remaining:
        headers_by_lower.setdefault(key.lower(), []).append(key)

    for header, key in remaining:
        lowered = key.lower()
        rivals = [
            name for name in expected_names
            if name not in named_columns and name.lower() == lowered
        ]
        if len(rivals) > 1:
            errors.append(
                f"Ambiguous input column '{key}': matches configured inputs "
                + ', '.join(rivals)
                + ' only by case. Rename the header to match one exactly.'
            )
            return {}, errors
        if rivals and len(headers_by_lower.get(lowered, [])) > 1:
            errors.append(
                f"Ambiguous input columns {', '.join(headers_by_lower[lowered])}: "
                f"more than one header matches configured input '{rivals[0]}' "
                'only by case. Rename the header to match it exactly.'
            )
            return {}, errors
        name = rivals[0] if rivals else key
        if name in named_columns:
            errors.append(f'Duplicate input column: {name}')
            return {}, errors
        named_columns[name] = header

    return named_columns, errors


def parse_batch_csv_bytes(
    raw: bytes,
    expected_input_names: Optional[Sequence[str]] = None,
) -> BatchCsvParseResult:
    """Parse uploaded CSV bytes into batch pairs."""
    result = BatchCsvParseResult()

    if raw is None or len(raw) == 0:
        result.errors.append('CSV file is empty')
        return result

    if len(raw) > MAX_CSV_BYTES:
        result.errors.append(
            f'CSV file exceeds maximum size of {MAX_CSV_BYTES // (1024 * 1024)} MiB'
        )
        return result

    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        result.errors.append(f'CSV must be UTF-8 encoded: {exc}')
        return result

    if not text.strip():
        result.errors.append('CSV file is empty')
        return result

    if _has_unbalanced_quotes(text):
        result.errors.append('Malformed CSV: unclosed quoted field')
        return result

    # Use csv.reader (not DictReader) so blank physical lines are visible.
    stream = io.StringIO(text, newline='')
    try:
        reader = csv.reader(stream)
        try:
            header_row = next(reader)
        except StopIteration:
            result.errors.append('CSV file is empty or missing a header row')
            return result
        except csv.Error as exc:
            result.errors.append(f'Malformed CSV: {exc}')
            return result
    except csv.Error as exc:
        result.errors.append(f'Malformed CSV: {exc}')
        return result

    fieldnames = header_row
    if not fieldnames or all(_is_blank(f) for f in fieldnames):
        result.errors.append('CSV file is empty or missing a header row')
        return result

    mapping = _map_columns(fieldnames)
    scenario_mode = expected_input_names is not None
    expected = [str(name) for name in (expected_input_names or [])]
    reserved_original = {
        value for key, value in mapping.items()
        if key in ('output', 'prompt') and value is not None
    }
    legacy_original = {
        value for key, value in mapping.items()
        if key not in ('output', 'prompt') and value is not None
    } if not scenario_mode else set()
    named_columns, binding_errors = _bind_named_columns(
        fieldnames, expected, reserved_original | legacy_original
    )
    if binding_errors:
        result.errors.extend(binding_errors)
        return result
    result.missing_input_columns = [name for name in expected if name not in named_columns]
    result.unused_input_columns = (
        [name for name in named_columns if name not in set(expected)]
        if scenario_mode else []
    )
    result.columns = {**mapping, 'named_inputs': named_columns}

    has_input_col = (scenario_mode and not expected) or bool(named_columns) or any(
        mapping[k] for k in ('chat_content', 'rag_context', 'tool_results', 'other_input')
    )
    has_prompt_col = mapping['prompt'] is not None
    has_output_col = mapping['output'] is not None

    header_errors: List[str] = []
    if result.missing_input_columns:
        header_errors.append(
            'Missing named input columns: ' + ', '.join(result.missing_input_columns)
        )
    if not has_input_col and not has_prompt_col:
        header_errors.append(
            'Missing required columns: need at least one input column '
            '(chat_content/input/chat, rag_context/rag, tool_results/tools, '
            'other_input/other) and/or a prompt column (prompt/system_prompt/full_prompt)'
        )
    if not has_output_col:
        header_errors.append(
            'Missing required output column (output, suggested_message, or response)'
        )
    if header_errors:
        result.errors.extend(header_errors)
        return result

    if result.unused_input_columns:
        result.warnings.append(
            'Unused input columns: ' + ', '.join(result.unused_input_columns)
        )

    # Index of each canonical column in the header row.
    col_index = {name: fieldnames.index(name) for name in fieldnames if name}

    data_rows_seen = 0
    row_num = 1  # header is row 1
    try:
        for raw_row in reader:
            row_num += 1
            # Completely empty physical line (csv.reader yields []).
            if len(raw_row) == 0 or all(_is_blank(c) for c in raw_row):
                result.warnings.append(f'Row {row_num}: skipped blank row')
                continue

            data_rows_seen += 1
            if data_rows_seen > MAX_CSV_ROWS:
                result.errors.append(
                    f'CSV exceeds maximum of {MAX_CSV_ROWS} data rows'
                )
                return result

            def cell(col_name: Optional[str]) -> str:
                if not col_name:
                    return ''
                idx = col_index.get(col_name)
                if idx is None or idx >= len(raw_row):
                    return ''
                val = raw_row[idx]
                return val if isinstance(val, str) else str(val)

            inputs: Dict[str, str] = {}
            if not expected:
                for key in ('chat_content', 'rag_context', 'tool_results', 'other_input'):
                    col = mapping[key]
                    if col:
                        inputs[key] = cell(col)
            for name, col in named_columns.items():
                inputs[name] = cell(col)

            output = cell(mapping['output'])
            prompt = cell(mapping['prompt']) if has_prompt_col else None

            all_blank = (
                all(_is_blank(v) for v in inputs.values())
                and _is_blank(output)
                and (prompt is None or _is_blank(prompt))
            )
            if all_blank:
                result.warnings.append(f'Row {row_num}: skipped blank row')
                continue

            has_input = any(not _is_blank(v) for v in inputs.values())
            has_prompt = prompt is not None and not _is_blank(prompt)

            if not has_input and not has_prompt and not (scenario_mode and not expected):
                result.errors.append(
                    f'Row {row_num}: missing input and/or prompt '
                    '(need non-empty chat/rag/tools/other and/or prompt)'
                )
                continue

            blank_named = [
                name for name in expected
                if name not in inputs or _is_blank(inputs.get(name))
            ]
            if blank_named:
                result.errors.append(
                    f"Row {row_num}: Blank named inputs: {', '.join(blank_named)}"
                )
                continue

            if _is_blank(output):
                result.errors.append(f'Row {row_num}: missing required output')
                continue

            pair: Dict[str, Any] = {
                'inputs': inputs,
                'output': output,
            }
            if has_prompt_col and prompt is not None:
                # Preserve exact prompt text (including leading/trailing whitespace).
                pair['prompt'] = prompt

            result.pairs.append(pair)
    except csv.Error as exc:
        result.errors.append(f'Malformed CSV: {exc}')
        return result

    if data_rows_seen == 0 and not result.pairs:
        result.errors.append('CSV has a header but no data rows')
        return result

    if not result.pairs and not result.errors:
        result.errors.append('No valid data rows found in CSV')

    return result


def parse_result_to_response(result: BatchCsvParseResult) -> Tuple[Dict[str, Any], int]:
    """Map parse result to (json_body, http_status)."""
    fatal_prefixes = (
        'CSV file is empty',
        'CSV file is empty or missing',
        'CSV has a header but no data',
        'CSV exceeds',
        'CSV must be',
        'Malformed CSV',
        'Missing required',
        'No valid data rows',
    )
    fatal = [e for e in result.errors if any(e.startswith(p) for p in fatal_prefixes)]
    # Size/format fatals always win — do not return a partial 200.
    if fatal and any(e.startswith('CSV exceeds') or e.startswith('Malformed CSV') for e in fatal):
        return {
            'error': '; '.join(fatal),
            'errors': result.errors,
            'warnings': result.warnings,
            'pairs': [],
            'columns': result.columns,
            'missing_input_columns': result.missing_input_columns,
            'unused_input_columns': result.unused_input_columns,
        }, 400
    if fatal and not result.pairs:
        return {
            'error': '; '.join(fatal or result.errors),
            'errors': result.errors,
            'warnings': result.warnings,
            'pairs': [],
            'columns': result.columns,
            'missing_input_columns': result.missing_input_columns,
            'unused_input_columns': result.unused_input_columns,
        }, 400

    if not result.pairs:
        return {
            'error': '; '.join(result.errors) if result.errors else 'No valid pairs',
            'errors': result.errors,
            'warnings': result.warnings,
            'pairs': [],
            'columns': result.columns,
            'missing_input_columns': result.missing_input_columns,
            'unused_input_columns': result.unused_input_columns,
        }, 400

    body: Dict[str, Any] = {
        'pairs': result.pairs,
        'errors': result.errors,
        'warnings': result.warnings,
        'columns': result.columns,
        'missing_input_columns': result.missing_input_columns,
        'unused_input_columns': result.unused_input_columns,
        'count': len(result.pairs),
    }
    return body, 200
