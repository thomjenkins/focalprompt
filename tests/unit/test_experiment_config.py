"""Experiment configuration copy, cost, suggestions, power preview, results header."""

import json
import subprocess
from math import comb, sqrt
from pathlib import Path

import pytest

from utils.experiment_config import (
    ABLATION_LOADING_TEMPLATE,
    BATCH_LOADING_TEMPLATE,
    COST_LINE_COUNTED,
    COST_LINE_FORMULA,
    EXACT_DISCLOSURE_TEMPLATE,
    POWER_FAIL,
    POWER_OK,
    RUN_HEADER_TEMPLATE,
    SAMPLED_DISCLOSURE_TEMPLATE,
    SUGGESTION_LABEL,
    SUGGESTION_TOOLTIP,
    TEMPERATURE_HELP,
    TEMPERATURE_HIGH,
    experiment_preview,
    format_ablation_loading,
    format_batch_loading,
    format_cost_line,
    format_permutation_disclosure,
    format_power_preview_line,
    format_run_header,
    model_call_count,
    suggested_sample_sizes,
    temperature_rejection,
)
from utils.permutation_test import (
    monte_carlo_pvalue_se,
    power_guardrail,
    power_guardrail_message,
    stochastic_temperature_message,
    design_test_type,
)
from utils.results_copy import render_ablation_results_html, render_run_header

REPO = Path(__file__).resolve().parents[2]


def test_temperature_help_and_high_copy():
    assert TEMPERATURE_HELP == (
        "Use the temperature your prompt runs at in production. Results describe "
        "the model's behaviour at this temperature only."
    )
    assert TEMPERATURE_HIGH == (
        "High temperature widens normal output variation, so subtle effects need "
        "more samples to detect."
    )


def test_client_side_rejects_temperature_at_or_below_zero():
    assert temperature_rejection(0) == stochastic_temperature_message(0)
    assert temperature_rejection(0.0) == stochastic_temperature_message(0.0)
    assert temperature_rejection(-0.1) == stochastic_temperature_message(-0.1)
    assert 'output stochasticity' in temperature_rejection(0)
    assert 'temperature must be > 0' in temperature_rejection(0)
    assert temperature_rejection(0.1) is None
    assert temperature_rejection(0.7) is None


def test_suggestion_chip_values_by_temperature_band():
    assert suggested_sample_sizes(0.3) == (10, 5)
    assert suggested_sample_sizes(0.49) == (10, 5)
    assert suggested_sample_sizes(0.5) == (10, 5)
    assert suggested_sample_sizes(1.0) == (10, 5)
    assert suggested_sample_sizes(1.01) == (15, 8)
    assert suggested_sample_sizes(1.5) == (15, 8)
    assert SUGGESTION_LABEL == "suggested for this temperature"
    assert SUGGESTION_TOOLTIP == (
        "A heuristic starting point. If results warn about power or sit near the "
        "threshold, increase ablated samples."
    )


def test_cost_line_arithmetic():
    assert model_call_count(10, 5, 3) == 25
    assert model_call_count(15, 8, 4) == 15 + 8 * 4
    assert format_cost_line(10, 5, foci_tagged=False) == (
        "This experiment will make 10 + 5 × n_foci model calls."
    )
    assert format_cost_line(10, 5, n_attributable_foci=3, foci_tagged=True) == (
        "This experiment will make 25 model calls."
    )
    assert '{n_calls}' in COST_LINE_COUNTED
    assert 'n_foci' in COST_LINE_FORMULA


def test_ablation_loading_copy_uses_live_experiment_settings():
    msg = format_ablation_loading(0.7, 10, 5, 3)
    assert msg == (
        "Running ablation analysis at temperature 0.7: "
        "10 baseline samples and 5 ablated samples "
        "for each of 3 foci (25 model calls). "
        "This may take several minutes."
    )
    assert '20 baseline' not in msg
    assert format_ablation_loading(0.7, 10, 5, 1).endswith(
        "for each of 1 focus (15 model calls). This may take several minutes."
    )
    assert '{n_calls}' in ABLATION_LOADING_TEMPLATE

    batch = format_batch_loading(4, 0.7, 10, 5)
    assert batch == (
        "Running batch analysis on 4 pairs at temperature 0.7: "
        "10 baseline samples and 5 ablated samples per focus per pair. "
        "This may take a long time."
    )
    assert 'pair at temperature' in format_batch_loading(1, 0.7, 10, 5)
    assert 'pairs at temperature' not in format_batch_loading(1, 0.7, 10, 5)
    assert '{n_pairs}' in BATCH_LOADING_TEMPLATE


def test_exact_vs_sampled_disclosure_switches_at_enumeration_budget():
    exact = format_permutation_disclosure(10, 5, 10000)
    assert exact == EXACT_DISCLOSURE_TEMPLATE.format(n_assignments=f'{comb(15, 5):,}')
    assert 'exact test' in exact
    assert design_test_type(10, 5) == 'exact'

    sampled = format_permutation_disclosure(15, 8, 10000)
    se = monte_carlo_pvalue_se(0.05, 10000)
    assert sampled == SAMPLED_DISCLOSURE_TEMPLATE.format(se=f'{se:.3f}')
    assert sampled == f"Significance: 10,000 sampled permutations (p-value margin ~±{se:.3f})"
    assert design_test_type(15, 8) == 'sampled'
    assert se == pytest.approx(sqrt(0.05 * 0.95 / 10000))
    assert f'{se:.3f}' == '0.002'


def test_power_preview_uses_shared_guardrail():
    ok = power_guardrail(10, 5, n_foci=2, alpha=0.05)
    assert ok['can_reach_significance'] is True
    assert format_power_preview_line(10, 5, 2) == POWER_OK
    assert power_guardrail_message(10, 5, 2) is None

    fail = power_guardrail(2, 2, n_foci=3, alpha=0.05)
    assert fail['can_reach_significance'] is False
    assert format_power_preview_line(2, 2, 3) == POWER_FAIL.format(n_foci=3)
    msg = power_guardrail_message(2, 2, 3)
    assert msg is not None
    assert fail['min_p'] == pytest.approx(1 / 6)


def test_power_guardrail_message_agrees_with_pure_function():
    for n_b, n_a, n_f in [(10, 5, 8), (2, 2, 3), (15, 8, 4), (10, 5, 0)]:
        info = power_guardrail(n_b, n_a, n_f)
        msg = power_guardrail_message(n_b, n_a, n_f)
        if info['can_reach_significance'] is False:
            assert msg is not None
        else:
            assert msg is None


def test_run_header_persists_config():
    header = format_run_header(0.7, 10, 5, 'exact')
    assert header == "Run at temperature 0.7, 10+5 samples per focus, exact test."
    assert header == RUN_HEADER_TEMPLATE.format(
        t='0.7', n_baseline=10, n_ablated=5, test_type='exact'
    )
    sampled = format_run_header(1.5, 15, 8, 'sampled')
    assert sampled == "Run at temperature 1.5, 15+8 samples per focus, sampled test."


def test_results_html_renders_persisted_config():
    html = render_ablation_results_html({
        'temperature': 0.7,
        'n_baseline': 10,
        'n_ablated': 5,
        'test_type': 'exact',
        'alpha': 0.05,
        'ablation_results': [],
        'influence_scores': [],
    })
    assert "Run at temperature 0.7, 10+5 samples per focus, exact test." in html
    assert 'results-run-header' in html
    assert render_run_header({
        'temperature': 1.2,
        'n_baseline': 15,
        'n_ablated': 8,
        'test_type': 'sampled',
    }) == (
        '<p class="results-run-header">'
        'Run at temperature 1.2, 15+8 samples per focus, sampled test.'
        '</p>'
    )


def test_preview_payload_includes_high_temperature_flag():
    cool = experiment_preview(0.7, 10, 5, foci=[{'focus': 'A'}])
    assert cool['high_temperature'] is False
    assert cool['cost_line'] == "This experiment will make 15 model calls."
    hot = experiment_preview(1.0, 10, 5, foci=[{'focus': 'A'}])
    assert hot['high_temperature'] is True


def test_js_power_guardrail_matches_python():
    js = REPO / 'static' / 'js' / 'experiment_config.js'
    script = (
        "const m = require(%s); "
        "const cases = [[10,5,8],[2,2,3],[15,8,4],[10,5,0]]; "
        "console.log(JSON.stringify(cases.map(([b,a,f]) => {"
        "  const g = m.powerGuardrail(b,a,f);"
        "  return {min_p: g.min_p, can: g.can_reach_significance, type: g.test_type};"
        "})));"
    ) % json.dumps(str(js))
    proc = subprocess.run(
        ['node', '-e', script],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    js_out = json.loads(proc.stdout)
    cases = [(10, 5, 8), (2, 2, 3), (15, 8, 4), (10, 5, 0)]
    for (n_b, n_a, n_f), row in zip(cases, js_out):
        info = power_guardrail(n_b, n_a, n_f)
        assert row['can'] == info['can_reach_significance']
        assert row['type'] == info['test_type']
        assert row['min_p'] == pytest.approx(info['min_p'], rel=1e-9)


def test_js_cost_and_suggestion_match_python():
    js = REPO / 'static' / 'js' / 'experiment_config.js'
    script = (
        "const m = require(%s); "
        "console.log(JSON.stringify({"
        "  calls: m.modelCallCount(10,5,3),"
        "  costTagged: m.formatCostLine(10,5,3,true),"
        "  costOpen: m.formatCostLine(10,5,0,false),"
        "  loadAbl: m.formatAblationLoading(0.7,10,5,3),"
        "  loadBatch: m.formatBatchLoading(4,0.7,10,5),"
        "  s03: m.suggestedSampleSizes(0.3),"
        "  s07: m.suggestedSampleSizes(0.7),"
        "  s10: m.suggestedSampleSizes(1.0),"
        "  s11: m.suggestedSampleSizes(1.1),"
        "  rej: m.temperatureRejection(0),"
        "  discExact: m.formatPermutationDisclosure(10,5),"
        "  discMc: m.formatPermutationDisclosure(15,8)"
        "}));"
    ) % json.dumps(str(js))
    proc = subprocess.run(
        ['node', '-e', script],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    out = json.loads(proc.stdout)
    assert out['calls'] == 25
    assert out['costTagged'] == format_cost_line(10, 5, 3, foci_tagged=True)
    assert out['costOpen'] == format_cost_line(10, 5, foci_tagged=False)
    assert out['loadAbl'] == format_ablation_loading(0.7, 10, 5, 3)
    assert out['loadBatch'] == format_batch_loading(4, 0.7, 10, 5)
    assert out['s03'] == {'n_baseline': 10, 'n_ablated': 5}
    assert out['s07'] == {'n_baseline': 10, 'n_ablated': 5}
    assert out['s10'] == {'n_baseline': 10, 'n_ablated': 5}
    assert out['s11'] == {'n_baseline': 15, 'n_ablated': 8}
    assert 'temperature must be > 0' in out['rej']
    assert out['discExact'] == format_permutation_disclosure(10, 5)
    assert out['discMc'] == format_permutation_disclosure(15, 8)
