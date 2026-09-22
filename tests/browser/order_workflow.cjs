/* Actual lab UI with bounded HTTP failures injected; no paid model requests. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert=require('node:assert/strict');
const base=process.env.FOCALPROMPT_TEST_URL || 'http://127.0.0.1:5014';
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try {
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],calls=[],received=[];
  page.on('pageerror',e=>errors.push(e.message));
  let fail=true,plan;
  await page.route('**/api/**',async route=>{
   const path=new URL(route.request().url()).pathname;
   if(path==='/api/focus-order-sensitivity/plan'){
    const response=await route.fetch();plan=await response.json();assert.equal(response.status(),200);await route.fulfill({json:plan});return;
   }
   if(path.startsWith('/api/focus-order-sensitivity/')){
    if(path.endsWith('estimate-cost')){await route.fulfill({json:{total_model_calls:4,global_order_model_calls:4}});return;}
    const body=route.request().postDataJSON();calls.push({path,body});
    assert.equal(body.model,'gpt-6-astra');
    if(path.endsWith('/sample')){
     if(fail && body.condition_id==='permutation_1'){await route.fulfill({status:504,contentType:'text/html',body:'FUNCTION_INVOCATION_TIMEOUT'});return;}
     const condition=plan.conditions.find(c=>c.id===body.condition_id);
     const row={condition_id:condition.id,scenario:condition.scenario,content:'saved output '+received.length};received.push(row);
     await route.fulfill({json:row});return;
    }
    if(path.endsWith('/score')){await route.fulfill({json:{ok:true,experiment_type:'focus_order_sensitivity',global_order_experiment:{permutations:[],summary:{}},position_sweeps:[]}});return;}
    throw new Error('Unexpected endpoint '+path);
   }
   assert.notEqual(path,'/api/focus-order-sensitivity','the UI must not send a monolithic request');
   await route.fulfill({json:{models:[]}});
  });
  await page.goto(base+'/lab');
  await page.waitForFunction(()=>window.focalPromptWorkspaceReady);
  await page.evaluate(()=>{
   const scenario={version:1,messages:[{id:'rules',role:'system',analysis_mode:'analyse',content:'Be kind.\n\nBe brief.'},
    {id:'chat',role:'user',analysis_mode:'retain',content:'Say hello.'}]};
   const foci=[{focus:'Kind',spans:[{message_id:'rules',char_start:0,char_end:8,text_snapshot:'Be kind.'}]},
    {focus:'Brief',spans:[{message_id:'rules',char_start:10,char_end:19,text_snapshot:'Be brief.'}]}];
   restoreWorkspaceSession({focalprompt_workspace:true,version:2,active_tab:'prompt-analysis',
    model:{model:'gpt-6-astra',provider:'openai'},prompt_analysis:{scenario,foci,
     single_ablation:{scenario,foci_list:foci,baseline_outputs:['base one','base two'],ablation_results:[],model:'gpt-6-astra',provider:'openai',temperature:.7},
     focus_order:{k:'2',m:'2',run_sweep:false,run_judge:false}}});
  });
  await page.locator('#run-focus-order-btn').click();
  await page.waitForFunction(()=>window.focusOrderRunState?.phase==='incomplete');
  assert.equal(await page.evaluate(()=>FocalPromptOrder.progress(focusOrderRunState).samples),2);
  assert.match(await page.locator('#focus-order-progress').textContent(),/2\/4 order samples saved/);
  assert.equal(await page.locator('#run-focus-order-btn').textContent(),'Resume order analysis');
  await page.locator('#error-modal-ok').click();
  const saved=await page.evaluate(()=>JSON.parse(JSON.stringify(collectWorkspaceSession())));
  assert.equal(saved.prompt_analysis.focus_order.run_state.phase,'incomplete');
  const count=received.length;
  await page.evaluate(workspace=>restoreWorkspaceSession(workspace),saved);
  assert.equal(await page.locator('#run-focus-order-btn').textContent(),'Resume order analysis');
  fail=false;await page.locator('#run-focus-order-btn').click();
  await page.waitForFunction(()=>window.focusOrderRunState?.phase==='complete');
  assert.equal(received.length-count,2,'resuming must generate only the two missing samples');
  assert.equal(await page.locator('#run-focus-order-btn').isDisabled(),true);
  assert.equal(await page.locator('#new-focus-order-btn').isVisible(),true);
  assert.equal(await page.locator('#focus-order-results .focus-order-panel').count(),1);
  const final=await page.evaluate(()=>collectWorkspaceSession().prompt_analysis.focus_order);
  assert.equal(final.results.experiment_type,'focus_order_sensitivity');assert.equal(final.run_state.result.ok,true);
  assert.deepEqual(final.run_state.samples.permutation_0,saved.prompt_analysis.focus_order.run_state.samples.permutation_0);
  assert.deepEqual(errors,[]);
  console.log('PASS order UI: Astra selection, single-sample requests, timeout recovery, workspace export/import, resume without duplicate successes, completed report.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
