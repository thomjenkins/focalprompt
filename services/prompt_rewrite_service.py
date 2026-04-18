#!/usr/bin/env python3
"""
Prompt rewrite service.

Handles rewriting prompts with emphasis based on focus weights.
"""

import inspect
from typing import List, Dict
from core.focal_assessor import FocalAssessor


class PromptRewriteService:
    """Service for rewriting prompts with focus emphasis."""
    
    def __init__(self, assessor: FocalAssessor):
        """
        Initialize prompt rewrite service.
        
        Args:
            assessor: FocalAssessor instance
        """
        self.assessor = assessor
    
    def rewrite_prompt(
        self,
        prompt: str,
        foci_weights: List[Dict]
    ) -> str:
        """
        Rewrite prompt with emphasis based on focus weights.
        
        Args:
            prompt: Original prompt
            foci_weights: List of foci with weights
            
        Returns:
            Rewritten prompt string
        """
        llm = self.assessor.provider
        provider_name = getattr(self.assessor, 'provider_name', 'openai')
        
        # Build the rewrite instruction
        weights_text = '\n'.join([
            f"- {f['focus']}: {f['weight']}% emphasis (covers: {f['prompt_section'][:100]}...)"
            for f in foci_weights
        ])
        
        rewrite_instruction = f"""Rewrite the following prompt to emphasize different aspects based on the specified weights. 
The weights indicate how much attention/emphasis should be given to each focus area in the final output.

ORIGINAL PROMPT:
{prompt}

FOCUS WEIGHTS:
{weights_text}

INSTRUCTIONS:
1. Rewrite the prompt to naturally emphasize aspects with higher weights
2. For high-weight foci (70-100%), make them prominent and explicit
3. For medium-weight foci (30-70%), include them clearly but not as prominently
4. For low-weight foci (0-30%), mention them briefly or implicitly
5. Maintain the original structure and meaning
6. Use emphasis techniques like:
   - Repetition for high-weight items
   - Stronger language for important aspects
   - Positioning important items earlier
   - Adding explicit instructions for high-weight foci
7. The rewritten prompt should guide the LLM to produce output that matches the intended focus distribution

Return only the rewritten prompt, without any additional explanation or formatting."""

        kwargs = {
            'model': self.assessor.model,
            'messages': [
                {
                    "role": "system",
                    "content": "You are an expert at rewriting prompts to emphasize different aspects while maintaining clarity and coherence."
                },
                {
                    "role": "user",
                    "content": rewrite_instruction
                }
            ],
            'temperature': 0.7
        }
        if hasattr(llm, 'chat_completion'):
            sig = inspect.signature(llm.chat_completion)
            if 'provider' in sig.parameters:
                kwargs['provider'] = provider_name
        response = llm.chat_completion(**kwargs)
        
        rewritten = response['content'].strip()
        return rewritten


