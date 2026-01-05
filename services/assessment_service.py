#!/usr/bin/env python3
"""
Assessment service for focus detection and assessment.

Handles:
- Automatic focus detection from prompts
- Dynamic focus detection
- Focus assessment (scoring)
"""

import json
from typing import List, Dict, Optional
from core.focal_assessor import FocalAssessor, FocusScore, FocusAssessment
from utils.prompt_builder import get_pair_inputs


class AssessmentService:
    """Service for focus assessment operations."""
    
    def __init__(
        self,
        assessor: FocalAssessor,
        checkpoint_service=None
    ):
        """
        Initialize assessment service.
        
        Args:
            assessor: FocalAssessor instance
            checkpoint_service: Optional CheckpointService for saving results
        """
        self.assessor = assessor
        self.checkpoint_service = checkpoint_service
    
    def detect_foci(self, prompt: str) -> Dict:
        """
        Use LLM to automatically detect foci from the prompt.
        
        Args:
            prompt: The prompt to analyze
            
        Returns:
            Dict with 'foci' list
        """
        provider = self.assessor.provider
        
        # Use LLM to detect foci from the prompt structure
        response = provider.chat_completion(
            model=self.assessor.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at analyzing prompts and breaking them down into distinct structural components (foci). Each focus should be a specific instruction, requirement, constraint, or task from the prompt."
                },
                {
                    "role": "user",
                    "content": f"""Analyze the following prompt and break it down into distinct structural foci. Each focus should be a specific, identifiable part of the prompt itself - such as:
- A specific instruction or requirement
- A specific constraint or rule
- A specific task or objective
- A specific format requirement
- A specific section with distinct content

PROMPT:
{prompt}

Return a JSON object with this structure:
{{
  "foci": [
    {{
      "focus": "A brief description of this focus point",
      "prompt_section": "The exact text from the prompt that defines this focus (quote it directly)",
      "description": "A more detailed explanation of what this focus represents"
    }}
  ]
}}

Identify all distinct structural components of the prompt."""
                }
            ],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        
        result = json.loads(response['content'])
        return result
    
    def detect_dynamic_foci(
        self,
        prompt: str,
        foci: List[Dict],
        pairs: List[Dict]
    ) -> Dict:
        """
        Auto-detect which foci should be marked as dynamic based on prompt structure and input patterns.
        
        Args:
            prompt: The prompt text
            foci: List of focus dictionaries
            pairs: List of input-output pairs for pattern analysis
            
        Returns:
            Dict with 'foci' (updated) and 'suggestions'
        """
        provider = self.assessor.provider
        
        # Extract input patterns from pairs
        input_samples = []
        for pair in pairs[:10]:  # Sample up to 10 pairs for analysis
            inputs = get_pair_inputs(pair)
            input_samples.append({
                'chat_content': inputs.get('chat_content', '')[:200],  # Truncate for analysis
                'rag_context': inputs.get('rag_context', '')[:200],
                'tool_results': inputs.get('tool_results', '')[:200]
            })
        
        # Build foci list for analysis
        foci_list_text = '\n'.join([
            f"{i+1}. {f.get('focus', 'Unknown')}: {f.get('prompt_section', '')[:300]}"
            for i, f in enumerate(foci)
        ])
        
        # Use LLM to analyze which foci correspond to dynamic inputs
        response = provider.chat_completion(
            model=self.assessor.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at analyzing prompt structures and identifying which sections correspond to dynamic inputs (chat content, RAG context, tool results) versus static instructions."
                },
                {
                    "role": "user",
                    "content": f"""Analyze the prompt structure and the input patterns to determine which foci should be marked as dynamic.

PROMPT:
{prompt}

FOCI:
{foci_list_text}

INPUT SAMPLES (showing patterns across different pairs):
{json.dumps(input_samples, indent=2)}

For each focus, determine:
1. Does this focus section contain a placeholder or reference to dynamic content (like "current chat", "user message", "retrieved context", "tool results", etc.)?
2. Do the input samples show that different pairs have different values for chat_content, rag_context, or tool_results?
3. Does the prompt_section text suggest this is where dynamic content would be inserted?

Return a JSON object with this structure:
{{
  "dynamic_suggestions": [
    {{
      "focus_index": 0,
      "focus_name": "Name of the focus",
      "should_be_dynamic": true,
      "dynamic_type": "chat" | "rag" | "tools" | null,
      "confidence": 0.0-1.0,
      "reasoning": "Explanation of why this should/shouldn't be dynamic"
    }}
  ]
}}

Match foci to input types based on:
- Keywords in prompt_section: "chat", "conversation", "message", "user input" → chat
- Keywords: "retrieved", "context", "knowledge", "RAG", "search results" → rag
- Keywords: "tool", "function", "API", "execution result" → tools
- Pattern matching: If prompt_section contains placeholders or references to variable content
- Input variation: If different pairs have different values for a specific input type

Only mark as dynamic if confidence > 0.6."""
                }
            ],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        
        result = json.loads(response['content'])
        
        # Apply suggestions to foci
        suggestions = result.get('dynamic_suggestions', [])
        updated_foci = []
        
        for i, focus in enumerate(foci):
            # Find matching suggestion
            suggestion = next(
                (s for s in suggestions if s.get('focus_index') == i or 
                 s.get('focus_name', '').lower() == focus.get('focus', '').lower()),
                None
            )
            
            if suggestion and suggestion.get('should_be_dynamic') and suggestion.get('confidence', 0) > 0.6:
                updated_foci.append({
                    **focus,
                    'is_dynamic': True,
                    'dynamic_type': suggestion.get('dynamic_type')
                })
            else:
                updated_foci.append({
                    **focus,
                    'is_dynamic': focus.get('is_dynamic', False),
                    'dynamic_type': focus.get('dynamic_type')
                })
        
        return {
            'foci': updated_foci,
            'suggestions': suggestions
        }
    
    def assess_focus(
        self,
        prompt: str,
        output: str,
        user_foci: Optional[List[Dict]] = None,
        max_foci: Optional[int] = None
    ) -> Dict:
        """
        Assess focus distribution in output relative to prompt.
        
        Args:
            prompt: The original prompt
            output: The LLM output to assess
            user_foci: Optional user-defined foci
            max_foci: Optional maximum number of foci
            
        Returns:
            Dict with assessment results
        """
        # If user provided foci, use them for assessment
        if user_foci and len(user_foci) > 0:
            # Build a custom assessment that uses the user-defined foci
            assessment_prompt = self.assessor._build_assessment_prompt_with_foci(
                prompt, output, user_foci, max_foci
            )
            
            response = self.assessor.provider.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at analyzing how well LLM outputs address different aspects of prompts. You assess the level of attention given to each specified focus point."
                    },
                    {
                        "role": "user",
                        "content": assessment_prompt
                    }
                ],
                model=self.assessor.model,
                response_format={"type": "json_object"},
                temperature=0.3
            )
            
            result = json.loads(response['content'])
            
            # Parse the response
            foci_list = [
                FocusScore(
                    focus=item['focus'],
                    prompt_section=item.get('prompt_section', ''),
                    score=float(item['score']),
                    explanation=item['explanation']
                )
                for item in result['foci']
            ]
            
            # Verify total equals 100
            total = sum(f.score for f in foci_list)
            if abs(total - 100.0) > 0.1:
                if total > 0:
                    for focus in foci_list:
                        focus.score = (focus.score / total) * 100.0
            
            assessment = FocusAssessment(
                foci=foci_list,
                overall_summary=result.get('overall_summary', '')
            )
        else:
            # Use standard assessment
            assessment = self.assessor.assess(prompt, output, max_foci=max_foci)
        
        # Convert to dictionary for JSON response
        result = assessment.to_dict()
        
        return result


