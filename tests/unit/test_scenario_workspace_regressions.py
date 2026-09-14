"""Run the actual editor and download helpers to protect message identity and drafts."""

from pathlib import Path
import re
import subprocess


APP = (Path(__file__).resolve().parents[2] / 'static/js/app.js').read_text()


def test_readable_names_prediction_and_workspace_round_trip():
    names = (
        'remapFocusMessageId', 'syncScenarioMessageId', 'readMainScenario',
        'validateScenarioOutputContract', 'collectScenarioEditorDraft',
        'restoreScenarioEditorDraft', 'getBatchScenario',
        'collectPromptAnalysisWorkspace', 'collectWorkspaceSession',
        'exportWorkspaceSessionFile', 'restoreWorkspaceSession',
        'restoreBatchAnalysisWorkspace',
    )
    functions = '\n'.join(re.search(
        r'^function ' + name + r'\([^\n]*\) \{.*?^\}', APP, re.M | re.S
    ).group() for name in names)
    script = r"""
const assert = require('node:assert/strict');
const window = {};
const elements = new Map();
function element(value = '') { return {value, checked: false, textContent: '',
    classList: {toggle() {}, add() {}, remove() {}}, setCustomValidity() {}, setAttribute() {}}; }
function card(id, role, mode, content) {
    const fields = {'.scenario-message-id': element(id), '.scenario-role': element(role),
        '.scenario-analysis-mode': element(mode), '.scenario-content': element(content),
        '.scenario-input-name': element()};
    return {dataset: {messageId: id}, querySelector: s => fields[s]};
}
let cards = [card('copilot', 'developer', 'analyse', 'Be concise.'),
    card('chat', 'user', 'retain', 'Please book a visit.'),
    card('copilot edits', 'user', 'analyse', 'We are open on Monday.')];
let downloaded, blob, errorMessage, timeout;
const document = {querySelectorAll: () => cards,
    getElementById(id) { if (!elements.has(id)) elements.set(id, element()); return elements.get(id); },
    body: {appendChild(a) { a.parentNode = this; }},
    createElement() { return {click() { downloaded = this.download; }, remove() {this.parentNode = null;}}; }};
const URL = {createObjectURL(value) {blob = value; return 'blob:test';}, revokeObjectURL() {}};
function setTimeout(fn) { timeout = fn; }
function showErrorModal(message) { errorMessage = message; }
const originalFocus = {focus: 'Hours', message_id: 'copilot edits', message_ids: ['copilot', 'copilot edits'],
    spans: [{message_id: 'copilot', char_start: 0, char_end: 11},
        {message_id: 'copilot edits', char_start: 0, char_end: 21}]};
let foci = [structuredClone(originalFocus)], batchFoci = [structuredClone(originalFocus)],
    agentFoci = [structuredClone(originalFocus)], activeScenarioMessageId = 'copilot edits';
const batchPromptInput = {value: 'A different batch prompt.'};
let promptInput = cards[0].querySelector('.scenario-content'), assessmentFoci = [], batchPairs = [];
const outputInput = null, focusWeights = {}, rewrittenPromptText = '',
    rewrittenScenario = null, targetFocusMix = [], adjustedReportedFoci = [], adjustedOutput = null,
    evalCriteriaInput = null, qualityEvalSamplePct = null, qualitySecondJudgeEnabled = {checked: true},
    focusOrderKSel = null, focusOrderMSel = null,
    focusOrderSweepFocus = null, focusOrderRunSweep = null, focusOrderRunJudge = null, focusOrderCriterion = null,
    currentTab = 'prompt-analysis', userProvider = 'openai', userModel = 'test-model',
    WORKSPACE_SESSION_VERSION = 2, chatInput = null, batchAgentData = null,
    batchAgentResultsData = [], optimizationResults = null, promptOptimizationSection = null,
    exportResultsBtn = null, exportResultsJsonBtn = null, batchResults = null;
function readAblationExperimentConfig() { return {temperature: '.7', n_baseline: '10'}; }
function collectModelSettings() { return {}; }
function getCurrentModelSelection() { return {provider: userProvider, model: userModel}; }
function getSectionModel() { return getCurrentModelSelection(); }
function restoreModelSettings() {}
function restoreAgentBuilderWorkspace() {}
function renderBatchFoci() {}
function renderPairs() {}
function applyAblationExperimentConfig() {}
function updateBatchAnalysisButton() {}
function switchTab() {}
function setMainScenario(scenario) {
    cards = scenario.messages.map(m => card(m.id, m.role, m.analysis_mode, m.content));
    promptInput = cards[0]?.querySelector('.scenario-content');
}
function restorePromptAnalysisWorkspace(pa) {
    setMainScenario(pa.scenario);
    restoreScenarioEditorDraft(pa.scenario_editor);
    foci = structuredClone(pa.foci);
}
""" + functions + r"""
(async () => {
    const scenario = readMainScenario();
    assert.deepEqual(scenario.messages.map(m => m.id), ['copilot', 'chat', 'copilot-edits']);
    assert.equal(scenario.messages[1].content, 'Please book a visit.');
    assert.equal(cards[2].querySelector('.scenario-message-id').value, 'copilot edits');
    for (const list of [foci, batchFoci, agentFoci]) {
        assert.equal(list[0].message_id, 'copilot-edits');
        assert.deepEqual(list[0].message_ids, ['copilot', 'copilot-edits']);
        assert.equal(list[0].spans[0].message_id, 'copilot');
        assert.deepEqual(list[0].spans[1], {...originalFocus.spans[1], message_id: 'copilot-edits'});
    }
    assert.equal(activeScenarioMessageId, 'copilot-edits');
    const before = JSON.stringify(foci);
    assert.deepEqual(readMainScenario(), scenario, 'repeated reads must be stable');
    assert.equal(JSON.stringify(foci), before);

    // Clearing and retyping a name must not orphan or steal its focus spans.
    const input = cards[2].querySelector('.scenario-message-id');
    input.value = '';
    readMainScenario();
    assert.equal(foci[0].message_id, 'copilot-edits');
    input.value = 'copilot';
    assert.equal(readMainScenario().messages[2].id, 'copilot-2');
    assert.equal(foci[0].spans[0].message_id, 'copilot');
    assert.equal(foci[0].spans[1].message_id, 'copilot-2');
    input.value = 'copilot edits';
    readMainScenario();

    // Predict Focus must send the same canonical IDs in the scenario and foci.
    const workflow = WORKFLOW;
    let request;
    window.FocalPromptExperiment = {getState: () => ({temperature: .7, n_baseline: 10}), temperatureRejection: () => null};
    window.FocalPromptResults = {escapeHtml: s => s};
    document.addEventListener = () => {};
    for (const el of elements.values()) el.addEventListener = () => {};
    const oldGet = document.getElementById;
    document.getElementById = function (id) {const el = oldGet(id); el.addEventListener = () => {}; return el;};
    function getApiBody(payload) {return payload;}
    function getApiHeaders() {return {};}
    function escapeHtml(s) {return s;}
    function showLoading() {}
    async function fetch(path, options) {
        request = JSON.parse(options.body);
        return {ok: true, json: async () => ({foci: [{focus_index: 0, focus: 'Hours', score: 100, explanation: 'Opening hours.'}]})};
    }
    eval(workflow);
    await window.FocalPromptWorkflow.predict();
    assert.equal(request.phase, 'prospective');
    assert.equal(request.scenario.messages[2].id, 'copilot-edits');
    assert.equal(request.foci[0].spans[1].message_id, 'copilot-edits');
    assert.equal(request.output, undefined);

    // Export accepts an unfinished contract AND an invalid conversation order.
    document.getElementById('scenario-contract-enabled').checked = true;
    document.getElementById('scenario-contract-name').value = 'unfinished name';
    document.getElementById('scenario-contract-schema').value = '{ "type": ';
    cards[2].querySelector('.scenario-role').value = 'developer';
    assert.throws(() => readMainScenario(), /before conversation/);
    const snapshot = JSON.parse(JSON.stringify(collectWorkspaceSession()));
    assert.equal(snapshot.prompt_analysis.quality_eval.second_judge_enabled, true);
    assert.equal(snapshot.prompt_analysis.scenario_editor.message_names[2].name, 'copilot edits');
    assert.equal(snapshot.prompt_analysis.scenario_editor.output_contract.schema, '{ "type": ');
    assert.equal(snapshot.prompt_analysis.foci[0].spans[1].message_id, 'copilot-edits');
    assert.equal(snapshot.batch_analysis.scenario.messages[0].content, 'A different batch prompt.');
    assert.ok(snapshot.prompt_analysis.focus_workflow.prospective);
    exportWorkspaceSessionFile();
    assert.match(downloaded, /^focalprompt-workspace-.*\.json$/);
    assert.equal(errorMessage, undefined);
    const file = JSON.parse(await blob.text());
    restoreWorkspaceSession(file);
    assert.equal(cards[0].querySelector('.scenario-content').value, 'Be concise.', 'batch restore must preserve main prompt');
    assert.equal(cards[2].querySelector('.scenario-message-id').value, 'copilot edits');
    assert.equal(document.getElementById('scenario-contract-schema').value, '{ "type": ');
    assert.deepEqual(collectWorkspaceSession().prompt_analysis.scenario, snapshot.prompt_analysis.scenario);
    cards[2].querySelector('.scenario-role').value = 'user';
    assert.throws(() => readMainScenario(), /Output contract/);

    for (const name of ['Café hours?!', '💬', 'x'.repeat(200), 'chat']) {
        cards[2].querySelector('.scenario-message-id').value = name;
        const draft = readMainScenario({draft: true});
        assert.match(draft.messages[2].id, /^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/);
        assert.equal(new Set(draft.messages.map(m => m.id)).size, 3);
        assert.equal(foci[0].spans[1].message_id, draft.messages[2].id);
        assert.deepEqual(readMainScenario({draft: true}), draft);
    }
    // Even an empty draft can be saved. Unexpected download errors are visible.
    cards = [];
    assert.deepEqual(collectWorkspaceSession().prompt_analysis.scenario.messages, []);
    URL.createObjectURL = () => {throw new Error('Download unavailable');};
    exportWorkspaceSessionFile();
    assert.match(errorMessage, /Could not export workspace: Download unavailable/);
})().catch(error => { console.error(error); process.exit(1); });
"""
    import json
    script = script.replace('WORKFLOW', json.dumps(
        (Path(__file__).resolve().parents[2] / 'static/js/focus_workflow.js').read_text()
    ))
    result = subprocess.run(['node', '-e', script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
