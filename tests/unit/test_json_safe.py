"""JSON safety helpers for analysis payloads."""

import json
import math

import pytest

from utils.json_safe import sanitize_non_finite


def test_sanitize_non_finite_replaces_inf_and_nan():
    data = {
        'ok': 1.5,
        'bad': float('inf'),
        'nested': [{'x': float('nan')}],
    }
    cleaned = sanitize_non_finite(data)
    assert cleaned['ok'] == 1.5
    assert cleaned['bad'] is None
    assert cleaned['nested'][0]['x'] is None

    payload = json.dumps(cleaned)
    assert 'Infinity' not in payload
    assert 'NaN' not in payload


def test_sanitize_leaves_finite_unchanged():
    assert sanitize_non_finite(0.0) == 0.0
    assert sanitize_non_finite(-2.5) == -2.5
    assert math.isfinite(sanitize_non_finite(1e300))
