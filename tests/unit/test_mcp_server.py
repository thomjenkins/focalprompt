"""MCP server smoke tests (requires optional ``focalprompt[mcp]``)."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

pytest.importorskip('mcp')

from mcp.server.fastmcp.exceptions import ToolError

from focalprompt.mcp_server import create_mcp_server


@pytest.fixture
def server():
    return create_mcp_server()


@pytest.mark.unit
def test_list_tools(server):
    async def _list():
        return await server.list_tools()

    tools = asyncio.run(_list())
    names = {t.name for t in tools}
    assert names == {'extract_foci', 'report_focus', 'ablation_analysis'}


@pytest.mark.unit
def test_tool_descriptions_cover_interpretation_caveats(server):
    async def _list():
        return await server.list_tools()

    tools = {t.name: (t.description or '') for t in asyncio.run(_list())}
    assert 'self-report' in tools['report_focus'].lower() or 'self-assessment' in tools['report_focus'].lower()
    assert 'not' in tools['report_focus'].lower() and 'attention' in tools['report_focus'].lower()
    assert 'token' in tools['ablation_analysis'].lower() or 'expensive' in tools['ablation_analysis'].lower()
    assert 'not' in tools['ablation_analysis'].lower() and 'delete' in tools['ablation_analysis'].lower()


@pytest.mark.unit
def test_extract_foci_returns_schema(server):
    sample = {
        'foci': [
            {
                'focus': 'Role',
                'prompt_section': 'You are a helpful assistant.',
                'verified': True,
                'char_start': 0,
                'char_end': 31,
            }
        ],
        'rejected_proposals': [],
        'coverage': {'coverage_percent': 100},
        'quality': {'accepted_count': 1, 'rejected_count': 0},
        'usage': {'prompt_tokens': 10, 'completion_tokens': 20, 'total_tokens': 30},
    }

    async def _call():
        with patch('focalprompt.mcp_server.detect_foci', return_value=sample) as mock_detect:
            result = await server._tool_manager.call_tool(
                'extract_foci',
                {'prompt': 'You are a helpful assistant.', 'model': 'gpt-4o-mini'},
            )
            mock_detect.assert_called_once()
            kwargs = mock_detect.call_args.kwargs
            assert kwargs['model'] == 'gpt-4o-mini'
            assert kwargs['backend'] is None or isinstance(kwargs['backend'], str)
            return result

    out = asyncio.run(_call())
    assert out['foci'][0]['verified'] is True
    assert out['foci'][0]['char_start'] == 0


@pytest.mark.unit
def test_missing_credentials_returns_clear_message(server):
    async def _call():
        with patch(
            'focalprompt.mcp_server.detect_foci',
            side_effect=ValueError(
                'No inference credentials found. Set AI_GATEWAY_API_KEY (recommended), '
                'or a provider key (OPENAI_API_KEY / ANTHROPIC_API_KEY / …), '
                'or FOCALPROMPT_BASE_URL for a local OpenAI-compatible endpoint.'
            ),
        ):
            with pytest.raises(ToolError) as exc:
                await server._tool_manager.call_tool(
                    'extract_foci',
                    {'prompt': 'hello', 'model': 'gpt-4o-mini'},
                )
            return str(exc.value)

    message = asyncio.run(_call())
    assert 'AI_GATEWAY_API_KEY' in message
    assert 'Traceback' not in message


@pytest.mark.unit
def test_report_focus_wraps_assess_focus(server):
    sample = {
        'foci': [{'focus': 'Role', 'score': 55.0, 'explanation': 'x'}],
        'overall_summary': 'ok',
    }

    async def _call():
        with patch('focalprompt.mcp_server.assess_focus', return_value=sample) as mock_assess:
            result = await server._tool_manager.call_tool(
                'report_focus',
                {
                    'prompt': 'You are x.',
                    'completion': 'Hello',
                    'model': 'gpt-4o-mini',
                },
            )
            mock_assess.assert_called_once()
            return result

    out = asyncio.run(_call())
    assert out['foci'][0]['score'] == 55.0


@pytest.mark.unit
def test_ablation_analysis_returns_influence_scores(server):
    sample = {
        'influence_scores': [
            {
                'focus': 'Role',
                'q_value': 0.01,
                'p_value': 0.005,
                'standardized_effect': 2.4,
                't_obs': 0.12,
                'is_significant': True,
            }
        ],
        'alpha': 0.05,
    }

    async def _call():
        with patch('focalprompt.mcp_server.ablate', return_value=sample) as mock_ablate:
            result = await server._tool_manager.call_tool(
                'ablation_analysis',
                {
                    'prompt': 'You are x.',
                    'model': 'gpt-4o-mini',
                    'options': {'foci': [{'focus': 'Role', 'prompt_section': 'You are x.'}]},
                },
            )
            mock_ablate.assert_called_once()
            return result

    out = asyncio.run(_call())
    row = out['influence_scores'][0]
    assert row['q_value'] == 0.01
    assert row['standardized_effect'] == 2.4
