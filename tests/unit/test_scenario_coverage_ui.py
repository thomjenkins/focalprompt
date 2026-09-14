"""Execute coverage rendering and statistics against multiple scenario messages."""

import json
import re
import subprocess
from pathlib import Path

import pytest


APP = (Path(__file__).resolve().parents[2] / 'static/js/app.js').read_text()
FUNCTIONS = '\n'.join(
    re.search(r'^function ' + name + r'\([^\n]*\) \{.*?^\}', APP, re.M | re.S).group()
    for name in (
        'focusSpansOf', 'normalizeFocusClient', 'computeClientCoverage',
        'clientSpanUnion', 'intervalsIntersectionLen', 'computeClientOverlaps',
        'getScenarioCoverageData', 'renderCoverageMessage',
        'updateCoverageVisualization', 'updateCoverageStats',
    )
)


def run_coverage(messages, foci, active='last'):
    script = '''
const messages = MESSAGES;
const foci = FOCI;
const activeScenarioMessageId = ACTIVE;
const selectedFocusIndex = 0;
const document = {querySelectorAll: () => messages.map(message => ({
    dataset: {messageId: message.id},
    querySelector: selector => ({value: ({
        '.scenario-message-id': message.id,
        '.scenario-role': message.role || 'user',
        '.scenario-analysis-mode': message.analysis_mode || 'analyse',
        '.scenario-content': message.content
    })[selector]})
}))};
function element() { return {innerHTML: '', textContent: '', style: {},
    classList: {add() {}, remove() {}}}; }
const promptVisualization = element(), promptHighlighted = element();
const toggleVisualization = element(), coverageIndicator = element();
const coverageWarning = element(), coveragePercent = element();
const coverageDensity = element(), overlapMatrixEl = element();
function escapeHtml(text) {return String(text).replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');}
const escapeScenarioAttribute = escapeHtml;
function updateLegend() {}
FUNCTIONS
const before = JSON.stringify(foci);
updateCoverageVisualization();
updateCoverageStats();
const data = getScenarioCoverageData();
console.log(JSON.stringify({html: promptHighlighted.innerHTML,
    percent: coveragePercent.textContent, density: coverageDensity.textContent,
    stats: computeClientCoverage(data.prompt, data.foci),
    overlaps: computeClientOverlaps(data.prompt, data.foci),
    unchanged: before === JSON.stringify(foci)}));
'''
    for key, value in [('MESSAGES', json.dumps(messages)), ('FOCI', json.dumps(foci)),
                       ('ACTIVE', json.dumps(active)), ('FUNCTIONS', FUNCTIONS)]:
        script = script.replace(key, value)
    return json.loads(subprocess.run(['node', '-e', script], capture_output=True,
                                    text=True, check=True).stdout)


@pytest.mark.parametrize('active', ['first', 'last', 'retained'])
def test_all_analysis_messages_are_rendered_and_counted_independent_of_editor(active):
    result = run_coverage([
        {'id': 'first', 'content': ' ABC ', 'role': 'system'},
        {'id': 'retained', 'content': 'SECRET', 'analysis_mode': 'retain'},
        {'id': 'last', 'content': 'WXYZ'},
        {'id': 'uncovered', 'content': '<end>'},
    ], [
        {'focus': 'First focus', 'message_id': 'first', 'char_start': 1, 'char_end': 4},
        {'focus': 'Last focus', 'spans': [{'message_id': 'last', 'char_start': 0, 'char_end': 4}]},
        {'focus': 'Ignore', 'message_id': 'retained', 'char_start': 0, 'char_end': 6},
    ], active)
    html = result['html']
    assert html.index('system · first') < html.index('user · last') < html.index('user · uncovered')
    assert 'SECRET' not in html
    assert 'data-focus-indices="0">ABC</span>' in html
    assert 'data-focus-indices="1">WXYZ</span>' in html
    assert 'Not covered by any focus"> </span>' not in html
    assert '>ABC</span> </div>' in html
    assert 'Not covered by any focus">&lt;end&gt;</span>' in html
    assert result['percent'] == '50.0%'
    assert result['density'] == '50.0%'
    assert result['stats']['uncovered'] == 7
    assert result['overlaps'] == []
    assert result['unchanged']


def test_cross_message_focus_overlap_and_unverified_spans():
    result = run_coverage([
        {'id': 'first', 'content': 'abcd'}, {'id': 'last', 'content': 'wxyz'},
    ], [
        {'focus': 'Both', 'spans': [
            {'message_id': 'first', 'char_start': 0, 'char_end': 2},
            {'message_id': 'last', 'char_start': 0, 'char_end': 2},
        ]},
        {'focus': 'Last', 'message_id': 'last', 'char_start': 0, 'char_end': 2},
        {'focus': 'Unverified', 'verified': False, 'message_id': 'first', 'char_start': 0, 'char_end': 4},
    ])
    assert result['percent'] == '50.0%'
    assert result['density'] == '75.0%'
    assert result['overlaps'][0]['inter'] == 2
    assert result['overlaps'][0]['pctOfA'] == 50
    assert result['overlaps'][0]['pctOfB'] == 100
    first, last = result['html'].split('data-message-id="last"')
    assert 'highlight-overlap' not in first
    assert 'highlight-overlap' in last


def test_legacy_unscoped_focus_with_one_analysis_message():
    result = run_coverage([{'id': 'only', 'content': 'abc'}], [
        {'focus': 'Legacy', 'char_start': 0, 'char_end': 3},
    ])
    assert result['percent'] == '100.0%'
    assert 'data-focus-indices="0">abc</span>' in result['html']


def test_ambiguous_unscoped_and_out_of_bounds_spans_are_not_highlighted():
    result = run_coverage([
        {'id': 'first', 'content': 'abc'}, {'id': 'last', 'content': 'def'},
    ], [
        {'focus': 'Ambiguous', 'char_start': 0, 'char_end': 3},
        {'focus': 'Invalid', 'message_id': 'first', 'char_start': 0, 'char_end': 10},
    ])
    assert result['percent'] == '0.0%'
    assert 'data-focus-indices' not in result['html']
