"""Contract checks for insight-led experiment results report."""

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HTML = (REPO / 'templates' / 'index.html').read_text(encoding='utf-8')
APP_JS = (REPO / 'static' / 'js' / 'app.js').read_text(encoding='utf-8')
REPORT_JS = (REPO / 'static' / 'js' / 'results_report.js').read_text(encoding='utf-8')
METRICS_JS = (REPO / 'static' / 'js' / 'insight_metrics.js').read_text(encoding='utf-8')
CSS = (REPO / 'static' / 'css' / 'style.css').read_text(encoding='utf-8')
EXP_HTML = (REPO / 'templates' / 'experiment.html').read_text(encoding='utf-8')


def test_insight_scripts_loaded_before_app():
    assert 'js/insight_metrics.js' in HTML
    assert 'js/results_report.js' in HTML
    im = HTML.index('insight_metrics.js')
    rr = HTML.index('results_report.js')
    app = HTML.index('js/app.js')
    assert im < rr < app


def test_app_mounts_insight_report():
    assert 'FocalPromptReport.render' in APP_JS
    assert 'FocalPromptReport.refresh' in APP_JS
    assert 'window.assessmentFoci' in APP_JS


def test_report_views_and_inspector_exist():
    for token in (
        "overview",
        "focus-map",
        "stability",
        "order",
        "samples",
        "raw",
        "fp-inspector",
        "fp-dumbbell",
        "fp-focus-map",
        "fp-anatomy",
        "What to test next",
    ):
        assert token in REPORT_JS


def test_metrics_js_mirrors_key_thresholds():
    assert 'high_revealed: 12' in METRICS_JS or 'high_revealed: 12.0' in METRICS_JS
    assert 'claimed_but_inert' in METRICS_JS
    assert 'hidden_driver' in METRICS_JS
    assert 'FocalPromptInsightMetrics' in METRICS_JS


def test_report_css_present():
    assert '.fp-report' in CSS
    assert '.fp-status-strip' in CSS
    assert '.fp-inspector' in CSS


def test_experiment_index_shows_findings():
    assert 'exp-card-finding' in EXP_HTML
    assert 'principal_finding' in EXP_HTML
    assert 'exp-card-signals' in EXP_HTML


def test_order_tab_conditionally_hidden_in_js():
    # Order nav is omitted when hasOrderData is false
    assert 'hasOrderData' in REPORT_JS


def test_experiment_c_not_a_separate_lab_card():
    assert 'lab-jump-nav' in HTML
    assert 'href="#lab-results-report"' in HTML
    # Visible Exp C card removed; hidden mounts remain for API paint/explain
    assert 'id="experiment-c-section"' in HTML
    assert 'Experiment C — Reported vs revealed</h2>' not in HTML
    assert 'experiment-c-pointer' not in HTML
    assert '7. Focus order sensitivity' in HTML
    assert '8. Task quality evaluation' in HTML


def test_report_owns_concordance():
    assert 'renderConcordancePanel' in REPORT_JS or 'fp-concordance-panel' in REPORT_JS
    assert 'refresh-concordance' in REPORT_JS
    assert 'Full concordance table' in REPORT_JS or 'Concordance table' in REPORT_JS
    assert 'window.refreshExperimentCComparison' in APP_JS
