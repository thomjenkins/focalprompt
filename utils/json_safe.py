#!/usr/bin/env python3
"""JSON-serialisation helpers for analysis API payloads."""

from __future__ import annotations

import math
from typing import Any


def sanitize_non_finite(obj: Any) -> Any:
    """
    Recursively replace non-finite floats (inf, -inf, nan) with ``None``.

    Used as a backstop before ``jsonify`` on analysis responses so strict
    JSON parsers never see bare ``Infinity`` or ``NaN`` tokens.
    """
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {key: sanitize_non_finite(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [sanitize_non_finite(value) for value in obj]
    if isinstance(obj, tuple):
        return tuple(sanitize_non_finite(value) for value in obj)
    return obj
