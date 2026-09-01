"""Generic 500 JSON responses for route handlers (no exception text in body)."""

from __future__ import annotations

import sys
import traceback
from typing import Any, Dict, Optional, Tuple

from flask import jsonify


def internal_error(
    code: str,
    exc: BaseException,
    *,
    extra: Optional[Dict[str, Any]] = None,
) -> Tuple[Any, int]:
    """Log exception server-side; return stable client-facing 500 payload."""
    traceback.print_exc(file=sys.stderr)
    print(f'Route error [{code}]: {exc}', file=sys.stderr)
    body: Dict[str, Any] = {'error': 'internal error', 'code': code}
    if extra:
        body.update(extra)
    return jsonify(body), 500
