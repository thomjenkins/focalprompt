#!/usr/bin/env python3
"""Deprecated entrypoint — use `focalprompt` or `python -m focalprompt.cli`."""

from focalprompt.cli import main

if __name__ == '__main__':
    raise SystemExit(main())
