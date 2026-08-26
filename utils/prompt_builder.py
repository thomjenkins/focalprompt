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
            'tool_results': inputs.get('tool_results', ''),
            'other_input': inputs.get('other_input', ''),
        }
    else:
        # Old structure - backward compatibility
        return {
            'chat_content': pair_data.get('chat_content', '') or pair_data.get('input', ''),
            'rag_context': pair_data.get('rag_context', ''),
            'tool_results': pair_data.get('tool_results', ''),
            'other_input': pair_data.get('other_input', ''),
        }


def _focus_dynamic_type(focus_name: str, foci_list: List[Dict], fallback: Optional[Dict] = None) -> Optional[str]:
    """Resolve dynamic_type from full foci list, then from the weight row itself."""
    for f in foci_list or []:
        if f.get('focus', '') == focus_name:
            if f.get('is_dynamic'):
                return f.get('dynamic_type')
            return None
    if fallback and fallback.get('is_dynamic'):
        return fallback.get('dynamic_type')
    return None


def _placeholder_for(dynamic_type: str) -> str:
    placeholders = {
        'chat': '{{CHAT_CONTENT}}',
        'rag': '{{RAG_CONTEXT}}',
        'tools': '{{TOOL_RESULTS}}',
        'other': '{{OTHER_INPUT}}',
    }
    return placeholders.get(dynamic_type or '', '{{DYNAMIC_CONTENT}}')


def build_prompt_with_dynamic_foci(
    relevant_foci: List[Dict],
    foci_list: List[Dict],
    inputs: Dict[str, str],
    chat_weight: float = 0.5
) -> str:
    """
    Build prompt with placeholders for dynamic foci, then replace with actual values.

    Non-empty ``chat_content`` is always included exactly once. Agent replies are
    useless without the message being answered. ``chat_weight`` only affects
    labeling / priority when chat is appended as a dedicated section; it must
    not gate whether chat appears (normalized weights often fall ≤ 0.1).
    """
    inputs = inputs or {}
    prompt_parts = []

    def append_focus_block(f: Dict) -> None:
        focus_name = f.get('focus', '')
        prompt_section = f.get('prompt_section', '')
        dynamic_type = _focus_dynamic_type(focus_name, foci_list, f)
        prompt_parts.append(f"\n### {focus_name}")
        if dynamic_type:
            prompt_parts.append(prompt_section)
            prompt_parts.append(f"\n{_placeholder_for(dynamic_type)}")
        else:
            prompt_parts.append(prompt_section)

    # Add high-weight foci first (weight > 0.7)
    high_weight_foci = [f for f in relevant_foci if f.get('weight', 0) > 0.7]
    if high_weight_foci:
        prompt_parts.append("## Primary Instructions (High Priority)")
        for f in high_weight_foci:
            append_focus_block(f)

    # Add medium-weight foci (0.3 < weight <= 0.7)
    medium_weight_foci = [f for f in relevant_foci if 0.3 < f.get('weight', 0) <= 0.7]
    if medium_weight_foci:
        prompt_parts.append("\n## Secondary Instructions (Medium Priority)")
        for f in medium_weight_foci:
            append_focus_block(f)

    # Add low-weight but relevant foci (0.1 < weight <= 0.3)
    low_weight_foci = [f for f in relevant_foci if 0.1 < f.get('weight', 0) <= 0.3]
    if low_weight_foci:
        prompt_parts.append("\n## Context (Low Priority)")
        for f in low_weight_foci:
            append_focus_block(f)

    joined = '\n'.join(prompt_parts)
    had_chat_placeholder = '{{CHAT_CONTENT}}' in joined
    chat_content = (inputs.get('chat_content') or '')
    # Preserve intentional whitespace in chat; only treat pure empty as missing.
    chat_present = bool(str(chat_content).strip())

    constructed_prompt = joined.replace('{{CHAT_CONTENT}}', chat_content)
    constructed_prompt = constructed_prompt.replace(
        '{{RAG_CONTEXT}}', inputs.get('rag_context', '') or ''
    )
    constructed_prompt = constructed_prompt.replace(
        '{{TOOL_RESULTS}}', inputs.get('tool_results', '') or ''
    )
    constructed_prompt = constructed_prompt.replace(
        '{{OTHER_INPUT}}', inputs.get('other_input', '') or ''
    )
    constructed_prompt = constructed_prompt.replace(
        '{{DYNAMIC_CONTENT}}', inputs.get('other_input', '') or ''
    )

    # Always ensure chat appears once when provided. Placeholder path already
    # injected it; otherwise append a dedicated section (ignore chat_weight gate).
    if chat_present and not had_chat_placeholder:
        try:
            weight_label = f"{float(chat_weight):.2f}"
        except (TypeError, ValueError):
            weight_label = str(chat_weight)
        constructed_prompt = (
            constructed_prompt
            + f"\n\n## Current Chat Context (Weight: {weight_label})\n\n"
            + chat_content
        )
    elif chat_present and had_chat_placeholder:
        # Placeholder existed but may have been empty if substitution missed;
        # only append if chat text is still absent.
        if chat_content not in constructed_prompt:
            try:
                weight_label = f"{float(chat_weight):.2f}"
            except (TypeError, ValueError):
                weight_label = str(chat_weight)
            constructed_prompt = (
                constructed_prompt
                + f"\n\n## Current Chat Context (Weight: {weight_label})\n\n"
                + chat_content
            )

    return constructed_prompt
