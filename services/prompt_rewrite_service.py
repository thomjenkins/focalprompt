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
from typing import Dict, List, Tuple

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


def _dynamic_marker(index: int, dynamic_type: str) -> str:
    slug = re.sub(r'[^A-Za-z0-9]+', '_', dynamic_type or 'dynamic').strip('_')
    return f"<<FOCALPROMPT_DYNAMIC_{index}_{(slug or 'dynamic').upper()}>>"


def _span_from_focus(focus: Dict) -> List[Tuple[int, int]]:
    spans = focus.get('spans')
    if isinstance(spans, list) and spans:
        out = []
        for span in spans:
            if not isinstance(span, dict):
                continue
            start = span.get('char_start', span.get('start'))
            end = span.get('char_end', span.get('end'))
            try:
                start_i = int(start)
                end_i = int(end)
            except (TypeError, ValueError):
                continue
            if end_i > start_i:
                out.append((start_i, end_i))
        return out

    start = focus.get('char_start')
    end = focus.get('char_end')
    try:
        start_i = int(start)
        end_i = int(end)
    except (TypeError, ValueError):
        return []
    if end_i > start_i:
        return [(start_i, end_i)]
    return []


def protect_dynamic_spans(prompt: str, foci_weights: List[Dict]) -> Tuple[str, List[Dict]]:
    """Replace tagged dynamic source spans with stable markers before rewrite."""
    candidates = []
    prompt_len = len(prompt)
    seen = set()
    for focus in foci_weights or []:
        if not focus.get('is_dynamic'):
            continue
        dynamic_type = str(focus.get('dynamic_type') or 'dynamic')
        for start, end in _span_from_focus(focus):
            if start < 0 or end > prompt_len or end <= start:
                continue
            key = (start, end)
            if key in seen:
                continue
            seen.add(key)
            candidates.append({
                'start': start,
                'end': end,
                'text': prompt[start:end],
                'dynamic_type': dynamic_type,
                'focus': _focus_label(focus),
            })

    candidates.sort(key=lambda item: (item['start'], item['end']))
    protected = []
    last_end = -1
    for item in candidates:
        if item['start'] < last_end:
            continue
        item['marker'] = _dynamic_marker(len(protected), item['dynamic_type'])
        protected.append(item)
        last_end = item['end']

    protected_prompt = prompt
    for item in reversed(protected):
        protected_prompt = (
            protected_prompt[:item['start']]
            + item['marker']
            + protected_prompt[item['end']:]
        )
    return protected_prompt, protected


def restore_dynamic_spans(rewritten: str, protected: List[Dict]) -> str:
    """Restore exact dynamic text, appending any marker the model dropped."""
    output = rewritten or ''
    missing = []
    for item in protected:
        marker = item['marker']
        text = item['text']
        if marker in output:
            output = output.replace(marker, text, 1)
            output = output.replace(marker, '')
        else:
            missing.append(item)

    if missing:
        blocks = []
        for item in missing:
            label = str(item.get('dynamic_type') or 'dynamic').replace('_', ' ').title()
            blocks.append(f"{label}:\n{item['text']}")
        output = output.rstrip() + "\n\n" + "\n\n".join(blocks)
    return output


def foci_with_dynamic_markers(foci_weights: List[Dict], protected: List[Dict]) -> List[Dict]:
    """Replace dynamic focus source summaries with their markers for the LLM."""
    markers_by_focus: Dict[str, List[str]] = {}
    for item in protected:
        markers_by_focus.setdefault(str(item.get('focus') or ''), []).append(item['marker'])

    out = []
    for focus in foci_weights or []:
        next_focus = dict(focus)
        if next_focus.get('is_dynamic'):
            markers = markers_by_focus.get(_focus_label(next_focus)) or []
            if markers:
                next_focus['prompt_section'] = '\n'.join(markers)
        out.append(next_focus)
    return out


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


def looks_like_rewrite_instruction_leak(rewritten: str) -> bool:
    """True when the model copied the meta rewrite instructions into output."""
    text = strip_rewrite_fences(rewritten or '')
    if not text:
        return False
    head = text[:400].lower()
    if head.startswith('you are editing instruction text'):
        return True
    if head.startswith('rewrite the following prompt using the user-specified rewrite weights'):
        return True
    control_markers = (
        'original prompt:',
        'rewrite weights',
        'weight band rules',
        'foci to omit',
        'critical retry',
    )
    return sum(1 for marker in control_markers if marker in head) >= 2


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
        is_dynamic = bool(item.get('is_dynamic'))
        # Prefer explicit rewrite_weight; fall back to weight (UI legacy field).
        raw = item.get('rewrite_weight', item.get('weight', 0))
        weight = normalize_rewrite_weight(raw)
        section = _focus_section(item)
        snippet = section[:160].replace('\n', ' ')
        if len(section) > 160:
            snippet += '...'
        band = weight_band(weight)
        display_band = 'protected_dynamic' if is_dynamic else band
        dynamic_note = ''
        if is_dynamic:
            dynamic_note = (
                f" protected_dynamic={item.get('dynamic_type') or 'dynamic'};"
                " preserve this marker/content exactly once"
            )
        lines.append(
            f"- {name}: rewrite_weight={weight:.1f}% [{display_band}]"
            f"{dynamic_note} (source span: {snippet or '(no section provided)'})"
        )
        if is_dynamic:
            retain.append(name)
        elif band == 'omit':
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
- You may also have copied these rewrite-control instructions into the output.
  That is wrong. Do not copy text such as "You are editing INSTRUCTION TEXT",
  "ORIGINAL PROMPT", "REWRITE WEIGHTS", or "WEIGHT BAND RULES".
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
- Preserve any <<FOCALPROMPT_DYNAMIC_*>> marker exactly once in the rewritten
  prompt. These markers stand for user-tagged dynamic content such as chat,
  RAG context, or tool results; do not delete, paraphrase, summarize, or
  duplicate them.

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
            supports_kwargs = any(
                p.kind == inspect.Parameter.VAR_KEYWORD
                for p in sig.parameters.values()
            )
            if 'max_tokens' in sig.parameters or supports_kwargs:
                kwargs['max_tokens'] = 4096
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
        original = prompt or ''
        if not original.strip():
            raise ValueError('Prompt is required')
        protected_prompt, protected_dynamic = protect_dynamic_spans(
            original, foci_weights
        )
        protected_foci = foci_with_dynamic_markers(foci_weights, protected_dynamic)

        rewritten = self._chat_rewrite(
            build_rewrite_instruction(protected_prompt, protected_foci)
        )

        if (
            looks_like_sample_completion(original, rewritten)
            or looks_like_rewrite_instruction_leak(rewritten)
        ):
            rewritten = self._chat_rewrite(
                build_rewrite_instruction(
                    protected_prompt, protected_foci, retry_harden=True
                )
            )

        if not rewritten.strip():
            raise ValueError(
                'Rewrite returned empty text. Try again or adjust focus weights.'
            )

        if looks_like_rewrite_instruction_leak(rewritten):
            raise ValueError(
                'Rewrite copied internal rewrite instructions instead of '
                'returning only the rewritten prompt. Try again or use a model '
                'that follows instructions more reliably.'
            )

        if looks_like_sample_completion(original, rewritten):
            raise ValueError(
                'Rewrite produced a sample reply or completion instead of a '
                'rewritten prompt. Adjust weights and try again, or use a '
                'model that follows instructions more reliably.'
            )

        return restore_dynamic_spans(rewritten, protected_dynamic)

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
