#!/usr/bin/env python3
"""Focal Prompt CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _add_inference_args(p: argparse.ArgumentParser) -> None:
    p.add_argument('--model', default='gpt-4o-mini')
    p.add_argument('--provider', default='openai')
    p.add_argument('--backend', default=None, help='vercel_gateway | direct | openai_compatible | ollama')
    p.add_argument('--api-key', default=None)
    p.add_argument('--base-url', default=None)
    p.add_argument('-o', '--output-file', default=None)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog='focalprompt',
        description='Tools for studying how AI systems allocate attention and respond to context.',
    )
    sub = parser.add_subparsers(dest='cmd', required=True)

    p_ui = sub.add_parser('ui', help='Start the local web UI')
    p_ui.add_argument('--host', default='127.0.0.1')
    p_ui.add_argument('--port', type=int, default=5001)

    p_foci = sub.add_parser('foci', help='Detect foci in a prompt file')
    p_foci.add_argument('prompt')
    _add_inference_args(p_foci)

    p_assess = sub.add_parser('assess', help='Model-assessed focus distribution')
    p_assess.add_argument('prompt')
    p_assess.add_argument('completion', help='Model output to score against foci')
    p_assess.add_argument('--foci-json', default=None)
    _add_inference_args(p_assess)

    p_ablate = sub.add_parser('ablate', help='Leave-one-focus-out perturbation analysis')
    p_ablate.add_argument('prompt')
    p_ablate.add_argument('--foci-json', required=True)
    p_ablate.add_argument('--n-baseline', type=int, default=10)
    p_ablate.add_argument('--n-ablated', type=int, default=5)
    p_ablate.add_argument('--temperature', type=float, default=0.7)
    p_ablate.add_argument('--seed', type=int, default=None)
    _add_inference_args(p_ablate)

    p_analyze = sub.add_parser('analyze', help='End-to-end: foci + optional assess + ablate')
    p_analyze.add_argument('prompt')
    p_analyze.add_argument('--completion', default=None)
    p_analyze.add_argument('--foci-json', default=None)
    p_analyze.add_argument('--n-baseline', type=int, default=10)
    p_analyze.add_argument('--n-ablated', type=int, default=5)
    p_analyze.add_argument('--temperature', type=float, default=0.7)
    p_analyze.add_argument('--seed', type=int, default=None)
    p_analyze.add_argument('--skip-assess', action='store_true')
    p_analyze.add_argument('--skip-ablation', action='store_true')
    _add_inference_args(p_analyze)

    sub.add_parser('mcp', help='Start the Model Context Protocol server (stdio)')

    args = parser.parse_args(argv)

    if args.cmd == 'ui':
        import os
        os.environ.setdefault('HOST', args.host)
        os.environ.setdefault('PORT', str(args.port))
        from app_new import app
        from waitress import serve
        print(f'Focal Prompt UI → http://{args.host}:{args.port}/', file=sys.stderr)
        serve(app, host=args.host, port=args.port)
        return 0

    if args.cmd == 'mcp':
        try:
            from focalprompt.mcp_server import run_stdio
        except ImportError:
            print(
                'MCP support is not installed. Run: pip install focalprompt[mcp]',
                file=sys.stderr,
            )
            return 1
        run_stdio()
        return 0

    from focalprompt.api import analyze, assess_focus, detect_foci, ablate, save_result

    inf = dict(
        model=args.model,
        provider=args.provider,
        backend=args.backend,
        api_key=args.api_key,
        base_url=args.base_url,
    )

    if args.cmd == 'foci':
        result = detect_foci(args.prompt, **inf)
    elif args.cmd == 'assess':
        foci = json.loads(Path(args.foci_json).read_text()) if args.foci_json else None
        if isinstance(foci, dict) and 'foci' in foci:
            foci = foci['foci']
        result = assess_focus(args.prompt, Path(args.completion).read_text() if Path(args.completion).exists() else args.completion, foci, **inf)
    elif args.cmd == 'ablate':
        foci = json.loads(Path(args.foci_json).read_text())
        if isinstance(foci, dict) and 'foci' in foci:
            foci = foci['foci']
        result = ablate(
            args.prompt, foci,
            n_baseline=args.n_baseline, n_ablated=args.n_ablated,
            temperature=args.temperature, permutation_seed=args.seed, **inf,
        )
    elif args.cmd == 'analyze':
        foci = None
        if args.foci_json:
            foci = json.loads(Path(args.foci_json).read_text())
            if isinstance(foci, dict) and 'foci' in foci:
                foci = foci['foci']
        completion = None
        if args.completion:
            completion = Path(args.completion).read_text() if Path(args.completion).exists() else args.completion
        result = analyze(
            args.prompt,
            output=completion,
            foci=foci,
            n_baseline=args.n_baseline,
            n_ablated=args.n_ablated,
            temperature=args.temperature,
            permutation_seed=args.seed,
            run_assess=not args.skip_assess,
            run_ablation=not args.skip_ablation,
            **inf,
        )
    else:
        parser.error('unknown command')
        return 2

    text = json.dumps(result, indent=2, default=str)
    if getattr(args, 'output_file', None):
        save_result(result, args.output_file)
        print(f'Wrote {args.output_file}', file=sys.stderr)
    else:
        print(text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
