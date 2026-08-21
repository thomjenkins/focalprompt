#!/usr/bin/env python3
"""
Prompt rewrite service.

Rewrites prompts according to user-specified rewrite weights.
Reported-focus scores may initialize those weights in the UI, but rewrite
semantics are driven only by the weights sent to this service.
"""

from __future__ import annotations

import inspect
from typing import Dict, List, Optional, Tuple

from core.focal_assessor import FocalAssessor

# User-facing rewrite-weight bands (percentage points, 0–100).
WEIGHT_OMIT = 0.0
WEIGHT_MINIMIZE_MAX = 29.0
WEIGHT_RETAIN_MAX = 69.0


def normalize_rewrite_weight(raw) -> float:
    """Coerce a weight to [0, 100] percentage points. Does not clamp 0 upward."""
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0.0
    if value < 0:
        return 0.0
    if value > 100:
        return 100.0
    return value


def weight_band(weight: float) -> str:
    """Return omit | minimize | retain | emphasize for a rewrite weight."""
    w = normalize_rewrite_weight(weight)
    if w <= WEIGHT_OMIT:
        return 'omit'
    if w <= WEIGHT_MINIMIZE_MAX:
        return 'minimize'
    if w <= WEIGHT_RETAIN_MAX:
        return 'retain'
    return 'emphasize'


def _focus_label(item: Dict) -> str:
    return str(item.get('focus') or item.get('name') or 'Unnamed focus')


def _focus_section(item: Dict) -> str:
    return str(
        item.get('prompt_section')
        or item.get('prompt_section')
        or item.get('section')
        or ''
    )


def build_rewrite_instruction(prompt: str, foci_weights: List[Dict]) -> str:
    """
    Build the rewrite instruction sent to the LLM.

    Weight semantics (rewrite_weight, percentage points):
      * 0%     — omit the focus wherever possible
      * 1–29%  — minimize / compress heavily
      * 30–69% — retain clearly
      * 70–100% — emphasize strongly
    """
    lines: List[str] = []
    omit: List[str] = []
    minimize: List[str] = []
    retain: List[str] = []
    emphasize: List[str] = []

    for item in foci_weights or []:
        name = _focus_label(item)
        # Prefer explicit rewrite_weight; fall back to weight (UI legacy field).
        raw = item.get('rewrite_weight', item.get('weight', 0))
        weight = normalize_rewrite_weight(raw)
        section = _focus_section(item)
        snippet = section[:160].replace('\n', ' ')
        if len(section) > 160:
            snippet += '...'
        band = weight_band(weight)
        lines.append(
            f"- {name}: rewrite_weight={weight:.1f}% [{band}] "
            f"(source span: {snippet or '(no section provided)'})"
        )
        if band == 'omit':
            omit.append(name)
        elif band == 'minimize':
            minimize.append(name)
        elif band == 'retain':
            retain.append(name)
        else:
            emphasize.append(name)

    weights_text = '\n'.join(lines) if lines else '(no foci provided)'

    omit_block = (
        "FOCI TO OMIT (rewrite_weight = 0%):\n"
        + '\n'.join(f"- {n}" for n in omit)
        + "\nRemove the instruction/content these foci represent. "
          "Do not paraphrase them elsewhere. Do not retain equivalent wording "
          "implicitly. Do not keep them as brief mentions.\n"
        if omit
        else "FOCI TO OMIT: none\n"
    )

    return f"""Rewrite the following prompt using the user-specified rewrite weights.

ORIGINAL PROMPT:
{prompt}

REWRITE WEIGHTS (user intent for this rewrite — not causal importance scores):
{weights_text}

{omit_block}
WEIGHT BAND RULES:
1. Exactly 0% (omit): delete the instruction/content for that focus from the rewritten prompt wherever possible. Do not paraphrase it elsewhere. Do not retain equivalent wording implicitly. Do not "mention briefly."
2. 1–29% (minimize): keep only the minimum wording necessary to represent that focus. This is distinct from 0%: the focus must still appear, but compressed.
3. 30–69% (retain): keep the focus clearly and explicitly present.
4. 70–100% (emphasize): make the focus prominent and explicit (position, stronger language, and/or brief reinforcement).

COHERENCE:
- Preserve the meaning of all retained foci (weights > 0).
- After removals, keep the remaining prompt coherent and usable.
- Do NOT preserve the original prompt's overall meaning when that would require keeping a 0%-weight focus.
- Do NOT invent new requirements unrelated to retained foci.

Return only the rewritten prompt, with no preamble or explanation."""


class PromptRewriteService:
    """Service for rewriting prompts according to rewrite weights."""

    def __init__(self, assessor: FocalAssessor):
        self.assessor = assessor

    def rewrite_prompt(
        self,
        prompt: str,
        foci_weights: List[Dict],
    ) -> str:
        """
        Rewrite ``prompt`` according to per-focus rewrite weights.

        Each item in ``foci_weights`` should include:
          - focus
          - prompt_section (exact source span when available)
          - rewrite_weight or weight: percentage points in [0, 100]
        """
        llm = self.assessor.provider
        provider_name = getattr(self.assessor, 'provider_name', 'openai')

        rewrite_instruction = build_rewrite_instruction(prompt, foci_weights)

        kwargs = {
            'model': self.assessor.model,
            'messages': [
                {
                    'role': 'system',
                    'content': (
                        'You rewrite prompts according to explicit per-focus '
                        'rewrite weights. A weight of exactly 0% means omit that '
                        'focus. Do not keep omitted foci as brief or implicit mentions. '
                        'Preserve meaning only for retained foci (weights > 0) and '
                        'keep the result coherent after removals.'
                    ),
                },
                {
                    'role': 'user',
                    'content': rewrite_instruction,
                },
            ],
            'temperature': 0.7,
        }
        if hasattr(llm, 'chat_completion'):
            sig = inspect.signature(llm.chat_completion)
            if 'provider' in sig.parameters:
                kwargs['provider'] = provider_name
        response = llm.chat_completion(**kwargs)

        return response['content'].strip()

    @staticmethod
    def partition_by_band(
        foci_weights: List[Dict],
    ) -> Dict[str, List[Dict]]:
        """Group foci by rewrite-weight band (for tests / callers)."""
        out = {'omit': [], 'minimize': [], 'retain': [], 'emphasize': []}
        for item in foci_weights or []:
            raw = item.get('rewrite_weight', item.get('weight', 0))
            out[weight_band(raw)].append(item)
        return out
