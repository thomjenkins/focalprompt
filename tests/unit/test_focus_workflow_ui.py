"""Execute browser orchestration without credentials or paid inference."""

from pathlib import Path
import subprocess


REPO = Path(__file__).resolve().parents[2]


def test_ordered_workflow_resume_reuse_and_staleness():
    workflow = (REPO / 'static/js/focus_workflow.js').read_text()
    app = (REPO / 'static/js/app.js').read_text()
    paced = app[app.index('async function runPacedAblation('):app.index('if (runAblationBtn) {', app.index('async function runPacedAblation('))]
    script = r"""
const assert = require('node:assert/strict');
const window = globalThis;
const elements = new Map();
const document = {
  getElementById(id) {
    if (!elements.has(id)) elements.set(id, {innerHTML: '', textContent: '', value: '',
      classList: {add() {}, remove() {}}, addEventListener() {}});
    return elements.get(id);
  }, addEventListener() {}
};
let scenario = {version: 1, messages: [{id: 'rules', role: 'system', content: 'Be concise.', analysis_mode: 'analyse'},
  {id: 'chat', role: 'user', content: 'Retained chat', analysis_mode: 'retain'}]};
let foci = [{focus: 'Brief', prompt_section: 'Be concise.'}];
let model = {model: 'model-under-test', provider: 'openai'};
let config = {temperature: .7, n_baseline: 10, n_ablated: 3};
let assessmentFoci = [];
const outputInput = document.getElementById('output-input');
function readMainScenario() { return scenario; }
function getSectionModel() { return model; }
function getApiBody(payload, role, selected) { return {...payload, ...selected}; }
function getApiHeaders() { return {}; }
function escapeHtml(s) { return s.replaceAll('<', '&lt;'); }
function showLoading() {}
function renderAssessment(data) { window.lastAssessmentApiPayload = data; }
window.FocalPromptExperiment = {getState: () => config, temperatureRejection: () => null};
const requests = [], generated = [];
let failSample = true, calls = 0, scoreBody;
async function fetchAblationSample(inference, fs, kind, index, temperature, controller, inputs, selected) {
  assert.equal(temperature, .7);
  assert.deepEqual(selected, model);
  if (kind === 'baseline' && ++calls === 2 && failSample) { failSample = false; throw new Error('Transient failure'); }
  const content = kind + ' output ' + generated.length;
  generated.push({kind, content});
  return {content, scenario: kind === 'baseline' ? structuredClone(inference) : {...inference, messages: inference.messages.slice(1)},
    usage: {prompt_tokens: 10, completion_tokens: 20}};
}
const oneAllocation = {assessment_protocol: 'joint-budget-v4', assessment_temperature: .2,
  budget_normalized: true, raw_score_total: 60,
  allocation_recovery: {calls: 1, focus_indices: [0]},
  request_summary: 'Answer <this> request.', request_evidence: [{message_id: 'chat', quote: 'Retained chat'}],
  foci: [{focus: 'Brief', focus_index: 0, applicability: 'background', score: 100, explanation: 'A concise answer.'}]};
async function fetch(path, options) {
  const body = JSON.parse(options.body);
  requests.push({path, body});
  let result;
  if (path === '/api/focus-self-assessment') {
    assert.equal(body.model, model.model);
    assert.equal(body.scenario.messages[1].content, 'Retained chat');
    assert.equal(body.prospective, undefined);
    assert.equal(body.baseline_outputs, undefined);
    if (body.phase === 'prospective') assert.equal(body.output, undefined);
    result = oneAllocation;
  } else if (path === '/api/baseline-diagnostics') {
    assert.equal(body.baseline_outputs.length, 10);
    result = {baseline_stability: {}, output_distribution: {label: 'no_clear_multiple_modes', note: 'Advisory',
      membership: Array(10).fill(0), projection: {coordinates: Array(10).fill([0, 0])},
      pairwise_cosine_distances: Array.from({length: 10}, () => Array(10).fill(0))}};
  } else if (path === '/api/focus-comparison') {
    assert.equal(body.retrospective.length, 10);
    assert.deepEqual(body.influence_scores, [{focus_index: 0, t_obs: .2}]);
    result = {average: oneAllocation, comparison: []};
  } else if (path === '/api/ablation-score') {
    scoreBody = body;
    result = {baseline_outputs: body.baseline_outputs, focus_workflow: body.focus_workflow,
      baseline_reused: true, influence_scores: [{focus_index: 0, t_obs: .2}]};
  } else throw new Error('Unexpected ' + path);
  return {ok: true, json: async () => structuredClone(result)};
}
function isClientAttributableFocus() { return true; }
async function mapPool(items, count, task) { return Promise.all(items.map(task)); }
""" + workflow + '\n' + paced + r"""
(async () => {
  const flow = window.FocalPromptWorkflow;
  assert.ok(flow.matches({a: 1, b: {c: 2, d: 3}}, {b: {d: 3, c: 2}, a: 1}));
  assert.ok(!flow.matches({a: [1, 2]}, {a: [2, 1]}));
  await assert.rejects(flow.sampleBaseline, /Predict focus/);
  await flow.predict();
  assert.equal(requests.length, 1);
  flow.restore(flow.collect());
  assert.match(document.getElementById('focus-workflow-status').textContent, /generation temperature 0.7/);
  const rendered = document.getElementById('prospective-results').innerHTML;
  assert.match(rendered, /Assessment temperature: 0.2/);
  assert.match(rendered, /Current request \(model interpretation\)/);
  assert.match(rendered, /Answer &lt;this> request/);
  assert.match(rendered, /Background constraint/);
  assert.match(rendered, /Retained chat/);
  assert.match(rendered, /scores totaled 60/);
  assert.match(rendered, /Rescaled proportionally to 100%/);
  assert.match(rendered, /Completed with 1 follow-up model call/);
  assert.deepEqual(flow.collect().prospective.allocation_recovery, {calls: 1, focus_indices: [0]});
  await assert.rejects(flow.sampleBaseline, /Successful samples are saved/);
  const completed = flow.collect().samples.filter(Boolean).length;
  assert.ok(completed > 0 && completed < 10);
  assert.throws(() => flow.forAblation(scenario, foci, config, model), /Finish generating baseline/);
  await flow.sampleBaseline();
  assert.equal(generated.filter(s => s.kind === 'baseline').length, 10);
  const original = flow.collect().samples.map(s => s.content);
  const baselineOnly = flow.collect();
  assert.equal(baselineOnly.summary, null);
  baselineOnly.diagnostics = null;
  flow.restore(baselineOnly);
  const beforeAssessment = flow.forAblation(scenario, foci, config, model);
  window.singleAblationResults = await runPacedAblation(scenario, foci, config, null, null, 'ablation', beforeAssessment);
  flow.renderAblationComparison(window.singleAblationResults);
  assert.match(document.getElementById('focus-ablation-comparison').innerHTML, /optional retrospective/);
  assert.equal(requests.filter(r => r.body.phase === 'retrospective').length, 0);
  await flow.retrospective();
  const retros = requests.filter(r => r.body.phase === 'retrospective');
  assert.equal(retros.length, 10);
  assert.deepEqual(retros.map(r => r.body.output).sort(), [...original].sort());
  assert.equal(window.lastAssessmentApiPayload.foci[0].score, 100);
  const snapshot = flow.forAblation(scenario, foci, config, model);
  assert.equal(generated.filter(s => s.kind === 'baseline').length, 10, 'baseline must be reused');
  assert.equal(generated.filter(s => s.kind === 'ablated').length, 3);
  assert.equal(window.singleAblationResults.focus_comparison_status, 'complete');
  assert.equal(window.singleAblationResults.focus_workflow.retrospective.length, 10);
  assert.ok(window.singleAblationResults.focus_comparison);
  assert.deepEqual(scoreBody.baseline_outputs, original);
  assert.deepEqual(scoreBody.scenario, scenario, 'never score against the first ablated scenario');
  assert.equal(scoreBody.input_tokens, 130);
  assert.ok(scoreBody.focus_workflow.prospective);
  assert.equal(scoreBody.focus_workflow.retrospective.length, 0, 'scoring must permit no assessments');
  const withoutPrediction = structuredClone(baselineOnly);
  withoutPrediction.prospective = null;
  flow.restore(withoutPrediction);
  assert.deepEqual(flow.forAblation(scenario, foci, config, model).samples, snapshot.samples);
  flow.restore(snapshot);
  assert.throws(() => flow.forAblation(scenario, foci, config, {model: 'other', provider: 'openai'}), /same scenario/);
  const exported = flow.collect();
  const flat = structuredClone(exported);
  flat.prospective.assessment_protocol = 'joint-budget-v3';
  flat.prospective.foci = Array.from({length: 17}, (_, i) => ({focus: 'Focus ' + i, focus_index: i,
    score: 100 / 17, explanation: 'Explanation'}));
  flat.prospective.overall_summary = 'Equal <weights>.';
  flow.restore(flat);
  const flatHtml = document.getElementById('prospective-results').innerHTML;
  assert.match(flatHtml, /Assessment limitation/);
  assert.match(flatHtml, /identical weights to every focus/);
  assert.match(flatHtml, /Allocation rationale/);
  assert.match(flatHtml, /Equal &lt;weights>/);
  await assert.rejects(flow.sampleBaseline, /assessment method has been updated/);
  const legacy = structuredClone(exported);
  delete legacy.prospective.assessment_protocol;
  flow.restore(legacy);
  await assert.rejects(flow.sampleBaseline, /assessment method has been updated/);
  await assert.rejects(flow.retrospective, /assessment method has been updated/);
  flow.restore(null);
  flow.restore(exported);
  assert.deepEqual(flow.forAblation(scenario, foci, config, model).samples, snapshot.samples);
  config = {...config, temperature: .9};
  assert.throws(() => flow.forAblation(scenario, foci, config, model), /changed/);
  config = {...config, temperature: .7};
  scenario.messages[1].content = 'Changed retained input';
  await assert.rejects(flow.retrospective, /changed/);
})().catch(error => { console.error(error); process.exit(1); });
"""
    subprocess.run(['node', '-e', script], check=True, capture_output=True, text=True)
