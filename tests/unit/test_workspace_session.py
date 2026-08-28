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


def test_app_js_workspace_session_helpers():
    js = (REPO / 'static' / 'js' / 'app.js').read_text(encoding='utf-8')
    assert 'WORKSPACE_SESSION_VERSION' in js
    assert 'collectWorkspaceSession' in js
    assert 'restoreWorkspaceSession' in js
    assert 'focalprompt_workspace' in js
    assert 'lastAssessmentApiPayload' in js
    assert 'restorePromptAnalysisWorkspace' in js
    assert 'skipExperimentCRefresh' in js


def test_css_workspace_actions_layout():
    css = (REPO / 'static' / 'css' / 'style.css').read_text(encoding='utf-8')
    assert '.workspace-session-actions' in css
