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
    assert '{{CHAT_CONTENT}}' not in result
    assert result.count('Test chat') == 1
    assert 'Current Chat Context' not in result


def test_build_prompt_appends_chat_only_without_placeholder():
    relevant_foci = [
        {'focus': 'Focus 1', 'weight': 0.8, 'prompt_section': 'Section 1'},
    ]
    foci_list = [
        {'focus': 'Focus 1', 'prompt_section': 'Section 1', 'is_dynamic': False},
    ]
    result = build_prompt_with_dynamic_foci(relevant_foci, foci_list, {'chat_content': 'Test chat'})
    assert 'Current Chat Context' in result
    assert 'Test chat' in result


def test_chat_included_even_when_normalized_chat_weight_is_tiny():
    """Regression: many foci dilute chat_weight below the old 0.1 gate."""
    relevant_foci = [
        {'focus': f'Focus {i}', 'weight': 0.12, 'prompt_section': f'Section {i}'}
        for i in range(8)
    ]
    foci_list = [
        {'focus': f'Focus {i}', 'prompt_section': f'Section {i}', 'is_dynamic': False}
        for i in range(8)
    ]
    chat = 'Owner: Can we schedule a booster for Max next Tuesday?'
    # Mimic post-normalization chat_weight that used to drop chat entirely.
    result = build_prompt_with_dynamic_foci(
        relevant_foci, foci_list, {'chat_content': chat}, chat_weight=0.05
    )
    assert chat in result
    assert 'Current Chat Context' in result


def test_chat_included_when_dynamic_flags_missing_from_weight_rows():
    """UI used to omit is_dynamic on weight rows; chat must still appear."""
    relevant_foci = [
        {'focus': 'Role', 'weight': 0.8, 'prompt_section': 'You are a clinic assistant.'},
        {'focus': 'Live chat', 'weight': 0.4, 'prompt_section': 'Consider the current conversation.'},
    ]
    # Full catalog has the dynamic flag; weight rows do not (old client bug).
    foci_list = [
        {'focus': 'Role', 'prompt_section': 'You are a clinic assistant.', 'is_dynamic': False},
        {
            'focus': 'Live chat',
            'prompt_section': 'Consider the current conversation.',
            'is_dynamic': True,
            'dynamic_type': 'chat',
        },
    ]
    chat = 'Please book a dental cleaning for Bella.'
    result = build_prompt_with_dynamic_foci(
        relevant_foci, foci_list, {'chat_content': chat}, chat_weight=0.08
    )
    assert chat in result
    assert '{{CHAT_CONTENT}}' not in result
    assert result.count(chat) == 1


def test_empty_chat_does_not_force_section():
    relevant_foci = [
        {'focus': 'Role', 'weight': 0.9, 'prompt_section': 'You are helpful.'},
    ]
    foci_list = relevant_foci
    result = build_prompt_with_dynamic_foci(relevant_foci, foci_list, {'chat_content': '   '})
    assert 'Current Chat Context' not in result
