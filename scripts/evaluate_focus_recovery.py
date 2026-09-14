#!/usr/bin/env python3
"""Opt-in billed coverage, recovery and chat-sensitivity probe with synthetic data."""

import argparse
import copy
import json
from pathlib import Path
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

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


def check_result(result, foci, expected):
    assert len(result['foci']) == len(foci)
    assert [row['focus_index'] for row in result['foci']] == list(range(len(foci)))
    assert abs(sum(row['score'] for row in result['foci']) - 100) < 1e-8
    scores = {row['focus']: row['score'] for row in result['foci']}
    assert not result['uniform_allocation'], 'Uniform allocation does not distinguish contributions.'
    assert all(scores[expected] > scores[other] for other in {'Returns', 'Delivery', 'Damage'} - {expected}), scores


def run_case(args, case, chat, expected, reverse=False, output=None):
    scenario, foci = fixture()
    scenario['messages'][-1]['content'] = chat
    if reverse:
        foci.reverse()
    phase = 'retrospective' if output else 'prospective'
    row = {'case': case, 'phase': phase, 'order': 'reversed' if reverse else 'original', 'mode': 'natural'}
    try:
        service = FocusWorkflowService(get_assessor(model=args.model, provider=args.provider))
        chat_call = service.assessment._chat
        row['model_responses'] = []

        def trace(messages, **kwargs):
            response = chat_call(messages, **kwargs)
            row['model_responses'].append(response)
            return response

        service.assessment._chat = trace
        row['assessment'] = service.assess(scenario, foci, phase=phase, output=output)
        check_result(row['assessment'], foci, expected)
        row['passed'] = True
    except (ValueError, AssertionError) as exc:
        row.update(passed=False, error=str(exc))
    print(case, phase, row['order'], 'PASS' if row['passed'] else 'FAIL: ' + row['error'], flush=True)
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--model', default='gpt-3.5-turbo')
    parser.add_argument('--provider', default='openai')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not args.live:
        parser.error('Pass --live to enable billed model calls with synthetic data.')
    scenario, foci = fixture()
    results = []
    cases = [
        ('returns', scenario['messages'][-1]['content'], 'Returns'),
        ('delivery', 'My order is three days late. Could you check where the parcel is?', 'Delivery'),
        ('damage', 'My new jacket arrived with a torn sleeve. How do I report the damage?', 'Damage'),
    ]
    def save():
        args.output.write_text(json.dumps({'model': args.model, 'scenario': scenario, 'foci': foci,
                                          'results': results}, indent=2))
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs = [pool.submit(run_case, args, *case, reverse=reverse) for case in cases for reverse in (False, True)]
        jobs.append(pool.submit(run_case, args, *cases[0], output='You can return the unworn jacket within thirty days with its tags. Have your order number ready; I can help arrange a prepaid label.'))
        for job in as_completed(jobs):
            results.append(job.result())
            save()

    full = next((row.get('assessment') for row in results if row['case'] == 'returns'
                 and row['phase'] == 'prospective' and row['order'] == 'original'), None)
    if full:
        service = FocusWorkflowService(get_assessor(model=args.model, provider=args.provider))

        # Omit explanations, not budget entries. The entire budget must be generated anew.
        partial = copy.deepcopy(full)
        missing = {0, 3, 10, 15, 16}
        partial['foci'] = [{k: row[k] for k in ('focus_index', 'applicability', 'explanation')}
                           for row in full['foci'] if row['focus_index'] not in missing]
        chat = service.assessment._chat
        first = True

        def omit_then_chat(messages, **kwargs):
            nonlocal first
            if first:
                first = False
                return {'content': json.dumps(partial)}
            return chat(messages, **kwargs)

        service.assessment._chat = omit_then_chat
        row = {'case': 'returns', 'phase': 'prospective', 'mode': 'forced_omissions'}
        try:
            recovered = service.assess(scenario, foci, phase='prospective')
            row['assessment'] = recovered
            check_result(recovered, foci, 'Returns')
            assert set(recovered['allocation_recovery']['focus_indices']) == missing
            for i in set(range(len(foci))) - missing:
                assert recovered['foci'][i]['explanation'] == full['foci'][i]['explanation']
            row['passed'] = True
        except (ValueError, AssertionError) as exc:
            row.update(passed=False, error=str(exc))
        results.append(row)
        save()
        print('Forced omissions:', 'PASS' if row['passed'] else 'FAIL: ' + row['error'], flush=True)
    print(f"{sum(row['passed'] for row in results)}/{len(results)} checks passed", flush=True)
    if len(results) != 8 or not all(row['passed'] for row in results):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
