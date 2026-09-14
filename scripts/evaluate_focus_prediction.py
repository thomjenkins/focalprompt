#!/usr/bin/env python3
"""Opt-in live evaluation of chat sensitivity and focus-list order effects.

Uses synthetic scenarios, configured inference credentials and billed model calls.
No exact percentage is treated as ground truth. The relevant conditional instruction
should outrank the two unrelated conditional instructions when only the chat changes.
"""

import argparse
import json
from pathlib import Path
import subprocess
import sys
import types

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from services.assessor_factory import get_assessor
from services.focus_workflow_service import FocusWorkflowService


FOCI = [
    ('Identity', 'You assist veterinary teams in replying to pet owners.'),
    ('Goal', 'Address the pet owner’s current concern professionally.'),
    ('Objective', 'Help resolve requests in chat to reduce pressure on the phone lines.'),
    ('Extra info', 'If a concern needs visual clarification, invite relevant photos or videos.'),
    ('Appointment booking', 'When an owner requests an appointment, help arrange an in-clinic visit.'),
    ('No med request consults', 'Do not automatically require an appointment for medication refill requests.'),
    ('First aid', 'If the owner reports an injury, provide appropriate first-aid guidance and next steps.'),
    ('Do not ask', 'Do not ask for owner or pet details that are already available in the conversation.'),
    ('No online store', 'Do not refer owners to an online store.'),
    ('Med requests', 'For medication requests, explain the clinic’s payment and collection process.'),
    ('Human in the loop', 'If the issue cannot be resolved in chat, offer to pass it to the clinic team.'),
    ('PII', 'Do not disclose another client’s private information.'),
]
CASES = {
    'booking': ('My pup needs a booster, I would like an appointment please.', 'Appointment booking'),
    'refill': ('I need a repeat of my dog’s usual medication. How do I pay and collect it?', 'Med requests'),
    'injury': ('My dog cut his paw. What should I do right now?', 'First aid'),
}


def fixture(chat):
    content = '\n'.join(text for _, text in FOCI)
    scenario = {'version': 1, 'messages': [
        {'id': 'instructions', 'role': 'system', 'analysis_mode': 'analyse', 'content': content},
        {'id': 'chat', 'role': 'user', 'analysis_mode': 'retain', 'content': chat},
    ]}
    foci = [{'focus': name, 'message_id': 'instructions', 'prompt_section': text,
             'spans': [{'message_id': 'instructions', 'char_start': content.index(text),
                        'char_end': content.index(text) + len(text), 'text_snapshot': text}]}
            for name, text in FOCI]
    return scenario, foci


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='Enable billed inference calls')
    parser.add_argument('--model', default='gpt-3.5-turbo')
    parser.add_argument('--provider', default='openai')
    parser.add_argument('--compare-ref', help='Also evaluate the implementation at a trusted local Git ref')
    parser.add_argument('--repeats', type=int, default=1)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not args.live:
        parser.error('Pass --live to authorize billed evaluation calls.')
    if args.repeats < 1:
        parser.error('--repeats must be positive')
    assessor = get_assessor(model=args.model, provider=args.provider)
    services = {'current': FocusWorkflowService(assessor)}
    if args.compare_ref:
        source = subprocess.check_output(
            ['git', 'show', args.compare_ref + ':services/focus_workflow_service.py'], cwd=REPO, text=True)
        old = types.ModuleType('previous_focus_workflow')
        exec(compile(source, 'previous_focus_workflow', 'exec'), old.__dict__)
        services = {'previous': old.FocusWorkflowService(assessor), **services}
    results = []
    for name, (chat, expected) in CASES.items():
        scenario, foci = fixture(chat)
        for order, ordered in (('original', foci), ('reversed', list(reversed(foci)))):
            for repeat in range(args.repeats):
                for version, service in services.items():
                    row = {'case': name, 'chat': chat, 'order': order, 'repeat': repeat,
                           'version': version, 'expected_conditional_focus': expected}
                    try:
                        result = service.assess(scenario, ordered, phase='prospective')
                        scores = {item['focus']: item['score'] for item in result['foci']}
                        unrelated = [label for _, label in CASES.values() if label != expected]
                        passed = all(scores[expected] > scores[other] for other in unrelated)
                        row.update(relevance_check_passed=passed, assessment=result)
                        print(f'{version} {name} {order}: relevant={scores[expected]:g}%, '
                              f'unrelated={[scores[label] for label in unrelated]}, check={passed}', flush=True)
                    except ValueError as error:
                        row.update(relevance_check_passed=False, error=str(error))
                        print(f'{version} {name} {order}: invalid assessment ({error})', flush=True)
                    results.append(row)
                    args.output.write_text(json.dumps({'model': args.model, 'provider': args.provider,
                                                      'results': results}, indent=2, ensure_ascii=False))
    for version in services:
        subset = [r for r in results if r['version'] == version]
        print(f"{version}: {sum(r['relevance_check_passed'] for r in subset)}/{len(subset)} relevance checks passed")


if __name__ == '__main__':
    main()
