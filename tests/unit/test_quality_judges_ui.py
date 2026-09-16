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
    const prepare = async input => ({version: 1, outputs: input.outputs, batch_size: 4,
        n_outputs_total: input.outputs.length, sample_fraction: 1, sample_seed: 0});
    const evaluate = args => q.evaluate({prepare, ...args});
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
        assert.deepEqual(input, {...context, sample_pct: 100, sample_fraction: 1, batch_mode: true}, 'No peer scores are included in judge input');
        assert.equal(judge.result, undefined);
        if (failPeer && judge.id === 'external') throw new Error('Temporary failure');
        return {judge: {role: judge.id, model: judge.model, provider: judge.provider},
            evaluations: [{label: 'A', overall_score: judge.id === 'self' ? 0 : 80},
                {label: 'B', overall_score: 25}]};
    }
    let state = await evaluate({context, judges: single, request});
    assert.equal(calls.length, 1, 'Disabled peer makes no request');
    assert.equal(state.judges[0].status, 'complete');
    const saved = JSON.parse(JSON.stringify(state));
    calls = [];
    failPeer = true;
    state = await evaluate({context, judges: dual, previous: saved, request});
    assert.deepEqual(calls.map(c => c.judge), ['external'], 'Adding a judge reuses completed self judgment');
    assert.equal(state.judges[0].status, 'complete');
    assert.equal(state.judges[1].status, 'error');
    assert.deepEqual(state.judges[1].result.evaluations, []);
    calls = [];
    failPeer = false;
    state = await evaluate({context, judges: dual, previous: JSON.parse(JSON.stringify(state)), request});
    assert.deepEqual(calls.map(c => c.judge), ['external'], 'Retry preserves successful peer');
    assert.deepEqual(q.comparisonRows(state), [
        {label: 'A', self: 0, external: 80, difference: 80},
        {label: 'B', self: 25, external: 25, difference: 0}]);
    assert.match(q.comparisonHtml(state, s => s), /\+80.0/);
    assert.deepEqual(context, original);
    calls = [];
    state = await evaluate({context, judges: dual, previous: state, request});
    assert.equal(calls.length, 2, 'An explicit rerun evaluates a completed pair anew');
    assert.deepEqual(calls[0].input, calls[1].input);
    calls = [];
    context.eval_criteria = 'Revised criteria';
    state = await evaluate({context, judges: dual, previous: state, request});
    assert.equal(calls.length, 2, 'Changed criteria invalidates both previous results');
    state = await evaluate({context, judges: single, request: async () => ({judge: {
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
    const input = JSON.parse(options.body);
    if (url === '/api/quality-evaluation-plan') return {ok: true, text: async () => JSON.stringify({
        version: 1, batch_size: 4, outputs: input.outputs.map(o => ({label:o.label, text:o.text})),
        n_outputs_total: input.outputs.length, sample_fraction: 1, sample_seed: 0})};
    assert.equal(url, '/api/evaluate-outputs-quality');
    requests.push(input);
    return {ok: true, text: async () => JSON.stringify({judge: {role: input.judge_role, model: input.model, provider: input.provider},
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


def test_95_outputs_partial_scores_timeout_and_exported_retry():
    run_js("const assert = require('node:assert/strict'); const window = {};\n" + MODULE + r"""
(async () => {
    const q = window.FocalPromptQuality;
    const context = {outputs: Array.from({length:95}, (_,i) => ({label:'Sample '+i, text:'Output '+i})),
        eval_criteria:'Synthetic task fit', sample_pct:100, sample_seed:0, temperature:.2};
    const judges = q.judgesFor({model:'gpt-3.5-turbo',provider:'openai'}, true,
        {model:'gpt-5.6-sol',provider:'openai'});
    let prepares = 0, attempt = 1, calls = [], updates = [];
    const prepare = async input => {
        prepares++;
        return {version:1, batch_size:4, outputs:input.outputs, n_outputs_total:95, sample_fraction:1, sample_seed:0};
    };
    const missing = new Set([13,14,15,89,90,91]);
    async function request(input, judge) {
        const index = Number(input.outputs[0].label.split(' ')[1]);
        calls.push({id:judge.id, index, input:structuredClone(input)});
        assert.equal(input.batch_mode, true);
        assert.equal(input.sample_fraction, 1);
        assert.ok(input.outputs.length <= 4);
        assert.equal(input.evaluations, undefined);
        assert.equal(judge.result, undefined);
        if (attempt === 1 && judge.id === 'external' && index === 8) {
            return q.readResponse({status:504, ok:false, text:async ()=>'An error occurred. FUNCTION_INVOCATION_TIMEOUT'});
        }
        return {judge:{role:judge.id,model:judge.model,provider:judge.provider},
            evaluations:input.outputs.map(item => ({label:item.label, output_text:item.text,
                overall_score:attempt === 1 && judge.id === 'self' && missing.has(Number(item.label.split(' ')[1]))
                    ? null : attempt === 1 ? 70 : 85})),
            usage:{prompt_tokens:100,completion_tokens:20}, cost_breakdown:{total_cost:.01},
            assessment_protocol:'task-quality-batches-v2'};
    }
    const options = {context, judges, prepare, request, wait: async()=>{}, onUpdate: s=>updates.push(s)};
    let state = await q.evaluate(options);
    assert.equal(calls.filter(c=>c.id==='self').length, 24);
    assert.equal(calls.filter(c=>c.id==='external').length, 5, 'Two completed batches plus three attempts at the failed batch');
    assert.equal(state.judges[0].status, 'partial');
    assert.equal(state.judges[1].status, 'error');
    assert.match(state.judges[1].error, /timed out/);
    assert.equal(q.progress(state,state.judges[0]).scored,89);
    assert.equal(q.progress(state,state.judges[1]).scored,8);
    assert.equal(q.comparisonRows(state).length,95,'Unscored rows remain visible');
    assert.match(q.comparisonHtml(state,s=>s), /—/);
    assert.ok(updates.some(s=>q.progress(s,s.judges[0]).scored===4),'Completed batches appear immediately');
    const saved = JSON.parse(JSON.stringify(state));
    calls = []; attempt = 2;
    state = await q.evaluate({...options,previous:saved});
    assert.equal(prepares,1,'Exported plan is reused without a new draw');
    assert.deepEqual(calls.filter(c=>c.id==='self').map(c=>c.index),[12,88]);
    assert.equal(calls.filter(c=>c.id==='external').length,22);
    assert.ok(state.judges.every(j=>j.status==='complete' && q.progress(state,j).scored===95));
    assert.equal(state.judges[0].result.evaluations[12].overall_score,70,'Successful rows are not overwritten on retry');
    assert.equal(state.judges[0].result.evaluations[13].overall_score,85);
    assert.equal(state.judges[1].result.evaluations[0].overall_score,70,'Successful peer batches are not rerun');
    assert.equal(state.judges[0].result.usage.prompt_tokens,2600);
    assert.ok(Math.abs(state.judges[0].result.cost_breakdown.total_cost-.26)<1e-9);
    for (const own of calls.filter(c=>c.id==='self')) {
        assert.deepEqual(own.input, calls.find(c=>c.id==='external' && c.index===own.index).input,
            'Retried batches preserve the common neighbouring outputs');
    }
    calls=[];
    await q.evaluate({...options,previous:state});
    assert.equal(calls.length,48,'Explicit rerun of a complete pair evaluates both again');
    // Old exports marked complete with gaps must also resume rather than discard 89 valid rows.
    const legacy = structuredClone(saved); delete legacy.plan;
    for (const j of legacy.judges) {delete j.batches; j.status='complete';}
    calls=[];
    await q.evaluate({...options,previous:legacy});
    assert.deepEqual(calls.filter(c=>c.id==='self').map(c=>c.index),[12,88]);
    calls=[];
    await q.evaluate({...options,context:{...context,eval_criteria:'Changed criteria'},previous:state});
    assert.equal(calls.length,48,'Changed criteria do not mix old scores into the new evaluation');
    await assert.rejects(q.readResponse({status:502,ok:false,text:async()=>'<html>private backend details</html>'}),
        error=>/HTTP 502/.test(error.message) && !error.message.includes('private'));
    await assert.rejects(q.readResponse({status:422,ok:false,text:async()=>'{"error":"Unknown model"}'}),/Unknown model/);
})().catch(e=>{console.error(e);process.exit(1);});
""")


def test_network_failure_at_64_scores_recovers_without_rerunning_saved_batches():
    run_js("const assert = require('node:assert/strict'); const window = {};\n" + MODULE + r"""
(async () => {
    const q = window.FocalPromptQuality;
    const context = {outputs:Array.from({length:95},(_,i)=>({label:String(i),text:'Synthetic output '+i})),
        eval_criteria:'Correct arithmetic',sample_pct:100,sample_seed:0,temperature:.2};
    const judges=q.judgesFor({model:'self-model',provider:'openai'},true,{model:'peer-model',provider:'openai'});
    const prepare=async input=>({version:1,batch_size:4,outputs:input.outputs,n_outputs_total:95,sample_fraction:1,sample_seed:0});
    const attempts=new Map(), calls=[], updates=[], delays=[];
    let persistent=false;
    globalThis.fetch=async (_path,options)=>{
        const body=JSON.parse(options.body), index=Number(body.outputs[0].label), key=body.role+':'+index;
        attempts.set(key,(attempts.get(key)||0)+1); calls.push(body);
        if (body.role==='external' && index===64 && (persistent || attempts.get(key)===1)) throw new TypeError('Failed to fetch');
        return {ok:true,status:200,text:async()=>JSON.stringify({
            judge:{role:body.role,model:body.model,provider:'openai'},
            evaluations:body.outputs.map(o=>({label:o.label,overall_score:index,output_text:o.text})),
            cost_breakdown:{total_cost:.01},usage:{prompt_tokens:10},assessment_protocol:'task-quality-batches-v2'})};
    };
    const request=(input,judge)=>q.fetchJson('/api/evaluate-outputs-quality',{body:JSON.stringify({...input,role:judge.id,model:judge.model})});
    const options={context,judges,prepare,request,wait:async ms=>delays.push(ms),onUpdate:s=>updates.push(s)};
    let state=await q.evaluate(options);
    assert.ok(state.judges.every(j=>j.status==='complete' && q.progress(state,j).scored===95));
    assert.deepEqual(delays,[2000]);
    assert.equal(calls.filter(c=>c.role==='self').length,24);
    assert.equal(calls.filter(c=>c.role==='external').length,25);
    assert.ok(updates.some(s=>s.judges[1].retry?.attempt===2 && q.progress(s,s.judges[1]).scored===64));
    const retried=calls.filter(c=>c.role==='external'&&c.outputs[0].label==='64');
    assert.deepEqual(retried[0],retried[1],'Retry payload preserves criteria, model, sample and output order');
    assert.equal(state.judges[1].retry,undefined);
    assert.equal(state.judges[1].batches.filter(b=>b.will_retry).length,1);
    assert.equal(state.judges[1].result.usage.prompt_tokens,240,'Only received usage is counted');
    assert.ok(Math.abs(state.judges[1].result.cost_breakdown.total_cost-.24)<1e-9);

    // A sustained outage must stop after the bounded attempts, then resume from 64.
    persistent=true; attempts.clear(); calls.length=0; delays.length=0;
    state=await q.evaluate(options);
    assert.equal(state.judges[1].status,'error');
    assert.equal(q.progress(state,state.judges[1]).scored,64);
    assert.equal(attempts.get('external:64'),3);
    assert.deepEqual(delays,[2000,5000]);
    assert.match(state.judges[1].error,/Stopped after 3 attempts/);
    assert.doesNotMatch(state.judges[1].error,/Failed to fetch/);
    const saved=JSON.parse(JSON.stringify(state));
    persistent=false; calls.length=0; delays.length=0;
    state=await q.evaluate({...options,previous:saved});
    assert.equal(calls.length,8,'Only the remaining 31 outputs need requests');
    assert.ok(calls.every(c=>c.role==='external' && Number(c.outputs[0].label)>=64));
    assert.ok(state.judges.every(j=>j.status==='complete'));
    assert.deepEqual(state.judges[1].result.evaluations.slice(0,64),saved.judges[1].result.evaluations);
    assert.deepEqual(delays,[]);
})().catch(e=>{console.error(e);process.exit(1);});
""")


def test_retry_classification_and_retry_after_without_paid_calls():
    run_js("const assert = require('node:assert/strict'); const window = {};\n" + MODULE + r"""
(async () => {
    const q=window.FocalPromptQuality;
    const ok=()=>({ok:true,status:200,text:async()=>'{"done":true}'});
    for (const status of [408,429,500,502,503,504]) {
        let count=0; const waits=[];
        globalThis.fetch=async()=>++count===1 ? {ok:false,status,headers:{get:()=>status===429?'3':null},
            text:async()=>status===502?'<html>private backend error</html>':'{"error":"Service temporarily unavailable"}'} : ok();
        assert.deepEqual(await q.retryRequest(()=>q.fetchJson('/quality',{}),{wait:async ms=>waits.push(ms)}),{done:true});
        assert.equal(count,2);
        assert.deepEqual(waits,[status===429?3000:2000]);
    }
    for (const status of [400,401,403,404,409,422]) {
        let count=0;
        globalThis.fetch=async()=>{count++;return {ok:false,status,text:async()=>'{"error":"Permanent failure"}'};};
        await assert.rejects(q.retryRequest(()=>q.fetchJson('/quality',{}),{wait:async()=>assert.fail('Must not wait')}),/Permanent failure/);
        assert.equal(count,1);
    }
    let count=0;
    globalThis.fetch=async()=>{count++;return {ok:true,status:200,text:async()=>'{broken json'};};
    await assert.rejects(q.retryRequest(()=>q.fetchJson('/quality',{}),{wait:async()=>assert.fail('Invalid JSON is not a network failure')}),/non-JSON/);
    assert.equal(count,1);
    for (const failure of [new TypeError('Failed to fetch'),Object.assign(new Error('Load failed'),{name:'NetworkError'})]) {
        count=0;
        globalThis.fetch=async()=>{count++;return count===1 ? {ok:true,status:200,text:async()=>{throw failure;}} : ok();};
        await q.retryRequest(()=>q.fetchJson('/quality',{}),{wait:async()=>{}});
        assert.equal(count,2,'Interrupted response bodies are retried too');
    }
    count=0;
    await assert.rejects(q.retryRequest(async()=>{count++;throw new TypeError('Programming error');},
        {wait:async()=>assert.fail('Programming errors are not retryable')}),/Programming error/);
    assert.equal(count,1);
    globalThis.fetch=async()=>{throw Object.assign(new Error('Cancelled'),{name:'AbortError'});};
    await assert.rejects(q.retryRequest(()=>q.fetchJson('/quality',{}),{wait:async()=>assert.fail('Cancellation is not retryable')}),/Cancelled/);
})().catch(e=>{console.error(e);process.exit(1);});
""")
