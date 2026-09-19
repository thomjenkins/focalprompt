"""Resumable Jev orchestration, isolated state and export round trips."""
from pathlib import Path
import subprocess


def test_jev_resume_staleness_and_workspace_isolation():
    source = (Path(__file__).resolve().parents[2] / 'static/js/jev_experiment.js').read_text()
    script = r"""
const assert = require('node:assert/strict');
const window = globalThis, elements = new Map();
const document = {getElementById(id) {
  if (!elements.has(id)) elements.set(id, {value:'',checked:false,innerHTML:'',textContent:'',addEventListener(){}});
  return elements.get(id);
}, addEventListener(){}};
const read = id => document.getElementById(id);
read('jev-threshold').value = '.5'; read('jev-count').value = '2'; read('jev-temperature').value = '0'; read('jev-order').checked = true;
let scenario = {version:1,messages:[{id:'rules',role:'developer',analysis_mode:'analyse',content:'A. B. C.'},
 {id:'chat',role:'user',analysis_mode:'retain',content:'Synthetic request.'}]};
let foci = ['A','B','C'].map(focus=>({focus}));
let model = {model:'generation-model',provider:'openai'};
const main = window.singleAblationResults = {kept:'unchanged'};
const readMainScenario = () => scenario, getSectionModel = () => model;
const getApiHeaders = () => ({}), getApiBody = (p,r,m) => ({...p,...m});
const escapeHtml = s => s.replaceAll('<','&lt;');
window.FocalPromptWorkflow = {matches:(a,b)=>JSON.stringify(a)===JSON.stringify(b)};
let calls = [], fails = true, ordered = false;
window.FocalPromptQuality = {retryRequest: task=>task(), fetchJson:async(path,options)=>{
 const b=JSON.parse(options.body); calls.push({path,b});
 assert.equal(b.model, 'generation-model');
 if(path.endsWith('/select')) return {selected_indices:[0,1,2],decisions:[0,1,2].map(i=>({focus_index:i,focus:foci[i].focus,probability:1,included:true})),
   order_groups:[{message_id:'rules',role:'developer',focus_indices:[0,1,2]}]};
 if(path.endsWith('/order-next')) {
   if(b.prefix.length && !ordered) {ordered=true;throw new Error('connection failed');}
   return {focus_index:b.prefix.length?1:2};
 }
 if(path.endsWith('/compose')) return {scenario:structuredClone(scenario),shared_text_retained_for_excluded:[]};
 if(path.endsWith('/generate-agent-response')) {
   assert.equal(b.temperature,0);
   if(calls.filter(c=>c.path.endsWith('/generate-agent-response')).length===3 && fails){fails=false;throw new Error('interrupted');}
   return {output:'Synthetic <output>'};
 }
 throw new Error(path);
}};
""" + source + r"""
(async()=>{
 const flow=window.FocalPromptJev;
 await assert.rejects(flow.preview,/connection failed/);
 assert.deepEqual(flow.collect().state.orders.rules,[2]);
 flow.restore(JSON.parse(JSON.stringify(flow.collect())));
 await flow.preview();
 assert.equal(calls.filter(c=>c.path.endsWith('/select')).length,1);
 assert.deepEqual(flow.collect().state.orders.rules,[2,1,0]);
 assert.equal(flow.collect().state.schedule.length,6);
 await assert.rejects(flow.generate,/interrupted/);
 const partial=flow.collect();
 assert.equal(Object.values(partial.state.arms).flatMap(a=>a.samples.filter(Boolean)).length,2);
 flow.restore(JSON.parse(JSON.stringify(partial)));
 await flow.generate();
 const completed=flow.collect();
 assert.equal(Object.values(completed.state.arms).flatMap(a=>a.samples.filter(Boolean)).length,6);
 assert.ok(completed.state.completed_at);
 assert.match(read('jev-results').innerHTML,/&lt;output>/);
 assert.equal(window.singleAblationResults,main);
 scenario={...scenario,messages:[...scenario.messages,{id:'more',role:'user',content:'Changed input',analysis_mode:'retain'}]};
 await assert.rejects(flow.generate,/Inputs or settings changed/);
 flow.render(); assert.match(read('jev-results').innerHTML,/Inputs changed/);
 assert.equal(read('jev-generate-btn').disabled,true);
 flow.restore(null); assert.equal(flow.collect().state,null);
 assert.equal(read('jev-count').value,10);
})().catch(e=>{console.error(e);process.exit(1)});
"""
    subprocess.run(['node', '-e', script], check=True, text=True, capture_output=True)
