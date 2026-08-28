#!/usr/bin/env python3
"""
Hosted-demo controls for focalprompt.com (optional; off by default).

Local / open-source installs leave these unset: full BYO inference works.

Environment:
  FOCALPROMPT_HOSTED_MODE=1          Prefer landing + precomputed experiments
  FOCALPROMPT_ALLOW_LIVE_INFERENCE=0 Disable live /api analytical calls (default when hosted)
  FOCALPROMPT_ALLOW_LIVE_INFERENCE=1 Enable live calls with optional budget/rate caps
  FOCALPROMPT_DEMO_DAILY_BUDGET_USD  Soft daily USD estimate cap (0 = unlimited)
  FOCALPROMPT_DEMO_RPM               Max analytical requests per minute per IP (0 = off)
"""

from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque
from typing import Any, Dict, Optional, Tuple


def _truthy(name: str, default: str = '0') -> bool:
    return os.getenv(name, default).strip().lower() in ('1', 'true', 'yes', 'on')


def is_hosted_mode() -> bool:
    return _truthy('FOCALPROMPT_HOSTED_MODE')


def allow_live_inference() -> bool:
    if not is_hosted_mode():
        return True
    # Hosted defaults to precomputed-only unless explicitly enabled.
    if os.getenv('FOCALPROMPT_ALLOW_LIVE_INFERENCE') is None:
        return False
    return _truthy('FOCALPROMPT_ALLOW_LIVE_INFERENCE')


def daily_budget_usd() -> float:
    try:
        return float(os.getenv('FOCALPROMPT_DEMO_DAILY_BUDGET_USD', '0') or 0)
    except ValueError:
        return 0.0


def rpm_limit() -> int:
    try:
        return int(os.getenv('FOCALPROMPT_DEMO_RPM', '0') or 0)
    except ValueError:
        return 0


_lock = threading.Lock()
_spend_day: Optional[str] = None
_spend_usd: float = 0.0
_rpm: Dict[str, deque] = defaultdict(deque)


def record_estimated_spend(usd: float) -> None:
    global _spend_day, _spend_usd
    if usd <= 0:
        return
    day = time.strftime('%Y-%m-%d', time.gmtime())
    with _lock:
        if _spend_day != day:
            _spend_day = day
            _spend_usd = 0.0
        _spend_usd += usd


def check_live_allowed(client_ip: str = 'unknown') -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Return (ok, error_payload). When not ok, caller should respond 503.
    """
    if allow_live_inference():
        limit = rpm_limit()
        if limit > 0:
            now = time.time()
            with _lock:
                q = _rpm[client_ip]
                while q and now - q[0] > 60:
                    q.popleft()
                if len(q) >= limit:
                    return False, {
                        'error': 'Hosted demo rate limit exceeded. Run Focal Prompt locally with your own credentials, or wait a minute.',
                        'code': 'demo_rpm',
                        'rpm': limit,
                    }
                q.append(now)
        budget = daily_budget_usd()
        if budget > 0:
            day = time.strftime('%Y-%m-%d', time.gmtime())
            with _lock:
                spent = _spend_usd if _spend_day == day else 0.0
            if spent >= budget:
                return False, {
                    'error': 'Hosted demo daily inference budget exhausted. Browse precomputed experiments or run locally.',
                    'code': 'demo_budget',
                    'budget_usd': budget,
                }
        return True, None

    return False, {
        'error': (
            'Live inference is disabled on the hosted demo. '
            'Browse /experiments for precomputed results, or run Focal Prompt locally with your own AI_GATEWAY_API_KEY / provider credentials.'
        ),
        'code': 'live_disabled',
        'experiments': '/experiments',
        'docs': 'https://github.com/thomjenkins/focalprompt',
    }


# Analytical paths that consume inference (not pricing/health/checkpoints list).
LIVE_INFERENCE_PREFIXES = (
    '/api/detect-foci',
    '/api/detect-dynamic-foci',
    '/api/assess',
    '/api/generate-output',
    '/api/rewrite-prompt',
    '/api/build-agent-prompt',
    '/api/ablation',
    '/api/ablation-shuffle-robustness',
    '/api/focus-order-sensitivity',
    '/api/behavioral-difference/llm-judge',
    '/api/explain-reported-vs-revealed',
    '/api/evaluate-outputs-quality',
    '/api/batch-analysis',
    '/api/assess-chat-foci',
    '/api/generate-agent-response',
    '/api/v1/detect-foci',
    '/api/v1/detect-dynamic-foci',
    '/api/v1/assess',
    '/api/v1/generate-output',
    '/api/v1/rewrite-prompt',
    '/api/v1/build-agent-prompt',
    '/api/v1/ablation-analysis',
)


def path_requires_live(path: str) -> bool:
    return any(path.startswith(p) for p in LIVE_INFERENCE_PREFIXES)
