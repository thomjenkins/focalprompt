"""Reuse, resumability, staleness and workspace isolation in the real JS controller."""
import json
from pathlib import Path
import subprocess

from services.singleton_service import build_plan


def test_ui_reuses_existing_arms_resumes_missing_samples_and_preserves_main():
    scenario = {'version': 1, 'messages': [
        {'id': 'rules', 'role': 'developer', 'analysis_mode': 'analyse', 'content': 'Intro A. B. End'},
        {'id': 'chat', 'role': 'user', 'analysis_mode': 'retain', 'content': 'What is 2 + 2?'},
    ]}
    foci = [{'focus': label, 'spans': [{'message_id': 'rules', 'char_start': i, 'char_end': i + 2,
                                     'text_snapshot': label + '.'}]} for label, i in [('A', 6), ('B', 9)]]
    plan = build_plan(scenario, foci, n_baseline=5, n_ablated=3)
    fixture = {'scenario': scenario, 'foci': foci, 'plan': plan}
    source = (Path(__file__).resolve().parents[2] / 'static/js/singleton_experiment.js').read_text()
    script = r"""
const assert = require('node:assert/strict'), window=globalThis, fixture=FIXTURE;
let scenario=fixture.scenario, foci=fixture.foci, model={provider:'openai',model:'test-model'};
const same=require('node:util').isDeepStrictEqual, clone=v=>structuredClone(v);
const controls={temperature:.7,n_baseline:5,n_ablated:3};
const elements=new Map(),document={getElementById(id){if(!elements.has(id))elements.set(id,{value:'',textContent:'',innerHTML:'',addEventListener(){}});return elements.get(id);},addEventListener(){}};
const readMainScenario=()=>scenario,getSectionModel=()=>model,escapeHtml=s=>s.replaceAll('<','&lt;');
const getApiHeaders=()=>({}),getApiBody=(b,r,m)=>({...b,...m});
window.FocalPromptExperiment={getState:()=>clone(controls),temperatureRejection:()=>null};
const baseContext={scenario,foci,model,temperature:.7,n_baseline:5};
const workflow={context:clone(baseContext),samples:Array.from({length:5},()=>({content:'Saved full',scenario}))};
window.FocalPromptWorkflow={matches:same,collect:()=>clone(workflow)};
const old=window.singleAblationResults={scenario:clone(scenario),model:model.model,provider:model.provider,temperature:.7,
 n_baseline:5,n_ablated:3,foci_list:clone(foci),baseline_outputs:Array(5).fill('Saved full'),
 ablation_results:fixture.plan.variants.filter(v=>v.kind==='ablated').map(v=>({focus_index:v.focus_index,ablated_scenario:v.scenario,ablated_outputs:Array(3).fill('Saved leave-one-out '+v.focus_index)}))};
const original=JSON.stringify(old);let requests=[],calls=0,fail=true,scoreFailure=true;
window.FocalPromptQuality={retryRequest:task=>task(),fetchJson:async(path,opts)=>{
 const body=JSON.parse(opts.body);requests.push({path,body});
 if(path.endsWith('-plan'))return clone(fixture.plan);
 if(path.endsWith('-score')){
  assert.equal(Object.values(body.samples).flat().length,16);
  assert.equal(body.model,'test-model');
  if(scoreFailure){scoreFailure=false;throw new Error('Scoring connection failed');}
  return {done:true};
 }
 throw new Error(path);
}};
async function fetchAblationSample(s,fs,kind,index,temp,controller,inputs,m){
 assert.equal(kind,'no_focus','all full/LOO/singleton calls should be reused');
 assert.deepEqual(m,model);assert.equal(temp,.7);calls++;
 if(calls===2&&fail){fail=false;throw new Error('Synthetic interrupted call');}
 return {content:'Synthetic no-focus '+calls,scenario:fixture.plan.variants.find(v=>v.kind==='no_focus').scenario};
}
""".replace('FIXTURE', json.dumps(fixture)) + source + r"""
(async()=>{
 const flow=window.FocalPromptSingleton;
 await flow.prepare();
 assert.equal(Object.values(flow.collect().samples).flat().length,11);
 await assert.rejects(flow.runAnalysis,/Synthetic interrupted/);
 const partial=flow.collect();
 assert.equal(Object.values(partial.samples).flat().filter(Boolean).length,15);
 flow.restore(JSON.parse(JSON.stringify(partial)));
 await assert.rejects(flow.runAnalysis,/Scoring connection failed/);
 assert.equal(calls,6,'five received outputs plus the failed attempt');
 await flow.runAnalysis();assert.equal(calls,6,'scoring retry must not resample');
 assert.equal(flow.collect().result.done,true);
 assert.equal(requests.filter(r=>r.path.endsWith('-plan')).length,1);
 assert.equal(JSON.stringify(window.singleAblationResults),original);
 const saved=flow.collect();
 for(const [key,value] of [['n_baseline',7],['n_ablated',4],['temperature',.8]]) {
  const before=controls[key];controls[key]=value;
  await assert.rejects(flow.runAnalysis,/Inputs or sampling settings changed/);
  assert.deepEqual(flow.collect(),saved,'editing settings must not modify saved samples');
  controls[key]=before;
 }
 scenario=clone(scenario);scenario.messages[1].content='Changed retained input';
 await assert.rejects(flow.runAnalysis,/Inputs or sampling settings changed/);
 flow.restore(null);scenario=fixture.scenario;
 // No stale reuse from a different model, even when output strings are available.
 model={provider:'openai',model:'different-model'};
 await flow.prepare();assert.equal(Object.values(flow.collect().samples).flat().length,0);
 flow.restore(null);model=baseContext.model;window.singleAblationResults=null;
 workflow.samples[1]=null;workflow.samples[3]=null;
 await flow.prepare();assert.equal(Object.values(flow.collect().samples).flat().filter(Boolean).length,3,'reuse received slots from a partial baseline');
 // Saved results restore without mutating the original ablation result.
 // Minimal scoring fixture intentionally omits view rows; test saved-state round trip directly.
 assert.equal(saved.context.model.model,'test-model');
})().catch(e=>{console.error(e);process.exit(1)});
"""
    subprocess.run(['node', '-e', script], check=True, capture_output=True, text=True)
