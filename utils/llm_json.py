#!/usr/bin/env python3
"""Parse JSON from LLM chat responses (plain or markdown-fenced)."""

from __future__ import annotations

import json
import re
from typing import Any


def parse_llm_json(content: str) -> Any:
    """
    Parse a JSON object/array from model output.

    Models often wrap JSON in ```json fences even when response_format
    requests json_object. Bare json.loads then fails with
    ``Expecting value: line 1 column 1``.
    """
    text = (content or '').strip()
    if not text:
        raise ValueError('Empty response from LLM')

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fenced = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text, re.IGNORECASE)
    if fenced:
        inner = fenced.group(1).strip()
        try:
            return json.loads(inner)
        except json.JSONDecodeError:
            text = inner

    start = text.find('{')
    end = text.rfind('}')
    if start >= 0 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    start = text.find('[')
    end = text.rfind(']')
    if start >= 0 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f'LLM did not return valid JSON. Response: {text[:200]}...')
