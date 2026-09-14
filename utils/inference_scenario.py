#!/usr/bin/env python3
"""Versioned, ordered inference scenarios.

This module is the single boundary between Focal Prompt experiments and a
model-under-test request.  Analysis/judge prompts deliberately do not use the
user's output contract.
"""

from __future__ import annotations

import copy
import json
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


SCENARIO_VERSION = 1
MESSAGE_ROLES = frozenset({'system', 'developer', 'user', 'assistant'})
ANALYSIS_MODES = frozenset({'analyse', 'retain'})
INSTRUCTION_ROLES = frozenset({'system', 'developer'})
_ID_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$')
_INPUT_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_.-]{0,127}$')


class ScenarioValidationError(ValueError):
    """A scenario is invalid before any provider request is made."""


class ProviderCapabilityError(ValueError):
    """A provider cannot express a required scenario feature."""


class StructuredOutputError(ValueError):
    """A model-under-test response did not satisfy its output contract."""


def default_scenario() -> Dict[str, Any]:
    """Return the default two-message editor scenario."""
    return {
        'version': SCENARIO_VERSION,
        'messages': [
            {
                'id': 'instructions',
                'role': 'system',
                'content': '',
                'analysis_mode': 'analyse',
            },
            {
                'id': 'user-input',
                'role': 'user',
                'content': '',
                'analysis_mode': 'retain',
            },
        ],
    }


def legacy_prompt_to_scenario(
    prompt: str,
    *,
    message_id: str = 'legacy-prompt',
) -> Dict[str, Any]:
    """Preserve the historical inference role for a single prompt string."""
    if not isinstance(prompt, str) or not prompt.strip():
        raise ScenarioValidationError('Prompt is required')
    return {
        'version': SCENARIO_VERSION,
        'messages': [
            {
                'id': message_id,
                'role': 'user',
                'content': prompt,
                'analysis_mode': 'analyse',
            }
        ],
    }


def _validate_output_contract(contract: Any) -> Optional[Dict[str, Any]]:
    if contract is None:
        return None
    if not isinstance(contract, Mapping):
        raise ScenarioValidationError('output_contract must be an object')
    allowed = {'type', 'name', 'strict', 'schema'}
    extra = set(contract) - allowed
    if extra:
        raise ScenarioValidationError(
            'output_contract contains unsupported fields: ' + ', '.join(sorted(extra))
        )
    if contract.get('type') != 'json_schema':
        raise ScenarioValidationError('Only output_contract.type=json_schema is supported')
    name = contract.get('name')
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', name):
        raise ScenarioValidationError(
            'output_contract.name must be 1-64 letters, numbers, underscores, or dashes'
        )
    if contract.get('strict') is not True:
        raise ScenarioValidationError('output_contract.strict must be true')
    schema = contract.get('schema')
    if not isinstance(schema, Mapping):
        raise ScenarioValidationError('output_contract.schema must be a JSON Schema object')
    try:
        from jsonschema.validators import validator_for
    except ImportError as exc:  # pragma: no cover - packaging guard
        raise RuntimeError('jsonschema is required for structured output contracts') from exc
    try:
        validator_for(dict(schema)).check_schema(dict(schema))
    except Exception as exc:
        raise ScenarioValidationError(f'output_contract.schema is invalid: {exc}') from exc
    return copy.deepcopy(dict(contract))


def validate_scenario(
    scenario: Mapping[str, Any],
    *,
    require_user: bool = True,
) -> Dict[str, Any]:
    """Validate and return a deep, normalized copy without flattening messages."""
    if not isinstance(scenario, Mapping):
        raise ScenarioValidationError('scenario must be an object')
    extra_scenario_fields = set(scenario) - {'version', 'messages', 'output_contract'}
    if extra_scenario_fields:
        raise ScenarioValidationError(
            'scenario contains unsupported fields: '
            + ', '.join(sorted(extra_scenario_fields))
        )
    if scenario.get('version') != SCENARIO_VERSION:
        raise ScenarioValidationError(
            f'scenario.version must be {SCENARIO_VERSION}'
        )
    raw_messages = scenario.get('messages')
    if not isinstance(raw_messages, list) or not raw_messages:
        raise ScenarioValidationError('scenario.messages must be a non-empty array')

    messages: List[Dict[str, Any]] = []
    ids = set()
    input_names = set()
    conversation_started = False
    has_user = False
    for index, raw in enumerate(raw_messages):
        if not isinstance(raw, Mapping):
            raise ScenarioValidationError(f'messages[{index}] must be an object')
        allowed = {'id', 'role', 'content', 'analysis_mode', 'input_name'}
        extra = set(raw) - allowed
        if extra:
            raise ScenarioValidationError(
                f'messages[{index}] contains unsupported fields: ' + ', '.join(sorted(extra))
            )
        message_id = raw.get('id')
        if not isinstance(message_id, str) or not _ID_RE.fullmatch(message_id):
            raise ScenarioValidationError(
                f'messages[{index}].id must be a portable, non-empty identifier'
            )
        if message_id in ids:
            raise ScenarioValidationError(f'Duplicate message id: {message_id}')
        ids.add(message_id)

        role = raw.get('role')
        if role not in MESSAGE_ROLES:
            raise ScenarioValidationError(
                f'messages[{index}].role must be one of: ' + ', '.join(sorted(MESSAGE_ROLES))
            )
        if role in INSTRUCTION_ROLES:
            if conversation_started:
                raise ScenarioValidationError(
                    'All system/developer messages must precede user/assistant messages'
                )
        else:
            conversation_started = True
        has_user = has_user or role == 'user'

        content = raw.get('content')
        if not isinstance(content, str):
            raise ScenarioValidationError(f'messages[{index}].content must be text')
        mode = raw.get('analysis_mode')
        if mode is None:
            mode = 'analyse' if role in INSTRUCTION_ROLES else 'retain'
        if mode not in ANALYSIS_MODES:
            raise ScenarioValidationError(
                f'messages[{index}].analysis_mode must be analyse or retain'
            )

        input_name = raw.get('input_name')
        if input_name is not None:
            if mode != 'retain':
                raise ScenarioValidationError('input_name is allowed only on retained messages')
            if not isinstance(input_name, str) or not _INPUT_RE.fullmatch(input_name):
                raise ScenarioValidationError(
                    f'messages[{index}].input_name must be a portable input identifier'
                )
            if input_name in input_names:
                raise ScenarioValidationError(f'Duplicate input_name: {input_name}')
            input_names.add(input_name)

        message = {
            'id': message_id,
            'role': role,
            'content': content,
            'analysis_mode': mode,
        }
        if input_name is not None:
            message['input_name'] = input_name
        messages.append(message)

    if require_user and not has_user:
        raise ScenarioValidationError('At least one user message is required for generation')

    normalized: Dict[str, Any] = {
        'version': SCENARIO_VERSION,
        'messages': messages,
    }
    contract = _validate_output_contract(scenario.get('output_contract'))
    if contract is not None:
        normalized['output_contract'] = contract
    return normalized


def normalize_scenario_input(
    *,
    scenario: Optional[Mapping[str, Any]] = None,
    prompt: Optional[str] = None,
    require_user: bool = True,
) -> Tuple[Dict[str, Any], bool]:
    """Resolve exactly one modern scenario or legacy prompt.

    Returns ``(scenario, is_legacy_prompt)``.
    """
    has_scenario = scenario is not None
    has_prompt = prompt is not None and isinstance(prompt, str) and bool(prompt.strip())
    if has_scenario == has_prompt:
        raise ScenarioValidationError('Provide exactly one of scenario or prompt')
    if has_scenario:
        return validate_scenario(scenario, require_user=require_user), False
    return validate_scenario(
        legacy_prompt_to_scenario(str(prompt)), require_user=require_user
    ), True


def scenario_from_request(
    data: Mapping[str, Any],
    *,
    require_user: bool = True,
) -> Tuple[Dict[str, Any], bool]:
    """HTTP-friendly exactly-one resolver."""
    return normalize_scenario_input(
        scenario=data.get('scenario'),
        prompt=data.get('prompt'),
        require_user=require_user,
    )


def named_inputs(scenario: Mapping[str, Any]) -> List[str]:
    normalized = validate_scenario(scenario)
    return [
        str(message['input_name'])
        for message in normalized['messages']
        if message.get('input_name')
    ]


def bind_scenario_inputs(
    scenario: Mapping[str, Any],
    inputs: Optional[Mapping[str, Any]],
    *,
    reject_unused: bool = False,
) -> Tuple[Dict[str, Any], Dict[str, List[str]]]:
    """Replace complete named-message content when values are supplied.

    ``inputs=None`` is a single-run scenario using the message defaults. Batch
    callers pass an explicit mapping, where every named input is mandatory.
    """
    normalized = validate_scenario(scenario)
    if inputs is not None and not isinstance(inputs, Mapping):
        raise ScenarioValidationError('inputs must be an object keyed by input_name')
    expected = named_inputs(normalized)
    if inputs is None:
        return normalized, {
            'missing': [], 'blank': [], 'unused': [], 'used_defaults': expected,
        }
    values = dict(inputs or {})
    missing = [name for name in expected if name not in values]
    blank = [name for name in expected if name in values and not str(values[name]).strip()]
    unused = sorted(str(name) for name in values if name not in set(expected))
    if missing:
        raise ScenarioValidationError('Missing named inputs: ' + ', '.join(missing))
    if blank:
        raise ScenarioValidationError('Blank named inputs: ' + ', '.join(blank))
    if reject_unused and unused:
        raise ScenarioValidationError('Unused named inputs: ' + ', '.join(unused))
    for message in normalized['messages']:
        name = message.get('input_name')
        if name:
            value = values[name]
            if not isinstance(value, str):
                value = json.dumps(value, ensure_ascii=False)
            message['content'] = value
    return normalized, {
        'missing': missing, 'blank': blank, 'unused': unused, 'used_defaults': [],
    }


def openai_response_format(contract: Optional[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    if contract is None:
        return None
    checked = _validate_output_contract(contract)
    assert checked is not None
    return {
        'type': 'json_schema',
        'json_schema': {
            'name': checked['name'],
            'strict': True,
            'schema': copy.deepcopy(checked['schema']),
        },
    }


def compile_scenario(scenario: Mapping[str, Any]) -> Dict[str, Any]:
    """Compile a scenario to the provider-neutral chat boundary."""
    normalized = validate_scenario(scenario)
    return {
        'messages': [
            {'role': message['role'], 'content': message['content']}
            for message in normalized['messages']
        ],
        'response_format': openai_response_format(normalized.get('output_contract')),
        'metadata': {
            'scenario_version': normalized['version'],
            'message_ids': [message['id'] for message in normalized['messages']],
            'provider_translation': 'openai_chat',
            'role_merges': [],
        },
    }


def validate_structured_response(
    content: Any,
    output_contract: Optional[Mapping[str, Any]],
    *,
    refusal: Optional[str] = None,
    incomplete: bool = False,
) -> Any:
    """Parse and locally validate every configured structured response."""
    if output_contract is None:
        return None
    contract = _validate_output_contract(output_contract)
    if refusal:
        raise StructuredOutputError(f'Model refused the structured request: {refusal}')
    if incomplete:
        raise StructuredOutputError('Model returned an incomplete structured response')
    if not isinstance(content, str) or not content.strip():
        raise StructuredOutputError('Model returned an empty structured response')
    try:
        def reject_constant(value: str) -> None:
            raise ValueError(f'non-standard JSON constant {value}')

        parsed = json.loads(content, parse_constant=reject_constant)
    except (ValueError, TypeError) as exc:
        raise StructuredOutputError(f'Model returned malformed JSON: {exc}') from exc
    try:
        import jsonschema

        validator_class = jsonschema.validators.validator_for(contract['schema'])
        validator = validator_class(
            contract['schema'],
            format_checker=jsonschema.FormatChecker(),
        )
        validator.validate(parsed)
    except Exception as exc:
        from jsonschema import ValidationError

        if isinstance(exc, ValidationError):
            path = '.'.join(str(p) for p in exc.absolute_path) or '<root>'
            raise StructuredOutputError(
                f'Model response does not match output_contract at {path}: {exc.message}'
            ) from exc
        raise StructuredOutputError(
            f'Model response could not be validated against output_contract: {exc}'
        ) from exc
    return parsed


def complete_scenario(
    provider: Any,
    model: str,
    provider_name: str,
    scenario: Mapping[str, Any],
    *,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    """Use the canonical compiler and enforce the contract after the call."""
    from utils.gateway_chat import chat_completion

    normalized = validate_scenario(scenario)
    compiled = compile_scenario(normalized)
    kwargs: Dict[str, Any] = {}
    if compiled['response_format'] is not None:
        kwargs['response_format'] = compiled['response_format']
    if max_tokens is not None:
        kwargs['max_tokens'] = max_tokens
    try:
        response = chat_completion(
            provider,
            model,
            provider_name,
            compiled['messages'],
            temperature=temperature,
            **kwargs,
        )
    except (ProviderCapabilityError, StructuredOutputError):
        raise
    except Exception as exc:
        # Preserve transient/service failures so existing retry and rate-limit
        # handling remains effective. A deterministic adapter/request rejection
        # means the required contract cannot be expressed and must never be
        # silently retried without it.
        error_text = str(exc).lower()
        transient = (
            exc.__class__.__name__ in {'RateLimitError', 'Timeout', 'APITimeoutError'}
            or any(marker in error_text for marker in (
                'rate limit', 'too many requests', '429', 'timed out',
                'timeout', 'connection error', 'service unavailable', '503',
            ))
        )
        if normalized.get('output_contract') and not transient:
            raise ProviderCapabilityError(
                f"Provider '{provider_name}' rejected the required structured output contract: {exc}"
            ) from exc
        raise
    result = dict(response or {})
    refusal = result.get('refusal')
    finish_reason = str(result.get('finish_reason') or '').lower()
    incomplete = bool(result.get('incomplete')) or any(
        marker in finish_reason
        for marker in (
            'length', 'max_tokens', 'max_output_tokens', 'content_filter',
            'safety', 'recitation',
        )
    )
    parsed = validate_structured_response(
        result.get('content'),
        normalized.get('output_contract'),
        refusal=refusal,
        incomplete=incomplete,
    )
    result['scenario_metadata'] = {
        **compiled['metadata'],
        **dict(result.get('provider_metadata') or {}),
    }
    if normalized.get('output_contract') is not None:
        result['parsed_output'] = parsed
    return result


def _focus_spans(focus: Mapping[str, Any]) -> List[Dict[str, Any]]:
    raw = focus.get('spans')
    if isinstance(raw, list) and raw:
        return [dict(span) for span in raw if isinstance(span, Mapping)]
    if focus.get('char_start') is not None and focus.get('char_end') is not None:
        return [{
            'message_id': focus.get('message_id'),
            'char_start': focus.get('char_start'),
            'char_end': focus.get('char_end'),
            'text_snapshot': focus.get('text_snapshot') or focus.get('prompt_section'),
        }]
    return []


def normalize_scenario_focus(
    scenario: Mapping[str, Any],
    focus: Mapping[str, Any],
) -> Dict[str, Any]:
    """Ground one focus solely against Analyse messages."""
    normalized = validate_scenario(scenario)
    by_id = {message['id']: message for message in normalized['messages']}
    out = copy.deepcopy(dict(focus))
    spans: List[Dict[str, Any]] = []
    for index, span in enumerate(_focus_spans(out)):
        message_id = span.get('message_id') or out.get('message_id')
        if not message_id or message_id not in by_id:
            raise ScenarioValidationError(
                f"Focus '{out.get('focus', '')}' span {index} requires a valid message_id"
            )
        message = by_id[str(message_id)]
        if message['analysis_mode'] != 'analyse':
            raise ScenarioValidationError(
                f"Focus '{out.get('focus', '')}' targets retained message '{message_id}'"
            )
        try:
            start = int(span.get('char_start'))
            end = int(span.get('char_end'))
        except (TypeError, ValueError) as exc:
            raise ScenarioValidationError('Focus spans require integer char_start/char_end') from exc
        content = message['content']
        if start < 0 or end <= start or end > len(content):
            raise ScenarioValidationError(
                f"Invalid span [{start}, {end}) for message '{message_id}'"
            )
        exact = content[start:end]
        snapshot = span.get('text_snapshot', span.get('text'))
        if snapshot is not None and str(snapshot) != exact:
            raise ScenarioValidationError(
                f"Focus span snapshot does not match message '{message_id}'[{start}:{end}]"
            )
        spans.append({
            'message_id': str(message_id),
            'char_start': start,
            'char_end': end,
            'text_snapshot': exact,
        })
    if not spans:
        out['verified'] = False
        out['attributable'] = False
        out['reason'] = out.get('reason') or 'unverified'
        out['spans'] = []
        return out
    seen = set()
    deduped = []
    for span in sorted(spans, key=lambda s: (s['message_id'], s['char_start'], s['char_end'])):
        key = (span['message_id'], span['char_start'], span['char_end'])
        if key not in seen:
            seen.add(key)
            deduped.append(span)
    out['spans'] = deduped
    out['verified'] = True
    out['attributable'] = True
    out['reason'] = None
    out['is_dynamic'] = False
    out['message_ids'] = list(dict.fromkeys(span['message_id'] for span in deduped))
    out['span_count'] = len(deduped)
    out['is_multi_span'] = len(deduped) > 1
    out['order_reorderable'] = len(deduped) == 1 and len(out['message_ids']) == 1
    out['prompt_section'] = '\n…\n'.join(span['text_snapshot'] for span in deduped)
    if len(out['message_ids']) == 1:
        out['message_id'] = out['message_ids'][0]
        out['char_start'] = deduped[0]['char_start']
        out['char_end'] = deduped[-1]['char_end']
    return out


def scenario_order_groups(
    scenario: Mapping[str, Any],
    foci: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    """Return independently reorderable focus groups by message and role."""
    normalized = validate_scenario(scenario)
    classified = normalize_scenario_foci(normalized, foci)
    messages = {message['id']: message for message in normalized['messages']}
    grouped: Dict[Tuple[str, str], List[int]] = {}
    for index, focus in enumerate(classified):
        if not focus.get('order_reorderable'):
            continue
        message_id = focus['message_ids'][0]
        grouped.setdefault((message_id, messages[message_id]['role']), []).append(index)
    result = []
    for (message_id, role), indices in grouped.items():
        indices.sort(key=lambda i: classified[i]['spans'][0]['char_start'])
        if len(indices) > 1:
            result.append({
                'message_id': message_id,
                'role': role,
                'focus_indices': indices,
            })
    return result


def reorder_scenario_focus_group(
    scenario: Mapping[str, Any],
    foci: Sequence[Mapping[str, Any]],
    *,
    focus_indices: Sequence[int],
    assignment: Sequence[int],
) -> Dict[str, Any]:
    """Reassign exact focus texts to slots inside one message and role only."""
    normalized = validate_scenario(scenario)
    classified = normalize_scenario_foci(normalized, foci)
    indices = [int(index) for index in focus_indices]
    if len(indices) < 2 or sorted(int(value) for value in assignment) != list(range(len(indices))):
        raise ScenarioValidationError('A reorder assignment must be a permutation of one focus group')
    selected = [classified[index] for index in indices]
    message_ids = {focus['spans'][0]['message_id'] for focus in selected if focus.get('order_reorderable')}
    if len(message_ids) != 1 or any(not focus.get('order_reorderable') for focus in selected):
        raise ScenarioValidationError('Foci may be reordered only within the same message and role')
    message_id = next(iter(message_ids))
    by_id = {message['id']: message for message in normalized['messages']}
    role = by_id[message_id]['role']
    if any(by_id[focus['spans'][0]['message_id']]['role'] != role for focus in selected):
        raise ScenarioValidationError('Foci may be reordered only within the same message and role')
    slots = sorted(
        (focus['spans'][0]['char_start'], focus['spans'][0]['char_end'])
        for focus in selected
    )
    for (_start, end), (next_start, _next_end) in zip(slots, slots[1:]):
        if end > next_start:
            raise ScenarioValidationError('Overlapping focus spans cannot be reordered')
    texts = [
        selected[position]['spans'][0]['text_snapshot']
        for position in range(len(selected))
    ]
    content = by_id[message_id]['content']
    parts: List[str] = []
    cursor = 0
    for slot_index, (start, end) in enumerate(slots):
        parts.append(content[cursor:start])
        parts.append(texts[int(assignment[slot_index])])
        cursor = end
    parts.append(content[cursor:])
    result = copy.deepcopy(normalized)
    for message in result['messages']:
        if message['id'] == message_id:
            message['content'] = ''.join(parts)
            break
    return validate_scenario(result)


def normalize_scenario_foci(
    scenario: Mapping[str, Any],
    foci: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    return [normalize_scenario_focus(scenario, focus) for focus in (foci or [])]


def ablate_scenario(
    scenario: Mapping[str, Any],
    focus: Mapping[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Delete a focus's exact spans, removing an empty Analyse message."""
    normalized = validate_scenario(scenario)
    grounded = normalize_scenario_focus(normalized, focus)
    if not grounded.get('attributable'):
        raise ScenarioValidationError(
            f"Focus '{grounded.get('focus', '')}' cannot be ablated ({grounded.get('reason')})"
        )
    spans_by_message: Dict[str, List[Tuple[int, int]]] = {}
    for span in grounded['spans']:
        spans_by_message.setdefault(span['message_id'], []).append(
            (span['char_start'], span['char_end'])
        )
    removed_messages: List[str] = []
    deleted_ranges: List[Dict[str, Any]] = []
    result_messages = []
    for message in normalized['messages']:
        ranges = spans_by_message.get(message['id'])
        if not ranges:
            result_messages.append(message)
            continue
        content = message['content']
        merged: List[List[int]] = []
        for start, end in sorted(ranges):
            if merged and start <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])
        cursor = 0
        parts: List[str] = []
        for start, end in merged:
            parts.append(content[cursor:start])
            cursor = end
            deleted_ranges.append({
                'message_id': message['id'],
                'char_start': start,
                'char_end': end,
            })
        parts.append(content[cursor:])
        next_message = dict(message)
        next_message['content'] = ''.join(parts)
        if not next_message['content'].strip() and next_message['analysis_mode'] == 'analyse':
            removed_messages.append(message['id'])
            continue
        result_messages.append(next_message)
    result = dict(normalized)
    result['messages'] = result_messages
    # Retained/user history still makes a valid generation request. If removal
    # also removed the only user, fail before sampling rather than changing role.
    result = validate_scenario(result)
    return result, {
        'deleted_spans': deleted_ranges,
        'removed_message_ids': removed_messages,
    }


def scenario_coverage(
    scenario: Mapping[str, Any],
    foci: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Coverage by Analyse message plus an aggregate over Analyse characters."""
    normalized = validate_scenario(scenario)
    grounded = normalize_scenario_foci(normalized, foci)
    by_message: Dict[str, Any] = {}
    total_chars = 0
    total_unique = 0
    total_depth = 0
    for message in normalized['messages']:
        if message['analysis_mode'] != 'analyse':
            continue
        content = message['content']
        depth = [0] * len(content)
        for focus in grounded:
            if not focus.get('attributable'):
                continue
            covered_by_focus = set()
            for span in focus.get('spans') or []:
                if span['message_id'] != message['id']:
                    continue
                covered_by_focus.update(range(span['char_start'], span['char_end']))
            for pos in covered_by_focus:
                depth[pos] += 1
        unique = sum(value > 0 for value in depth)
        summed = sum(depth)
        total_chars += len(content)
        total_unique += unique
        total_depth += summed
        by_message[message['id']] = {
            'message_id': message['id'],
            'role': message['role'],
            'message_length': len(content),
            'covered_chars_unique': unique,
            'covered_chars_total': summed,
            'unique_coverage_percent': round(100 * unique / len(content), 2) if content else 0.0,
            'focus_density_percent': round(100 * summed / len(content), 2) if content else 0.0,
        }
    aggregate_unique = round(100 * total_unique / total_chars, 2) if total_chars else 0.0
    aggregate_density = round(100 * total_depth / total_chars, 2) if total_chars else 0.0
    return {
        'messages': by_message,
        'analysed_chars': total_chars,
        'covered_chars_unique': total_unique,
        'covered_chars_total': total_depth,
        'unique_coverage_percent': aggregate_unique,
        'focus_density_percent': aggregate_density,
        'coverage_percent': aggregate_unique,
    }


def project_scenario_for_legacy_scoring(
    scenario: Mapping[str, Any],
    foci: Sequence[Mapping[str, Any]],
) -> Tuple[str, List[Dict[str, Any]]]:
    """Build a private analysis-only projection for existing statistical code."""
    normalized = validate_scenario(scenario)
    grounded = normalize_scenario_foci(normalized, foci)
    offsets: Dict[str, int] = {}
    parts: List[str] = []
    cursor = 0
    for message in normalized['messages']:
        if message['analysis_mode'] != 'analyse':
            continue
        offsets[message['id']] = cursor
        parts.append(message['content'])
        cursor += len(message['content'])
        parts.append('\n')
        cursor += 1
    projected_foci: List[Dict[str, Any]] = []
    for focus in grounded:
        item = copy.deepcopy(focus)
        spans = []
        for span in focus.get('spans') or []:
            base = offsets[span['message_id']]
            spans.append({
                'char_start': base + span['char_start'],
                'char_end': base + span['char_end'],
                'text_snapshot': span['text_snapshot'],
            })
        item['spans'] = spans
        item.pop('message_id', None)
        item.pop('message_ids', None)
        projected_foci.append(item)
    return ''.join(parts), projected_foci


def scenario_analysis_messages(scenario: Mapping[str, Any]) -> List[Dict[str, Any]]:
    normalized = validate_scenario(scenario)
    return [message for message in normalized['messages'] if message['analysis_mode'] == 'analyse']


def scenario_analysis_document(scenario: Mapping[str, Any]) -> str:
    """Readable analysis-only view; never used for model-under-test generation."""
    return '\n\n'.join(
        f"[{message['role']}:{message['id']}]\n{message['content']}"
        for message in scenario_analysis_messages(scenario)
    )


def rewrite_analysed_messages(
    scenario: Mapping[str, Any],
    rewritten_by_message_id: Mapping[str, str],
) -> Dict[str, Any]:
    """Apply rewrites only to Analyse messages, preserving all other bytes.

    Empty text is accepted: it means every focus mapped to that message was
    omitted. The message keeps its id, role, order and analysis mode, so the
    boundary stays intact. Callers own the question of whether emptiness was
    actually requested.
    """
    normalized = validate_scenario(scenario)
    out = copy.deepcopy(normalized)
    for message in out['messages']:
        if message['analysis_mode'] != 'analyse':
            continue
        if message['id'] in rewritten_by_message_id:
            content = rewritten_by_message_id[message['id']]
            if not isinstance(content, str):
                raise ScenarioValidationError(
                    f"Rewrite for message '{message['id']}' must be text"
                )
            message['content'] = content
    return validate_scenario(out)
