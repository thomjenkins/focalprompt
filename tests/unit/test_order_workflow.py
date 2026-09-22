"""Bounded order requests preserve the original experiment and resumable work."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
from unittest.mock import Mock

import numpy as np
import pytest

from services.order_sensitivity_service import OrderSensitivityService

ROOT = Path(__file__).resolve().parents[2]


def context():
    rules = ['Be concise.', 'Mention cats.', 'Be polite.']
    text = '\n\n'.join(rules)
    return {'scenario': {'version': 1, 'messages': [
        {'id': 'rules', 'role': 'system', 'analysis_mode': 'analyse', 'content': text},
        {'id': 'chat', 'role': 'user', 'analysis_mode': 'retain', 'content': 'Hello there.'},
    ], 'output_contract': {'type': 'json_schema', 'name': 'reply', 'strict': True,
        'schema': {'type': 'object', 'properties': {'reply': {'type': 'string'}},
                   'required': ['reply'], 'additionalProperties': False}}},
        'foci': [{'focus': str(i), 'spans': [{'message_id': 'rules', 'char_start': text.index(rule),
                   'char_end': text.index(rule) + len(rule), 'text_snapshot': rule}]} for i, rule in enumerate(rules)],
        'baseline_outputs': ['baseline one', 'baseline two'], 'model': 'gpt-6-astra', 'provider': 'openai',
        'k_permutations': 2, 'm_samples': 2, 'order_seed': 7, 'statistical_seed': 42,
        'temperature': .7, 'run_position_sweep': True, 'focus_index_for_sweep': 1,
        'run_behavioral_judge': True, 'behavioral_criterion': 'Be polite.'}


def embeddings():
    service = Mock(model='test-embeddings')
    service.batch_embeddings_with_usage.side_effect = lambda texts: (
        [np.array([len(t), sum(map(ord, t)) % 17, 1.]) for t in texts], len(texts))
    return service


def test_plan_is_pure_and_samples_are_one_call_with_astra_and_exact_contract(monkeypatch):
    from app_new import app
    monkeypatch.setenv('FOCALPROMPT_HOSTED_MODE', '0')
    getter = Mock()
    monkeypatch.setattr('routes.order_sensitivity_routes.get_assessor', getter)
    client = app.test_client()
    c = context()
    response = client.post('/api/focus-order-sensitivity/plan', json=c)
    assert response.status_code == 200
    plan = response.get_json()
    getter.assert_not_called()
    assert len(plan['conditions']) == 5
    assert plan['planned_samples'] == 10
    assert client.post('/api/focus-order-sensitivity/plan', json=c).get_json() == plan
    provider = Mock()
    provider.chat_completion.return_value = {'content': '{"reply":"Hello."}', 'usage': {'prompt_tokens': 8, 'completion_tokens': 4}}
    getter.return_value = Mock(provider=provider)
    for condition in plan['conditions']:
        arm = condition['scenario']
        assert arm['messages'][1] == c['scenario']['messages'][1]
        assert arm['output_contract'] == c['scenario']['output_contract']
        assert sorted(arm['messages'][0]['content'].split('\n\n')) == sorted(c['scenario']['messages'][0]['content'].split('\n\n'))
    sample = client.post('/api/focus-order-sensitivity/sample', json={**c, 'condition_id': plan['conditions'][0]['id']})
    assert sample.status_code == 200
    provider.chat_completion.assert_called_once()
    call = provider.chat_completion.call_args.kwargs
    assert call['model'] == 'gpt-6-astra'
    assert call['temperature'] == .7
    assert call['messages'][-1]['content'] == 'Hello there.'
    assert call['response_format']['type'] == 'json_schema'
    assert sample.get_json()['scenario'] == plan['conditions'][0]['scenario']
    assert client.post('/api/focus-order-sensitivity/sample', json={**c, 'condition_id': 'missing'}).status_code == 400
    assert provider.chat_completion.call_count == 1


def test_scoring_matches_the_existing_engine_and_never_generates_or_judges(monkeypatch):
    from routes.order_sensitivity_routes import _workflow_settings
    monkeypatch.setattr('services.order_sensitivity_service.time.sleep', lambda *_: None)
    c = context()
    calls = []
    provider = Mock()
    def complete(**_):
        row = {'content': json.dumps({'reply': 'sample ' + str(len(calls))}), 'usage': {'prompt_tokens': 5, 'completion_tokens': 3}}
        calls.append(deepcopy(row))
        return row
    provider.chat_completion.side_effect = complete
    judge = Mock()
    judge.chat_completion.return_value = {'content': '{"classification":"COMPLIES","score":90,"rationale":"Polite"}', 'usage': {}}
    live = OrderSensitivityService(provider, c['model'], judge_provider=judge, embedding_service=embeddings())
    options = _workflow_settings(c)
    plan = live.run_scenario_order_experiment(scenario=c['scenario'], plan_only=True, **options)
    original = live.run_scenario_order_experiment(scenario=c['scenario'], **options)
    samples, judgments, offset = {}, {'baseline': original['baseline_behavioral_judgments']}, 0
    rows = original['global_order_experiment']['permutations'] + original['position_sweeps'][0]['positions']
    for condition, row in zip(plan['conditions'], rows):
        samples[condition['id']] = calls[offset:offset+condition['n_samples']]
        judgments[condition['id']] = row['behavioral_judgments']
        offset += condition['n_samples']
    blocked = Mock()
    blocked.chat_completion.side_effect = AssertionError('Scoring must never call a generation or judge model')
    emb = embeddings()
    scorer = OrderSensitivityService(blocked, c['model'], judge_provider=blocked, embedding_service=emb)
    result = scorer.run_scenario_order_experiment(scenario=c['scenario'], recorded_samples=samples,
                                                 recorded_judgments=judgments, **options)
    for key in ['global_order_experiment', 'position_sweeps', 'baseline_stability', 'baseline_behavioral_judgments']:
        assert result[key] == original[key]
    blocked.chat_completion.assert_not_called()
    assert emb.batch_embeddings_with_usage.call_count == 1
    broken = deepcopy(samples)
    broken[plan['conditions'][0]['id']].pop()
    with pytest.raises(ValueError, match='Complete every sample'):
        scorer.run_scenario_order_experiment(scenario=c['scenario'], recorded_samples=broken,
                                             recorded_judgments=judgments, **options)
    assert emb.batch_embeddings_with_usage.call_count == 1


def test_judge_is_one_call_and_incomplete_score_never_invokes_a_model(monkeypatch):
    from app_new import app
    monkeypatch.setenv('FOCALPROMPT_HOSTED_MODE', '0')
    provider = Mock()
    provider.chat_completion.return_value = {'content': '{"classification":"COMPLIES","score":80,"rationale":"Polite"}', 'usage': {}}
    getter = Mock(return_value=Mock(provider=provider))
    monkeypatch.setattr('routes.order_sensitivity_routes.get_assessor', getter)
    client, c = app.test_client(), context()
    judgment = client.post('/api/focus-order-sensitivity/judge', json={**c, 'condition_id': 'baseline',
        'sample_index': 1, 'output': c['baseline_outputs'][1]})
    assert judgment.status_code == 200
    assert judgment.get_json()['sample_index'] == 1
    provider.chat_completion.assert_called_once()
    getter.reset_mock()
    result = client.post('/api/focus-order-sensitivity/score', json={**c, 'samples': {}, 'judgments': {}})
    assert result.status_code == 400
    getter.assert_not_called()
    for action in ['sample', 'judge', 'score']:
        from utils.hosted_mode import path_requires_live
        assert path_requires_live('/api/focus-order-sensitivity/' + action)


def test_completed_score_route_preserves_saved_outputs_and_rejects_wrong_scenarios(monkeypatch):
    from app_new import app
    monkeypatch.setenv('FOCALPROMPT_HOSTED_MODE', '0')
    getter = Mock(side_effect=AssertionError('Scoring must not create an LLM provider'))
    monkeypatch.setattr('routes.order_sensitivity_routes.get_assessor', getter)
    emb = embeddings()
    monkeypatch.setattr('services.order_sensitivity_service.EmbeddingService', lambda: emb)
    c = {**context(), 'run_behavioral_judge': False}
    client = app.test_client()
    plan = client.post('/api/focus-order-sensitivity/plan', json=c).get_json()
    samples = {condition['id']: [{'content': f'output {condition["id"]} {i}',
        'scenario': condition['scenario'], 'scenario_metadata': {'saved_translation': True}}
        for i in range(condition['n_samples'])] for condition in plan['conditions']}
    response = client.post('/api/focus-order-sensitivity/score', json={**c, 'samples': samples})
    assert response.status_code == 200
    result = response.get_json()
    assert result['sampling_protocol'] == 'focus-order-v1'
    assert result['global_order_experiment']['permutations'][0]['outputs'] == [s['content'] for s in samples['permutation_0']]
    assert result['scenario_metadata']['provider_translations'] == [{'saved_translation': True}] * 10
    getter.assert_not_called()
    assert emb.batch_embeddings_with_usage.call_count == 1
    samples['permutation_0'][0]['scenario'] = {}
    assert client.post('/api/focus-order-sensitivity/score', json={**c, 'samples': samples}).status_code == 400
    assert emb.batch_embeddings_with_usage.call_count == 1


def test_provider_timeout_remains_a_specific_retryable_http_error(monkeypatch):
    from app_new import app
    from requests.exceptions import ReadTimeout
    monkeypatch.setenv('FOCALPROMPT_HOSTED_MODE', '0')
    provider = Mock()
    provider.chat_completion.side_effect = ReadTimeout('Astra request timed out')
    monkeypatch.setattr('routes.order_sensitivity_routes.get_assessor', lambda **_: Mock(provider=provider))
    response = app.test_client().post('/api/focus-order-sensitivity/sample', json={**context(), 'condition_id': 'permutation_0'})
    assert response.status_code == 504
    assert 'Astra request timed out' in response.get_json()['error']


@pytest.mark.parametrize('headers', [
    {'Referer': 'http://localhost/'},
    {'Referer': 'http://localhost/lab?imported=1'},
    {'Referer': 'http://localhost/app'},
    {'Sec-Fetch-Site': 'same-origin', 'Sec-Fetch-Dest': 'empty'},
])
def test_old_browser_handler_gets_json_recovery_before_any_model_calls(monkeypatch, headers):
    from app_new import app
    monkeypatch.setenv('FOCALPROMPT_HOSTED_MODE', '0')
    getter = Mock(side_effect=AssertionError('An old tab must never start the long-running request'))
    monkeypatch.setattr('routes.order_sensitivity_routes.get_assessor', getter)
    response = app.test_client().post('/api/focus-order-sensitivity', json=context(), headers=headers)
    assert response.status_code == 409
    assert response.is_json
    assert response.get_json()['code'] == 'order_client_upgrade_required'
    assert 'Export your workspace first' in response.get_json()['error']
    getter.assert_not_called()
    # Those same browser headers are valid on the current workflow.
    plan = app.test_client().post('/api/focus-order-sensitivity/plan', json=context(), headers=headers)
    assert plan.status_code == 200
    assert plan.get_json()['protocol'] == 'focus-order-v1'
    getter.assert_not_called()


def test_direct_legacy_api_remains_available(monkeypatch):
    from app_new import app
    monkeypatch.setenv('FOCALPROMPT_HOSTED_MODE', '0')
    getter = Mock(return_value=Mock(provider=Mock(), provider_name='openai'))
    monkeypatch.setattr('routes.order_sensitivity_routes.get_assessor', getter)
    run = Mock(return_value={'ok': True, 'experiment_type': 'focus_order_sensitivity'})
    monkeypatch.setattr(OrderSensitivityService, 'run_scenario_order_experiment', run)
    response = app.test_client().post('/api/focus-order-sensitivity', json=context())
    assert response.status_code == 200
    run.assert_called_once()


def test_browser_resumes_after_sampling_judging_and_scoring_failures_without_resampling():
    script = r"""
const assert=require('node:assert/strict'),fs=require('node:fs');globalThis.window=globalThis;
eval(fs.readFileSync('static/js/quality_judges.js','utf8'));
eval(fs.readFileSync('static/js/order_workflow.js','utf8'));
const scenario={version:1,messages:[{id:'u',role:'user',content:'test'}]};
const context={scenario,baseline_outputs:['base1','base2'],run_behavioral_judge:true,model:'gpt-6-astra',temperature:.7};
const plan={protocol:'focus-order-v1',baseline_outputs:context.baseline_outputs,planned_samples:4,
 conditions:[{id:'permutation_0',scenario,n_samples:2},{id:'position_0',scenario,n_samples:2}]};
(async()=>{
 for(const stage of ['sample','judge','score']) {
  let saved=null, fail=true;const calls={plan:0,sample:0,judge:0,score:0},received=[];
  async function request(action,body) {
   calls[action]++;
   assert.equal(body.model,'gpt-6-astra');assert.equal(body.temperature,.7);
   if(action===stage && fail && calls[action] >= (stage==='score'?1:2))throw Object.assign(new Error('Service unavailable'),{retryable:true});
   if(action==='plan')return structuredClone(plan);
   if(action==='sample') {const s={condition_id:body.condition_id,scenario,content:'output '+calls.sample};received.push(s.content);return s;}
   if(action==='judge')return {sample_index:body.sample_index,classification:'COMPLIES',score:80};
   return {ok:true,experiment_type:'focus_order_sensitivity'};
  }
  const opts={context,request,onUpdate:s=>saved=s,wait:async()=>{}};
  await assert.rejects(FocalPromptOrder.execute(opts),/Service unavailable/);
  const original=structuredClone(saved),before={...calls};
  assert.equal(saved.phase,'incomplete');
  fail=false; await FocalPromptOrder.execute({...opts,previous:JSON.parse(JSON.stringify(saved))});
  assert.equal(saved.phase,'complete');assert.equal(FocalPromptOrder.progress(saved).samples,4);
  assert.equal(FocalPromptOrder.progress(saved).judged,6);assert.equal(calls.plan,1);
  for(const [id,samples] of Object.entries(original.samples))samples.forEach((s,i)=>{if(s)assert.deepEqual(saved.samples[id][i],s);});
  if(stage!=='sample')assert.equal(calls.sample,before.sample,'judge/score retry must not regenerate samples');
  await assert.rejects(FocalPromptOrder.execute({...opts,previous:saved,context:{...context,model:'other'}}),/settings changed/);
 }
 // Stop retains already received in-flight samples and prevents the next request.
 let stopped=false,saved=null,calls=0;
 const options={context,wait:async()=>{},check:()=>{if(stopped)throw new Error('Stopped');},
  onUpdate:s=>{saved=s;if(FocalPromptOrder.progress(s).samples)stopped=true;},
  request:async(action,body)=>{if(action==='plan')return plan;assert.equal(action,'sample');calls++;return {condition_id:body.condition_id,scenario,content:'stopped '+calls};}};
 await assert.rejects(FocalPromptOrder.execute(options),/Stopped/);
 assert.equal(calls,2);assert.equal(FocalPromptOrder.progress(saved).samples,2);
 // An actual browser transport failure is retried as one bounded request.
 let attempts=0,retained;
 globalThis.fetch=async()=>{attempts++;if(attempts===1)throw new TypeError('Failed to fetch');return {ok:true,status:200,text:async()=>JSON.stringify(plan)};};
 await assert.rejects(FocalPromptOrder.execute({context,wait:async()=>{},onUpdate:s=>retained=s,
  request:async(action)=>{if(action==='plan')return FocalPromptQuality.fetchJson('/plan',{});throw new Error('End test');}}),/End test/);
 assert.equal(attempts,2);assert.ok(retained.plan);
})().catch(e=>{console.error(e);process.exit(1)});
"""
    result = subprocess.run(['node', '-e', script], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
