#!/usr/bin/env python3
"""Opt-in billed coverage/recovery probe using a wholly synthetic retail scenario."""

import argparse
import copy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.assessor_factory import get_assessor
from services.focus_workflow_service import FocusWorkflowService


RULES = [
    ('Role', 'You assist customers of a fictional clothing store.'),
    ('Tone', 'Be courteous and calm.'),
    ('Brevity', 'Keep answers concise.'),
    ('Returns', 'Unworn clothing can be returned within thirty days of delivery.'),
    ('Exchanges', 'Customers may exchange an item for another available size.'),
    ('Refund timing', 'Refunds are issued within five working days of receiving a return.'),
    ('Condition', 'Returned clothing must have its original tags attached.'),
    ('Receipt', 'A receipt or order number is required to start a return.'),
    ('Return label', 'Offer a prepaid return label when a customer wants to return an item.'),
    ('Damage', 'If a product arrived damaged, ask for a photograph of the damage.'),
    ('Delivery', 'For late deliveries, offer to check the tracking information.'),
    ('Privacy', 'Never request a full payment card number.'),
    ('Stock', 'Do not claim a size is in stock without checking inventory.'),
    ('Discounts', 'Do not invent discount codes.'),
    ('Reviews', 'If a customer wants to leave a review, explain where to find the review form.'),
    ('Format', 'Use plain text without a greeting or signature.'),
    ('Relevance', 'Include only information relevant to the current question.'),
]


def fixture():
    text = '\n'.join(rule for _, rule in RULES)
    scenario = {'version': 1, 'messages': [
        {'id': 'rules', 'role': 'system', 'analysis_mode': 'analyse', 'content': text},
        {'id': 'chat', 'role': 'user', 'analysis_mode': 'retain',
         'content': 'How can I return a jacket that does not fit? It arrived yesterday and still has its tags.'},
    ]}
    foci = [{'focus': name, 'message_id': 'rules', 'prompt_section': rule,
             'spans': [{'message_id': 'rules', 'char_start': text.index(rule),
                        'char_end': text.index(rule) + len(rule), 'text_snapshot': rule}]}
            for name, rule in RULES]
    return scenario, foci


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--model', default='gpt-3.5-turbo')
    parser.add_argument('--provider', default='openai')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not args.live:
        parser.error('Pass --live to enable billed model calls with synthetic data.')
    assessor = get_assessor(model=args.model, provider=args.provider)
    scenario, foci = fixture()
    results = []
    for phase in ('prospective', 'retrospective'):
        output = 'You can return the unworn jacket within thirty days with its tags. Have your order number ready; I can help arrange a prepaid label.' if phase == 'retrospective' else None
        service = FocusWorkflowService(assessor)
        full = service.assess(scenario, foci, phase=phase, output=output)
        results.append({'phase': phase, 'mode': 'natural', 'assessment': full})
        print(phase, 'natural:', len(full['foci']), 'foci;', full['allocation_recovery'], flush=True)

        # Replay model-produced raw scores with omissions, then let the real model repair them.
        partial = copy.deepcopy(full)
        missing = {0, 3, 10, 15, 16}
        partial['foci'] = [{**row, 'score': row['raw_score']} for row in full['foci'] if row['focus_index'] not in missing]
        chat = service.assessment._chat
        first = True

        def omit_then_chat(messages, **kwargs):
            nonlocal first
            if first:
                first = False
                return {'content': json.dumps(partial)}
            requested = json.loads(messages[1]['content'])['recovery']['requested_focus_indices']
            response = chat(messages, **kwargs)
            print(phase, 'recovery requested indices:', requested, flush=True)
            return response

        service.assessment._chat = omit_then_chat
        recovered = service.assess(scenario, foci, phase=phase, output=output)
        assert len(recovered['foci']) == len(foci)
        assert abs(sum(row['score'] for row in recovered['foci']) - 100) < 1e-8
        assert set(recovered['allocation_recovery']['focus_indices']) == missing
        for i in set(range(len(foci))) - missing:
            assert recovered['foci'][i]['raw_score'] == full['foci'][i]['raw_score']
        results.append({'phase': phase, 'mode': 'forced_omissions', 'assessment': recovered})
        args.output.write_text(json.dumps({'scenario': scenario, 'foci': foci, 'results': results}, indent=2))
        print(phase, 'forced omissions: PASS;', recovered['allocation_recovery'], flush=True)


if __name__ == '__main__':
    main()
