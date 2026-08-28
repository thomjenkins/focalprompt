#!/usr/bin/env python3
"""
Prompt focus ordering / reordering with semantic completeness guarantees.

Reorders verified static attributable focus spans among fixed slot positions while
preserving glue text, dynamic slots, and all non-movable content exactly once.

This is behavioural sensitivity tooling — not mechanistic attention analysis.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from utils.span_alignment import append_dynamic_inputs, classify_foci_for_ablation

ORDERING_FIXED = 'fixed'
ORDERING_MOVABLE_WITHIN_SECTION = 'movable_within_section'
ORDERING_MOVABLE = 'movable'

DEFAULT_ORDERING_POLICY = ORDERING_MOVABLE_WITHIN_SECTION


def resolve_ordering_policies(
    classified: Sequence[Mapping[str, Any]],
    user_policies: Optional[Mapping[Any, str]] = None,
) -> Dict[int, str]:
    """
    Resolve per-focus ordering policy.

    Default (conservative): only verified, attributable, non-dynamic static foci
    are ``movable_within_section``. Everything else is fixed.
    """
    user_policies = user_policies or {}
    policies: Dict[int, str] = {}
    for i, focus in enumerate(classified):
        override = user_policies.get(i) or user_policies.get(focus.get('focus'))
        if override in (ORDERING_FIXED, ORDERING_MOVABLE_WITHIN_SECTION, ORDERING_MOVABLE):
            policies[i] = str(override)
            continue
        if not focus.get('attributable'):
            policies[i] = ORDERING_FIXED
        elif focus.get('is_dynamic'):
            policies[i] = ORDERING_FIXED
        else:
            policies[i] = DEFAULT_ORDERING_POLICY
    return policies


def _is_movable(policies: Mapping[int, str], focus_index: int) -> bool:
    pol = policies.get(focus_index, ORDERING_FIXED)
    return pol in (ORDERING_MOVABLE_WITHIN_SECTION, ORDERING_MOVABLE)


def build_order_template(
    prompt: str,
    classified: Sequence[Mapping[str, Any]],
    *,
    policies: Optional[Mapping[int, str]] = None,
    exclude_focus_indices: Optional[Sequence[int]] = None,
    omit_focus_indices: Optional[Sequence[int]] = None,
) -> Dict[str, Any]:
    """
    Decompose prompt into fixed segments and movable focus slots at document positions.

    Each slot holds one focus span; permutations reassign focus texts to slots.
    ``omit_focus_indices``: spans removed entirely (LOO deletion), not fixed or slotted.
    ``exclude_focus_indices``: alias for omit (legacy).
    """
    prompt = prompt or ''
    policies = dict(policies or resolve_ordering_policies(classified))
    omitted = set(int(x) for x in (omit_focus_indices or exclude_focus_indices or ()))

    # Document-order walk including omitted spans so glue is captured correctly.
    ordered = sorted(
        range(len(classified)),
        key=lambda idx: int(classified[idx].get('char_start') or 0),
    )

    movable_indices: List[int] = []
    for i in ordered:
        if i in omitted:
            continue
        if _is_movable(policies, i) and classified[i].get('attributable'):
            movable_indices.append(i)

    focus_texts: Dict[int, str] = {}
    for idx in movable_indices:
        start = int(classified[idx]['char_start'])
        end = int(classified[idx]['char_end'])
        focus_texts[idx] = prompt[start:end]

    segments: List[Dict[str, Any]] = []
    cursor = 0
    slot_index = 0
    for idx in ordered:
        focus = classified[idx]
        start_raw = focus.get('char_start')
        end_raw = focus.get('char_end')
        if start_raw is None or end_raw is None:
            continue
        start = int(start_raw)
        end = int(end_raw)
        if cursor < start:
            segments.append({'type': 'fixed', 'text': prompt[cursor:start]})
        if idx in omitted:
            cursor = max(cursor, end)
            continue
        if idx in movable_indices:
            segments.append({
                'type': 'slot',
                'slot_index': slot_index,
                'focus_index': idx,
                'focus_name': (focus.get('focus') or f'Focus {idx + 1}').strip(),
                'default_assignment': slot_index,
            })
            slot_index += 1
        else:
            segments.append({'type': 'fixed', 'text': prompt[start:end]})
        cursor = max(cursor, end)

    if cursor < len(prompt):
        segments.append({'type': 'fixed', 'text': prompt[cursor:]})

    return {
        'segments': segments,
        'focus_texts': {str(k): v for k, v in focus_texts.items()},
        'movable_focus_indices': movable_indices,
        'movable_focus_names': [
            (classified[i].get('focus') or f'Focus {i + 1}').strip() for i in movable_indices
        ],
        'ordering_policy': {str(k): v for k, v in policies.items()},
        'n_slots': len(movable_indices),
        'default_assignment': list(range(len(movable_indices))),
    }


def assignment_to_ordered_focus_names(
    template: Mapping[str, Any],
    assignment: Sequence[int],
) -> List[str]:
    """Map slot assignment → focus names in slot order."""
    movable = list(template.get('movable_focus_indices') or [])
    names = list(template.get('movable_focus_names') or [])
    by_movable = {i: names[i] for i in range(len(names))}
    out: List[str] = []
    for slot_i, movable_i in enumerate(assignment):
        if 0 <= int(movable_i) < len(movable):
            out.append(by_movable[int(movable_i)])
        else:
            out.append(f'slot_{slot_i}')
    return out


def reassemble_from_assignment(
    template: Mapping[str, Any],
    assignment: Sequence[int],
    *,
    inputs: Optional[Mapping[str, Any]] = None,
) -> str:
    """
    Reconstruct prompt from template + slot assignment.

    ``assignment[slot_index]`` = movable-list index (which focus text fills the slot).
    """
    n_slots = int(template.get('n_slots') or 0)
    if len(assignment) != n_slots:
        raise ValueError(f'assignment length {len(assignment)} != n_slots {n_slots}')
    focus_texts = template.get('focus_texts') or {}
    movable_indices = list(template.get('movable_focus_indices') or [])

    parts: List[str] = []
    for seg in template.get('segments') or []:
        if seg.get('type') == 'fixed':
            parts.append(str(seg.get('text') or ''))
            continue
        slot_i = int(seg['slot_index'])
        movable_i = int(assignment[slot_i])
        if movable_i < 0 or movable_i >= len(movable_indices):
            raise ValueError(f'invalid assignment[{slot_i}]={movable_i}')
        focus_idx = movable_indices[movable_i]
        parts.append(str(focus_texts.get(str(focus_idx), '')))
    # Byte-exact join: do not collapse newlines or strip — validation checks exact
    # movable/fixed substrings from the original prompt.
    out = ''.join(parts)
    return append_dynamic_inputs(out, inputs)


def validate_semantic_completeness(
    original: str,
    reconstructed: str,
    template: Mapping[str, Any],
    *,
    inputs: Optional[Mapping[str, Any]] = None,
    required_substrings: Optional[Sequence[str]] = None,
) -> Tuple[bool, List[str]]:
    """
    Verify fixed segments and each movable focus text appear exactly once.

    Returns (ok, list of error messages).
    """
    errors: List[str] = []
    recon = reconstructed or ''

    for seg in template.get('segments') or []:
        if seg.get('type') != 'fixed':
            continue
        text = str(seg.get('text') or '')
        if len(text.strip()) < 12:
            continue
        count = recon.count(text)
        if count != 1:
            errors.append(f'fixed segment appears {count} times (expected 1)')

    focus_texts = template.get('focus_texts') or {}
    for _key, text in focus_texts.items():
        if not text:
            continue
        count = recon.count(text)
        if count != 1:
            errors.append(f'movable focus text appears {count} times (expected 1)')

    for req in required_substrings or ():
        if req and recon.count(req) != 1:
            errors.append(f'required substring {req!r} appears {recon.count(req)} times')

    if inputs:
        for key in ('chat_content', 'rag_context', 'tool_results', 'other_input'):
            value = inputs.get(key)
            if value and str(value).strip() and str(value) not in (original or ''):
                if recon.count(str(value)) != 1:
                    errors.append(f'dynamic input {key} missing or duplicated')

    return (len(errors) == 0, errors)


def sample_random_assignments(
    n_slots: int,
    k: int,
    *,
    seed: Optional[int] = None,
    include_identity: bool = True,
) -> List[Tuple[int, List[int]]]:
    """Sample up to k distinct slot assignments (permutation_id, assignment)."""
    if n_slots < 2:
        return []
    rng = random.Random(seed)
    seen = set()
    out: List[Tuple[int, List[int]]] = []
    if include_identity:
        ident = tuple(range(n_slots))
        seen.add(ident)
        out.append((0, list(ident)))
    pid = len(out)
    attempts = 0
    max_attempts = max(k * 50, 100)
    while len(out) < k and attempts < max_attempts:
        attempts += 1
        perm = list(range(n_slots))
        rng.shuffle(perm)
        key = tuple(perm)
        if key in seen:
            continue
        seen.add(key)
        out.append((pid, perm))
        pid += 1
    return out[:k]


def position_sweep_slot_indices(n_slots: int) -> List[int]:
    """Valid slot indices to test in a single-focus position sweep."""
    if n_slots <= 0:
        return []
    if n_slots <= 5:
        return list(range(n_slots))
    return sorted({
        0,
        max(0, n_slots // 4),
        n_slots // 2,
        min(n_slots - 1, (3 * n_slots) // 4),
        n_slots - 1,
    })


def assignment_for_focus_at_slot(
    n_slots: int,
    target_movable_index: int,
    target_slot: int,
) -> List[int]:
    """
    Place one movable focus at ``target_slot``; preserve relative order of others.
    """
    if n_slots < 1:
        raise ValueError('n_slots must be at least 1')
    if not (0 <= target_movable_index < n_slots):
        raise ValueError('target_movable_index out of range')
    if not (0 <= target_slot < n_slots):
        raise ValueError('target_slot out of range')
    others = [i for i in range(n_slots) if i != target_movable_index]
    assignment: List[Optional[int]] = [None] * n_slots
    assignment[target_slot] = target_movable_index
    oi = 0
    for si in range(n_slots):
        if assignment[si] is None:
            assignment[si] = others[oi]
            oi += 1
    return [int(x) for x in assignment]


def build_loo_shuffle_prompt(
    prompt: str,
    classified: Sequence[Mapping[str, Any]],
    removed_index: int,
    *,
    shuffle_seed: Optional[int] = None,
    inputs: Optional[Mapping[str, Any]] = None,
    policies: Optional[Mapping[int, str]] = None,
) -> Tuple[str, bool, List[str], List[str], Dict[str, Any]]:
    """
    LOO shuffle using slot-preserving reorder of remaining movable foci.

    Returns (prompt, empty, document_order, shuffled_order, reconstruction_metadata).
    """
    policies = policies or resolve_ordering_policies(classified)
    template = build_order_template(
        prompt,
        classified,
        policies=policies,
        omit_focus_indices=[removed_index],
    )
    n_slots = int(template.get('n_slots') or 0)
    doc_names = list(template.get('movable_focus_names') or [])
    if n_slots <= 1:
        assignment = list(range(max(n_slots, 0)))
        shuffled_names = list(doc_names)
    else:
        rng = random.Random(shuffle_seed)
        assignment = list(range(n_slots))
        rng.shuffle(assignment)
        shuffled_names = assignment_to_ordered_focus_names(template, assignment)

    reconstructed = reassemble_from_assignment(template, assignment, inputs=inputs)
    ok, errors = validate_semantic_completeness(prompt, reconstructed, template, inputs=inputs)
    if not ok:
        raise ValueError(
            'Shuffle reconstruction failed semantic completeness: ' + '; '.join(errors)
        )
    meta = {
        'method': 'slot_preserving_reorder',
        'template': {
            'n_slots': n_slots,
            'movable_focus_indices': template.get('movable_focus_indices'),
            'ordering_policy': template.get('ordering_policy'),
        },
        'assignment': assignment,
        'removed_focus_index': removed_index,
        'validation_errors': errors,
    }
    return reconstructed, (not reconstructed.strip()), doc_names, shuffled_names, meta


def build_reordered_prompt(
    prompt: str,
    classified: Sequence[Mapping[str, Any]],
    assignment: Sequence[int],
    *,
    inputs: Optional[Mapping[str, Any]] = None,
    policies: Optional[Mapping[int, str]] = None,
) -> Tuple[str, Dict[str, Any]]:
    """Build a full-prompt reorder from assignment; validate completeness."""
    policies = policies or resolve_ordering_policies(classified)
    template = build_order_template(prompt, classified, policies=policies)
    if int(template.get('n_slots') or 0) != len(assignment):
        raise ValueError('assignment length does not match movable slot count')
    reconstructed = reassemble_from_assignment(template, assignment, inputs=inputs)
    ok, errors = validate_semantic_completeness(prompt, reconstructed, template, inputs=inputs)
    if not ok:
        raise ValueError(
            'Reorder reconstruction failed semantic completeness: ' + '; '.join(errors)
        )
    return reconstructed, {
        'template': template,
        'assignment': list(assignment),
        'ordered_focus_names': assignment_to_ordered_focus_names(template, assignment),
        'validation_errors': errors,
    }


def prepare_order_experiment(
    prompt: str,
    foci: Sequence[Mapping[str, Any]],
    *,
    user_policies: Optional[Mapping[Any, str]] = None,
) -> Dict[str, Any]:
    """Classify foci and build template; refuse if reordering is unsafe."""
    classified = classify_foci_for_ablation(prompt, list(foci))
    policies = resolve_ordering_policies(classified, user_policies)
    template = build_order_template(prompt, classified, policies=policies)
    n_slots = int(template.get('n_slots') or 0)
    if n_slots < 2:
        return {
            'ok': False,
            'reason': (
                'Need at least two movable attributable static foci to run order '
                'sensitivity. Dynamic, unverified, overlapping, or fixed-policy foci '
                'are not reordered.'
            ),
            'classified': classified,
            'ordering_policy': policies,
            'template': template,
            'n_movable_slots': n_slots,
        }
    return {
        'ok': True,
        'classified': classified,
        'ordering_policy': policies,
        'template': template,
        'n_movable_slots': n_slots,
    }
