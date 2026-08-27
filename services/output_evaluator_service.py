#!/usr/bin/env python3
"""
Task / quality evaluation for model outputs against user criteria.

This is explicit quality & task-fit assessment — NOT behavioral-difference
(compare baseline vs ablated sets) and NOT reported-focus self-assessment.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Mapping, Optional, Sequence

from utils.gateway_chat import chat_completion as gateway_chat_completion
from utils.llm_json import parse_llm_json

MAX_OUTPUTS = 12
MAX_OUTPUT_CHARS = 4000
MAX_CRITERIA_CHARS = 3000
MAX_CONTEXT_CHARS = 2000
MAX_PROMPT_CHARS = 2500

QUALITY_EVAL_SYSTEM = (
    'You are an expert task-quality evaluator. You score how well each model '
    'output meets the user\'s evaluation criteria. You judge task fit, '
    'instruction following, correctness, completeness, and tone — not '
    'embedding similarity or whether two outputs differ. Return valid JSON only.'
)


def _clip(text: str, limit: int) -> str:
    t = (text or '').strip()
    if len(t) <= limit:
        return t
    return t[: limit - 3].rstrip() + '...'


def build_quality_evaluation_prompt(
    *,
    eval_criteria: str,
    outputs: Sequence[Mapping[str, Any]],
    task_context: str = '',
    prompt: str = '',
) -> str:
    """Build user message for criterion-based output evaluation."""
    blocks: List[str] = []
    for i, item in enumerate(outputs):
        label = str(item.get('label') or f'Output {i + 1}')
        text = _clip(str(item.get('text') or ''), MAX_OUTPUT_CHARS)
        blocks.append(f'--- {label} ---\n{text or "(empty)"}')

    criteria = _clip(eval_criteria, MAX_CRITERIA_CHARS)
    ctx = _clip(task_context, MAX_CONTEXT_CHARS)
    prompt_excerpt = _clip(prompt, MAX_PROMPT_CHARS)

    return f"""Evaluate each OUTPUT below against the EVALUATION CRITERIA.

EVALUATION CRITERIA (what "good" means for this task):
{criteria or '(No criteria provided — use general helpfulness, accuracy, and instruction-following.)'}

TASK / USER CONTEXT (if any):
{ctx or '(not provided)'}

SYSTEM PROMPT CONTEXT (excerpt; outputs should comply with this):
{prompt_excerpt or '(not provided)'}

OUTPUTS TO SCORE ({len(outputs)}):
{chr(10).join(blocks)}

For EACH output, return an evaluation object. Score overall quality 0–100.
Break down against the criteria where possible (0–5 per sub-criterion).
Do NOT compare outputs for "difference only" — judge each on task merit.
You may add brief comparative_notes if multiple outputs are present.

Return JSON:
{{
  "evaluations": [
    {{
      "label": "exact label from above",
      "overall_score": 85,
      "meets_primary_criterion": true,
      "criterion_breakdown": [
        {{"name": "short criterion name", "score": 4, "met": true, "notes": "..."}}
      ],
      "strengths": ["..."],
      "weaknesses": ["..."],
      "summary": "1-2 sentences"
    }}
  ],
  "comparative_notes": "optional: which output best met criteria and why"
}}
"""


def normalize_output_items(outputs: Sequence[Mapping[str, Any]]) -> List[Dict[str, str]]:
    """Validate and trim the outputs list."""
    if not outputs:
        raise ValueError('At least one output is required')
    out: List[Dict[str, str]] = []
    for i, item in enumerate(outputs):
        if not isinstance(item, Mapping):
            continue
        text = str(item.get('text') or '').strip()
        if not text:
            continue
        label = str(item.get('label') or f'Output {i + 1}').strip() or f'Output {i + 1}'
        out.append({'label': label, 'text': text})
    if not out:
        raise ValueError('All outputs were empty')
    if len(out) > MAX_OUTPUTS:
        raise ValueError(
            f'Too many outputs ({len(out)}). Maximum is {MAX_OUTPUTS} per evaluation.'
        )
    return out


class OutputQualityEvaluator:
    """LLM judge for task/quality against user criteria."""

    def __init__(
        self,
        provider,
        model: str,
        provider_name: Optional[str] = None,
    ):
        self.provider = provider
        self.model = model
        self.provider_name = provider_name or 'openai'

    def evaluate_outputs(
        self,
        *,
        eval_criteria: str,
        outputs: Sequence[Mapping[str, Any]],
        task_context: str = '',
        prompt: str = '',
        temperature: float = 0.2,
    ) -> Dict[str, Any]:
        """
        Score each output against eval_criteria.

        Returns evaluations aligned to input labels plus usage metadata.
        """
        items = normalize_output_items(outputs)
        if not (eval_criteria or '').strip():
            raise ValueError('Evaluation criteria are required')

        user_prompt = build_quality_evaluation_prompt(
            eval_criteria=eval_criteria,
            outputs=items,
            task_context=task_context,
            prompt=prompt,
        )
        response = gateway_chat_completion(
            self.provider,
            self.model,
            self.provider_name,
            [
                {'role': 'system', 'content': QUALITY_EVAL_SYSTEM},
                {'role': 'user', 'content': user_prompt},
            ],
            temperature=temperature,
            response_format={'type': 'json_object'},
            max_tokens=4096,
        )
        raw = parse_llm_json(response.get('content') or '')
        if not isinstance(raw, dict):
            raise ValueError('Evaluator did not return a JSON object')

        by_label = {it['label']: it for it in items}
        parsed = raw.get('evaluations') or []
        if not isinstance(parsed, list):
            parsed = []

        evaluations: List[Dict[str, Any]] = []
        seen = set()
        for row in parsed:
            if not isinstance(row, dict):
                continue
            label = str(row.get('label') or '').strip()
            if label not in by_label:
                # Fuzzy match by prefix
                for k in by_label:
                    if k.lower() == label.lower() or k.startswith(label) or label.startswith(k):
                        label = k
                        break
            if label not in by_label or label in seen:
                continue
            seen.add(label)
            try:
                overall = float(row.get('overall_score', 0))
            except (TypeError, ValueError):
                overall = 0.0
            overall = max(0.0, min(100.0, overall))
            evaluations.append({
                'label': label,
                'overall_score': overall,
                'meets_primary_criterion': bool(row.get('meets_primary_criterion')),
                'criterion_breakdown': row.get('criterion_breakdown') or [],
                'strengths': row.get('strengths') or [],
                'weaknesses': row.get('weaknesses') or [],
                'summary': str(row.get('summary') or ''),
            })

        # Ensure every submitted output gets a row (model may omit some)
        for label in by_label:
            if label not in seen:
                evaluations.append({
                    'label': label,
                    'overall_score': None,
                    'meets_primary_criterion': None,
                    'criterion_breakdown': [],
                    'strengths': [],
                    'weaknesses': [],
                    'summary': 'Not scored in model response.',
                })

        return {
            'evaluations': evaluations,
            'comparative_notes': str(raw.get('comparative_notes') or ''),
            'n_outputs': len(items),
            'evaluation_type': 'task_quality',
            'explicitly_not_behavioral_difference': True,
            'usage': response.get('usage'),
        }
