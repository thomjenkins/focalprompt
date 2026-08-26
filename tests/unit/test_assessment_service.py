"""
Unit tests for AssessmentService.
"""

import json
from unittest.mock import Mock

import pytest

from services.assessment_service import AssessmentService
from core.focal_assessor import FocalAssessor


@pytest.fixture
def mock_assessor():
    """Create a mock assessor."""
    assessor = Mock(spec=FocalAssessor)
    assessor.provider = Mock()
    assessor.model = 'gpt-4o-mini'
    assessor.provider_name = 'openai'
    assessor.assess = Mock(return_value=Mock(to_dict=lambda: {'foci': []}))
    return assessor


def test_detect_foci(mock_assessor):
    """Test focus detection with span verification and provenance gating."""
    service = AssessmentService(mock_assessor)
    prompt = "Test prompt with a real section."

    mock_assessor.provider.chat_completion.return_value = {
        'content': json.dumps({
            'foci': [{
                'focus': 'Test',
                'evidence_quote': 'Test prompt with a real section.',
                'prompt_section': 'Test prompt with a real section.',
                'description': 'Desc',
            }]
        }),
        'usage': {},
    }

    result = service.detect_foci(prompt)
    assert 'foci' in result
    assert len(result['foci']) == 1
    assert result['foci'][0]['verified'] is True
    assert result['foci'][0]['char_start'] == 0
    assert result['foci'][0]['char_end'] == len(prompt)
    assert 'rejected_proposals' in result


def test_detect_foci_unaligned_quote_rejected_not_listed(mock_assessor):
    """Ungrounded automatic proposals are omitted from foci (not merely flagged)."""
    service = AssessmentService(mock_assessor)
    mock_assessor.provider.chat_completion.side_effect = [
        {
            'content': json.dumps({
                'foci': [{
                    'focus': 'Test',
                    'evidence_quote': 'not a substring',
                    'prompt_section': 'not a substring',
                    'description': 'Desc',
                }]
            }),
            'usage': {},
        },
        {'content': json.dumps({'foci': []}), 'usage': {}},
    ]
    result = service.detect_foci("Test prompt")
    assert result['foci'] == []
    assert any(r.get('focus') == 'Test' for r in result['rejected_proposals'])


def test_assess_focus(mock_assessor):
    """Test focus assessment."""
    service = AssessmentService(mock_assessor)
    result = service.assess_focus("Test prompt", "Test output")
    assert result is not None


def test_assess_focus_with_user_foci_reattaches_prompt_section(mock_assessor):
    """Model may omit prompt_section; we restore it from user-defined foci."""
    long_section = (
        "You are an AI assistant designed to help veterinary teams provide "
        "informative, empathetic, and professional responses to queries from "
        "clients about their pets and clinical workflows." * 3
    )
    user_foci = [
        {'focus': 'Role', 'prompt_section': long_section},
        {'focus': 'Tone', 'prompt_section': 'Be empathetic.'},
    ]
    real = FocalAssessor.__new__(FocalAssessor)
    mock_assessor._build_assessment_prompt_with_foci = (
        lambda prompt, output, foci, max_foci=None: real._build_assessment_prompt_with_foci(
            prompt, output, foci, max_foci
        )
    )
    mock_assessor.provider.chat_completion.return_value = {
        'content': json.dumps({
            'foci': [
                {'focus': 'Role', 'score': 70, 'explanation': 'Output stays in role.'},
                {'focus': 'Tone', 'score': 30, 'explanation': 'Tone is warm.'},
            ],
            'overall_summary': 'Mostly role.',
        }),
        'usage': {'prompt_tokens': 10, 'completion_tokens': 20},
    }

    service = AssessmentService(mock_assessor)
    result = service.assess_focus(
        'System prompt here',
        'Hello, I can help with your pet.',
        user_foci=user_foci,
    )
    by_name = {f['focus']: f for f in result['foci']}
    assert by_name['Role']['prompt_section'] == long_section
    assert by_name['Tone']['prompt_section'] == 'Be empathetic.'
    # Prompt must not ask the model to echo full prompt_section into JSON
    built = mock_assessor._build_assessment_prompt_with_foci(
        'System prompt here', 'out', user_foci, None
    )
    assert 'Do NOT include prompt_section' in built
    assert 'ORIGINAL PROMPT:' not in built
    assert long_section not in built  # excerpted in the foci list
    call_kw = mock_assessor.provider.chat_completion.call_args.kwargs
    assert call_kw.get('max_tokens') == 4096


def test_assess_focus_retries_when_first_response_truncated(mock_assessor):
    """Truncated prompt_section echo triggers one retry with stricter instructions."""
    user_foci = [
        {'focus': 'Role', 'prompt_section': 'You are a vet assistant.'},
        {'focus': 'Tone', 'prompt_section': 'Be kind.'},
    ]
    real = FocalAssessor.__new__(FocalAssessor)
    mock_assessor._build_assessment_prompt_with_foci = (
        lambda prompt, output, foci, max_foci=None: real._build_assessment_prompt_with_foci(
            prompt, output, foci, max_foci
        )
    )
    truncated = (
        '{\n  "foci": [\n    {\n      "focus": "Role",\n'
        '      "prompt_section": "You are an AI assistant designed to help veterinary'
    )
    good = json.dumps({
        'foci': [
            {'focus': 'Role', 'score': 60, 'explanation': 'In role.'},
            {'focus': 'Tone', 'score': 40, 'explanation': 'Kind.'},
        ],
        'overall_summary': 'ok',
    })
    mock_assessor.provider.chat_completion.side_effect = [
        {'content': truncated, 'usage': {'prompt_tokens': 5, 'completion_tokens': 5}},
        {'content': good, 'usage': {'prompt_tokens': 5, 'completion_tokens': 10}},
    ]
    service = AssessmentService(mock_assessor)
    result = service.assess_focus('p', 'o', user_foci=user_foci)
    assert len(result['foci']) == 2
    assert mock_assessor.provider.chat_completion.call_count == 2
    retry_user = mock_assessor.provider.chat_completion.call_args_list[1].kwargs['messages'][1]['content']
    assert 'CRITICAL RETRY' in retry_user


def test_detect_dynamic_foci(mock_assessor):
    """Test dynamic focus detection."""
    service = AssessmentService(mock_assessor)

    mock_assessor.provider.chat_completion.return_value = {
        'content': json.dumps({'dynamic_suggestions': []}),
        'usage': {},
    }

    foci = [{'focus': 'Test', 'prompt_section': 'Section'}]
    pairs = [{'inputs': {'chat_content': 'test'}}]

    result = service.detect_dynamic_foci("Test prompt", foci, pairs)
    assert 'foci' in result
    assert 'suggestions' in result
