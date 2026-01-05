#!/usr/bin/env python3
"""
Prompt building utilities.

Functions for constructing prompts from foci and dynamic inputs.
"""

from typing import Dict, List, Optional


def get_pair_inputs(pair_data: Dict) -> Dict[str, str]:
    """
    Extract inputs from pair data, handling both old and new structure.
    
    Args:
        pair_data: Pair data dictionary
        
    Returns:
        Dict with 'chat_content', 'rag_context', 'tool_results'
    """
    if 'inputs' in pair_data:
        # New structure
        inputs = pair_data.get('inputs', {})
        return {
            'chat_content': inputs.get('chat_content', ''),
            'rag_context': inputs.get('rag_context', ''),
            'tool_results': inputs.get('tool_results', '')
        }
    else:
        # Old structure - backward compatibility
        return {
            'chat_content': pair_data.get('chat_content', '') or pair_data.get('input', ''),
            'rag_context': pair_data.get('rag_context', ''),
            'tool_results': pair_data.get('tool_results', '')
        }


def build_prompt_with_dynamic_foci(
    relevant_foci: List[Dict],
    foci_list: List[Dict],
    inputs: Dict[str, str],
    chat_weight: float = 0.5
) -> str:
    """
    Build prompt with placeholders for dynamic foci, then replace with actual values.
    
    Args:
        relevant_foci: List of foci with weights to include
        foci_list: Full list of all foci (for dynamic type lookup)
        inputs: Dict with chat_content, rag_context, tool_results
        chat_weight: Weight for chat content (for backward compatibility)
        
    Returns:
        Constructed prompt string
    """
    prompt_parts = []
    
    # Helper to get dynamic type for a focus
    def get_focus_dynamic_type(focus_name: str) -> Optional[str]:
        for f in foci_list:
            if f.get('focus', '') == focus_name:
                return f.get('dynamic_type') if f.get('is_dynamic') else None
        return None
    
    # Helper to get placeholder for dynamic type
    def get_placeholder(dynamic_type: str) -> str:
        placeholders = {
            'chat': '{{CHAT_CONTENT}}',
            'rag': '{{RAG_CONTEXT}}',
            'tools': '{{TOOL_RESULTS}}',
            'other': '{{OTHER_INPUT}}'
        }
        return placeholders.get(dynamic_type, '{{DYNAMIC_CONTENT}}')
    
    # Add high-weight foci first (weight > 0.7)
    high_weight_foci = [f for f in relevant_foci if f.get('weight', 0) > 0.7]
    if high_weight_foci:
        prompt_parts.append("## Primary Instructions (High Priority)")
        for f in high_weight_foci:
            focus_name = f.get('focus', '')
            prompt_section = f.get('prompt_section', '')
            dynamic_type = get_focus_dynamic_type(focus_name)
            
            prompt_parts.append(f"\n### {focus_name}")
            if dynamic_type:
                prompt_parts.append(prompt_section)
                prompt_parts.append(f"\n{get_placeholder(dynamic_type)}")
            else:
                prompt_parts.append(prompt_section)
    
    # Add medium-weight foci (0.3 < weight <= 0.7)
    medium_weight_foci = [f for f in relevant_foci if 0.3 < f.get('weight', 0) <= 0.7]
    if medium_weight_foci:
        prompt_parts.append("\n## Secondary Instructions (Medium Priority)")
        for f in medium_weight_foci:
            focus_name = f.get('focus', '')
            prompt_section = f.get('prompt_section', '')
            dynamic_type = get_focus_dynamic_type(focus_name)
            
            prompt_parts.append(f"\n### {focus_name}")
            if dynamic_type:
                prompt_parts.append(prompt_section)
                prompt_parts.append(f"\n{get_placeholder(dynamic_type)}")
            else:
                prompt_parts.append(prompt_section)
    
    # Add low-weight but relevant foci (0.1 < weight <= 0.3)
    low_weight_foci = [f for f in relevant_foci if 0.1 < f.get('weight', 0) <= 0.3]
    if low_weight_foci:
        prompt_parts.append("\n## Context (Low Priority)")
        for f in low_weight_foci:
            focus_name = f.get('focus', '')
            prompt_section = f.get('prompt_section', '')
            dynamic_type = get_focus_dynamic_type(focus_name)
            
            prompt_parts.append(f"\n### {focus_name}")
            if dynamic_type:
                prompt_parts.append(prompt_section)
                prompt_parts.append(f"\n{get_placeholder(dynamic_type)}")
            else:
                prompt_parts.append(prompt_section)
    
    # Replace placeholders with actual values
    constructed_prompt = '\n'.join(prompt_parts)
    
    # Replace all placeholders with actual values
    constructed_prompt = constructed_prompt.replace('{{CHAT_CONTENT}}', inputs.get('chat_content', ''))
    constructed_prompt = constructed_prompt.replace('{{RAG_CONTEXT}}', inputs.get('rag_context', ''))
    constructed_prompt = constructed_prompt.replace('{{TOOL_RESULTS}}', inputs.get('tool_results', ''))
    constructed_prompt = constructed_prompt.replace('{{OTHER_INPUT}}', inputs.get('other_input', ''))
    
    # Also handle chat_weight for backward compatibility (if chat_weight > 0.1 and no chat focus)
    # This is for the old way where chat was added separately
    if chat_weight > 0.1 and '{{CHAT_CONTENT}}' not in constructed_prompt:
        chat_content = inputs.get('chat_content', '')
        if chat_content:
            prompt_parts.append(f"\n## Current Chat Context (Weight: {chat_weight:.2f})")
            prompt_parts.append(f"\n{chat_content}")
            constructed_prompt = '\n'.join(prompt_parts)
    
    return constructed_prompt


