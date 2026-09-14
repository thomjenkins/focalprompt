"""Focus identity and grounded evidence for scenario assessments.

Covers the two ways a judge call used to go wrong:
  * a focus grounded only by spans reached the judge with no source text;
  * results were joined back onto submitted foci by display name, which
    collapses repeated names onto one another.
"""

import json
from unittest.mock import Mock

import pytest

from core.focal_assessor import FocalAssessor
from services.assessment_service import AssessmentService
from utils.inference_scenario import ScenarioValidationError


RULES = 'Always answer briefly. Say BANANAS when greeted. Never mention cats.'
BANANA_SPAN = (RULES.index('Say BANANAS'), RULES.index(' Never mention cats.'))
CATS_SPAN = (RULES.index('Never mention cats.'), len(RULES))

SCENARIO = {
    'version': 1,
    'messages': [
        {'id': 'rules', 'role': 'system', 'content': RULES, 'analysis_mode': 'analyse'},
        {'id': 'chat', 'role': 'user', 'content': 'Hello there', 'analysis_mode': 'retain'},
    ],
}


@pytest.fixture
def assessor():
    mock = Mock(spec=FocalAssessor)
    mock.provider = Mock()
    mock.model = 'gpt-4o-mini'
    mock.provider_name = 'openai'
    real = FocalAssessor.__new__(FocalAssessor)
    mock._build_assessment_prompt_with_foci = (
        lambda prompt, output, foci, max_foci=None:
        real._build_assessment_prompt_with_foci(prompt, output, foci, max_foci)
    )
    return mock


def _span(message_id, bounds, content=RULES):
    start, end = bounds
    return {
        'message_id': message_id,
        'char_start': start,
        'char_end': end,
        'text_snapshot': content[start:end],
    }


def _reply(items, summary='ok'):
    return {
        'content': json.dumps({'foci': items, 'overall_summary': summary}),
        'usage': {'prompt_tokens': 1, 'completion_tokens': 1},
    }


def _judge_message(assessor_mock, call_index=0):
    kwargs = assessor_mock.provider.chat_completion.call_args_list[call_index].kwargs
    return kwargs['messages'][1]['content']


def test_span_only_focus_reaches_judge_with_scenario_text(assessor):
    """A focus with spans but no prompt_section must still carry its evidence."""
    focus = {'focus': 'Greeting rule', 'spans': [_span('rules', BANANA_SPAN)]}
    assessor.provider.chat_completion.return_value = _reply(
        [{'focus_index': 0, 'focus': 'Greeting rule', 'score': 100, 'explanation': 'x'}]
    )

    result = AssessmentService(assessor).assess_focus(
        'analysis document', 'Hi!', user_foci=[focus], scenario=SCENARIO
    )

    assert 'Say BANANAS when greeted.' in _judge_message(assessor)
    assert result['foci'][0]['prompt_section'] == 'Say BANANAS when greeted.'
    assert result['foci'][0]['spans'] == [_span('rules', BANANA_SPAN)]
    assert result['foci'][0]['message_id'] == 'rules'
    assert result['foci'][0]['message_ids'] == ['rules']
    assert result['foci'][0]['focus_index'] == 0


def test_stale_span_snapshot_rejected_before_any_model_call(assessor):
    focus = {
        'focus': 'Greeting rule',
        'spans': [{
            'message_id': 'rules',
            'char_start': BANANA_SPAN[0],
            'char_end': BANANA_SPAN[1],
            'text_snapshot': 'Say APPLES when greeted.',
        }],
    }
    with pytest.raises(ScenarioValidationError):
        AssessmentService(assessor).assess_focus(
            'analysis document', 'Hi!', user_foci=[focus], scenario=SCENARIO
        )
    assessor.provider.chat_completion.assert_not_called()


def test_retained_message_span_rejected_before_any_model_call(assessor):
    focus = {
        'focus': 'Chat text',
        'spans': [_span('chat', (0, 5), content='Hello there')],
    }
    with pytest.raises(ScenarioValidationError):
        AssessmentService(assessor).assess_focus(
            'analysis document', 'Hi!', user_foci=[focus], scenario=SCENARIO
        )
    assessor.provider.chat_completion.assert_not_called()


def test_focus_without_any_source_text_rejected_before_any_model_call(assessor):
    with pytest.raises(ScenarioValidationError):
        AssessmentService(assessor).assess_focus(
            'analysis document', 'Hi!',
            user_foci=[{'focus': 'Nothing at all'}],
            scenario=SCENARIO,
        )
    assessor.provider.chat_completion.assert_not_called()


def test_repeated_display_names_keep_separate_provenance_and_scores(assessor):
    foci = [
        {'focus': 'Rule', 'spans': [_span('rules', BANANA_SPAN)]},
        {'focus': 'Rule', 'spans': [_span('rules', CATS_SPAN)]},
    ]
    assessor.provider.chat_completion.return_value = _reply([
        {'focus_index': 1, 'focus': 'Rule', 'score': 25, 'explanation': 'cats untouched'},
        {'focus_index': 0, 'focus': 'Rule', 'score': 75, 'explanation': 'said bananas'},
    ])

    result = AssessmentService(assessor).assess_focus(
        'analysis document', 'BANANAS', user_foci=foci, scenario=SCENARIO
    )

    first, second = result['foci']
    assert [f['focus_index'] for f in result['foci']] == [0, 1]
    assert first['prompt_section'] == RULES[slice(*BANANA_SPAN)]
    assert second['prompt_section'] == RULES[slice(*CATS_SPAN)]
    assert first['spans'] == [_span('rules', BANANA_SPAN)]
    assert second['spans'] == [_span('rules', CATS_SPAN)]
    assert (first['score'], second['score']) == (75.0, 25.0)
    assert first['explanation'] == 'said bananas'


def test_repeated_names_without_identity_retry_instead_of_guessing(assessor):
    foci = [
        {'focus': 'Rule', 'spans': [_span('rules', BANANA_SPAN)]},
        {'focus': 'Rule', 'spans': [_span('rules', CATS_SPAN)]},
    ]
    assessor.provider.chat_completion.side_effect = [
        _reply([
            {'focus': 'Rule', 'score': 70, 'explanation': 'ambiguous'},
            {'focus': 'Rule', 'score': 30, 'explanation': 'ambiguous'},
        ]),
        _reply([
            {'focus_index': 1, 'focus': 'Rule', 'score': 70, 'explanation': 'cats'},
            {'focus_index': 0, 'focus': 'Rule', 'score': 30, 'explanation': 'bananas'},
        ]),
    ]

    result = AssessmentService(assessor).assess_focus(
        'analysis document', 'BANANAS', user_foci=foci, scenario=SCENARIO
    )

    assert [f['score'] for f in result['foci']] == [30.0, 70.0]
    assert [f['spans'][0]['char_start'] for f in result['foci']] == [
        BANANA_SPAN[0], CATS_SPAN[0]
    ]


def test_dropped_focus_is_reported_as_zero_not_borrowed_from_namesake(assessor):
    foci = [
        {'focus': 'Rule', 'spans': [_span('rules', BANANA_SPAN)]},
        {'focus': 'Rule', 'spans': [_span('rules', CATS_SPAN)]},
    ]
    assessor.provider.chat_completion.return_value = _reply([
        {'focus_index': 0, 'focus': 'Rule', 'score': 100, 'explanation': 'only one scored'},
    ])

    result = AssessmentService(assessor).assess_focus(
        'analysis document', 'BANANAS', user_foci=foci, scenario=SCENARIO
    )

    assert len(result['foci']) == 2
    assert result['foci'][1]['score'] == 0.0


def test_legacy_foci_keep_index_and_omit_scenario_provenance(assessor):
    user_foci = [
        {'focus': 'Role', 'prompt_section': 'You are a vet assistant.'},
        {'focus': 'Tone', 'prompt_section': 'Be kind.'},
    ]
    assessor.provider.chat_completion.return_value = _reply([
        {'focus_index': 0, 'focus': 'Role', 'score': 60, 'explanation': 'in role'},
        {'focus_index': 1, 'focus': 'Tone', 'score': 40, 'explanation': 'kind'},
    ])

    result = AssessmentService(assessor).assess_focus('p', 'o', user_foci=user_foci)

    assert [f['focus_index'] for f in result['foci']] == [0, 1]
    assert all('spans' not in f for f in result['foci'])
    assert all('message_id' not in f for f in result['foci'])
    assert result['foci'][0]['prompt_section'] == 'You are a vet assistant.'
