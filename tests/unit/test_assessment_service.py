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
