"""Execute scenario-facing app.js behaviour (spans, restore, provenance, optimization).

Functions are lifted out of static/js/app.js and run under node with narrow DOM
stubs, so these tests observe real client behaviour instead of source text.
"""

import json
import re
import subprocess
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]
APP = (REPO / 'static/js/app.js').read_text()
PROMPT_EDIT = (REPO / 'static/js/prompt_edit.js').read_text()


def extract(*names):
    parts = []
    for name in names:
        match = re.search(r'^function ' + name + r'\([^\n]*\) \{.*?^\}', APP, re.M | re.S)
        assert match, f'{name} not found as a top-level function in app.js'
        parts.append(match.group())
    return '\n'.join(parts)


def run_node(script, **values):
    for key, value in values.items():
        script = script.replace(key, json.dumps(value))
    result = subprocess.run(['node', '-e', script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


# --------------------------------------------------------------------------
# Prompt edits never disturb spans anchored to other scenario messages.
# --------------------------------------------------------------------------

SPAN_SCRIPT = '''
const window = globalThis;
''' + PROMPT_EDIT + '''
let activeScenarioMessageId = __ACTIVE__;
''' + extract('focusSpansOf', 'normalizeFocusClient', 'adjustFociForPromptEdit') + '''
const result = adjustFociForPromptEdit(__FOCI__, __PREVIOUS__, __NEXT__);
console.log(JSON.stringify(result));
'''


def adjust_foci(foci, previous, next_text, active='instructions'):
    return run_node(SPAN_SCRIPT, __FOCI__=foci, __PREVIOUS__=previous, __NEXT__=next_text, __ACTIVE__=active)


def test_untouched_spans_in_other_messages_survive_an_edit():
    focus = {
        'focus': 'Tone',
        'spans': [
            {'message_id': 'instructions', 'char_start': 0, 'char_end': 3,
             'text_snapshot': 'abc'},
            {'message_id': 'user-input', 'char_start': 0, 'char_end': 5,
             'text_snapshot': 'hello'},
        ],
    }
    result = adjust_foci([focus], 'abc def', 'abcX def')
    spans = result['foci'][0]['spans']
    assert len(spans) == 2
    edited = [s for s in spans if s['message_id'] == 'instructions'][0]
    kept = [s for s in spans if s['message_id'] == 'user-input'][0]
    assert (edited['char_start'], edited['char_end'], edited['text']) == (0, 4, 'abcX')
    assert (kept['char_start'], kept['char_end']) == (0, 5)
    assert kept['text'] == 'hello'
    assert result['foci'][0]['message_ids'] == ['instructions', 'user-input']


def test_edit_in_another_message_leaves_every_span_intact():
    focus = {
        'focus': 'Safety',
        'spans': [
            {'message_id': 'user-input', 'char_start': 2, 'char_end': 7,
             'text_snapshot': 'llo w'},
        ],
    }
    result = adjust_foci([focus], 'abc def', 'abc  def')
    spans = result['foci'][0]['spans']
    assert len(spans) == 1
    assert (spans[0]['char_start'], spans[0]['char_end']) == (2, 7)
    assert spans[0]['text'] == 'llo w'
    assert not result['foci'][0].get('needs_span_review')


# --------------------------------------------------------------------------
# Batch restore owns only batch state; the main scenario is restored elsewhere.
# --------------------------------------------------------------------------
RESTORE_SCRIPT = '''
const window = globalThis;
const WORKSPACE_SESSION_VERSION = 2;
const mainScenarioCalls = [];
function setMainScenario(scenario) { mainScenarioCalls.push(scenario); }
const batchPromptInput = { value: 'existing override' };
let batchFoci = [];
let batchPairs = [];
const batchResults = { innerHTML: '' };
const exportResultsBtn = { disabled: true };
const exportResultsJsonBtn = { disabled: true };
const document = { getElementById: () => null };
function renderBatchFoci() {}
function renderPairs() {}
function renderBatchResults() {}
function applyAblationExperimentConfig() {}
function updateBatchAnalysisButton() {}
''' + extract('legacyPromptScenario', 'migrateWorkspaceV1', 'restoreBatchAnalysisWorkspace') + '''
const payload = migrateWorkspaceV1(__WORKSPACE__);
restoreBatchAnalysisWorkspace(payload.batch_analysis);
console.log(JSON.stringify({
    main_scenario_calls: mainScenarioCalls,
    batch_prompt: batchPromptInput.value,
    batch_foci: batchFoci,
    batch_pairs: batchPairs,
    migrated: payload,
}));
'''


def restore_batch(workspace):
    return run_node(RESTORE_SCRIPT, __WORKSPACE__=workspace)


def test_batch_restore_never_replaces_the_main_scenario():
    scenario_a = {'version': 1, 'messages': [
        {'id': 'instructions', 'role': 'system', 'content': 'A', 'analysis_mode': 'analyse'},
        {'id': 'user-input', 'role': 'user', 'content': '', 'analysis_mode': 'retain'},
    ]}
    scenario_b = {'version': 1, 'messages': [
        {'id': 'batch-only', 'role': 'user', 'content': 'B', 'analysis_mode': 'analyse'},
    ]}
    result = restore_batch({
        'focalprompt_workspace': True,
        'version': 2,
        'prompt_analysis': {'scenario': scenario_a, 'foci': []},
        'batch_analysis': {
            'scenario': scenario_b,
            'prompt': 'batch override',
            'foci': [{'focus': 'F', 'prompt_section': 'B'}],
            'pairs': [{'inputs': {'chat_content': 'x'}, 'output': 'y'}],
        },
    })
    assert result['main_scenario_calls'] == []
    assert result['batch_prompt'] == 'batch override'
    assert [f['focus'] for f in result['batch_foci']] == ['F']
    assert len(result['batch_pairs']) == 1


def test_v1_workspace_with_empty_batch_still_migrates_without_touching_main():
    result = restore_batch({
        'focalprompt_workspace': True,
        'version': 1,
        'prompt_analysis': {
            'prompt': 'legacy prompt',
            'foci': [{'focus': 'F', 'prompt_section': 'legacy',
                      'spans': [{'char_start': 0, 'char_end': 6}]}],
        },
        'batch_analysis': {'prompt': '', 'foci': [], 'pairs': []},
    })
    assert result['main_scenario_calls'] == []
    assert result['batch_prompt'] == ''
    migrated = result['migrated']
    assert migrated['version'] == 2
    assert migrated['migrated_from_version'] == 1
    assert migrated['prompt_analysis']['scenario']['messages'][0]['id'] == 'legacy-prompt'
    assert migrated['prompt_analysis']['foci'][0]['message_id'] == 'legacy-prompt'
    assert migrated['prompt_analysis']['foci'][0]['spans'][0]['message_id'] == 'legacy-prompt'


# --------------------------------------------------------------------------
# Assessment results and rewrite payloads are joined by focus_index.
# --------------------------------------------------------------------------

ASSESSMENT_SCRIPT = '''
const window = globalThis;
function escapeHtml(text) { return String(text)
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;'); }
const assessmentResults = { innerHTML: '' };
const focusControlSection = { classList: { add() {}, remove() {} } };
const compareIntentBtn = { classList: { add() {}, remove() {} } };
let foci = __FOCI__;
let assessmentFoci = [];
let focusWeights = {};
let intendedDistribution = {};
function initializeSlidersFromAssessment() {}
function refreshExperimentCComparison() {}
''' + extract('renderAssessment', 'buildRewriteFociPayload') + '''
renderAssessment(__DATA__);
focusWeights = __WEIGHTS__;
console.log(JSON.stringify({
    assessment_foci: assessmentFoci,
    rewrite_payload: buildRewriteFociPayload(),
    html: assessmentResults.innerHTML,
}));
'''


def assess_and_rewrite(foci, data, weights):
    return run_node(ASSESSMENT_SCRIPT, __FOCI__=foci, __DATA__=data, __WEIGHTS__=weights)


DUPLICATE_FOCI = [
    {'focus': 'Tone', 'prompt_section': 'warm', 'message_id': 'instructions',
     'spans': [{'message_id': 'instructions', 'char_start': 0, 'char_end': 4,
                'text_snapshot': 'warm'}]},
    {'focus': 'Tone', 'prompt_section': 'curt', 'message_id': 'context',
     'spans': [{'message_id': 'context', 'char_start': 5, 'char_end': 9,
                'text_snapshot': 'curt'}]},
]


@pytest.mark.parametrize('order', [(0, 1), (1, 0)])
def test_duplicate_display_names_keep_separate_provenance(order):
    results = {
        0: {'focus': 'Tone', 'focus_index': 0, 'score': 60, 'explanation': 'first',
            'prompt_section': 'warm', 'message_id': 'instructions',
            'message_ids': ['instructions'],
            'spans': [{'message_id': 'instructions', 'char_start': 0, 'char_end': 4,
                       'text_snapshot': 'warm'}]},
        1: {'focus': 'Tone', 'focus_index': 1, 'score': 40, 'explanation': 'second',
            'prompt_section': 'curt', 'message_id': 'context',
            'message_ids': ['context'],
            'spans': [{'message_id': 'context', 'char_start': 5, 'char_end': 9,
                       'text_snapshot': 'curt'}]},
    }
    result = assess_and_rewrite(
        DUPLICATE_FOCI,
        {'foci': [results[order[0]], results[order[1]]], 'overall_summary': 'ok'},
        {'0': 70, '1': 30},
    )
    assessed = result['assessment_foci']
    assert [f['focus_index'] for f in assessed] == [0, 1]
    assert [f['score'] for f in assessed] == [60, 40]
    assert [f['explanation'] for f in assessed] == ['first', 'second']
    assert [f['spans'][0]['message_id'] for f in assessed] == ['instructions', 'context']

    payload = result['rewrite_payload']
    assert [item['rewrite_weight'] for item in payload] == [70, 30]
    assert [item['weight'] for item in payload] == [70, 30]
    assert [item['spans'][0]['message_id'] for item in payload] == ['instructions', 'context']
    assert [item['spans'][0]['char_start'] for item in payload] == [0, 5]
    assert [item['prompt_section'] for item in payload] == ['warm', 'curt']
    assert [item['reported_focus_score'] for item in payload] == [60, 40]


def test_focus_missing_from_the_response_scores_zero_and_keeps_its_spans():
    result = assess_and_rewrite(
        DUPLICATE_FOCI,
        {'foci': [{'focus': 'Tone', 'focus_index': 1, 'score': 100,
                   'explanation': 'only the second'}], 'overall_summary': ''},
        {'0': 0, '1': 100},
    )
    assessed = result['assessment_foci']
    assert [f['score'] for f in assessed] == [0, 100]
    assert [f['spans'][0]['message_id'] for f in assessed] == ['instructions', 'context']
    assert result['rewrite_payload'][0]['spans'][0]['char_end'] == 4
    assert result['rewrite_payload'][1]['rewrite_weight'] == 100


def test_legacy_response_without_focus_index_falls_back_to_position():
    result = assess_and_rewrite(
        DUPLICATE_FOCI,
        {'foci': [{'focus': 'Tone', 'score': 30, 'explanation': 'a'},
                  {'focus': 'Tone', 'score': 70, 'explanation': 'b'}],
         'overall_summary': ''},
        {'0': 50, '1': 50},
    )
    assessed = result['assessment_foci']
    assert [f['score'] for f in assessed] == [30, 70]
    assert [f['spans'][0]['message_id'] for f in assessed] == ['instructions', 'context']


AGENT_SCRIPT = '''
const window = globalThis;
const console = { warn() {} };
let agentFoci = __FOCI__;
''' + extract('buildAgentFociPayload') + '''
console_out = buildAgentFociPayload(__WEIGHTS__);
process.stdout.write(JSON.stringify(console_out));
'''


def test_agent_payload_resolves_weighted_foci_by_index():
    payload = run_node(AGENT_SCRIPT, __FOCI__=DUPLICATE_FOCI, __WEIGHTS__=[
        {'focus': 'Tone', 'focus_index': 1, 'weight': 0.7},
        {'focus': 'Tone', 'focus_index': 0, 'weight': 0.3},
    ])
    assert [item['spans'][0]['message_id'] for item in payload] == ['context', 'instructions']
    assert [item['focus_index'] for item in payload] == [1, 0]
    assert [item['weight'] for item in payload] == [0.7, 0.3]


# --------------------------------------------------------------------------
# Scenario reading, output contract, and batch readiness.
# --------------------------------------------------------------------------

SCENARIO_SCRIPT = '''
const window = globalThis;
function stubField(value) {
    return { value: value, validity: '', setCustomValidity(v) { this.validity = v; },
        setAttribute() {}, classList: { toggle() {}, add() {}, remove() {} } };
}
const elements = {
    'scenario-contract-enabled': { checked: __CONTRACT_ENABLED__,
        classList: { toggle() {} } },
    'scenario-contract-fields': { classList: { toggle() {} } },
    'scenario-contract-name': stubField(__CONTRACT_NAME__),
    'scenario-contract-schema': stubField(__CONTRACT_SCHEMA__),
    'scenario-contract-error': { textContent: '', classList: { toggle() {} } },
};
const cards = __MESSAGES__.map(function (message) {
    return {
        dataset: { messageId: message.id },
        querySelector: function (selector) {
            return {
                '.scenario-role': { value: message.role },
                '.scenario-analysis-mode': { value: message.analysis_mode },
                '.scenario-content': { value: message.content },
                '.scenario-input-name': { value: message.input_name || '' },
            }[selector];
        },
    };
});
const document = { getElementById: id => elements[id] || null,
    querySelectorAll: () => cards };
const batchPromptInput = { value: __BATCH_OVERRIDE__ };
''' + extract('validateScenarioOutputContract', 'readMainScenario', 'getBatchScenario',
              'batchScenarioReadiness') + '''
const out = { readiness: batchScenarioReadiness(), contract_error:
    elements['scenario-contract-error'].textContent };
try {
    out.scenario = readMainScenario();
} catch (error) {
    out.error = error.message;
}
try {
    out.batch_scenario = getBatchScenario();
} catch (error) {
    out.batch_error = error.message;
}
console.log(JSON.stringify(out));
'''

MAIN_ONLY = [
    {'id': 'instructions', 'role': 'system', 'content': 'Be precise.',
     'analysis_mode': 'analyse'},
    {'id': 'user-input', 'role': 'user', 'content': '', 'analysis_mode': 'retain',
     'input_name': 'chat'},
]


def read_scenario(messages, batch='', contract_enabled=False, name='model_output', schema=''):
    return run_node(SCENARIO_SCRIPT, __MESSAGES__=messages, __BATCH_OVERRIDE__=batch,
                    __CONTRACT_ENABLED__=contract_enabled, __CONTRACT_NAME__=name,
                    __CONTRACT_SCHEMA__=schema)


def test_main_only_scenario_is_ready_for_batch_without_a_prompt_override():
    result = read_scenario(MAIN_ONLY)
    assert result['readiness'] == {'hasPrompt': True, 'promptChars': 11, 'error': ''}
    assert result['batch_scenario']['messages'][0]['content'] == 'Be precise.'
    assert [m['id'] for m in result['scenario']['messages']] == ['instructions', 'user-input']
    assert result['scenario']['messages'][1]['input_name'] == 'chat'


def test_batch_override_only_replaces_the_first_analysed_message():
    messages = [dict(MAIN_ONLY[0], content=''), MAIN_ONLY[1]]
    result = read_scenario(messages, batch='batch text')
    assert result['readiness']['hasPrompt'] is True
    assert result['batch_scenario']['messages'][0]['content'] == 'batch text'
    assert result['scenario']['messages'][0]['content'] == ''
    assert result['batch_scenario']['messages'][1] == result['scenario']['messages'][1]


def test_empty_analysed_content_without_override_is_not_ready():
    messages = [dict(MAIN_ONLY[0], content='   '), MAIN_ONLY[1]]
    result = read_scenario(messages)
    assert result['readiness'] == {'hasPrompt': False, 'promptChars': 0, 'error': ''}


def test_invalid_scenario_surfaces_its_error_through_readiness():
    messages = [MAIN_ONLY[0], dict(MAIN_ONLY[1], id='instructions')]
    result = read_scenario(messages)
    assert result['readiness']['hasPrompt'] is False
    assert 'unique' in result['readiness']['error']
    assert 'unique' in result['error']


def test_valid_output_contract_is_read_into_the_scenario():
    schema = json.dumps({'type': 'object', 'properties': {'answer': {'type': 'string'}}})
    result = read_scenario(MAIN_ONLY, contract_enabled=True, name='answer_only',
                           schema=schema)
    assert result['contract_error'] == ''
    assert result['scenario']['output_contract'] == {
        'type': 'json_schema', 'name': 'answer_only', 'strict': True,
        'schema': json.loads(schema),
    }
    assert result['readiness']['hasPrompt'] is True


def test_invalid_output_contract_blocks_reading_the_scenario():
    result = read_scenario(MAIN_ONLY, contract_enabled=True, schema='{not json')
    assert 'scenario' not in result
    assert result['error'].startswith('Output contract: Invalid JSON')
    assert result['readiness']['hasPrompt'] is False


# --------------------------------------------------------------------------
# Optimization exposes, copies, and persists the complete optimized scenario.
# --------------------------------------------------------------------------

OPTIMIZATION_SCRIPT = '''
const window = globalThis;
function escapeHtml(text) { return String(text)
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;'); }
function showErrorModal(message) { window.lastError = message; }
const optimizationResults = { innerHTML: '' };
const promptOptimizationSection = { style: { display: 'none' } };
''' + extract('escapeScenarioAttribute', 'optimizedScenarioMessageLabel',
              'renderOptimizedScenarioHtml',
              'displayOptimizationRecommendations', 'collectOptimizationWorkspace',
              'restoreOptimizationWorkspace') + '''
function decode(text) { return text.replaceAll('&lt;', '<').replaceAll('&gt;', '>')
    .replaceAll('&amp;', '&'); }
displayOptimizationRecommendations(__RESPONSE__);
const html = optimizationResults.innerHTML;
const jsonMatch = html.match(/id="optimized-scenario-json"[^>]*>([\\s\\S]*?)<\\/textarea>/);
const renderedJson = jsonMatch ? JSON.parse(decode(jsonMatch[1])) : null;
const collected = collectOptimizationWorkspace();
// Simulate a fresh page: state is gone, only the exported workspace remains.
window.lastOptimizedScenario = null;
restoreOptimizationWorkspace(JSON.parse(JSON.stringify(collected)));
console.log(JSON.stringify({
    html: html,
    rendered_json: renderedJson,
    collected: collected,
    restored: window.lastOptimizedScenario,
}));
'''


OPTIMIZED_SCENARIO = {
    'version': 1,
    'messages': [
        {'id': 'instructions', 'role': 'system', 'content': 'Optimized <rules>',
         'analysis_mode': 'analyse'},
        {'id': 'chat', 'role': 'user', 'content': 'untouched input',
         'analysis_mode': 'retain', 'input_name': 'chat'},
    ],
    'output_contract': {'type': 'json_schema', 'name': 'answer_only', 'strict': True,
                        'schema': {'type': 'object'}},
}


def test_complete_optimized_scenario_is_shown_and_persisted():
    result = run_node(OPTIMIZATION_SCRIPT, __RESPONSE__={
        'recommendations': {'summary': 'do less'},
        'analysis_summary': 'summary',
        'optimized_prompt': 'Optimized <rules>',
        'optimized_scenario': OPTIMIZED_SCENARIO,
        'cost_breakdown': {'cost': 0.1, 'input_tokens': 1, 'output_tokens': 2},
    })
    assert result['rendered_json'] == OPTIMIZED_SCENARIO
    assert result['collected']['optimized_scenario'] == OPTIMIZED_SCENARIO
    assert result['restored'] == OPTIMIZED_SCENARIO
    html = result['html']
    assert '1. system · Analyse' in html
    assert '2. user · Retain · input: chat' in html
    assert 'Optimized &lt;rules&gt;' in html
    assert 'untouched input' in html
    assert 'Output contract · answer_only' in html


def test_optimization_without_a_scenario_offers_nothing_to_copy():
    result = run_node(
        OPTIMIZATION_SCRIPT, __RESPONSE__={'recommendations': {'summary': 'nothing'}}
    )
    assert result['rendered_json'] is None
    assert result['collected']['optimized_scenario'] is None
    assert 'Optimized Scenario' not in result['html']
