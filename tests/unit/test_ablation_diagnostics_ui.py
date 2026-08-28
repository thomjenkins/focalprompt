#!/usr/bin/env python3
"""UI-facing copy / serialization checks for new ablation diagnostics."""

from pathlib import Path

from utils.results_copy import COPY


REPO = Path(__file__).resolve().parents[2]


def test_copy_includes_baseline_and_dynamics_strings():
    assert 'BASELINE_STABILITY_TITLE' in COPY
    assert 'BASELINE_STABILITY_DISCLAIMER' in COPY
    assert 'REPORTED_FOCUS_DYNAMICS_TITLE' in COPY
    assert 'REPORTED_FOCUS_DYNAMICS_DISCLAIMER' in COPY
    assert 'REPORTED_FOCUS_DYNAMICS_BUTTON' in COPY
    assert 'FOCUS_ORDER_TITLE' in COPY
    assert 'FOCUS_ORDER_DISCLAIMER' in COPY
    assert 'mechanistic' in COPY['FOCUS_ORDER_DISCLAIMER'].lower()
    assert 'permutation' in COPY['BASELINE_STABILITY_DISCLAIMER'].lower() or 'significance' in COPY['BASELINE_STABILITY_DISCLAIMER'].lower()


def test_results_copy_js_renders_new_panels():
    js = (REPO / 'static' / 'js' / 'results_copy.js').read_text(encoding='utf-8')
    assert 'renderBaselineStabilityHtml' in js
    assert 'renderReportedFocusDynamicsHtml' in js
    assert 'renderFocusOrderSensitivityHtml' in js
    assert 'baseline_stability' in js
    assert 'run-reported-focus-dynamics-btn' in js
    assert 'not a significance test' in js.lower() or 'not a significance' in js.lower()


def test_app_js_binds_reported_focus_dynamics():
    js = (REPO / 'static' / 'js' / 'app.js').read_text(encoding='utf-8')
    assert 'bindReportedFocusDynamicsHandlers' in js
    assert '/api/ablation-reported-focus-dynamics' in js
    assert '/api/focus-order-sensitivity' in js
    assert 'refreshFocusOrderControls' in js


def test_ablation_route_registers_dynamics_endpoint():
    routes = (REPO / 'routes' / 'ablation_routes.py').read_text(encoding='utf-8')
    assert 'ablation-reported-focus-dynamics' in routes
    assert 'AssessmentService' in routes


def test_order_sensitivity_route_registered():
    routes = (REPO / 'routes' / 'order_sensitivity_routes.py').read_text(encoding='utf-8')
    assert 'focus-order-sensitivity' in routes
    assert 'OrderSensitivityService' in routes
