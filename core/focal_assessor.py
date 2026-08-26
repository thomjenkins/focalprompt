"""
FocalPrompt - Assess relative focus of attention in LLM outputs.

This module provides functionality to analyze how well an LLM output
addresses different aspects (foci) of a given prompt.
"""

import json
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
# OpenAI import removed - we use AI Gateway now via LLMProvider abstraction


@dataclass
class FocusScore:
    """Represents a single focus point and its score."""
    focus: str
    prompt_section: str  # Specific section of prompt this focus relates to
    score: float  # Points out of 100 (total must equal 100)
    explanation: str


@dataclass
class FocusAssessment:
    """Complete assessment result with all foci and scores."""
    foci: List[FocusScore]
    overall_summary: str
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'foci': [asdict(f) for f in self.foci],
            'overall_summary': self.overall_summary
        }
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
    
    def print_summary(self):
        """Print a human-readable summary."""
        total_points = sum(f.score for f in self.foci)
        print("\n" + "="*60)
        print("FOCUS ASSESSMENT RESULTS")
        print("="*60)
        print(f"\nOverall Summary: {self.overall_summary}\n")
        print("-"*60)
        print("Focus Scores (Total must equal 100 points):")
        print("-"*60)
        for i, focus_score in enumerate(self.foci, 1):
            print(f"\n{i}. Focus: {focus_score.focus}")
            print(f"   Prompt Section: {focus_score.prompt_section}")
            print(f"   Points: {focus_score.score:.1f}/100")
            print(f"   Explanation: {focus_score.explanation}")
        print(f"\nTotal Points: {total_points:.1f}/100")
        if abs(total_points - 100.0) > 0.1:
            print(f"⚠️  WARNING: Total does not equal 100 points!")
        print("\n" + "="*60)


class FocalAssessor:
    """
    Assesses the relative focus of attention given to different parts
    of a prompt in an LLM output.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        agent_model: Optional[str] = None,
        provider: str = "openai",
        provider_instance: Optional[object] = None
    ):
        """
        Initialize the FocalAssessor.
        
        Args:
            api_key: API key for the provider. If None, will try to get from environment.
            model: The model to use for assessment (default: gpt-4o-mini)
            agent_model: The model to use for generating output (default: same as model)
            provider: The LLM provider to use ('openai', 'anthropic', 'google', 'grok')
            provider_instance: Optional pre-initialized provider instance (e.g., AI Gateway)
        """
        if provider_instance:
            # Use provided provider instance (e.g., from AI Gateway)
            self.provider = provider_instance
            self.provider_name = provider
        else:
            # Create provider from API key
            from core.llm_providers import get_provider
            self.provider = get_provider(provider, api_key)
            self.provider_name = provider
        
        self.model = model
        self.agent_model = agent_model or model
        # Keep client for backward compatibility (will be provider instance)
        self.client = self.provider
    
    def generate_output(
        self,
        prompt: str,
        temperature: float = 0.7
    ) -> str:
        """
        Generate an output using an LLM agent based on the prompt.
        
        Args:
            prompt: The prompt/input to generate output for
            temperature: Temperature for generation (default: 0.7)
        
        Returns:
            Generated output string
        """
        # Pass provider name if using AI Gateway
        if hasattr(self.provider, 'chat_completion'):
            # Check if provider needs provider parameter (AI Gateway)
            import inspect
            sig = inspect.signature(self.provider.chat_completion)
            if 'provider' in sig.parameters:
                response = self.provider.chat_completion(
                    messages=[
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    model=self.agent_model,
                    temperature=temperature,
                    provider=self.provider_name
                )
            else:
                response = self.provider.chat_completion(
                    messages=[
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    model=self.agent_model,
                    temperature=temperature
                )
        else:
            raise ValueError("Provider does not have chat_completion method")
        
        return response['content']
    
    def assess(
        self,
        prompt: str,
        output: str,
        max_foci: Optional[int] = None
    ) -> FocusAssessment:
        """
        Assess the focus distribution in an LLM output relative to the prompt.
        
        Args:
            prompt: The original prompt/input given to the LLM
            output: The LLM's output/response
            max_foci: Maximum number of foci to identify (None for automatic)
        
        Returns:
            FocusAssessment object with foci, scores, and explanations
        """
        assessment_prompt = self._build_assessment_prompt(
            prompt, output, max_foci
        )
        
        response = self.provider.chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at analyzing how well LLM outputs address different aspects of prompts. You break prompts into distinct focus points (foci) and assess the level of attention given to each."
                },
                {
                    "role": "user",
                    "content": assessment_prompt
                }
            ],
            model=self.model,
            response_format={"type": "json_object"},
            temperature=0.3
        )
        
        from utils.llm_json import parse_llm_json
        result = parse_llm_json(response.get('content', ''))
        
        # Parse the response
        foci = [
            FocusScore(
                focus=item['focus'],
                prompt_section=item.get('prompt_section', ''),
                score=float(item['score']),
                explanation=item['explanation']
            )
            for item in result['foci']
        ]
        
        # Verify total equals 100
        total = sum(f.score for f in foci)
        if abs(total - 100.0) > 0.1:
            # Normalize if needed (though the LLM should handle this)
            if total > 0:
                for focus in foci:
                    focus.score = (focus.score / total) * 100.0
        
        return FocusAssessment(
            foci=foci,
            overall_summary=result.get('overall_summary', '')
        )
    
    def _build_assessment_prompt_with_foci(
        self,
        prompt: str,
        output: str,
        user_foci: List[Dict],
        max_foci: Optional[int]
    ) -> str:
        """Build assessment prompt using user-defined foci."""
        # Short excerpts only — do not ask the model to echo full spans back as JSON
        # (long prompt_section copies routinely truncate mid-string and break parsing).
        foci_lines = []
        for i, f in enumerate(user_foci):
            name = f.get('focus', 'Unknown')
            section = (f.get('prompt_section') or '').strip()
            if len(section) > 160:
                section = section[:157].rstrip() + '...'
            if section:
                foci_lines.append(f"{i+1}. Focus: {name}\n   Excerpt: {section}")
            else:
                foci_lines.append(f"{i+1}. Focus: {name}")
        foci_list_text = '\n'.join(foci_lines)

        # Foci excerpts + output are enough; pasting the full ORIGINAL PROMPT
        # encourages models to echo long spans into JSON and truncate.
        _ = prompt
        return f"""Assess how the LLM OUTPUT distributes attention across the USER-DEFINED FOCI.

USER-DEFINED FOCI (you must assess ALL of these; Excerpt is context only — do not copy it into your JSON):
{foci_list_text}

LLM OUTPUT:
{output}

TASK:
1. For EACH of the user-defined foci above, assess how much attention the output gives to it.
2. Assign points to each focus based on how much attention/emphasis the output gives to that focus.
3. CRITICAL: You must assess ALL {len(user_foci)} foci listed above. If a focus is not addressed, give it 0 points but still include it.
4. CRITICAL: The total of all points must equal exactly 100 points (not percentages, but points that sum to 100).
5. Provide a brief explanation for each score that references specific parts of the output.

Return your analysis as a JSON object with this EXACT structure (three keys per focus only):
{{
  "foci": [
    {{
      "focus": "The exact focus name from the user-defined list above",
      "score": 35.0,
      "explanation": "Brief explanation referencing the output (keep under 2 sentences)"
    }}
  ],
  "overall_summary": "A brief overall assessment of how the output distributes attention across the specified foci"
}}

CRITICAL REQUIREMENTS:
- You MUST include ALL {len(user_foci)} foci from the user-defined list
- Use the EXACT focus names provided above
- Each focus object may ONLY have: focus, score, explanation
- Do NOT include prompt_section, excerpt, quote, or any other keys
- Do NOT copy Excerpt text into the JSON
- Keep explanations short so the JSON response stays complete
- The sum of all scores MUST equal exactly 100.0 points
- If a focus is completely ignored, give it 0 points but still include it with an explanation
- Scores reflect the relative amount of attention/emphasis the output gives to each prompt component
"""

    def _build_assessment_prompt(
        self,
        prompt: str,
        output: str,
        max_foci: Optional[int]
    ) -> str:
        """Build the assessment prompt for the LLM."""
        max_foci_text = f"Identify up to {max_foci} distinct foci." if max_foci else "Identify all distinct foci."
        
        # Break prompt into sections for reference
        prompt_lines = prompt.strip().split('\n')
        prompt_sections = []
        current_section = []
        current_section_num = 0
        
        for line in prompt_lines:
            stripped = line.strip()
            # Detect section markers (numbered items, headers, etc.)
            if stripped and (stripped[0].isdigit() or stripped.startswith('#') or 
                           stripped.startswith('##') or stripped.isupper()):
                if current_section:
                    prompt_sections.append((current_section_num, '\n'.join(current_section)))
                current_section = [line]
                current_section_num += 1
            else:
                current_section.append(line)
        if current_section:
            prompt_sections.append((current_section_num, '\n'.join(current_section)))
        
        sections_text = ""
        if prompt_sections:
            sections_text = "\n\nPROMPT SECTIONS (for reference):\n"
            for i, (num, section) in enumerate(prompt_sections, 1):
                sections_text += f"\n[Section {i}]:\n{section}\n"
        
        return f"""Analyze the following prompt and output to assess focus distribution.

ORIGINAL PROMPT:
{prompt}
{sections_text}

LLM OUTPUT:
{output}

TASK:
1. FIRST: Anatomically break down the PROMPT itself into distinct structural foci. Each focus should be a specific, identifiable part of the prompt itself - such as:
   - A specific instruction or requirement stated in the prompt
   - A specific constraint or rule mentioned
   - A specific task or objective described
   - A specific format requirement
   - A specific section or paragraph with distinct content
   
   The foci should be based on the ACTUAL STRUCTURE AND CONTENT of the prompt, not on abstract concepts or sentiments.

2. For each focus, quote or reference the exact text from the prompt that defines it (e.g., quote the specific sentence or paragraph).

3. Then, assign points to each focus based on how much attention/emphasis the output gives to that specific part of the prompt. 
   - Points represent the relative amount of focus/attention the output dedicates to each prompt component
   - A focus that is heavily addressed in the output gets more points
   - A focus that is barely addressed or ignored gets fewer points

4. CRITICAL: The total of all points must equal exactly 100 points (not percentages, but points that sum to 100).

5. Provide a brief explanation for each score that:
   - References the specific part of the prompt this focus comes from
   - References specific parts of the output that address (or fail to address) this focus
   - Explains why this point allocation was given

{max_foci_text}

Return your analysis as a JSON object with this structure:
{{
  "foci": [
    {{
      "focus": "A specific structural component/requirement/instruction from the prompt itself (e.g., 'Provide first aid advice when appropriate')",
      "prompt_section": "A short quote from the prompt (under 120 characters) that identifies this focus",
      "score": 35.0,
      "explanation": "Brief explanation: (1) which part of the prompt this comes from, (2) how the output addresses it, (3) why this score was given"
    }}
  ],
  "overall_summary": "A brief overall assessment of how the output distributes attention across the prompt's structural components"
}}

CRITICAL REQUIREMENTS:
- The foci MUST be based on the actual structural components of the prompt itself, not on abstract concepts
- Keep prompt_section SHORT (under 120 characters). Do not paste long paragraphs — a brief identifying quote is enough
- Keep explanations short so the JSON response stays complete
- Each focus must quote or reference the exact text from the prompt that defines it
- The sum of all scores MUST equal exactly 100.0 points
- Scores reflect the relative amount of attention/emphasis the output gives to each prompt component
- Consider both explicit mentions and implicit coverage in the output
- Ensure all major structural components of the prompt are represented in the foci
- Points represent relative attention/emphasis given to each prompt component, not quality of response
"""


def assess_focus(
    prompt: str,
    output: Optional[str] = None,
    api_key: Optional[str] = None,
    model: str = "gpt-4o-mini",
    agent_model: Optional[str] = None,
    max_foci: Optional[int] = None,
    generate_output: bool = False
) -> FocusAssessment:
    """
    Convenience function to assess focus distribution.
    
    Args:
        prompt: The original prompt/input
        output: The LLM output to assess (if None and generate_output=True, will generate it)
        api_key: OpenAI API key (optional, can use environment variable)
        model: Model to use for assessment
        agent_model: Model to use for generating output (if None, uses model)
        max_foci: Maximum number of foci to identify
        generate_output: If True and output is None, generate output using an agent
    
    Returns:
        FocusAssessment object
    """
    assessor = FocalAssessor(api_key=api_key, model=model, agent_model=agent_model)
    
    # Generate output if needed
    if output is None and generate_output:
        print("Generating output using agent...")
        output = assessor.generate_output(prompt)
        print(f"\nGenerated Output:\n{output}\n")
        print("="*60)
    
    if output is None:
        raise ValueError("Either provide an output or set generate_output=True")
    
    return assessor.assess(prompt, output, max_foci)


if __name__ == "__main__":
    # Example usage with agent-generated output
    example_prompt = """
    Write a comprehensive analysis of climate change that includes:
    1. The scientific evidence for climate change
    2. Economic impacts on different sectors
    3. Policy recommendations for governments
    4. Individual actions people can take
    """
    
    print("Example: Using agent to generate output and assess focus")
    print("\nPrompt:", example_prompt)
    print("\n" + "="*60)
    
    # Generate output using agent and assess
    try:
        assessment = assess_focus(
            prompt=example_prompt,
            generate_output=True,  # Use agent to generate output
            model="gpt-4o-mini"
        )
        assessment.print_summary()
    except Exception as e:
        print(f"\nError: {e}")
        print("Please set your OPENAI_API_KEY environment variable to run this example.")

