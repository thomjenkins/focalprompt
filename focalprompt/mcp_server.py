#!/usr/bin/env python3
"""MCP server exposing FocalPrompt research tools over stdio (FastMCP)."""

from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, List, Mapping, Optional

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from focalprompt.api import ablate, assess_focus, detect_foci

EXTRACT_FOCI_DESCRIPTION = (
    'Detect source-grounded foci in a prompt with verified character spans. '
    'Fast and safe to call iteratively while refining a prompt.'
)

REPORT_FOCUS_DESCRIPTION = (
    "Lens A — reported focus: the model's self-assessment of how a single "
    'completion attended to each focus (scores and explanations). '
    'This is model self-report from an LLM judge, NOT transformer attention '
    'weights or mechanistic interpretability.'
)

ABLATION_DESCRIPTION = (
    'Lens B — perturbation sensitivity: leave-one-focus-out ablation with a '
    'permutation test and Benjamini–Hochberg FDR correction per focus. '
    'WARNING: makes many inference calls (baseline + ablated samples per focus); '
    'slow and token-expensive on your API key. '
    'A non-significant ablation is NOT permission to delete that text — it '
    'measures behavioural sensitivity in embedding space, not correctness, '
    'quality, or real-world importance.'
)

_CREDENTIAL_MARKERS = (
    'No inference credentials found',
    'AI_GATEWAY_API_KEY',
    'FOCALPROMPT_BASE_URL',
)

_ABLATION_HEARTBEAT_SEC = 5.0


def _inference_kwargs(
    model: str,
    *,
    provider: str = 'openai',
    backend: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Match ``focalprompt.cli`` inference resolution (env + explicit overrides)."""
    return {
        'model': model,
        'provider': provider,
        'backend': backend if backend is not None else os.getenv('FOCALPROMPT_BACKEND'),
        'api_key': api_key,
        'base_url': base_url if base_url is not None else os.getenv('FOCALPROMPT_BASE_URL'),
    }


def _merge_options_inference(model: str, options: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    opts = dict(options or {})
    return _inference_kwargs(
        model,
        provider=str(opts.get('provider') or 'openai'),
        backend=opts.get('backend'),
        api_key=opts.get('api_key'),
        base_url=opts.get('base_url'),
    )


def _raise_tool_error(exc: BaseException) -> None:
    """Surface credential and validation failures without a stack trace."""
    message = str(exc).strip() or repr(exc)
    if any(marker in message for marker in _CREDENTIAL_MARKERS):
        raise ToolError(message) from None
    if isinstance(exc, ValueError):
        raise ToolError(message) from None
    raise ToolError(message) from None


async def _ablation_heartbeat(ctx: Context, *, interval: float = _ABLATION_HEARTBEAT_SEC) -> None:
    """Log progress while a blocking ablation run executes."""
    step = 0
    messages = (
        'Sampling baseline completions…',
        'Generating ablated completions per focus…',
        'Embedding outputs and running permutation tests…',
        'Applying Benjamini–Hochberg FDR correction…',
    )
    try:
        while True:
            await asyncio.sleep(interval)
            step += 1
            msg = messages[min(step - 1, len(messages) - 1)]
            await ctx.info(
                f'Ablation analysis in progress ({step * interval:.0f}s): {msg} '
                '(many LLM calls — still running on your API key).'
            )
            await ctx.report_progress(step, total=None, message=msg)
    except asyncio.CancelledError:
        return


def create_mcp_server() -> FastMCP:
    """Build and register FocalPrompt MCP tools."""
    server = FastMCP('focalprompt')

    @server.tool(name='extract_foci', description=EXTRACT_FOCI_DESCRIPTION)
    async def extract_foci_tool(prompt: str, model: str = 'gpt-4o-mini') -> Dict[str, Any]:
        try:
            return detect_foci(prompt, **_inference_kwargs(model))
        except Exception as exc:
            _raise_tool_error(exc)
            raise AssertionError('unreachable')

    @server.tool(name='report_focus', description=REPORT_FOCUS_DESCRIPTION)
    async def report_focus_tool(
        prompt: str,
        completion: str,
        model: str = 'gpt-4o-mini',
    ) -> Dict[str, Any]:
        try:
            return assess_focus(
                prompt,
                completion,
                foci=None,
                **_inference_kwargs(model),
            )
        except Exception as exc:
            _raise_tool_error(exc)
            raise AssertionError('unreachable')

    @server.tool(name='ablation_analysis', description=ABLATION_DESCRIPTION)
    async def ablation_analysis_tool(
        prompt: str,
        model: str = 'gpt-4o-mini',
        options: Optional[Dict[str, Any]] = None,
        ctx: Context = None,  # type: ignore[assignment]
    ) -> Dict[str, Any]:
        opts = dict(options or {})
        inf = _merge_options_inference(model, opts)
        foci: Optional[List[Dict[str, Any]]] = opts.get('foci')
        if foci is None and opts.get('foci_json'):
            import json

            raw = json.loads(str(opts['foci_json']))
            foci = raw.get('foci') if isinstance(raw, dict) else raw
        if not foci:
            try:
                detected = detect_foci(prompt, **inf)
                foci = detected.get('foci') or []
            except Exception as exc:
                _raise_tool_error(exc)
                raise AssertionError('unreachable')
        if not foci:
            raise ToolError(
                'No attributable foci available. Run extract_foci first or pass '
                'options.foci with verified spans.'
            )

        n_baseline = int(opts.get('n_baseline', opts.get('num_samples', 10)))
        n_ablated = int(opts.get('n_ablated', 5))
        temperature = float(opts.get('temperature', 0.7))
        permutation_seed = opts.get('permutation_seed', opts.get('seed'))

        if ctx is not None:
            await ctx.info(
                f'Starting ablation analysis ({len(foci)} foci, '
                f'n_baseline={n_baseline}, n_ablated={n_ablated}). '
                'This will make many inference calls on your API key.'
            )

        heartbeat: asyncio.Task[None] | None = None
        if ctx is not None:
            heartbeat = asyncio.create_task(_ablation_heartbeat(ctx))

        try:
            result = await asyncio.to_thread(
                ablate,
                prompt,
                foci,
                n_baseline=n_baseline,
                n_ablated=n_ablated,
                temperature=temperature,
                permutation_seed=permutation_seed,
                **inf,
            )
        except Exception as exc:
            _raise_tool_error(exc)
            raise AssertionError('unreachable')
        finally:
            if heartbeat is not None:
                heartbeat.cancel()
                try:
                    await heartbeat
                except asyncio.CancelledError:
                    pass

        if ctx is not None:
            await ctx.info('Ablation analysis complete.')

        return result

    return server


def run_stdio() -> None:
    """Run the MCP server on stdio (default transport)."""
    create_mcp_server().run(transport='stdio')
