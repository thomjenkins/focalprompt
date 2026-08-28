#!/usr/bin/env python3
"""
User-defined behavioural criterion judge for generated outputs.

Structured LLM classification — not ground truth and not a replacement for
embedding-based perturbation tests.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from utils.gateway_chat import chat_completion as gateway_chat_completion
from utils.llm_json import parse_llm_json

VALID_CLASSIFICATIONS = ('COMPLIES', 'AMBIGUOUS', 'VIOLATES')

JUDGE_SYSTEM = (
    'You are a behavioural criterion judge. Given a user criterion and a model '
    'output, classify whether the output complies. Return valid JSON only. '
    'You are not ground truth — you provide a structured rubric-based judgment.'
)


def build_behavioral_criterion_prompt(
    criterion: str,
    output_text: str,
    *,
    task_context: str = '',
) -> str:
    return f"""Classify this OUTPUT against the BEHAVIOURAL CRITERION.

CRITERION:
{criterion or '(none)'}

TASK CONTEXT (optional):
{task_context or '(none)'}

OUTPUT:
{output_text}

Return JSON:
{{
  "classification": "COMPLIES" | "AMBIGUOUS" | "VIOLATES",
  "score": 0-100,
  "rationale": "one or two sentences"
}}
"""


def normalize_judgment(raw: Mapping[str, Any]) -> Dict[str, Any]:
    classification = str(raw.get('classification') or 'AMBIGUOUS').upper()
    if classification not in VALID_CLASSIFICATIONS:
        classification = 'AMBIGUOUS'
    try:
        score = float(raw.get('score', 0))
    except (TypeError, ValueError):
        score = 0.0
    score = max(0.0, min(100.0, score))
    return {
        'classification': classification,
        'score': score,
        'rationale': str(raw.get('rationale') or ''),
    }


class BehavioralCriterionJudge:
    """LLM judge for a single user-defined behavioural criterion."""

    def __init__(self, provider, model: str, provider_name: Optional[str] = None):
        self.provider = provider
        self.model = model
        self.provider_name = provider_name or 'openai'

    def judge_output(
        self,
        *,
        criterion: str,
        output_text: str,
        task_context: str = '',
        temperature: float = 0.2,
    ) -> Dict[str, Any]:
        if not (criterion or '').strip():
            raise ValueError('behavioral criterion is required')
        if not (output_text or '').strip():
            raise ValueError('output_text is required')
        response = gateway_chat_completion(
            self.provider,
            self.model,
            self.provider_name,
            [
                {'role': 'system', 'content': JUDGE_SYSTEM},
                {
                    'role': 'user',
                    'content': build_behavioral_criterion_prompt(
                        criterion, output_text, task_context=task_context
                    ),
                },
            ],
            temperature=temperature,
            response_format={'type': 'json_object'},
            max_tokens=512,
        )
        parsed = parse_llm_json(response.get('content') or '')
        if not isinstance(parsed, dict):
            raise ValueError('Judge did not return a JSON object')
        judgment = normalize_judgment(parsed)
        judgment['usage'] = response.get('usage')
        judgment['disclaimer'] = 'LLM behavioral criterion judgment — not ground truth.'
        return judgment

    def judge_many(
        self,
        *,
        criterion: str,
        outputs: Sequence[str],
        task_context: str = '',
        temperature: float = 0.2,
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        total_usage: Dict[str, int] = {}
        for i, text in enumerate(outputs):
            row = self.judge_output(
                criterion=criterion,
                output_text=str(text),
                task_context=task_context,
                temperature=temperature,
            )
            usage = row.pop('usage', None) or {}
            for k, v in usage.items():
                try:
                    total_usage[k] = int(total_usage.get(k) or 0) + int(v or 0)
                except (TypeError, ValueError):
                    pass
            results.append({'sample_index': i, **row})
        return results
