"""Replay provenance, stored results, deterministic controls, and offline route contract."""
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / 'examples/demos/lisbon/pup4ominiFull.json'
SHA256 = 'bf8271e5a361474aa3f24c062790d3ccf81045a5ce50080c967848ffbe50ae6e'
ASTRA_FIXTURE = ROOT / 'examples/demos/lisbon/Astrapup.json'
ASTRA_SHA256 = '3abe3ee83d92e8da6dc5db1c025e044bce730b85697e2d926a8892981de67134'


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


def test_fixture_is_the_verified_privacy_redacted_workspace():
    raw = FIXTURE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SHA256
    data = json.loads(raw)
    assert data['demo_redaction']['version'] == 1
    assert 'Clinic location redacted' in data['demo_redaction']['notice']
    assert '█' in data['prompt_analysis']['scenario']['messages'][2]['content']
    assert data['focalprompt_workspace'] is True
    assert data['version'] == 2
    assert data['prompt_analysis']['scenario']['messages'][0]['role'] == 'system'


def test_redacted_astra_recording_and_comparison_are_grounded_in_actual_data():
    assert hashlib.sha256(ASTRA_FIXTURE.read_bytes()).hexdigest() == ASTRA_SHA256
    node("""
const astra=JSON.parse(fs.readFileSync('examples/demos/lisbon/Astrapup.json','utf8'));
assert.equal(astra.demo_redaction.version,1);
assert.match(astra.demo_redaction.notice,/Clinic location redacted/);
const before=JSON.stringify(astra), recording=definition.comparisonWorkspaces[0];
const data=adapter.prepareComparison(astra,recording);
assert.equal(data.modelLabel,astra.prompt_analysis.focus_workflow.context.model.model);
assert.equal(data.modelLabel,'gpt-6-astra');
assert.equal(data.booking.index,3);assert.equal(data.cat.index,19);assert.equal(data.hierarchy.index,15);
for(const key of ['booking','cat','hierarchy'])assert.equal(data[key].spans[0].text,recording.expectedText[key]);
assert.equal(data.booking.spans[0].role,'system');assert.equal(data.hierarchy.spans[0].role,'user');
assert.equal(data.series.baseline.n,10);assert.equal(data.series.baseline.counts.refusal,10);
assert.match(data.series.baseline.evidence,/Editorial reading/);
assert.deepEqual(data.series.baseline.samples.map(s=>s.raw),astra.prompt_analysis.focus_workflow.samples.map(s=>s.content));
assert.equal(data.bookingShare,0);
assert.equal(data.pair.views.combined.output_count,105);
assert.equal(data.pair.views.combined.condition_count,20);
assert.equal(data.pair.views.full.row_share,0);
assert.deepEqual(data.pair,astra.prompt_analysis.singleton_experiment.result.pairwise_resemblance.pairs.find(p=>p.row_index===3 && p.column_index===19));
assert.equal(JSON.stringify(astra),before);assert.equal(JSON.stringify(data.workspace),before);
const primary=adapter.prepare(workspace,definition);
assert.equal(primary.singleton.pairwise_resemblance.pairs.find(p=>p.row_index===4 && p.column_index===15).views.combined.row_share,1);
const frames=adapter.frames(primary,definition,[data]);
assert.equal(frames.length,16);
const first=frames.findIndex(f=>f.id==='comparison');
assert.equal(frames[first-1].id,'order');
assert.deepEqual(frames.slice(first,first+3).map(f=>[f.id,f.phase,f.workspaceId]),[
 ['comparison','prompt','astra'],['comparison','baseline','astra'],['comparison','dominance','astra']]);
assert.equal(frames[first+3].id,'jev');assert.equal(frames[first+3].workspaceId,undefined);
""")


def test_astra_comparison_fails_loudly_on_inconsistent_recordings():
    node(r"""
const original=JSON.parse(fs.readFileSync('examples/demos/lisbon/Astrapup.json','utf8'));
const recording=definition.comparisonWorkspaces[0];
function rejects(change,pattern){const input=structuredClone(original);change(input.prompt_analysis);assert.throws(()=>adapter.prepareComparison(input,recording),pattern);}
rejects(pa=>pa.focus_workflow.context.model.model='wrong-model',/unexpected baseline model/);
rejects(pa=>pa.foci[3].focus='Missing booking',/grounded focus/);
rejects(pa=>pa.foci[15].focus='Missing hierarchy',/hierarchy/);
rejects(pa=>pa.foci[19].focus='Missing cat',/grounded focus/);
rejects(pa=>[pa.foci[3],pa.foci[4]]=[pa.foci[4],pa.foci[3]],/booking focus index/);
rejects(pa=>pa.foci[3].prompt_section='Altered text',/Source text mismatch/);
rejects(pa=>pa.scenario.messages[0].content=pa.scenario.messages[0].content.replace('must always','might often'),/Source text mismatch/);
rejects(pa=>pa.focus_workflow.samples.pop(),/ten reviewed baseline outputs/);
rejects(pa=>pa.focus_workflow.samples[0].content='I will book the dog here.',/refusal evidence/);
rejects(pa=>pa.singleton_experiment.result.pairwise_resemblance.pairs=[],/missing booking\/cat-only matrix pair/);
rejects(pa=>pa.singleton_experiment.result.pairwise_resemblance.pairs.find(p=>p.row_index===3 && p.column_index===19).views.combined.row_share=.8,/does not favor Cat-only/);
rejects(pa=>pa.singleton_experiment.context.model.model='wrong-model',/models differ/);
""")


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
assert.equal(frames.length,13); assert.equal(nav.frame.id,'problem');
assert.deepEqual(frames.filter(f=>f.id==='order').map(f=>f.phase),['condition-a','condition-b']);
assert.deepEqual([...new Set(frames.map(f=>f.id))],
 ['problem','baseline','foci','singleton','dominance','ablation','order','jev','end']);
nav.previous(); assert.equal(nav.index,0);
for(let i=0;i<frames.length;i++) {firstRun.push(JSON.stringify(nav.frame));nav.next();}
assert.equal(nav.index,frames.length-1);
for(let i=frames.length-1;i>=0;i--) {assert.equal(JSON.stringify(nav.frame),firstRun[i]);nav.previous();}
nav.go(frames.findIndex(f=>f.id==='jev' && f.phase==='ordered'));assert.equal(nav.frame.phase,'ordered');nav.reset();assert.equal(nav.index,0);
for(let i=0;i<frames.length;i++) {assert.equal(JSON.stringify(nav.frame),firstRun[i]);nav.next();}
assert.equal(frames.some(f=>f.id==='comparison'),false);
const withComparison = adapter.frames(data,{...definition,comparisonWorkspaces:[{id:'second'}]},[data]);
assert.equal(withComparison.length,16);
const comparisonFrames=withComparison.filter(f=>f.id==='comparison');
assert.deepEqual(comparisonFrames.map(f=>f.phase),['prompt','baseline','dominance']);
assert.ok(comparisonFrames.every(f=>f.workspaceId==='second'));
const firstComparison=withComparison.findIndex(f=>f.id==='comparison');
assert.equal(withComparison[firstComparison-1].id,'order');
assert.equal(withComparison[firstComparison+3].id,'jev');
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


def test_matched_global_orders_are_semantically_selected_and_preserve_all_evidence():
    node("""
const compare=require('./static/js/order_comparison.js');
const source=workspace.prompt_analysis.focus_order.results;
source.global_order_experiment.permutations.reverse(); // Not a positional lookup.
const data=adapter.prepare(workspace,definition), [a,b]=data.matchedOrders;
assert.equal(a.permutation_id,4);assert.equal(b.permutation_id,2);
assert.equal(a.focus_positions['Cat only'],1);assert.equal(b.focus_positions['Cat only'],1);
assert.deepEqual(compare.counts(a),{n:3,judged:3,complies:1});
assert.deepEqual(compare.counts(b),{n:3,judged:3,complies:0});
assert.deepEqual(a.outputs,compare.findPermutationByOrder(source.global_order_experiment.permutations,definition.orderComparison.orders[0]).outputs);
assert.deepEqual(b.outputs,compare.findPermutationByOrder(source.global_order_experiment.permutations,definition.orderComparison.orders[1]).outputs);
assert.deepEqual(a.behavioral_judgments.map(j=>j.classification),['VIOLATES','COMPLIES','VIOLATES']);
assert.ok(b.outputs.every(raw=>!adapter.outputText(raw).includes('cat-only')));
assert.ok(a.outputs.every(raw=>adapter.outputText(raw).includes('cat-only clinic')));
assert.ok(adapter.outputText(a.outputs[1]).includes('at a different clinic'));
assert.ok(adapter.outputText(a.outputs[2]).includes('please confirm that your pup is actually a cat'));
assert.equal(data.positions.length,4,'controlled sweep is still available');
for(const permutation of [a,b]) {
 assert.equal(permutation.model,'gpt-4o-mini');assert.equal(permutation.temperature,.7);
 assert.equal(permutation.reconstruction.template.focus_texts['2'],data.cat.spans[0].text);
}
assert.equal(source.scenario_metadata.ordering_role,'user');
const broken=JSON.parse(JSON.stringify(workspace));
broken.prompt_analysis.focus_order.results.global_order_experiment.permutations=source.global_order_experiment.permutations.filter(p=>p.permutation_id!==2);
assert.throws(()=>adapter.prepare(broken,definition),/Expected one recorded global permutation/);
const wrong=compare.findPermutationByOrder(source.global_order_experiment.permutations,definition.orderComparison.orders[0]);
wrong.focus_positions['Cat only']=0;
assert.throws(()=>adapter.prepare(workspace,definition),/inconsistent focus positions/);
""")


def test_all_output_view_highlights_without_changing_or_trusting_recorded_text():
    node(r'''
const samples=require('./static/js/recorded_samples.js');
const value='A <script> & repeated repeated.\nUnchanged.';
const marked=samples.highlight(value,['<script>','repeated','repeat']);
assert.equal(marked,'A <mark>&lt;script&gt;</mark> &amp; <mark>repeated</mark> <mark>repeated</mark>.\nUnchanged.');
const raw=JSON.stringify({suggestedMessage:value,other:'preserved'});
const html=samples.renderAll([raw,'Another output'],{highlights:['<script>'],judgments:[{sample_index:1,classification:'COMPLIES',rationale:'<img src=x>'}]});
assert.ok(html.includes('&quot;other&quot;:&quot;preserved&quot;'));
assert.ok(html.includes('data-recorded-panel="0"'));
assert.ok(html.includes('data-recorded-panel="1"'));
assert.ok(html.includes('data-classification="COMPLIES"'));
assert.ok(html.includes('&lt;img src=x&gt;'));
assert.ok(!html.includes('<script>'));assert.ok(!html.includes('<img'));
const compare=require('./static/js/order_comparison.js');
const data=workspace.prompt_analysis.focus_order.results;
data.global_order_experiment.permutations[0].outputs[0]='</script><img src=x>';
assert.ok(!compare.render(data).includes('</script><img'));
''')


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
        assert b'Clinic location is redacted in prompts, recorded outputs and downloads.' in r.data
        assert b'js/app.js' in r.data  # actual lab template and renderers, isolated by replay guard
        assert b'js/replay_guard.js' in r.data
        assert r.data.index(b'js/replay_guard.js') < r.data.index(b'js/app.js')
        assert b'fonts.googleapis.com' not in r.data
        fixture = client.get('/demo/lisbon/workspaces/gpt4omini.json')
        assert fixture.status_code == 200
        assert fixture.headers['Content-Encoding'] == 'gzip'
        assert len(fixture.data) < 4_000_000
        assert gzip.decompress(fixture.data) == FIXTURE.read_bytes()
        astra = client.get('/demo/lisbon/workspaces/astra.json')
        assert astra.status_code == 200
        assert len(astra.data) < 4_000_000
        assert gzip.decompress(astra.data) == ASTRA_FIXTURE.read_bytes()
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
