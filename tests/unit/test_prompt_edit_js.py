import json
import re
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]


def run_prompt_edit_case(previous, next_text, spans):
    js = REPO / 'static' / 'js' / 'prompt_edit.js'
    script = (
        "const edit = require(%s);"
        "const previous = %s;"
        "const nextText = %s;"
        "const spans = %s;"
        "const detected = edit.detectPromptEdit(previous, nextText);"
        "const adjusted = spans.map((span) => edit.adjustSpanForPromptEdit(span, detected));"
        "console.log(JSON.stringify({detected, adjusted}));"
    ) % (
        json.dumps(str(js)),
        json.dumps(previous),
        json.dumps(next_text),
        json.dumps(spans),
    )
    proc = subprocess.run(
        ['node', '-e', script],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout)


def test_replacement_inside_dynamic_span_extends_it_and_shifts_following_spans():
    previous = 'Intro\nChat: My pup needs a booster.\nReply JSON.'
    next_text = previous.replace('pup', 'canine')
    chat_start = previous.index('My pup')
    chat_end = previous.index('\nReply')
    reply_start = previous.index('Reply')
    result = run_prompt_edit_case(
        previous,
        next_text,
        [
            {'char_start': chat_start, 'char_end': chat_end},
            {'char_start': reply_start, 'char_end': len(previous)},
        ],
    )

    chat, reply = result['adjusted']
    assert result['detected']['delta'] == len('canine') - len('pup')
    assert chat['span']['char_start'] == chat_start
    assert chat['span']['char_end'] == chat_end + 3
    assert chat['changed'] is True
    assert chat['needsReview'] is False
    assert reply['span']['char_start'] == reply_start + 3
    assert reply['span']['char_end'] == len(next_text)
    assert reply['changed'] is True
    assert reply['needsReview'] is False


def test_same_length_replacement_inside_span_refreshes_snapshot():
    previous = 'Chat: My pup needs a booster.\nReply JSON.'
    next_text = previous.replace('pup', 'dog')
    span = {'char_start': previous.index('My pup'), 'char_end': previous.index('\nReply')}
    result = run_prompt_edit_case(previous, next_text, [span])

    adjusted = result['adjusted'][0]
    assert result['detected']['delta'] == 0
    assert adjusted['span'] == span
    assert adjusted['changed'] is True
    assert adjusted['needsReview'] is False


def test_edit_before_span_shifts_span_by_delta():
    previous = 'Intro\nChat: My pup needs a booster.'
    next_text = 'Short intro\nChat: My pup needs a booster.'
    span = {'char_start': previous.index('My pup'), 'char_end': len(previous)}
    result = run_prompt_edit_case(previous, next_text, [span])

    delta = len('Short intro') - len('Intro')
    adjusted = result['adjusted'][0]
    assert adjusted['span']['char_start'] == span['char_start'] + delta
    assert adjusted['span']['char_end'] == span['char_end'] + delta
    assert adjusted['changed'] is True
    assert adjusted['needsReview'] is False


def test_boundary_overlap_is_marked_for_review():
    previous = 'abcFOCUSdef'
    next_text = 'abZZCUSdef'
    span = {'char_start': 3, 'char_end': 8}
    result = run_prompt_edit_case(previous, next_text, [span])

    adjusted = result['adjusted'][0]
    assert adjusted['changed'] is True
    assert adjusted['needsReview'] is True


def test_template_loads_prompt_edit_before_app():
    html = (REPO / 'templates' / 'index.html').read_text(encoding='utf-8')
    assert html.index('js/prompt_edit.js') < html.index('js/app.js')


def run_editor_script(script, extra_functions=()):
    app = (REPO / 'static/js/app.js').read_text()
    names = ('focusSpansOf', 'normalizeFocusClient', 'adjustFociForPromptEdit') + extra_functions
    functions = '\n'.join(re.search(
        r'^function ' + name + r'\([^\n]*\) \{.*?^\}', app, re.M | re.S
    ).group() for name in names)
    setup = f"""
const assert = require('node:assert/strict');
const window = {{}};
window.FocalPromptPromptEdit = require({json.dumps(str(REPO / 'static/js/prompt_edit.js'))});
let activeScenarioMessageId = 'instructions';
"""
    proc = subprocess.run(['node', '-e', setup + functions + script], cwd=REPO,
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout) if proc.stdout.strip() else None


def test_editing_one_message_preserves_other_message_focus_for_ablation():
    from utils.inference_scenario import ablate_scenario

    result = run_editor_script("""
const hours = {focus: 'Opening hours', verified: true, attributable: true,
    spans: [{message_id: 'hours', char_start: 0, char_end: 12, text_snapshot: 'Open Monday.'}]};
const adjusted = adjustFociForPromptEdit([hours], 'Be brief.', 'Be very brief.');
assert.equal(adjusted.needsReview, false);
assert.equal(adjusted.foci[0].spans.length, 1);
assert.equal(adjusted.foci[0].spans[0].message_id, 'hours');
assert.equal(adjusted.foci[0].prompt_section, 'Open Monday.');
console.log(JSON.stringify(adjusted.foci[0]));
""")
    scenario = {'version': 1, 'messages': [
        {'id': 'instructions', 'role': 'developer', 'analysis_mode': 'analyse',
         'content': 'Be very brief.'},
        {'id': 'chat', 'role': 'user', 'analysis_mode': 'retain', 'content': 'Book a visit.'},
        {'id': 'hours', 'role': 'user', 'analysis_mode': 'analyse',
         'content': 'Open Monday. Park outside.'},
    ]}
    ablated, _ = ablate_scenario(scenario, result)
    assert [m['content'] for m in ablated['messages']] == [
        'Be very brief.', 'Book a visit.', ' Park outside.']


def test_multimessage_focus_only_adjusts_edited_message_spans():
    run_editor_script("""
const focus = {focus: 'Context', verified: true, spans: [
    {message_id: 'instructions', char_start: 0, char_end: 9, text_snapshot: 'Be brief.'},
    {message_id: 'hours', char_start: 0, char_end: 12, text_snapshot: 'Open Monday.'}
]};
const result = adjustFociForPromptEdit([focus], 'Be brief.', 'Be very brief.');
assert.equal(result.changed, true);
assert.equal(result.needsReview, false);
const spans = result.foci[0].spans;
assert.equal(spans.length, 2);
assert.deepEqual(spans.map(s => [s.message_id, s.char_start, s.char_end, s.text]), [
    ['hours', 0, 12, 'Open Monday.'], ['instructions', 0, 14, 'Be very brief.']
]);
assert.equal(focus.spans[0].char_end, 9, 'must not mutate the input');
""")


def test_deleting_entire_focus_marks_it_unverified():
    run_editor_script("""
const focus = {focus: 'Style', verified: true, attributable: true, reason: null,
    spans: [{message_id: 'instructions', char_start: 0, char_end: 9, text: 'Be brief.'}]};
const result = adjustFociForPromptEdit([focus], 'Be brief.', '');
assert.equal(result.foci[0].spans.length, 0);
assert.equal(result.foci[0].verified, false);
assert.equal(result.foci[0].attributable, false);
assert.equal(result.foci[0].reason, 'unverified');
assert.equal(result.needsReview, true);
""")


def test_missing_spans_show_repair_control_even_with_stale_verified_flag():
    run_editor_script("""
let foci = [{focus: 'Opening hours', verified: true, spans: []}];
const fociContainer = {}, promptInput = {value: 'Open Monday.'}, runAblationBtn = {};
const focusColors = ['blue'];
const selectedFocusIndex = null;
function getDarkColor(c) { return c; }
function escapeHtml(s) { return s; }
function syncPromptSpanTracking() {}
function computeClientOverlaps() { return []; }
function overlapsForFocusIndex() { return []; }
function setupDragAndDrop() {}
function updateMergeButton() {}
function updateCoverageVisualization() {}
function updateCoverageStats() {}
renderFoci();
assert.match(fociContainer.innerHTML, /Not grounded for ablation/);
assert.match(fociContainer.innerHTML, /Use selection as span/);
assert.doesNotMatch(fociContainer.innerHTML, />Verified</);
""", extra_functions=('renderFoci',))
