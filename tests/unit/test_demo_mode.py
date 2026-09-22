"""Replay provenance, stored results, deterministic controls, and offline route contract."""
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / 'examples/demos/lisbon/pup4ominiFull.json'
SHA256 = '1c178997a02a417dbc039d0fe117a520c31b95e95dbf0f593961c2aada244a57'


def node(script):
    setup = """
const assert = require('node:assert/strict');
const fs = require('node:fs');
const definition = require('./static/js/demo_definition.js');
const adapter = require('./static/js/demo_data.js');
const workspace = JSON.parse(fs.readFileSync('examples/demos/lisbon/pup4ominiFull.json', 'utf8'));
"""
    result = subprocess.run(['node', '-e', setup + script], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_fixture_is_the_exact_supplied_workspace():
    raw = FIXTURE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SHA256
    data = json.loads(raw)
    assert data['focalprompt_workspace'] is True
    assert data['version'] == 2
    assert data['prompt_analysis']['scenario']['messages'][0]['role'] == 'system'


def test_replay_uses_actual_spans_outputs_orders_and_judgments_without_mutation():
    node("""
const before = JSON.stringify(workspace);
const data = adapter.prepare(workspace, definition);
const pa = workspace.prompt_analysis;
assert.equal(data.booking.index, 4); assert.equal(data.cat.index, 15);
assert.equal(data.booking.spans[0].role, 'system'); assert.equal(data.cat.spans[0].role, 'user');
assert.equal(data.cat.spans[0].text, pa.scenario.messages[2].content.slice(335,360));
assert.equal(data.series.baseline.n, 10);
assert.deepEqual(data.series.baseline.counts, {booking:10});
assert.match(data.series.baseline.evidence, /Stored LLM/);
assert.deepEqual(data.series.removeBooking.counts, {booking:4, refusal:1});
assert.deepEqual(data.series.catOnly.counts, {refusal:5});
assert.deepEqual(data.series['order-0'].counts, {refusal:3});
assert.deepEqual(data.positions[0].indices, [15,13,14,16]);
assert.deepEqual(data.jev.selected, pa.jev_experiment.state.selection.selected_indices);
assert.deepEqual(data.jev.groups[0].ordered, pa.jev_experiment.state.orders.instructions);
assert.deepEqual(data.series.jevSelected.counts, {refusal:10});
assert.deepEqual(data.series.jevOrdered.counts, {refusal:6,'cat-substitution':4});
assert.match(data.series.jevOrdered.evidence, /Editorial/);
assert.deepEqual(data.series.baseline.samples.map(s=>s.raw), pa.focus_workflow.samples.map(s=>s.content));
assert.deepEqual(data.series.removeBooking.samples.map(s=>s.raw), pa.single_ablation.ablation_results[4].ablated_outputs);
assert.deepEqual(data.series.catOnly.samples.map(s=>s.raw), pa.singleton_experiment.result.focus_results[15].singleton_outputs);
assert.deepEqual(data.series.jevOrdered.samples.map(s=>s.raw), pa.jev_experiment.state.arms.ordered.samples.map(s=>s.output));
for (const series of Object.values(data.series)) for (const sample of series.samples) {
 assert.equal(sample.text, JSON.parse(sample.raw).suggestedMessage);
}
assert.ok(Object.isFrozen(data.workspace.prompt_analysis.foci[0].spans));
assert.equal(JSON.stringify(workspace), before);
assert.equal(JSON.stringify(data.workspace), before);
""")


def test_navigation_is_deterministic_bounded_reversible_and_resettable():
    node("""
const data = adapter.prepare(workspace,definition), frames = adapter.frames(data,definition);
const nav = adapter.navigator(frames), firstRun = [];
assert.equal(frames.length,16); assert.equal(nav.frame.id,'problem');
assert.deepEqual([...new Set(frames.map(f=>f.id))],
 ['problem','baseline','foci','singleton','dominance','ablation','order','jev','end']);
nav.previous(); assert.equal(nav.index,0);
for(let i=0;i<frames.length;i++) {firstRun.push(JSON.stringify(nav.frame));nav.next();}
assert.equal(nav.index,frames.length-1);
for(let i=frames.length-1;i>=0;i--) {assert.equal(JSON.stringify(nav.frame),firstRun[i]);nav.previous();}
nav.go(frames.findIndex(f=>f.id==='jev' && f.phase==='ordered'));assert.equal(nav.frame.phase,'ordered');nav.reset();assert.equal(nav.index,0);
for(let i=0;i<frames.length;i++) {assert.equal(JSON.stringify(nav.frame),firstRun[i]);nav.next();}
assert.equal(frames.some(f=>f.id==='comparison'),false);
const withComparison = adapter.frames(data,definition,[data]);
assert.equal(withComparison.at(-2).id,'comparison');
delete workspace.prompt_analysis.singleton_experiment.result.pairwise_resemblance;
const withoutGrid = adapter.frames(adapter.prepare(workspace,definition),definition);
assert.equal(withoutGrid.some(f=>f.id==='dominance'),false);
assert.equal(withoutGrid.some(f=>f.id==='singleton'),true);
""")


def test_missing_optional_results_are_skipped_and_bad_grounding_is_rejected():
    node("""
delete workspace.prompt_analysis.focus_order;
delete workspace.prompt_analysis.jev_experiment;
delete workspace.prompt_analysis.singleton_experiment;
const data = adapter.prepare(workspace,definition);
assert.deepEqual(adapter.frames(data,definition).map(f=>f.id), ['problem','baseline','foci','ablation','end']);
assert.deepEqual(data.series.baseline.counts,{booking:10});
assert.match(data.series.baseline.evidence,/Editorial/);
workspace.prompt_analysis.foci[15].spans[0].text_snapshot = 'Changed';
assert.throws(()=>adapter.prepare(workspace,definition),/Source text mismatch/);
""")


def test_import_and_replay_share_workspace_validation_and_migration():
    node("""
const format = require('./static/js/workspace_format.js');
assert.equal(format.validate(workspace),null);
assert.match(format.validate({...workspace,version:99}),/Unsupported workspace version/);
const legacy={focalprompt_workspace:true,version:1,prompt_analysis:{prompt:'Hello',foci:[{focus:'Greeting',spans:[{char_start:0,char_end:5}]}]}};
const migrated=format.migrate(legacy);
assert.equal(legacy.version,1);assert.equal(migrated.version,2);
assert.equal(migrated.prompt_analysis.scenario.messages[0].role,'user');
assert.equal(migrated.prompt_analysis.foci[0].spans[0].message_id,'legacy-prompt');
""")
    app_js = (ROOT / 'static/js/app.js').read_text()
    assert 'return window.FocalPromptWorkspaceFormat.validate(data)' in app_js
    html = (ROOT / 'templates/index.html').read_text()
    assert html.index('js/workspace_format.js') < html.index('js/app.js')


def test_replay_routes_are_read_only_and_available_without_live_inference(monkeypatch):
    from app_new import app
    monkeypatch.setenv('FOCALPROMPT_HOSTED_MODE', '1')
    monkeypatch.setenv('FOCALPROMPT_ALLOW_LIVE_INFERENCE', '0')
    with app.test_client() as client:
        r = client.get('/demo/lisbon')
        assert r.status_code == 200
        assert b'demo_mode.js' in r.data
        assert b'js/app.js' in r.data  # actual lab template and renderers, isolated by replay guard
        assert b'js/replay_guard.js' in r.data
        assert r.data.index(b'js/replay_guard.js') < r.data.index(b'js/app.js')
        assert b'fonts.googleapis.com' not in r.data
        fixture = client.get('/demo/lisbon/workspaces/gpt4omini.json')
        assert fixture.status_code == 200
        assert fixture.headers['Content-Encoding'] == 'gzip'
        assert len(fixture.data) < 4_000_000
        assert gzip.decompress(fixture.data) == FIXTURE.read_bytes()
        for path in ['/experiments', '/about', '/lab']:
            assert b'/demo/lisbon' in client.get(path).data
        assert client.get('/demo/unknown').status_code == 404
        assert client.get('/demo/lisbon/workspaces/unknown.json').status_code == 404
        assert client.post('/demo/lisbon/workspaces/gpt4omini.json').status_code == 405


def test_shared_output_browser_preserves_text_and_escapes_untrusted_output():
    node(r'''
const samples = require('./static/js/recorded_samples.js');
const raw = JSON.stringify({suggestedMessage:'Use {{tag}}.\n<script>alert(1)</script> & "quoted"', other:'kept'});
assert.equal(samples.text(raw), JSON.parse(raw).suggestedMessage);
assert.equal(samples.text('verbatim <text>'), 'verbatim <text>');
const rendered = samples.render([raw, 'Second output'], {id:'test',selected:1});
assert.ok(rendered.includes('&lt;script&gt;'));
assert.ok(!rendered.includes('<script>'));
assert.ok(rendered.includes('data-recorded-panel="0" hidden'));
assert.ok(rendered.includes('data-recorded-panel="1" >'));
assert.ok(rendered.includes('&quot;other&quot;:&quot;kept&quot;'));
const partial = samples.render([null, 'Original sample two', null, 'Original sample four']);
assert.ok(partial.includes('2 samples'));
assert.ok(partial.includes('data-recorded-sample="3"'));
assert.ok(!partial.includes('data-recorded-sample="0"'));
assert.ok(partial.includes('data-recorded-panel="1" >'));
''')


def test_replay_guard_blocks_live_requests_and_keeps_preferences_in_memory():
    node(r'''
const vm = require('node:vm'), sent = [];
const browserWindow = {location:{href:'https://example.test/demo/lisbon',origin:'https://example.test'},
 fetch: (...args)=>{sent.push(args);return Promise.resolve(new Response('fixture'));}};
vm.runInNewContext(fs.readFileSync('./static/js/replay_guard.js','utf8'), {window:browserWindow,URL,Response});
(async()=>{
 browserWindow.FocalPromptReplayStorage.setItem('draft','local to replay');
 assert.equal(browserWindow.FocalPromptReplayStorage.getItem('draft'),'local to replay');
 assert.equal((await browserWindow.fetch('/api/generate-output',{method:'POST'})).status,409);
 assert.equal((await browserWindow.fetch('https://other.test/send')).status,409);
 assert.equal((await browserWindow.fetch('/demo/lisbon/workspaces/gpt4omini.json',{method:'POST'})).status,409);
 assert.equal(sent.length,0);
 assert.equal(await (await browserWindow.fetch('/demo/lisbon/workspaces/gpt4omini.json')).text(),'fixture');
 assert.equal(sent.length,1);
})().catch(error=>{console.error(error);process.exit(1)});
''')
