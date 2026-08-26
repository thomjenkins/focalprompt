#!/usr/bin/env python3
"""
Prompt rewrite service.

Rewrites prompts according to user-specified rewrite weights.
Reported-focus scores may initialize those weights in the UI, but rewrite
semantics are driven only by the weights sent to this service.
"""

from __future__ import annotations

import inspect
import json
import re
from typing import Dict, List

from core.focal_assessor import FocalAssessor

# User-facing rewrite-weight bands (percentage points, 0–100).
WEIGHT_OMIT = 0.0
WEIGHT_MINIMIZE_MAX = 29.0
WEIGHT_RETAIN_MAX = 69.0

_FENCE_RE = re.compile(
    r'^\s*```(?:\w+)?\s*\n?(.*?)\n?```\s*$',
    re.DOTALL,
)

# Keys that usually mean the model emitted a sample reply / schema instance
# instead of rewritten instruction text.
_COMPLETION_KEYS = frozenset({
    'suggestedmessage',
    'suggested_message',
    'message',
    'reply',
    'response',
    'assistant',
    'content',
    'text',
    'body',
    'email',
    'sms',
})


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
        or item.get('section')
        or ''
    )


def strip_rewrite_fences(text: str) -> str:
    """Remove a single surrounding markdown fence if the model added one."""
    raw = (text or '').strip()
    if not raw:
        return ''
    match = _FENCE_RE.match(raw)
    if match:
        return match.group(1).strip()
    return raw


def looks_like_sample_completion(original: str, rewritten: str) -> bool:
    """
    Heuristic: True when ``rewritten`` looks like a model *reply* / schema
    instance rather than rewritten instruction text.

    Conservative: only flag clear completions so valid short rewrites still pass.
    """
    original = (original or '').strip()
    rewritten = strip_rewrite_fences(rewritten or '')
    if not rewritten:
        return True

    # Identical to original is a failed rewrite only if weights asked for change;
    # callers handle emptiness; identity alone is not a "completion".
    orig_len = len(original)
    rew_len = len(rewritten)

    # Short JSON object while original was substantive instructions.
    stripped = rewritten.lstrip()
    if stripped.startswith('{') and orig_len >= 200 and rew_len < max(120, int(orig_len * 0.35)):
        try:
            parsed = json.loads(rewritten)
        except (json.JSONDecodeError, TypeError):
            parsed = None
        if isinstance(parsed, dict) and parsed:
            keys = {str(k).lower().replace('-', '_') for k in parsed.keys()}
            if keys & _COMPLETION_KEYS:
                return True
            # Tiny dict that does not resemble a prompt document
            if len(parsed) <= 3 and rew_len < 400:
                return True

    # Opening looks like a polite customer-service reply, not instructions.
    head = rewritten[:80].lower()
    reply_openers = (
        'thank you for your message',
        'thanks for reaching out',
        'dear ',
        'hi there',
        'hello!',
        'we look forward',
    )
    if orig_len >= 200 and any(head.startswith(p) or p in head[:60] for p in reply_openers):
        if 'you are' not in rewritten[:200].lower() and rew_len < max(200, int(orig_len * 0.4)):
            return True

    return False


def build_rewrite_instruction(
    prompt: str,
    foci_weights: List[Dict],
    *,
    retry_harden: bool = False,
) -> str:
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

    harden = ""
    if retry_harden:
        harden = """
CRITICAL RETRY — previous attempt FAILED:
- You previously returned a sample assistant reply, example message, or JSON
  completion instance (e.g. {"suggestedMessage": "..."}). That is wrong.
- Output the rewritten INSTRUCTION PROMPT only — the text a developer would
  paste as a system/user prompt — never an example of what that prompt produces.
"""

    return f"""Rewrite the following prompt using the user-specified rewrite weights.

You are editing INSTRUCTION TEXT (a system/developer prompt). Your job is to
produce a new version of those instructions.

DO NOT:
- Generate a sample reply, email, SMS, or chat message to an end user
- Emit an example JSON/XML completion that the original prompt asks a model to produce
  (e.g. do not invent {{"suggestedMessage": "..."}} unless the ORIGINAL PROMPT itself
  is only that template and you are rewriting that template as instructions)
- Answer the original prompt as if you were the assistant it describes
- Add preamble like "Here is the rewritten prompt:"

DO:
- Return the full rewritten prompt text, same genre as ORIGINAL PROMPT (instructions)
- If ORIGINAL PROMPT tells a model how to format outputs, keep/adjust those *rules*
  as instructions — do not execute them

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
{harden}
Return only the rewritten prompt, with no preamble or explanation."""


_REWRITE_SYSTEM = (
    'You rewrite instruction prompts according to explicit per-focus '
    'rewrite weights. A weight of exactly 0% means omit that focus. '
    'Do not keep omitted foci as brief or implicit mentions. '
    'Preserve meaning only for retained foci (weights > 0) and '
    'keep the result coherent after removals. '
    'Never produce sample assistant replies or example JSON completions; '
    'output only the rewritten instruction text.'
)


class PromptRewriteService:
    """Service for rewriting prompts according to rewrite weights."""

    def __init__(self, assessor: FocalAssessor):
        self.assessor = assessor

    def _chat_rewrite(self, instruction: str) -> str:
        llm = self.assessor.provider
        provider_name = getattr(self.assessor, 'provider_name', 'openai')
        kwargs = {
            'model': self.assessor.model,
            'messages': [
                {'role': 'system', 'content': _REWRITE_SYSTEM},
                {'role': 'user', 'content': instruction},
            ],
            'temperature': 0.3,
        }
        if hasattr(llm, 'chat_completion'):
            sig = inspect.signature(llm.chat_completion)
            if 'provider' in sig.parameters:
                kwargs['provider'] = provider_name
        response = llm.chat_completion(**kwargs)
        return strip_rewrite_fences(response.get('content') or '')

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

        Does not mutate the original prompt; returns a new string only.
        """
        original = (prompt or '').strip()
        if not original:
            raise ValueError('Prompt is required')

        rewritten = self._chat_rewrite(
            build_rewrite_instruction(original, foci_weights)
        )

        if looks_like_sample_completion(original, rewritten):
            rewritten = self._chat_rewrite(
                build_rewrite_instruction(
                    original, foci_weights, retry_harden=True
                )
            )

        if not rewritten.strip():
            raise ValueError(
                'Rewrite returned empty text. Try again or adjust focus weights.'
            )

        if looks_like_sample_completion(original, rewritten):
            raise ValueError(
                'Rewrite produced a sample reply or completion instead of a '
                'rewritten prompt. Adjust weights and try again, or use a '
                'model that follows instructions more reliably.'
            )

        return rewritten

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
