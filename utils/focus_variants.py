"""Exact focus-subset composition shared by Jev and singleton experiments."""

from copy import deepcopy

from utils.inference_scenario import normalize_scenario_foci, validate_scenario


def prepare_focus_variants(scenario, foci):
    scenario = validate_scenario(scenario)
    if (not isinstance(foci, list) or not foci
            or any(not isinstance(f, dict) or not isinstance(f.get('focus'), str)
                   or not f['focus'].strip() for f in foci)):
        raise ValueError('Supply a non-empty list of named foci.')
    foci = normalize_scenario_foci(scenario, foci)
    if any(not f.get('attributable') for f in foci):
        raise ValueError('Every focus must have verified source spans.')
    return scenario, foci


def indices(values, count, label='selected_indices'):
    if (not isinstance(values, list) or any(type(i) is not int or not 0 <= i < count for i in values)
            or len(set(values)) != len(values)):
        raise ValueError(f'{label} must contain unique valid focus indices.')
    return values


def overlaps(a, b):
    return (a['message_id'] == b['message_id'] and
            a['char_start'] < b['char_end'] and b['char_start'] < a['char_end'])


def order_groups(scenario, foci, selected):
    """Only independent contiguous source spans can move within their own message."""
    groups = []
    for message in scenario['messages']:
        movable = []
        for i in selected:
            spans = foci[i]['spans']
            if len(spans) != 1 or spans[0]['message_id'] != message['id']:
                continue
            if any(overlaps(spans[0], other) for j, f in enumerate(foci) if j != i for other in f['spans']):
                continue
            movable.append(i)
        movable.sort(key=lambda i: foci[i]['spans'][0]['char_start'])
        if len(movable) > 1:
            groups.append({'message_id': message['id'], 'role': message['role'], 'focus_indices': movable})
    return groups


def compose_scenario_foci(scenario, foci, selected, orders=None, *, preserve_whitespace=False):
    scenario, foci = prepare_focus_variants(scenario, foci)
    selected = indices(selected, len(foci))
    groups = order_groups(scenario, foci, selected)
    orders = orders if orders is not None else {}
    if not isinstance(orders, dict) or set(orders) - {g['message_id'] for g in groups}:
        raise ValueError('Orders must identify movable message groups only.')
    replacements = {}
    for group in groups:
        mid = group['message_id']
        order = orders.get(mid, group['focus_indices'])
        indices(order, len(foci), 'order')
        if sorted(order) != sorted(group['focus_indices']):
            raise ValueError('Each order must be an exact permutation of its selected group.')
        for slot, source in zip(group['focus_indices'], order):
            span = foci[slot]['spans'][0]
            replacements[(mid, span['char_start'], span['char_end'])] = source

    composed = deepcopy(scenario)
    messages, partial_exclusions, deleted_characters = [], set(), 0
    mapped = {i: [] for i in selected}
    for message in scenario['messages']:
        if message['analysis_mode'] == 'retain':
            messages.append(deepcopy(message))
            continue
        content, mid = message['content'], message['id']
        spans = [(i, s['char_start'], s['char_end']) for i, f in enumerate(foci)
                 for s in f['spans'] if s['message_id'] == mid]
        boundaries = sorted({0, len(content)} | {x for _, start, end in spans for x in (start, end)})
        parts, offset = [], 0
        for start, end in zip(boundaries, boundaries[1:]):
            covering = {i for i, a, b in spans if a <= start and b >= end}
            kept = covering.intersection(selected)
            if covering and not kept:
                deleted_characters += end - start
                continue
            if kept:
                partial_exclusions.update(covering.difference(selected))
            source = replacements.get((mid, start, end))
            text = foci[source]['spans'][0]['text_snapshot'] if source is not None else content[start:end]
            owners = {source} if source is not None else kept
            for i in owners:
                ranges = mapped[i]
                # A selected span can cross several overlap boundaries. Join its
                # adjacent pieces, tracking positions rather than searching text.
                if ranges and ranges[-1]['message_id'] == mid and ranges[-1]['char_end'] == offset:
                    ranges[-1]['char_end'] += len(text)
                    ranges[-1]['text_snapshot'] += text
                else:
                    ranges.append({'message_id': mid, 'char_start': offset,
                                   'char_end': offset + len(text), 'text_snapshot': text})
            parts.append(text)
            offset += len(text)
        updated = dict(message, content=''.join(parts))
        if (updated['content'] if preserve_whitespace else updated['content'].strip()) or updated['content'] == content:
            messages.append(updated)
    composed['messages'] = messages
    composed = validate_scenario(composed)
    derived = []
    # Keep catalogue identity/order; span positions reflect the chosen prompt order.
    for i in sorted(selected):
        focus = deepcopy(foci[i])
        for key in ('char_start', 'char_end', 'text_snapshot', 'message_id', 'message_ids'):
            focus.pop(key, None)
        focus.update(spans=mapped[i], source_focus_index=i)
        derived.append(focus)
    return {'scenario': composed, 'foci': normalize_scenario_foci(composed, derived), 'selected_indices': selected,
            'order_groups': groups, 'orders': {g['message_id']: orders.get(g['message_id'], g['focus_indices']) for g in groups},
            'shared_text_retained_for_excluded': sorted(partial_exclusions),
            'deleted_characters': deleted_characters,
            'original_characters': sum(len(m['content']) for m in scenario['messages']),
            'composed_characters': sum(len(m['content']) for m in messages)}
