"""Sampling keeps contracts and status codes through Gateway and browser retries."""
from pathlib import Path
import subprocess
from unittest.mock import Mock, patch

import pytest
import requests

from core.ai_gateway_provider import AIGatewayProvider, CHAT_MAX_ATTEMPTS
from services.ablation_service import AblationService


@pytest.mark.parametrize('upstream, message, expected, contract_error', [
    (503, 'Service temporarily unavailable. Please try again in a moment.', 503, False),
    (500, 'Internal server error processing json_schema', 502, False),
    (401, 'Invalid API key', 401, False),
    (403, 'Access denied', 403, False),
    (404, 'Model not found', 422, False),
    (400, "Unsupported value: temperature", 422, False),
    (400, "Unsupported response_format json_schema", 422, True),
])
def test_gateway_sampling_errors_keep_their_real_status(upstream, message, expected, contract_error):
    from app_new import app
    scenario = {'version': 1, 'messages': [
        {'id': 'chat', 'role': 'user', 'analysis_mode': 'retain', 'content': 'What is 2 + 2?'},
    ], 'output_contract': {'type': 'json_schema', 'name': 'answer', 'strict': True,
                          'schema': {'type': 'object', 'properties': {'answer': {'type': 'string'}},
                                     'required': ['answer'], 'additionalProperties': False}}}
    response = Mock(status_code=upstream)
    response.json.return_value = {'error': {'message': message}}
    failure = requests.exceptions.HTTPError(response=response)
    network = Mock()
    network.exceptions = requests.exceptions
    network.post.side_effect = failure
    service = AblationService(AIGatewayProvider('test-key'), 'gpt-4o-mini', provider_name='openai')
    with patch('routes.ablation_routes._ablation_service', return_value=service), \
            patch('core.ai_gateway_provider._check_requests', return_value=network), \
            patch('core.ai_gateway_provider.time.sleep'):
        result = app.test_client().post('/api/ablation-sample', json={
            'scenario': scenario, 'kind': 'baseline', 'foci': [], 'temperature': .7,
        })
    assert result.status_code == expected
    data = result.get_json()
    assert (data['code'] == 'inference_contract_error') is contract_error
    assert message in data['error']
    if not contract_error:
        assert data['provider_error']['status'] == upstream
        assert 'rejected the required structured output contract' not in data['error']
    assert network.post.call_count == (CHAT_MAX_ATTEMPTS if upstream >= 500 else 1)
    for call in network.post.call_args_list:
        assert call.kwargs['json']['response_format']['type'] == 'json_schema'


def test_browser_sample_retries_are_bounded_and_keep_the_request_unchanged():
    root = Path(__file__).resolve().parents[2]
    app = (root / 'static/js/app.js').read_text()
    sample = app[app.index('async function fetchAblationSample('):app.index('async function mapPool(')]
    retry = (root / 'static/js/quality_judges.js').read_text()
    script = "const assert=require('node:assert/strict'),window=globalThis;\n" + retry + sample + r"""
const getApiHeaders=()=>({'Content-Type':'application/json'}),getApiBody=(body,role,model)=>({...body,...model});
const scenario={version:1,messages:[{id:'chat',role:'user',analysis_mode:'retain',content:'What is 2 + 2?'}],
    output_contract:{type:'json_schema',schema:{type:'object'}}};
const success=()=>({ok:true,status:200,text:async()=>JSON.stringify({content:'{"answer":"4"}',scenario})});
const call=opts=>fetchAblationSample(scenario,[],'no_focus',null,.7,new AbortController(),null,{provider:'openai',model:'test-model'},opts);
(async()=>{
 for(const status of [429,500,502,503,504,'network']) {
  const bodies=[],waits=[];
  globalThis.fetch=async(path,opts)=>{
   assert.equal(path,'/api/ablation-sample');bodies.push(opts.body);
   if(bodies.length>1)return success();
   if(status==='network')throw new TypeError('Failed to fetch');
   return {ok:false,status,text:async()=>status===504?'<html>FUNCTION_INVOCATION_TIMEOUT</html>':JSON.stringify({error:'Temporary provider failure',retry_after:4})};
  };
  const result=await call({wait:async ms=>waits.push(ms)});
  assert.equal(result.content,'{"answer":"4"}');assert.equal(bodies.length,2);
  assert.equal(bodies[0],bodies[1]);assert.deepEqual(JSON.parse(bodies[0]).scenario,scenario);
  assert.equal(waits.length,1);if(status===429)assert.equal(waits[0],4000);
 }
 for(const status of [400,401,403,422,503]) {
  let calls=0;const waits=[];
  globalThis.fetch=async()=>{calls++;return {ok:false,status,text:async()=>'{"error":"Provider failure"}'};};
  await assert.rejects(call({wait:async ms=>waits.push(ms)}),e=>e.status===status);
  assert.equal(calls,status===503?3:1);assert.equal(waits.length,status===503?2:0);
 }
 // A user stop/context change during backoff prevents the next paid request.
 let stopped=false,calls=0;
 globalThis.fetch=async()=>{calls++;return {ok:false,status:503,text:async()=>'{"error":"Temporarily unavailable"}'};};
 await assert.rejects(call({wait:async()=>{stopped=true;},onAttempt:()=>{if(stopped)throw new Error('Stopped');}}),/Stopped/);
 assert.equal(calls,1);
})().catch(e=>{console.error(e);process.exit(1);});
"""
    subprocess.run(['node', '-e', script], check=True, capture_output=True, text=True)
