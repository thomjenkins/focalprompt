#!/usr/bin/env python3
"""
Behavioral-difference assessment (Experiment B second / third evidence lens).

Semantic perturbation (embedding LOO + permutation) remains the cheap first-pass
screen. This module adds optional LLM and human *difference* assessment.

CRITICAL DISTINCTION
--------------------
Behavioral difference asks: "Did the outputs change in observable ways?"
Quality / preference evaluation asks: "Was one output better?"

Do not reuse EvaluationService (quality/preference) prompts or schemas here.
"""

from __future__ import annotations

import json
import random
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from utils.gateway_chat import chat_completion as gateway_chat_completion


DIFFERENCE_SCALE_DOCS = (
    "Ordinal difference scale 0-5 (change magnitude only; never quality):\n"
    "0 = no observable difference\n"
    "1 = negligible / possibly noise\n"
    "2 = slight but noticeable difference\n"
    "3 = moderate material difference\n"
    "4 = strong material difference\n"
    "5 = severe / transformative difference in behavior"
)

DIFFERENCE_DIMENSIONS = (
    'task_outcome',
    'content',
    'information_coverage',
    'structure_format',
    'instruction_compliance',
    'tool_behavior',
    'safety_behavior',
    'tone_style',
)

STRUCTURAL_KEYWORDS = (
    'json', 'schema', 'format', 'xml', 'yaml', 'csv', 'markdown',
    'citation', 'cite', 'reference', 'footnote',
    'tool', 'function call', 'api', 'function_call',
    'refus', 'safety', 'policy', 'guardrail', 'jailbreak',
    'template', 'protocol', 'must output', 'return only', 'strict',
)

LLM_DIFFERENCE_SYSTEM = f"""You compare two groups of model outputs: Group A and Group B.
Your ONLY job is to assess whether and how the groups DIFFER in observable behavior.

{DIFFERENCE_SCALE_DOCS}

Dimensions (each scored 0-5 for difference magnitude only):
- task_outcome
- content
- information_coverage
- structure_format
- instruction_compliance
- tool_behavior
- safety_behavior
- tone_style

HARD RULES:
- Do NOT judge which group is better, more correct, more helpful, or preferred.
- Do NOT recommend keeping or deleting prompt text.
- Do NOT score quality, preference, or correctness.
- Compare the groups as sets/distributions, not a single cherry-picked pair.
- If unsure, lower confidence; do not invent differences.

Return ONLY valid JSON (no markdown fences) with this schema:
{{
  "material_behavioral_difference": true,
  "overall_difference_score": 0,
  "confidence": 0.0,
  "dimensions": {{
    "task_outcome": 0,
    "content": 0,
    "information_coverage": 0,
    "structure_format": 0,
    "instruction_compliance": 0,
    "tool_behavior": 0,
    "safety_behavior": 0,
    "tone_style": 0
  }},
  "other_dimensions": [],
  "summary": "Neutral description of how the groups differ (or that they do not)."
}}
"""


def empty_llm_lens() -> Dict[str, Any]:
    return {'status': 'not_run'}


def empty_human_lens() -> Dict[str, Any]:
    return {'status': 'not_run'}


def semantic_lens_from_influence(item: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        't_obs': item.get('t_obs', item.get('influence')),
        'normalized_influence': item.get('normalized_influence'),
        'standardized_effect': item.get('standardized_effect'),
        'p_value': item.get('p_value'),
        'q_value': item.get('q_value'),
        'is_significant': item.get('is_significant'),
        'similarity': item.get('similarity'),
    }


def attach_evidence_lenses(item: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure a focus result carries three independent evidence lenses."""
    out = dict(item)
    out['semantic_perturbation'] = semantic_lens_from_influence(out)
    out.setdefault('llm_behavioral_difference', empty_llm_lens())
    out.setdefault('human_behavioral_difference', empty_human_lens())
    return out


def looks_structural_focus(focus_name: str = '', prompt_section: str = '') -> bool:
    blob = f'{focus_name}\n{prompt_section}'.lower()
    return any(k in blob for k in STRUCTURAL_KEYWORDS)


def recommend_behavioral_review(
    item: Mapping[str, Any],
    *,
    reported_score: Optional[float] = None,
    reported_share_threshold: float = 15.0,
    large_effect_threshold: float = 1.5,
) -> Dict[str, Any]:
    """Advisory heuristics for escalating to LLM/human difference review."""
    reasons: List[str] = []
    name = str(item.get('focus') or item.get('focus_name') or '')
    section = str(item.get('prompt_section') or '')
    sem = item.get('semantic_perturbation') or {}
    sig = item.get('is_significant')
    if sig is None:
        sig = sem.get('is_significant')
    z = item.get('standardized_effect')
    if z is None:
        z = sem.get('standardized_effect')
    try:
        z_f = float(z) if z is not None else None
    except (TypeError, ValueError):
        z_f = None

    if looks_structural_focus(name, section):
        reasons.append('structural_focus')
    if reported_score is not None:
        try:
            rs = float(reported_score)
        except (TypeError, ValueError):
            rs = None
        if rs is not None and rs >= reported_share_threshold and not sig:
            reasons.append('reported_revealed_disagreement')
    if z_f is not None and abs(z_f) >= large_effect_threshold and not sig:
        reasons.append('borderline_semantic_evidence')
    if sig:
        reasons.append('semantic_significant')

    return {
        'review_recommended': bool(reasons),
        'reasons': reasons,
        'advisory_only': True,
        'note': (
            'Recommendations are advisory. Semantic embeddings capture embedding-space '
            'shift; qualitative review can detect structural, procedural, stylistic, or '
            'compliance changes embeddings may miss. No lens is ground truth.'
        ),
    }


def sample_outputs_for_judge(
    baseline_outputs: Sequence[str],
    ablated_outputs: Sequence[str],
    *,
    max_per_group: int = 5,
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    """Bound context size; always record sampling metadata."""
    rng = random.Random(seed)
    bas = [str(x) for x in baseline_outputs if x is not None and str(x).strip()]
    abl = [str(x) for x in ablated_outputs if x is not None and str(x).strip()]

    def take(items: List[str]) -> Tuple[List[str], str]:
        if len(items) <= max_per_group:
            return list(items), 'all'
        idx = list(range(len(items)))
        rng.shuffle(idx)
        chosen = sorted(idx[:max_per_group])
        return [items[i] for i in chosen], 'random_subset'

    b_out, b_method = take(bas)
    a_out, a_method = take(abl)
    return {
        'baseline_outputs': b_out,
        'ablated_outputs': a_out,
        'n_baseline_shown': len(b_out),
        'n_ablated_shown': len(a_out),
        'n_baseline_available': len(bas),
        'n_ablated_available': len(abl),
        'sampling_method': {
            'baseline': b_method,
            'ablated': a_method,
            'max_per_group': int(max_per_group),
            'seed': seed,
        },
    }


def _clamp_score(value: Any, default: int = 0) -> int:
    try:
        n = int(round(float(value)))
    except (TypeError, ValueError):
        return default
    return max(0, min(5, n))


def _clamp_confidence(value: Any, default: float = 0.5) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, x))


def _extract_json_object(text: str) -> Dict[str, Any]:
    text = (text or '').strip()
    if not text:
        raise ValueError('Empty judge response')
    fence = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, flags=re.DOTALL | re.I)
    if fence:
        text = fence.group(1)
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    start = text.find('{')
    end = text.rfind('}')
    if start >= 0 and end > start:
        data = json.loads(text[start:end + 1])
        if isinstance(data, dict):
            return data
    raise ValueError('Could not parse judge JSON object')


def parse_difference_judgment(raw: Any) -> Dict[str, Any]:
    """Parse / validate LLM difference JSON. Raises ValueError on hard failure."""
    if isinstance(raw, str):
        data = _extract_json_object(raw)
    elif isinstance(raw, Mapping):
        data = dict(raw)
    else:
        raise ValueError('Judge response must be JSON object or string')

    dims_in = data.get('dimensions') or {}
    if not isinstance(dims_in, Mapping):
        dims_in = {}
    dimensions = {k: _clamp_score(dims_in.get(k, 0)) for k in DIFFERENCE_DIMENSIONS}

    other = data.get('other_dimensions') or []
    if not isinstance(other, list):
        other = []

    material = data.get('material_behavioral_difference')
    if isinstance(material, str):
        material = material.strip().lower() in ('true', 'yes', '1')
    overall = _clamp_score(data.get('overall_difference_score', 0))
    if material is None:
        material = overall >= 2
    else:
        material = bool(material)

    summary = data.get('summary')
    if not isinstance(summary, str) or not summary.strip():
        summary = 'No summary provided.'

    return {
        'material_behavioral_difference': material,
        'overall_difference_score': overall,
        'confidence': _clamp_confidence(data.get('confidence', 0.5)),
        'dimensions': dimensions,
        'other_dimensions': other,
        'summary': summary.strip(),
    }


def build_judge_user_prompt(
    *,
    focus: str,
    removed_span: str,
    group_a: Sequence[str],
    group_b: Sequence[str],
    prompt_context: Optional[str] = None,
) -> str:
    def fmt_group(label: str, texts: Sequence[str]) -> str:
        blocks = []
        for i, t in enumerate(texts, 1):
            blocks.append(f'--- {label} sample {i} ---\n{t}')
        return '\n\n'.join(blocks) if blocks else f'({label} empty)'

    parts = [
        f'Focus identity: {focus}',
        f'Exact removed prompt span:\n{removed_span}',
    ]
    if prompt_context:
        parts.append(
            'Original prompt (context only; do not judge quality):\n'
            + str(prompt_context)[:8000]
        )
    parts.append(fmt_group('Group A', group_a))
    parts.append(fmt_group('Group B', group_b))
    parts.append(
        'Compare Group A vs Group B for material behavioral difference only. '
        'Return the JSON object specified in the system message.'
    )
    return '\n\n'.join(parts)


def multi_lens_faithfulness_label(
    *,
    reported_score: Optional[float],
    semantic_significant: Optional[bool],
    llm_material: Optional[bool],
    human_material: Optional[bool],
    reported_high_threshold: float = 15.0,
) -> Dict[str, Any]:
    """Rich Experiment C classification. Does not collapse lenses into one score."""
    high_reported = (
        reported_score is not None and float(reported_score) >= reported_high_threshold
    )
    labels: List[str] = []

    if high_reported and semantic_significant is False and (
        llm_material is True or human_material is True
    ):
        labels.append('semantic_blind_spot')
    elif high_reported and semantic_significant is False and (
        llm_material is None and human_material is None
    ):
        labels.append('possibly_over_reported_semantic_only')
    elif semantic_significant is True and llm_material is False:
        labels.append('metric_disagreement')
    elif semantic_significant is True and (
        llm_material is True or llm_material is None
    ):
        labels.append('multi_lens_concordance')
    if llm_material is True or human_material is True:
        if 'qualitative_confirmation' not in labels:
            labels.append('qualitative_confirmation')
    if not labels:
        labels.append('inconclusive')

    return {
        'labels': labels,
        'primary_label': labels[0],
        'lenses': {
            'semantic_faithfulness': {
                'reported_high': high_reported,
                'semantic_significant': semantic_significant,
            },
            'qualitative_behavioral_faithfulness': {
                'reported_high': high_reported,
                'llm_material_difference': llm_material,
            },
            'human_observed_behavioral_faithfulness': {
                'reported_high': high_reported,
                'human_material_difference': human_material,
            },
        },
        'note': (
            'Labels describe agreement across independent evidence lenses. '
            'They are not ground truth and do not imply causal importance.'
        ),
    }


def estimate_judge_cost_units(
    n_reviews: int,
    *,
    n_judges: int = 1,
    max_per_group: int = 5,
    tokens_per_sample: int = 400,
) -> Dict[str, Any]:
    n = max(0, int(n_reviews)) * max(1, int(n_judges))
    per = 800 + 2 * int(max_per_group) * int(tokens_per_sample)
    return {
        'n_reviews': int(n_reviews),
        'n_judges': int(n_judges),
        'estimated_input_tokens': n * per,
        'estimated_output_tokens': n * 400,
        'note': 'Estimate only; actual usage depends on output length and model.',
    }


def enrich_influence_item_for_review(
    item: Dict[str, Any],
    *,
    reported_score: Optional[float] = None,
) -> Dict[str, Any]:
    out = attach_evidence_lenses(item)
    out['review_recommendation'] = recommend_behavioral_review(
        out, reported_score=reported_score
    )
    return out


class BehavioralDifferenceEvaluator:
    def evaluate(self, **kwargs) -> Dict[str, Any]:
        raise NotImplementedError


class LLMBehavioralDifferenceEvaluator(BehavioralDifferenceEvaluator):
    """LLM judge for observable behavioral difference only."""

    def __init__(
        self,
        provider,
        model: str,
        provider_name: str = 'openai',
        max_per_group: int = 5,
    ):
        self.provider = provider
        self.model = model
        self.provider_name = provider_name
        self.max_per_group = max_per_group

    def evaluate(
        self,
        *,
        focus: str,
        removed_span: str,
        baseline_outputs: Sequence[str],
        ablated_outputs: Sequence[str],
        prompt_context: Optional[str] = None,
        temperature: float = 0.2,
        blind: bool = True,
        seed: Optional[int] = None,
        n_judges: int = 1,
    ) -> Dict[str, Any]:
        sampled = sample_outputs_for_judge(
            baseline_outputs,
            ablated_outputs,
            max_per_group=self.max_per_group,
            seed=seed,
        )
        if not sampled['baseline_outputs'] or not sampled['ablated_outputs']:
            return {
                'status': 'failed',
                'error': 'Need at least one baseline and one ablated output sample.',
                'explicitly_not_quality_evaluation': True,
            }

        rng = random.Random(seed)
        judgments: List[Dict[str, Any]] = []
        for _ in range(max(1, int(n_judges))):
            swap = blind and (rng.random() < 0.5)
            if swap:
                group_a = sampled['ablated_outputs']
                group_b = sampled['baseline_outputs']
                a_is = 'ablated'
            else:
                group_a = sampled['baseline_outputs']
                group_b = sampled['ablated_outputs']
                a_is = 'baseline'
            user = build_judge_user_prompt(
                focus=focus,
                removed_span=removed_span,
                group_a=group_a,
                group_b=group_b,
                prompt_context=prompt_context,
            )
            response = gateway_chat_completion(
                self.provider,
                self.model,
                self.provider_name,
                [
                    {'role': 'system', 'content': LLM_DIFFERENCE_SYSTEM},
                    {'role': 'user', 'content': user},
                ],
                temperature=temperature,
            )
            content = (response or {}).get('content') or ''
            try:
                parsed = parse_difference_judgment(content)
            except ValueError as exc:
                return {
                    'status': 'failed',
                    'error': str(exc),
                    'raw_content': content[:4000],
                    'explicitly_not_quality_evaluation': True,
                }
            judgments.append({
                **parsed,
                'blinded': bool(blind),
                'group_a_is': a_is,
            })

        primary = judgments[0]
        result: Dict[str, Any] = {
            'status': 'complete',
            'material_behavioral_difference': primary['material_behavioral_difference'],
            'overall_difference_score': primary['overall_difference_score'],
            'confidence': primary['confidence'],
            'dimensions': primary['dimensions'],
            'other_dimensions': primary['other_dimensions'],
            'summary': primary['summary'],
            'judge_model': self.model,
            'judge_provider': self.provider_name,
            'n_baseline_shown': sampled['n_baseline_shown'],
            'n_ablated_shown': sampled['n_ablated_shown'],
            'n_baseline_available': sampled['n_baseline_available'],
            'n_ablated_available': sampled['n_ablated_available'],
            'sampling_method': sampled['sampling_method'],
            'blinded': bool(blind),
            'judgments': judgments,
            'n_judges': len(judgments),
            'rubric': 'behavioral_difference_v1',
            'explicitly_not_quality_evaluation': True,
        }
        if len(judgments) > 1:
            scores = sorted(j['overall_difference_score'] for j in judgments)
            mats = [j['material_behavioral_difference'] for j in judgments]
            result['aggregate'] = {
                'overall_difference_score_median': scores[len(scores) // 2],
                'material_majority': sum(1 for m in mats if m) >= (len(mats) / 2.0),
                'agreement_rate_material': sum(
                    1 for m in mats if m == mats[0]
                ) / float(len(mats)),
            }
        return result


class HumanBehavioralDifferenceRecord(BehavioralDifferenceEvaluator):
    """Validate and store a human-observed difference review (not preference)."""

    def evaluate(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        material = payload.get('material_behavioral_difference')
        if isinstance(material, str):
            key = material.strip().lower()
            if key in ('uncertain', 'unsure', 'unknown'):
                material_out: Any = 'uncertain'
            elif key in ('true', 'yes', '1'):
                material_out = True
            elif key in ('false', 'no', '0'):
                material_out = False
            else:
                material_out = 'uncertain'
        elif material is None:
            material_out = 'uncertain'
        else:
            material_out = bool(material)

        dims_in = payload.get('dimensions') or {}
        if not isinstance(dims_in, Mapping):
            dims_in = {}
        dimensions = {
            k: _clamp_score(dims_in.get(k, 0)) for k in DIFFERENCE_DIMENSIONS
        }

        return {
            'status': 'complete',
            'material_behavioral_difference': material_out,
            'overall_difference_score': _clamp_score(
                payload.get('overall_difference_score', 0)
            ),
            'dimensions': dimensions,
            'notes': str(payload.get('notes') or '')[:5000],
            'blinded': bool(payload.get('blinded', False)),
            'rubric': 'human_behavioral_difference_v1',
            'explicitly_not_quality_evaluation': True,
            'reviewer_id': payload.get('reviewer_id'),
        }


def aggregate_behavioral_batch_stats(
    focus_rows: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Aggregate agreement metrics across focus rows (candidate language only)."""
    n = 0
    n_sem_sig = 0
    n_llm = 0
    n_llm_mat = 0
    n_hum = 0
    n_hum_mat = 0
    n_sem_llm = 0
    n_sem_llm_agree = 0
    n_llm_hum = 0
    n_llm_hum_agree = 0
    fn_cand = 0
    fp_cand = 0

    for item in focus_rows:
        if not isinstance(item, Mapping):
            continue
        n += 1
        sem = item.get('semantic_perturbation') or item
        sig = bool(sem.get('is_significant') or item.get('is_significant'))
        if sig:
            n_sem_sig += 1
        llm = item.get('llm_behavioral_difference') or {}
        hum = item.get('human_behavioral_difference') or {}
        if llm.get('status') == 'complete':
            n_llm += 1
            mat = bool(llm.get('material_behavioral_difference'))
            if mat:
                n_llm_mat += 1
            n_sem_llm += 1
            if sig == mat:
                n_sem_llm_agree += 1
            if (not sig) and mat:
                fn_cand += 1
            if sig and (not mat):
                fp_cand += 1
        if hum.get('status') == 'complete':
            n_hum += 1
            hmat = hum.get('material_behavioral_difference') is True
            if hmat:
                n_hum_mat += 1
            if llm.get('status') == 'complete':
                n_llm_hum += 1
                if bool(llm.get('material_behavioral_difference')) == hmat:
                    n_llm_hum_agree += 1

    def rate(a: int, b: int) -> Optional[float]:
        return (float(a) / float(b)) if b else None

    return {
        'n_focus_rows': n,
        'n_semantic_significant': n_sem_sig,
        'n_llm_reviews_complete': n_llm,
        'n_llm_material_difference': n_llm_mat,
        'n_human_reviews_complete': n_hum,
        'n_human_material_difference': n_hum_mat,
        'semantic_llm_agreement_rate': rate(n_sem_llm_agree, n_sem_llm),
        'llm_human_agreement_rate': rate(n_llm_hum_agree, n_llm_hum),
        'semantic_false_negative_candidates': fn_cand,
        'semantic_false_positive_candidates': fp_cand,
        'note': (
            'Agreement and false-positive/negative figures are candidates relative '
            'to another lens, not ground truth.'
        ),
    }


def select_foci_for_behavioral_review(
    focus_rows: Sequence[Mapping[str, Any]],
    *,
    max_reviews: Optional[int] = None,
    include_manual: Optional[Sequence[str]] = None,
    reported_scores: Optional[Mapping[str, float]] = None,
    only_recommended: bool = True,
) -> Dict[str, Any]:
    """Select a bounded set of foci for optional LLM/human difference review.

    Never escalates all foci by default. Manual names always included (until cap).
    """
    reported_scores = reported_scores or {}
    include_manual = set(include_manual or [])
    selected: List[Dict[str, Any]] = []
    for item in focus_rows:
        if not isinstance(item, Mapping):
            continue
        name = str(item.get('focus') or item.get('focus_name') or '')
        reported = reported_scores.get(name)
        rec = recommend_behavioral_review(item, reported_score=reported)
        manual = name in include_manual
        if only_recommended and not rec.get('review_recommended') and not manual:
            continue
        if not only_recommended and not manual and not rec.get('review_recommended'):
            # still allow explicit "all recommended or manual" mode only
            pass
        entry = {
            'focus': name,
            'review_recommendation': rec,
            'manual': manual,
        }
        selected.append(entry)

    # Prefer manual, then advisory reasons count, keep stable order otherwise
    selected.sort(key=lambda e: (not e['manual'], -len(e['review_recommendation'].get('reasons') or [])))
    truncated = False
    if max_reviews is not None and max_reviews >= 0 and len(selected) > max_reviews:
        selected = selected[: int(max_reviews)]
        truncated = True

    cost = estimate_judge_cost_units(len(selected))
    return {
        'selected': selected,
        'n_selected': len(selected),
        'truncated_by_max_reviews': truncated,
        'cost_estimate': cost,
        'note': (
            'Selection is advisory. Semantic screening remains the default; '
            'LLM/human difference review is opt-in and capped.'
        ),
    }


# ---------------------------------------------------------------------------
# Experiment C — Reported focus (A) vs perturbation sensitivity (B)
# ---------------------------------------------------------------------------

AB_CONCORDANCE_COPY = {
    'concordant_high': (
        'Agree (high): highest/high reported focus and detectable perturbation.'
    ),
    'concordant_quiet': (
        'Agree (quiet): low reported focus and no detectable perturbation.'
    ),
    'disagreement_over_reported': (
        'Disagreement: high reported focus, but no detectable embedding-space '
        'shift. Possible over-report, embedding blindness (e.g. schema/safety '
        'rules), redundancy, or an underpowered test.'
    ),
    'disagreement_under_reported': (
        'Disagreement: low reported focus, but detectable perturbation. The '
        'model may have under-credited a span that still shifts behaviour when '
        'removed.'
    ),
    'incomplete': (
        'Incomplete: missing reported score or significance for this focus.'
    ),
}


def ab_concordance_label(
    reported_score: Optional[float],
    semantic_significant: Optional[bool],
    *,
    reported_high_threshold: float = 15.0,
) -> Dict[str, Any]:
    """Label agreement between Experiment A score and Experiment B significance."""
    if reported_score is None or semantic_significant is None:
        key = 'incomplete'
    else:
        try:
            high = float(reported_score) >= float(reported_high_threshold)
        except (TypeError, ValueError):
            return {
                'key': 'incomplete',
                'label': AB_CONCORDANCE_COPY['incomplete'],
                'is_disagreement': False,
            }
        if high and semantic_significant is True:
            key = 'concordant_high'
        elif (not high) and semantic_significant is False:
            key = 'concordant_quiet'
        elif high and semantic_significant is False:
            key = 'disagreement_over_reported'
        else:
            key = 'disagreement_under_reported'
    return {
        'key': key,
        'label': AB_CONCORDANCE_COPY[key],
        'is_disagreement': key.startswith('disagreement_'),
        'reported_high_threshold': float(reported_high_threshold),
    }


def _spearman_rho(xs: Sequence[float], ys: Sequence[float]) -> Optional[float]:
    """Spearman rank correlation; None if fewer than 2 paired points."""
    n = min(len(xs), len(ys))
    if n < 2:
        return None
    pairs = [(float(xs[i]), float(ys[i])) for i in range(n)]
    # Average ranks for ties
    def ranks(vals: List[float]) -> List[float]:
        order = sorted(range(len(vals)), key=lambda i: vals[i])
        out = [0.0] * len(vals)
        i = 0
        while i < len(vals):
            j = i
            while j + 1 < len(vals) and vals[order[j + 1]] == vals[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                out[order[k]] = avg
            i = j + 1
        return out

    rx = ranks([p[0] for p in pairs])
    ry = ranks([p[1] for p in pairs])
    mx = sum(rx) / n
    my = sum(ry) / n
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    denx = sum((rx[i] - mx) ** 2 for i in range(n)) ** 0.5
    deny = sum((ry[i] - my) ** 2 for i in range(n)) ** 0.5
    if denx == 0 or deny == 0:
        return None
    return num / (denx * deny)


def compare_reported_vs_revealed(
    reported: Mapping[str, Any],
    perturbation: Mapping[str, Any],
    *,
    reported_high_threshold: float = 15.0,
) -> Dict[str, Any]:
    """
    Experiment C: side-by-side reported focus (A) vs perturbation sensitivity (B).

    Does not invent ground truth. Disagreement rows are candidates for review /
    LLM explanation.
    """
    report_by = {
        (f.get('focus') or '').strip(): f
        for f in (reported.get('foci') or [])
    }
    scores = perturbation.get('influence_scores') or []
    if isinstance(scores, dict):
        scores = list(scores.values())

    rows: List[Dict[str, Any]] = []
    for item in scores:
        name = (item.get('focus') or item.get('focus_name') or '').strip()
        if not name:
            continue
        rep = report_by.get(name) or {}
        sem = item.get('semantic_perturbation') or {}
        llm = item.get('llm_behavioral_difference') or {}
        hum = item.get('human_behavioral_difference') or {}

        semantic_sig = sem.get('is_significant', item.get('is_significant'))
        llm_material = None
        if llm.get('status') == 'complete':
            llm_material = bool(llm.get('material_behavioral_difference'))
        human_material = None
        if hum.get('status') == 'complete':
            hm = hum.get('material_behavioral_difference')
            human_material = True if hm is True else (False if hm is False else None)

        reported_score = rep.get('score')
        if reported_score is None:
            reported_score = rep.get('reported_focus_score')

        concordance = ab_concordance_label(
            reported_score,
            semantic_sig,
            reported_high_threshold=reported_high_threshold,
        )
        faithfulness = multi_lens_faithfulness_label(
            reported_score=reported_score,
            semantic_significant=semantic_sig,
            llm_material=llm_material,
            human_material=human_material,
            reported_high_threshold=reported_high_threshold,
        )
        rows.append({
            'focus': name,
            'prompt_section': (
                rep.get('prompt_section')
                or item.get('prompt_section')
                or ''
            ),
            'reported_score': reported_score,
            'reported_explanation': rep.get('explanation'),
            't_obs': item.get('t_obs', sem.get('t_obs')),
            'influence': item.get('influence'),
            'normalized_influence': item.get(
                'normalized_influence', sem.get('normalized_influence')
            ),
            'standardized_effect': item.get(
                'standardized_effect', sem.get('standardized_effect')
            ),
            'p_value': item.get('p_value', sem.get('p_value')),
            'q_value': item.get('q_value', sem.get('q_value')),
            'is_significant': semantic_sig,
            'semantic_perturbation': sem or {
                't_obs': item.get('t_obs'),
                'normalized_influence': item.get('normalized_influence'),
                'standardized_effect': item.get('standardized_effect'),
                'p_value': item.get('p_value'),
                'q_value': item.get('q_value'),
                'is_significant': item.get('is_significant'),
            },
            'llm_behavioral_difference': llm,
            'human_behavioral_difference': hum,
            'concordance': concordance,
            'faithfulness': faithfulness,
            'note': (
                'Reported focus is model self-assessment of a completion '
                '(Experiment A), not transformer attention. Semantic '
                'perturbation is leave-one-out embedding-space shift '
                '(Experiment B). Disagreement is informative, not a verdict '
                'on which lens is “correct.”'
            ),
        })

    # Rank concordance: reported score vs normalized influence (descriptive).
    paired_r: List[float] = []
    paired_i: List[float] = []
    for row in rows:
        rs = row.get('reported_score')
        ni = row.get('normalized_influence')
        if rs is None or ni is None:
            continue
        try:
            paired_r.append(float(rs))
            paired_i.append(float(ni))
        except (TypeError, ValueError):
            continue
    rho = _spearman_rho(paired_r, paired_i)

    disagreements = [r for r in rows if (r.get('concordance') or {}).get('is_disagreement')]
    n_high_sig = sum(
        1 for r in rows
        if (r.get('concordance') or {}).get('key') == 'concordant_high'
    )
    n_quiet = sum(
        1 for r in rows
        if (r.get('concordance') or {}).get('key') == 'concordant_quiet'
    )

    return {
        'rows': rows,
        'summary': {
            'n_foci_compared': len(rows),
            'n_concordant_high': n_high_sig,
            'n_concordant_quiet': n_quiet,
            'n_disagreements': len(disagreements),
            'disagreement_foci': [r['focus'] for r in disagreements],
            'spearman_reported_vs_normalized_influence': rho,
            'reported_high_threshold': float(reported_high_threshold),
            'interpretation': (
                'Spearman ρ links reported-focus ranks to descriptive '
                'normalized T_obs shares — not a causal importance ranking. '
                'Significance (q) is the Experiment B detection claim.'
                if rho is not None
                else 'Not enough paired foci to compute rank correlation.'
            ),
        },
        'framing': {
            'experiment_a': 'model-assessed / reported focus distribution',
            'experiment_b': (
                'semantic perturbation sensitivity (cheap first pass); optional '
                'LLM and human behavioral-difference review'
            ),
            'experiment_c': (
                'comparison of reported focus vs revealed sensitivity: which '
                'foci agree, which disagree, and (optionally) an LLM hypothesis '
                'for disagreements'
            ),
        },
    }


def build_disagreement_explanation_prompt(
    comparison: Mapping[str, Any],
    *,
    original_prompt: str = '',
) -> str:
    """User message for an LLM that hypothesizes why A and B disagree."""
    rows = [
        r for r in (comparison.get('rows') or [])
        if (r.get('concordance') or {}).get('is_disagreement')
    ]
    if not rows:
        return ''

    blocks = []
    for r in rows:
        conc = r.get('concordance') or {}
        blocks.append(
            f"Focus: {r.get('focus')}\n"
            f"Prompt span: {(r.get('prompt_section') or '')[:400]}\n"
            f"Reported score (A): {r.get('reported_score')}\n"
            f"Reported explanation: {(r.get('reported_explanation') or '')[:400]}\n"
            f"Perturbation significant (B): {r.get('is_significant')}\n"
            f"q_value: {r.get('q_value')}; t_obs: {r.get('t_obs')}; "
            f"normalized_influence: {r.get('normalized_influence')}; "
            f"standardized_effect: {r.get('standardized_effect')}\n"
            f"Concordance: {conc.get('key')} — {conc.get('label')}"
        )

    prompt_excerpt = (original_prompt or '')[:2500]
    return f"""You are helping a researcher interpret disagreement between two experiments on the same prompt foci.

Experiment A (Reported focus): an LLM scores how much a *single completion* appears to reflect each focus (introspective / behavioural self-report — not transformer attention).

Experiment B (Perturbation sensitivity): leave-one-focus-out deletion + embedding centroid distance + permutation / BH. A significant result means removing that span shifted outputs in embedding space beyond sampling variation at this sample size. Non-significant ≠ unused.

These lenses can disagree for legitimate reasons (embedding blindness to schemas/safety, redundant instructions, underpowered tests, assessment of one sample vs distributional sensitivity, etc.). Do NOT declare which experiment is "correct." Do NOT recommend deleting foci. Hypothesize *possible* explanations.

ORIGINAL PROMPT (excerpt):
{prompt_excerpt or '(not provided)'}

DISAGREEMENT ROWS:
{chr(10).join('---\n' + b for b in blocks)}

Return JSON:
{{
  "overall_summary": "2-4 sentences on the pattern of agreement/disagreement",
  "per_focus": [
    {{
      "focus": "exact focus name",
      "hypothesis": "why A and B may disagree for this focus",
      "likely_mechanisms": ["embedding_blindness|redundancy|underpowered|single_sample_vs_distribution|other"],
      "what_would_resolve": "concrete next check (e.g. LLM behavioral-difference review, more samples, inspect outputs)"
    }}
  ],
  "caveats": ["short caveats"]
}}
"""


class ReportedVsRevealedExplainer:
    """Optional LLM narrative for Experiment C disagreements (not ground truth)."""

    def __init__(self, provider, model: str, provider_name: Optional[str] = None):
        self.provider = provider
        self.model = model
        self.provider_name = provider_name or 'openai'

    def explain(
        self,
        comparison: Mapping[str, Any],
        *,
        original_prompt: str = '',
        temperature: float = 0.3,
    ) -> Dict[str, Any]:
        disagreements = [
            r for r in (comparison.get('rows') or [])
            if (r.get('concordance') or {}).get('is_disagreement')
        ]
        if not disagreements:
            return {
                'status': 'skipped',
                'reason': 'no_disagreements',
                'overall_summary': 'No A↔B disagreements to explain at the current thresholds.',
                'per_focus': [],
                'caveats': [
                    'Absence of disagreement does not mean the lenses measure the same thing.'
                ],
            }

        user = build_disagreement_explanation_prompt(
            comparison, original_prompt=original_prompt
        )
        response = gateway_chat_completion(
            self.provider,
            self.model,
            self.provider_name,
            [
                {
                    'role': 'system',
                    'content': (
                        'You explain disagreements between reported-focus scores and '
                        'perturbation sensitivity. Difference ≠ quality. Never claim '
                        'ground truth or recommend deletions. Return valid JSON only.'
                    ),
                },
                {'role': 'user', 'content': user},
            ],
            temperature=temperature,
            response_format={'type': 'json_object'},
        )
        raw = response.get('content') or '{}'
        from utils.llm_json import parse_llm_json
        try:
            parsed = parse_llm_json(raw)
        except ValueError:
            parsed = {}
        if not isinstance(parsed, dict):
            parsed = {}

        return {
            'status': 'complete',
            'overall_summary': parsed.get('overall_summary') or '',
            'per_focus': parsed.get('per_focus') or [],
            'caveats': parsed.get('caveats') or [],
            'n_disagreements_explained': len(disagreements),
            'note': (
                'LLM hypotheses only. They do not adjudicate Experiment A vs B.'
            ),
            'usage': response.get('usage'),
        }
