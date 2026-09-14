#!/usr/bin/env python3
"""Workspace export/import UI wiring checks."""

from pathlib import Path


REPO = Path(__file__).resolve().parents[2]


def test_index_includes_workspace_buttons():
    html = (REPO / 'templates' / 'index.html').read_text(encoding='utf-8')
    assert 'export-workspace-btn' in html
    assert 'import-workspace-btn' in html
    assert 'import-workspace-input' in html
    assert 'Export workspace' in html
    assert 'Import workspace' in html


def test_css_workspace_actions_layout():
    css = (REPO / 'static' / 'css' / 'style.css').read_text(encoding='utf-8')
    assert '.workspace-session-actions' in css


def test_ordered_scenario_editor_and_contract_controls_are_present():
    html = (REPO / 'templates' / 'index.html').read_text(encoding='utf-8')
    js = (REPO / 'static' / 'js' / 'app.js').read_text(encoding='utf-8')
    css = (REPO / 'static' / 'css' / 'style.css').read_text(encoding='utf-8')
    for marker in (
        'scenario-messages', 'scenario-message-card', 'scenario-role',
        'scenario-analysis-mode', 'scenario-input-name', 'scenario-move-up',
        'scenario-move-down', 'scenario-delete', 'scenario-contract-schema',
    ):
        assert marker in html
    assert 'scenarioRequestPayload' in js
    assert 'scenarioInputNames' in js
    assert 'scenario: getBatchScenario()' in js
    assert '.scenario-message-card' in css


def test_scenario_ui_uses_named_inputs_and_scenario_native_agent_builder():
    html = (REPO / 'templates' / 'index.html').read_text(encoding='utf-8')
    js = (REPO / 'static' / 'js' / 'app.js').read_text(encoding='utf-8')
    assert 'manual-primary-input-group' in html
    assert 'batch-detect-dynamic-foci-btn' not in html
    assert 'Mark as Dynamic' not in js
    assert 'scenarioWithAgentInput' in js
    assert 'scenario: buildData.constructed_scenario' in js
    assert 'constructed_prompt: buildData.constructed_prompt' not in js
