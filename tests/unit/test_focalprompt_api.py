"""Smoke tests for high-level focalprompt.api helpers (mocked assessor)."""

import json
from unittest.mock import MagicMock, Mock, patch

import pytest

from focalprompt.api import (
    _compare_reported_vs_revealed,
    analyze,
    assess_focus,
    detect_foci,
    generate_output,
)


def test_compare_reported_vs_revealed():
    reported = {
        'foci': [
            {'focus': 'A', 'score': 40, 'explanation': 'x'},
            {'focus': 'B', 'score': 60, 'explanation': 'y'},
        ]
    }
    perturbation = {
        'influence_scores': [
            {
                'focus': 'A',
                't_obs': 0.1,
                'influence': 0.1,
                'normalized_influence': 1.0,
                'p_value': 0.01,
                'q_value': 0.02,
                'is_significant': True,
            }
        ]
    }
    cmp = _compare_reported_vs_revealed(reported, perturbation)
    assert cmp['rows'][0]['reported_score'] == 40
    assert cmp['rows'][0]['is_significant'] is True
    assert cmp['rows'][0]['concordance']['key'] == 'concordant_high'
    assert 'summary' in cmp
    assert 'transformer attention' in cmp['rows'][0]['note'].lower() or 'not' in cmp['rows'][0]['note'].lower()


def test_analyze_skip_live(monkeypatch):
    with patch('focalprompt.api.detect_foci') as df, \
         patch('focalprompt.api.assess_focus') as af, \
         patch('focalprompt.api.ablate') as ab:
        df.return_value = {'foci': [{'focus': 'Role', 'prompt_section': 'You are x.'}]}
        af.return_value = {'foci': [{'focus': 'Role', 'score': 100}]}
        ab.return_value = {
            'influence_scores': [{
                'focus': 'Role', 't_obs': 0.05, 'influence': 0.05,
                'normalized_influence': 1, 'p_value': 0.2, 'q_value': 0.2,
                'is_significant': False,
            }]
        }
        out = analyze('You are x.', output='hi', run_assess=True, run_ablation=True)
        assert out['comparison'] is not None
        assert out['meta']['model'] == 'gpt-4o-mini'


def test_generate_output_accepts_scenario_and_named_inputs():
    scenario = {
        'version': 1,
        'messages': [
            {'id': 'rules', 'role': 'system', 'content': 'Be brief.', 'analysis_mode': 'analyse'},
            {'id': 'question', 'role': 'user', 'content': '', 'analysis_mode': 'retain', 'input_name': 'question'},
        ],
    }
    assessor = MagicMock()
    assessor.generate_output_response.return_value = {
        'content': 'answer', 'scenario_metadata': {'scenario_version': 1}
    }
    with patch('focalprompt.api.get_assessor', return_value=assessor):
        out = generate_output(scenario=scenario, inputs={'question': 'Why?'})
    assert out['output'] == 'answer'
    # Mocked assessors may omit the compiled scenario; the helper preserves the source.
    assert out['scenario'] == scenario
    assert assessor.generate_output_response.call_args.kwargs['inputs'] == {'question': 'Why?'}


def test_generate_output_rejects_prompt_and_scenario_together():
    with pytest.raises(ValueError, match='exactly one'):
        generate_output(
            'legacy',
            scenario={
                'version': 1,
                'messages': [
                    {'id': 'user', 'role': 'user', 'content': 'x', 'analysis_mode': 'analyse'}
                ],
            },
        )


def _detecting_assessor(prompt_section):
    assessor = Mock()
    assessor.model = 'gpt-4o-mini'
    assessor.provider_name = 'openai'
    assessor.provider = Mock()
    assessor.provider.chat_completion.return_value = {
        'content': json.dumps({
            'foci': [{
                'focus': 'Brevity',
                'evidence_quote': prompt_section,
                'prompt_section': prompt_section,
                'description': 'Desc',
            }]
        }),
        'usage': {},
    }
    return assessor


def test_detect_foci_legacy_prompt_keeps_flat_coverage_and_quality():
    """Legacy prompts keep the flat report; the scenario path has no equivalent."""
    prompt = 'Answer briefly. Never mention cats.'
    assessor = _detecting_assessor('Answer briefly.')
    with patch('focalprompt.api.get_assessor', return_value=assessor):
        result = detect_foci(prompt)

    uncovered = result['coverage']['uncovered_spans']
    assert any(span['text'].strip() == 'Never mention cats.' for span in uncovered)
    assert result['quality']['overlap_count'] == 0
    assert result['quality']['span_size_distribution']['count'] == 1
    assert 'messages' not in result['coverage']


def test_assess_focus_grounds_scenario_foci_against_scenario_text():
    """A span-only focus must reach the judge carrying its scenario evidence."""
    rules = 'Answer briefly. Say BANANAS when greeted.'
    scenario = {
        'version': 1,
        'messages': [
            {'id': 'rules', 'role': 'system', 'content': rules, 'analysis_mode': 'analyse'},
            {'id': 'chat', 'role': 'user', 'content': 'Hi', 'analysis_mode': 'retain'},
        ],
    }
    start = rules.index('Say BANANAS')
    focus = {
        'focus': 'Greeting rule',
        'spans': [{
            'message_id': 'rules',
            'char_start': start,
            'char_end': len(rules),
            'text_snapshot': rules[start:],
        }],
    }
    assessor = Mock()
    assessor.model = 'gpt-4o-mini'
    assessor.provider_name = 'openai'
    assessor.provider = Mock()
    assessor.provider.chat_completion.return_value = {
        'content': json.dumps({
            'foci': [
                {'focus_index': 0, 'focus': 'Greeting rule', 'score': 100,
                 'explanation': 'said it'},
            ],
            'overall_summary': 'ok',
        }),
        'usage': {},
    }
    from core.focal_assessor import FocalAssessor
    real = FocalAssessor.__new__(FocalAssessor)
    assessor._build_assessment_prompt_with_foci = (
        lambda p, o, f, m=None: real._build_assessment_prompt_with_foci(p, o, f, m)
    )

    with patch('focalprompt.api.get_assessor', return_value=assessor):
        result = assess_focus(output='BANANAS', foci=[focus], scenario=scenario)

    judge_message = assessor.provider.chat_completion.call_args.kwargs['messages'][1]['content']
    assert 'Say BANANAS when greeted.' in judge_message
    assert result['foci'][0]['focus_index'] == 0
    assert result['foci'][0]['message_ids'] == ['rules']
