"""
Unit tests for AssessmentService.
"""

import pytest
from unittest.mock import Mock, MagicMock
from services.assessment_service import AssessmentService
from core.focal_assessor import FocalAssessor


@pytest.fixture
def mock_assessor():
    """Create a mock assessor."""
    assessor = Mock(spec=FocalAssessor)
    assessor.provider = Mock()
    assessor.model = 'gpt-4o-mini'
    assessor.assess = Mock(return_value=Mock(to_dict=lambda: {'foci': []}))
    return assessor


def test_detect_foci(mock_assessor):
    """Test focus detection."""
    service = AssessmentService(mock_assessor)
    
    mock_assessor.provider.chat_completion.return_value = {
        'content': '{"foci": [{"focus": "Test", "prompt_section": "Section", "description": "Desc"}]}'
    }
    
    result = service.detect_foci("Test prompt")
    assert 'foci' in result
    assert len(result['foci']) == 1


def test_assess_focus(mock_assessor):
    """Test focus assessment."""
    service = AssessmentService(mock_assessor)
    
    result = service.assess_focus("Test prompt", "Test output")
    assert result is not None


def test_detect_dynamic_foci(mock_assessor):
    """Test dynamic focus detection."""
    service = AssessmentService(mock_assessor)
    
    mock_assessor.provider.chat_completion.return_value = {
        'content': '{"dynamic_suggestions": []}'
    }
    
    foci = [{'focus': 'Test', 'prompt_section': 'Section'}]
    pairs = [{'inputs': {'chat_content': 'test'}}]
    
    result = service.detect_dynamic_foci("Test prompt", foci, pairs)
    assert 'foci' in result
    assert 'suggestions' in result


