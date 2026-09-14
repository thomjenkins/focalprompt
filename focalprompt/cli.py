#!/usr/bin/env python3
"""Focal Prompt CLI."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


_STARTUP_LOGO = (
    '██████▄▄▄      ▄▄▄██████',
    '█       ▀██▄▄██▀       █',
    '██        ▄██▄        ██',
    '▀█       ██▄▄██       █▀',
    ' ██   ▄███▀▀▀▀███▄   ██ ',
    '  ▀██▀▀ █  ▄▄  █ ▀▀██▀  ',
    '  ▄██▄▄ █  ▀▀  █ ▄▄██▄  ',
    ' ██   ▀███▄▄▄▄███▀   ██ ',
    '▄█       ██▀▀██       █▄',
    '██        ▀██▀        ██',
    '█       ▄██▀▀██▄       █',
    '██████▀▀▀      ▀▀▀██████',
)


def print_startup_banner() -> None:
    """Render the pixel mark on terminals; keep redirected logs plain."""
    stream = sys.stderr
    if not stream.isatty() or os.environ.get('TERM') == 'dumb':
        print('\nFocal Prompt\n', file=stream)
        return
    try:
        '█▀▄'.encode(stream.encoding or 'utf-8')
    except (UnicodeEncodeError, LookupError):
        print('\nFocal Prompt\n', file=stream)
        return

    color = 'NO_COLOR' not in os.environ
    reset = '\033[0m' if color else ''
    heading = '\033[1;38;2;230;218;177m' if color else ''
    muted = '\033[38;2;156;163;175m' if color else ''
    lines = [f'\n  {heading}Focal Prompt{reset}\n']
    stops = ((226, 85, 190), (139, 92, 246), (73, 190, 214))
    for y, row in enumerate(_STARTUP_LOGO):
        pixels = ['  ']
        for x, char in enumerate(row):
            if color and char != ' ':
                position = (x + y) / 17
                segment = min(int(position), 1)
                fraction = position - segment
                rgb = tuple(
                    round(a + (b - a) * fraction)
                    for a, b in zip(stops[segment], stops[segment + 1])
                )
                pixels.append(f'\033[38;2;{rgb[0]};{rgb[1]};{rgb[2]}m')
            pixels.append(char)
        lines.append(''.join(pixels) + reset)
    lines.append(f'\n  {muted}Local analysis lab{reset}\n')
    print('\n'.join(lines), file=stream)


def _add_inference_args(p: argparse.ArgumentParser) -> None:
    p.add_argument('--model', default='gpt-4o-mini')
    p.add_argument('--provider', default='openai')
    p.add_argument('--backend', default=None, help='vercel_gateway | direct | openai_compatible | ollama')
    p.add_argument('--api-key', default=None)
    p.add_argument('--base-url', default=None)
    p.add_argument('-o', '--output-file', default=None)


def _add_prompt_or_scenario(p: argparse.ArgumentParser) -> None:
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument('prompt', nargs='?', help='Legacy prompt text or file')
    source.add_argument(
        '--scenario',
        metavar='FILE',
        help='Versioned inference scenario JSON file',
    )


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
    _add_prompt_or_scenario(p_foci)
    _add_inference_args(p_foci)

    p_assess = sub.add_parser('assess', help='Model-assessed focus distribution')
    p_assess.add_argument('prompt', nargs='?', help='Legacy prompt text or file')
    p_assess.add_argument('--scenario', metavar='FILE', help='Versioned inference scenario JSON file')
    p_assess.add_argument('completion', help='Model output to score against foci')
    p_assess.add_argument('--foci-json', default=None)
    _add_inference_args(p_assess)

    p_ablate = sub.add_parser('ablate', help='Leave-one-focus-out perturbation analysis')
    _add_prompt_or_scenario(p_ablate)
    p_ablate.add_argument('--foci-json', required=True)
    p_ablate.add_argument('--n-baseline', type=int, default=10)
    p_ablate.add_argument('--n-ablated', type=int, default=5)
    p_ablate.add_argument('--temperature', type=float, default=0.7)
    p_ablate.add_argument('--seed', type=int, default=None)
    _add_inference_args(p_ablate)

    p_analyze = sub.add_parser('analyze', help='End-to-end: foci + optional assess + ablate')
    _add_prompt_or_scenario(p_analyze)
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

    arguments = sys.argv[1:] if argv is None else argv
    if arguments and arguments[0] == 'assess':
        # Parse this command on its own so options can separate its positionals.
        args = p_assess.parse_intermixed_args(arguments[1:])
        args.cmd = 'assess'
        if (args.prompt is None) == (args.scenario is None):
            p_assess.error('provide exactly one of prompt or --scenario')
    else:
        args = parser.parse_args(arguments)

    if args.cmd == 'ui':
        os.environ.setdefault('HOST', args.host)
        os.environ.setdefault('PORT', str(args.port))
        from app_new import app, open_lab_in_chrome
        from waitress import serve
        print_startup_banner()
        display_host = args.host
        if ':' in display_host and not display_host.startswith('['):
            display_host = f'[{display_host}]'
        print(f'Focal Prompt UI → http://{display_host}:{args.port}/', file=sys.stderr)
        open_lab_in_chrome(args.host, args.port)
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
    scenario_kw = {'scenario': args.scenario} if getattr(args, 'scenario', None) else {}
    prompt_arg = None if scenario_kw else args.prompt

    if args.cmd == 'foci':
        result = detect_foci(prompt_arg, **scenario_kw, **inf)
    elif args.cmd == 'assess':
        foci = json.loads(Path(args.foci_json).read_text()) if args.foci_json else None
        if isinstance(foci, dict) and 'foci' in foci:
            foci = foci['foci']
        result = assess_focus(
            prompt_arg,
            Path(args.completion).read_text() if Path(args.completion).exists() else args.completion,
            foci,
            **scenario_kw,
            **inf,
        )
    elif args.cmd == 'ablate':
        foci = json.loads(Path(args.foci_json).read_text())
        if isinstance(foci, dict) and 'foci' in foci:
            foci = foci['foci']
        result = ablate(
            prompt_arg, foci, **scenario_kw,
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
            prompt_arg,
            **scenario_kw,
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
