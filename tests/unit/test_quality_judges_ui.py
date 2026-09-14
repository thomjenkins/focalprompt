"""Execute the real judge orchestration and UI handler without model calls."""

import json
from pathlib import Path
import re
import subprocess

REPO = Path(__file__).resolve().parents[2]
APP = (REPO / 'static/js/app.js').read_text()
MODULE = (REPO / 'static/js/quality_judges.js').read_text()


def run_js(script):
    result = subprocess.run(['node', '-e', script], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr


def test_independent_judges_retries_comparison_and_saved_state():
    run_js("const assert = require('node:assert/strict'); const window = {};\n" + MODULE + r"""
(async () => {
    const q = window.FocalPromptQuality;
    const run = {model: 'gpt-4o-mini', provider: 'openai'};
    const peer = {model: 'claude-test', provider: 'anthropic'};
    assert.throws(() => q.judgesFor({}, false), /not recorded/);
    assert.throws(() => q.judgesFor(run, true, {...run, model: 'openai/gpt-4o-mini'}), /different model/);
    assert.deepEqual(q.modelOf({focus_workflow: {context: {model: run}}}), run);
    const single = q.judgesFor(run, false, peer), dual = q.judgesFor(run, true, peer);
    const context = {outputs: [{label: 'A', text: '5'}, {label: 'B', text: 'six'}],
        eval_criteria: 'Correct arithmetic', sample_seed: 0};
    const original = structuredClone(context);
    let calls = [], failPeer = false;
    async function request(input, judge) {
        calls.push({input, judge: judge.id});
        assert.deepEqual(input, context, 'No peer scores are included in judge input');
        assert.equal(judge.result, undefined);
        if (failPeer && judge.id === 'external') throw new Error('Temporary failure');
        return {judge: {role: judge.id, model: judge.model, provider: judge.provider},
            evaluations: [{label: 'A', overall_score: judge.id === 'self' ? 0 : 80},
                {label: 'B', overall_score: null}]};
    }
    let state = await q.evaluate({context, judges: single, request});
    assert.equal(calls.length, 1, 'Disabled peer makes no request');
    assert.equal(state.judges[0].status, 'complete');
    const saved = JSON.parse(JSON.stringify(state));
    calls = [];
    failPeer = true;
    state = await q.evaluate({context, judges: dual, previous: saved, request});
    assert.deepEqual(calls.map(c => c.judge), ['external'], 'Adding a judge reuses completed self judgment');
    assert.equal(state.judges[0].status, 'complete');
    assert.equal(state.judges[1].status, 'error');
    assert.equal(state.judges[1].result, undefined);
    calls = [];
    failPeer = false;
    state = await q.evaluate({context, judges: dual, previous: JSON.parse(JSON.stringify(state)), request});
    assert.deepEqual(calls.map(c => c.judge), ['external'], 'Retry preserves successful peer');
    assert.deepEqual(q.comparisonRows(state), [
        {label: 'A', self: 0, external: 80, difference: 80},
        {label: 'B', self: null, external: null, difference: null}]);
    assert.match(q.comparisonHtml(state, s => s), /\+80.0/);
    assert.match(q.comparisonHtml(state, s => s), /—/);
    assert.deepEqual(context, original);
    calls = [];
    state = await q.evaluate({context, judges: dual, previous: state, request});
    assert.equal(calls.length, 2, 'An explicit rerun evaluates a completed pair anew');
    assert.deepEqual(calls[0].input, calls[1].input);
    calls = [];
    context.eval_criteria = 'Revised criteria';
    state = await q.evaluate({context, judges: dual, previous: state, request});
    assert.equal(calls.length, 2, 'Changed criteria invalidates both previous results');
    state = await q.evaluate({context, judges: single, request: async () => ({judge: {
        role: 'self', model: 'wrong-model', provider: 'openai'}})});
    assert.equal(state.judges[0].status, 'error');
    assert.match(state.judges[0].error, /different judge identity/);
})().catch(e => {console.error(e); process.exit(1);});
""")


def test_ui_sends_saved_run_model_context_and_persists_both_results():
    names = ('collectOutputsForQualityEval', 'renderQualityEvalResults',
             'refreshQualityJudgeControls')
    functions = '\n'.join(re.search(
        r'^function ' + name + r'\([^\n]*\) \{.*?^\}', APP, re.M | re.S
    ).group() for name in names)
    handler = APP.split('if (runQualityEvalBtn) {', 1)[1].split('// Make removeFocus', 1)[0]
    restore = APP.split('    if (qualitySecondJudgeEnabled) qualitySecondJudgeEnabled.checked = pa.', 1)[1]
    restore = 'if (qualitySecondJudgeEnabled) qualitySecondJudgeEnabled.checked = pa.' + restore.split('    if (pa.focus_order)', 1)[0]
    run_js(r"""
const assert = require('node:assert/strict');
const window = {singleAblationResults: {model: 'generation-model', provider: 'openai',
    prompt: 'Saved original prompt', scenario: {version: 1, messages: [{content: 'Original retained chat'}]},
    baseline_outputs: ['Baseline'], ablation_results: [
        {focus: 'Duplicate name', ablated_outputs: ['First ablation']},
        {focus: 'Duplicate name', ablated_outputs: ['Second ablation']}]}};
const elements = new Map();
const document = {getElementById(id) {if (!elements.has(id)) elements.set(id, {}); return elements.get(id);}};
let callback, requests = [];
const qualitySecondJudgeEnabled = {checked: true}, qualityEvalSamplePct = {value: '50'},
    evalCriteriaInput = {value: 'Evaluate task quality'}, qualityEvalResults = {scrollIntoView() {}},
    runQualityEvalBtn = {addEventListener(event, fn) {callback = fn;}};
function getSectionModel(section) {assert.equal(section, 'quality'); return {model: 'other-model', provider: 'google'};}
function getApiBody(input, role, judge) {return {...input, model: judge.model, provider: judge.provider};}
function getApiHeaders() {return {};}
function showErrorModal(error) {throw new Error(error);}
function showError(error) {throw new Error(error);}
function showLoading() {} function hideLoading() {}
function escapeHtml(s) {return s;}
function qualityEvalResultHtml(data) {return JSON.stringify(data);}
function refreshQualityEvalPreview() {refreshQualityJudgeControls();}
async function fetch(url, options) {
    assert.equal(url, '/api/evaluate-outputs-quality');
    const input = JSON.parse(options.body); requests.push(input);
    return {ok: true, json: async () => ({judge: {role: input.judge_role, model: input.model, provider: input.provider},
        evaluations: input.outputs.map(o => ({label: o.label, overall_score: 75, summary: 'Good task fit'}))})};
}
""" + MODULE + functions + '\nif (runQualityEvalBtn) {' + handler + r"""
(async () => {
    refreshQualityJudgeControls();
    assert.match(elements.get('quality-self-model').textContent, /generation-model/);
    assert.equal(elements.get('quality-second-judge-controls').hidden, false);
    await callback();
    assert.deepEqual(requests.map(r => r.model), ['generation-model', 'other-model']);
    assert.deepEqual(requests.map(r => r.judge_role), ['self', 'external']);
    assert.deepEqual(requests[0].scenario, window.singleAblationResults.scenario);
    assert.deepEqual(requests[0].scenario, requests[1].scenario);
    assert.deepEqual(requests[0].outputs, requests[1].outputs);
    assert.equal(new Set(requests[0].outputs.map(o => o.label)).size, 3, 'Duplicate focus names cannot merge rows');
    const exportedResults = JSON.parse(JSON.stringify(window.lastQualityEvalResults));
    assert.equal(exportedResults.judges.length, 2);
    assert.match(qualityEvalResults.innerHTML, /Second − self/);
    assert.match(qualityEvalResults.innerHTML, /Good task fit/);
    // Execute the actual restore block in this lexical environment.
    function restoreSaved(pa) {eval(RESTORE);}
    restoreSaved({quality_eval: {second_judge_enabled: true, results: exportedResults}});
    assert.deepEqual(window.lastQualityEvalResults, exportedResults);
    restoreSaved({quality_eval: {results: {evaluations: [{label: 'Legacy', overall_score: 90}]}}});
    assert.equal(qualitySecondJudgeEnabled.checked, false);
    assert.match(qualityEvalResults.innerHTML, /earlier single-judge/);
    assert.equal(elements.get('quality-second-judge-controls').hidden, true);
    restoreSaved({});
    assert.equal(window.lastQualityEvalResults, null);
    assert.equal(qualityEvalResults.innerHTML, '');
    requests = [];
    await callback();
    assert.equal(requests.length, 1);
    assert.equal(requests[0].judge_role, 'self');
})().catch(e => {console.error(e); process.exit(1);});
""".replace('RESTORE', json.dumps(restore)))
