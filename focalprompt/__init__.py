#!/usr/bin/env python3
"""
Focal Prompt — research toolkit for studying how AI systems allocate attention
and respond to their informational environment.

Public API::

    from focalprompt import analyze
    result = analyze(prompt=..., model=..., ...)
"""

from focalprompt.api import analyze, assess_focus, detect_foci, ablate

__all__ = [
    'analyze',
    'assess_focus',
    'detect_foci',
    'ablate',
    '__version__',
]

__version__ = '0.2.0'
