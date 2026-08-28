#!/usr/bin/env python3
"""
Task / quality evaluation for model outputs against user criteria.

This is explicit quality & task-fit assessment — NOT behavioral-difference
(compare baseline vs ablated sets) and NOT reported-focus self-assessment.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Mapping, Optional, Sequence

from utils.gateway_chat import chat_completion as gateway_chat_completion
from utils.llm_json import parse_quality_eval_json

MAX_OUTPUT_CHARS = 4000
MAX_CRITERIA_CHARS = 3000
MAX_CONTEXT_CHARS = 2000
MAX_PROMPT_CHARS = 2500
MAX_CRITERIA_BREAKDOWN = 5
MAX_STRENGTHS_WEAKNESSES = 2
MAX_NOTE_CHARS = 60
QUALITY_EVAL_BATCH_SIZE = 4
# Soft guard against accidental huge runs (100+ LLM batches). Batching handles any size below this.
ABSOLUTE_MAX_OUTPUTS = 500

QUALITY_EVAL_RETRY_SUFFIX = (
    '\n\nCRITICAL RETRY: Your previous JSON was invalid or truncated. '
    'Return ONLY compact JSON with ALL outputs scored:\n'
    '{"evaluations":[{"label":"exact label","overall_score":0,'
    '"meets_primary_criterion":true,'
    '"criterion_breakdown":[{"name":"short","score":0,"met":true,"notes":"brief"}],'
    '"strengths":["one"],"weaknesses":["one"],"summary":"one sentence"}],'
    '"comparative_notes":""}\n'
    f'Rules: max {MAX_CRITERIA_BREAKDOWN} criterion_breakdown items; notes under '
    f'{MAX_NOTE_CHARS} chars; max {MAX_STRENGTHS_WEAKNESSES} strengths and '
    f'{MAX_STRENGTHS_WEAKNESSES} weaknesses; do not quote output text.'
)

QUALITY_EVAL_SYSTEM = (
    'You are an expert task-quality evaluator. You score how well each model '
    'output meets the user\'s evaluation criteria. You judge task fit, '
    'instruction following, correctness, completeness, and tone — not '
    'embedding similarity or whether two outputs differ. Return valid JSON only. '
    'Keep JSON compact: short notes, no quoted output text, no extra keys.'
)


def quality_eval_max_tokens(n_outputs: int) -> int:
    """Scale completion budget so multi-output evaluations are less likely to truncate."""
    return min(16384, max(4096, 1024 + n_outputs * 768))


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
    include_comparative_notes: bool = True,
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
{'You may add brief comparative_notes if multiple outputs are present.' if include_comparative_notes else 'Set comparative_notes to an empty string for this batch.'}

JSON compactness (required):
- At most {MAX_CRITERIA_BREAKDOWN} criterion_breakdown entries per output
- Notes under {MAX_NOTE_CHARS} characters; no quoting output text in JSON
- At most {MAX_STRENGTHS_WEAKNESSES} strengths and {MAX_STRENGTHS_WEAKNESSES} weaknesses
- summary: one sentence only
- Score every output listed above

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
  "comparative_notes": "{'optional: which output best met criteria and why' if include_comparative_notes else ''}"
}}
"""


def sample_outputs_stratified(
    outputs: Sequence[Mapping[str, Any]],
    sample_fraction: float,
    *,
    seed: int = 0,
) -> List[Dict[str, str]]:
    """
    Stratified sample across baseline and each ablated focus group.

    Keeps at least one item per non-empty group when fraction < 1.
    ``sample_fraction`` in (0, 1]; 1 returns all outputs unchanged.
    """
    if sample_fraction >= 1.0:
        return [
            {'label': str(o.get('label') or ''), 'text': str(o.get('text') or '')}
            for o in outputs
            if str(o.get('text') or '').strip()
        ]
    if sample_fraction <= 0:
        raise ValueError('sample_fraction must be greater than 0')

    rng = random.Random(seed)
    normalized: List[Dict[str, Any]] = []
    for i, item in enumerate(outputs):
        if not isinstance(item, Mapping):
            continue
        text = str(item.get('text') or '').strip()
        if not text:
            continue
        normalized.append({
            'label': str(item.get('label') or f'Output {i + 1}').strip(),
            'text': text,
            'group': item.get('group'),
            'focus': item.get('focus'),
        })

    def _pick(group_items: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        if not group_items:
            return []
        n = max(1, round(len(group_items) * sample_fraction))
        n = min(n, len(group_items))
        chosen = group_items if n >= len(group_items) else rng.sample(group_items, n)
        return [{'label': g['label'], 'text': g['text']} for g in chosen]

    baselines = [o for o in normalized if o.get('group') == 'baseline']
    ablated = [o for o in normalized if o.get('group') == 'ablated']
    other = [o for o in normalized if o.get('group') not in ('baseline', 'ablated')]

    sampled: List[Dict[str, str]] = []
    sampled.extend(_pick(baselines))

    by_focus: Dict[str, List[Dict[str, Any]]] = {}
    for row in ablated:
        key = str(row.get('focus') or row.get('label') or 'ablated')
        by_focus.setdefault(key, []).append(row)
    for rows in by_focus.values():
        sampled.extend(_pick(rows))
    sampled.extend(_pick(other))
    return sampled


def normalize_output_items(
    outputs: Sequence[Mapping[str, Any]],
    *,
    max_outputs: int = ABSOLUTE_MAX_OUTPUTS,
) -> List[Dict[str, str]]:
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
    if len(out) > max_outputs:
        raise ValueError(
            f'Too many outputs ({len(out)}). Maximum is {max_outputs} per evaluation run. '
            'Use a lower sample percentage or reduce Experiment B sample counts.'
        )
    return out


def _merge_usage(
    base: Optional[Dict[str, Any]],
    extra: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not extra:
        return base
    if not base:
        return dict(extra)
    merged = dict(base)
    for key, value in (extra or {}).items():
        try:
            merged[key] = int(merged.get(key) or 0) + int(value or 0)
        except (TypeError, ValueError):
            merged[key] = value
    return merged


def _normalize_evaluation_rows(
    parsed: Sequence[Mapping[str, Any]],
    by_label: Mapping[str, Mapping[str, str]],
) -> List[Dict[str, Any]]:
    evaluations: List[Dict[str, Any]] = []
    seen = set()
    for row in parsed:
        if not isinstance(row, dict):
            continue
        label = str(row.get('label') or '').strip()
        if label not in by_label:
            for key in by_label:
                if (
                    key.lower() == label.lower()
                    or key.startswith(label)
                    or label.startswith(key)
                ):
                    label = key
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
    return evaluations


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

    def _evaluate_output_batch(
        self,
        *,
        eval_criteria: str,
        items: Sequence[Mapping[str, str]],
        task_context: str,
        prompt: str,
        temperature: float,
        include_comparative_notes: bool,
    ) -> Dict[str, Any]:
        user_prompt = build_quality_evaluation_prompt(
            eval_criteria=eval_criteria,
            outputs=items,
            task_context=task_context,
            prompt=prompt,
            include_comparative_notes=include_comparative_notes,
        )
        max_tokens = quality_eval_max_tokens(len(items))

        def _chat(user_content: str) -> Dict[str, Any]:
            return gateway_chat_completion(
                self.provider,
                self.model,
                self.provider_name,
                [
                    {'role': 'system', 'content': QUALITY_EVAL_SYSTEM},
                    {'role': 'user', 'content': user_content},
                ],
                temperature=temperature,
                response_format={'type': 'json_object'},
                max_tokens=max_tokens,
            )

        response = _chat(user_prompt)
        usage = response.get('usage')
        raw_content = response.get('content') or ''
        try:
            raw = parse_quality_eval_json(raw_content)
        except ValueError:
            retry_response = _chat(user_prompt + QUALITY_EVAL_RETRY_SUFFIX)
            usage = _merge_usage(usage, retry_response.get('usage'))
            response = retry_response
            raw = parse_quality_eval_json(response.get('content') or '')
        if not isinstance(raw, dict):
            raise ValueError('Evaluator did not return a JSON object')

        by_label = {it['label']: it for it in items}
        parsed = raw.get('evaluations') or []
        if not isinstance(parsed, list):
            parsed = []
        evaluations = _normalize_evaluation_rows(parsed, by_label)
        return {
            'evaluations': evaluations,
            'comparative_notes': str(raw.get('comparative_notes') or ''),
            'usage': usage,
        }

    def evaluate_outputs(
        self,
        *,
        eval_criteria: str,
        outputs: Sequence[Mapping[str, Any]],
        task_context: str = '',
        prompt: str = '',
        temperature: float = 0.2,
        sample_fraction: float = 1.0,
        sample_seed: int = 0,
    ) -> Dict[str, Any]:
        """
        Score each output against eval_criteria.

        Returns evaluations aligned to input labels plus usage metadata.
        """
        if sample_fraction < 1.0:
            items = sample_outputs_stratified(
                outputs, sample_fraction, seed=sample_seed
            )
            items = normalize_output_items(items)
        else:
            items = normalize_output_items(outputs)
        n_total = len([
            o for o in outputs
            if isinstance(o, Mapping) and str(o.get('text') or '').strip()
        ])
        if not (eval_criteria or '').strip():
            raise ValueError('Evaluation criteria are required')

        all_evaluations: List[Dict[str, Any]] = []
        comparative_notes_parts: List[str] = []
        usage: Optional[Dict[str, Any]] = None
        batches = [
            items[i : i + QUALITY_EVAL_BATCH_SIZE]
            for i in range(0, len(items), QUALITY_EVAL_BATCH_SIZE)
        ]

        for batch_index, batch in enumerate(batches):
            batch_result = self._evaluate_output_batch(
                eval_criteria=eval_criteria,
                items=batch,
                task_context=task_context,
                prompt=prompt,
                temperature=temperature,
                include_comparative_notes=(batch_index == len(batches) - 1),
            )
            usage = _merge_usage(usage, batch_result.get('usage'))
            all_evaluations.extend(batch_result.get('evaluations') or [])
            note = (batch_result.get('comparative_notes') or '').strip()
            if note:
                comparative_notes_parts.append(note)

        by_label = {row['label']: row for row in all_evaluations}
        ordered_evaluations = [
            by_label[item['label']]
            for item in items
            if item['label'] in by_label
        ]

        return {
            'evaluations': ordered_evaluations,
            'comparative_notes': ' '.join(comparative_notes_parts).strip(),
            'n_outputs': len(items),
            'n_outputs_total': n_total,
            'n_outputs_evaluated': len(items),
            'sample_fraction': float(sample_fraction) if sample_fraction < 1.0 else 1.0,
            'n_batches': len(batches),
            'evaluation_type': 'task_quality',
            'explicitly_not_behavioral_difference': True,
            'usage': usage,
        }
