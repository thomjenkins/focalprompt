"""
Unit tests for prompt builder utilities.
"""

import pytest
from utils.prompt_builder import get_pair_inputs, build_prompt_with_dynamic_foci


def test_get_pair_inputs_new_structure():
    """Test extracting inputs from new structure."""
    pair_data = {
        'inputs': {
            'chat_content': 'Chat',
            'rag_context': 'RAG',
            'tool_results': 'Tools'
        }
    }
    
    result = get_pair_inputs(pair_data)
    assert result['chat_content'] == 'Chat'
    assert result['rag_context'] == 'RAG'
    assert result['tool_results'] == 'Tools'


def test_get_pair_inputs_old_structure():
    """Test extracting inputs from old structure."""
    pair_data = {
        'chat_content': 'Chat',
        'input': 'Input'
    }
    
    result = get_pair_inputs(pair_data)
    assert result['chat_content'] == 'Chat'


def test_build_prompt_with_dynamic_foci():
    """Test building prompt with dynamic foci."""
    relevant_foci = [
        {'focus': 'Focus 1', 'weight': 0.8, 'prompt_section': 'Section 1'},
        {'focus': 'Focus 2', 'weight': 0.5, 'prompt_section': 'Section 2'}
    ]
    foci_list = [
        {'focus': 'Focus 1', 'prompt_section': 'Section 1', 'is_dynamic': False},
        {'focus': 'Focus 2', 'prompt_section': 'Section 2', 'is_dynamic': True, 'dynamic_type': 'chat'}
    ]
    inputs = {'chat_content': 'Test chat'}
    
    result = build_prompt_with_dynamic_foci(relevant_foci, foci_list, inputs)
    
    assert 'Focus 1' in result
    assert 'Focus 2' in result
    assert 'Test chat' in result


