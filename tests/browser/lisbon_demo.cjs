/* Real lab integration: run against a local server, without model credentials. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),crypto=require('node:crypto');
const base=process.env.FOCALPROMPT_TEST_URL || 'http://127.0.0.1:5014';
const fixture=fs.readFileSync(require('node:path').join(__dirname,'../../examples/demos/lisbon/pup4ominiFull.json'));
const sha=value=>crypto.createHash('sha256').update(value).digest('hex');
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try {
  for(const [width,height] of [[1280,720],[1920,1080],[390,844]]) {
   const context=await browser.newContext({viewport:{width,height},reducedMotion:'reduce'});
   const page=await context.newPage(),errors=[],requests=[];
   page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>requests.push(r.url()));
   // Saved lab settings, including prompt data, must never be read or overwritten by the replay.
   await page.goto(base+'/experiments');
   await page.evaluate(()=>{localStorage.setItem('focalprompt_saved_prompt',JSON.stringify({prompt:'Untouched private draft',foci:[]}));localStorage.setItem('focalprompt_mut_model','untouched-model');});
   const storageBefore=await page.evaluate(()=>JSON.stringify(localStorage));
   const tabEvent=context.waitForEvent('page');await page.locator('.lisbon-demo-card').click();
   const replay=await tabEvent;
   replay.on('pageerror',e=>errors.push(e.message));replay.on('request',r=>requests.push(r.url()));
   await replay.waitForFunction(()=>window.FocalPromptDemo);
   assert.equal(await replay.locator('#scenario-messages').count(),1);
   assert.equal(await replay.locator('#baseline-results .recorded-samples').count(),1);
   assert.equal(await replay.locator('#demo-stage').count(),0,'no separate slide renderer');
   const original=await replay.evaluate(()=>JSON.stringify(FocalPromptDemo.data.workspace));
   assert.equal(original,JSON.stringify(JSON.parse(fixture)));
   await replay.evaluate(()=>{window.nativeScenarioNode=document.getElementById('scenario-messages');window.nativeBaselineNode=document.getElementById('baseline-results');});
   await context.setOffline(true);const offlineRequests=[];replay.on('request',r=>offlineRequests.push(r.url()));
   const states=[],length=await replay.evaluate(()=>FocalPromptDemo.length);
   assert.equal(length,13);
   for(let i=0;i<length;i++) {
    assert.equal(await replay.evaluate(()=>FocalPromptDemo.index),i);
    const snapshot=await replay.evaluate(()=>({frame:FocalPromptDemo.frame,section:document.querySelector('.demo-section')?.id,
      sameNodes:nativeScenarioNode===document.getElementById('scenario-messages') && nativeBaselineNode===document.getElementById('baseline-results'),
      outputs:[...document.querySelectorAll('.demo-section .recorded-sample-panel:not([hidden])')].filter(e=>e.checkVisibility()).map(el=>({
       text:el.querySelector('.recorded-output').textContent,raw:el.querySelector('.recorded-raw pre').textContent})),
      overflow:document.documentElement.scrollWidth>innerWidth+1}));
    assert.ok(snapshot.section);assert.ok(snapshot.sameNodes,'guide must manipulate native components in place');
    assert.equal(snapshot.overflow,false,`horizontal overflow at ${width}, state ${i}`);
    for(const output of snapshot.outputs){let expected=output.raw;try{const j=JSON.parse(expected);if(typeof j.suggestedMessage==='string')expected=j.suggestedMessage;}catch(_){}assert.equal(output.text,expected);}
    const {id,phase,position}=snapshot.frame;
    if(id==='baseline'){assert.equal(await replay.locator('#baseline-results [data-recorded-sample]').count(),10);await replay.locator('#baseline-results [data-recorded-sample="6"]').click();assert.equal(await replay.locator('#baseline-results [data-recorded-panel="6"]').isVisible(),true);}
    if(id==='foci'){
     assert.equal(await replay.locator('#legend-items [data-coverage-focus]').count(),17);
     const texts=await replay.locator('.coverage-message>div:last-child').allTextContents();
     assert.deepEqual(texts,JSON.parse(fixture).prompt_analysis.scenario.messages.filter(m=>m.analysis_mode==='analyse').map(m=>m.content));
     await replay.locator('[data-coverage-focus="15"]').click();assert.equal(await replay.locator('[data-coverage-focus="15"]').getAttribute('aria-pressed'),'true');
    }
    if(id==='ablation'){assert.equal(snapshot.outputs.length,2);assert.equal(await replay.locator('.demo-featured [data-recorded-sample="1"][aria-pressed="true"]').count(),1);}
    if(id==='singleton')assert.equal(snapshot.outputs.length,3,'three actual singleton/no-focus sample browsers');
    if(id==='dominance'){
     assert.equal(snapshot.section,'lab-singleton');
     assert.equal(await replay.locator('.pairwise-grid').isVisible(),true);
     assert.equal(await replay.locator('.pairwise-cell').count(),17*16);
     assert.equal(await replay.locator('#pairwise-view').inputValue(),'combined');
     assert.equal(await replay.locator('#singleton-result-order').inputValue(),'focus_index');
     assert.equal(await replay.locator('#pairwise-cell-4-15').getAttribute('aria-pressed'),'true');
     if(width>=1000) {
      const visible=await replay.evaluate(()=>{
       const grid=document.querySelector('.pairwise-grid-wrap').getBoundingClientRect(),card=document.querySelector('.demo-section').getBoundingClientRect(),cell=document.querySelector('.pairwise-cell[aria-pressed=true]').getBoundingClientRect();
       return grid.top>=card.top && grid.bottom<=card.bottom && cell.top>=grid.top && cell.bottom<=grid.bottom && cell.left>=grid.left && cell.right<=grid.right;
      });
      assert.equal(visible,true,'grid and preselected pair must fit inside the expanded native card');
     }
     assert.match(await replay.locator('#pairwise-detail').textContent(),/100.0% closer to Appointment booking/);
     assert.match(await replay.locator('#pairwise-detail').textContent(),/16 distinct prompt condition\(s\), 85 unique sampled outputs/);
     await replay.locator('#pairwise-cell-15-4').click();
     assert.match(await replay.locator('#pairwise-detail h4').textContent(),/Cat only \(row\) vs Appointment booking \(column\)/);
     assert.match(await replay.locator('#pairwise-detail').textContent(),/0.0% closer to Cat only/);
     await replay.locator('#pairwise-view').selectOption('full');
     assert.match(await replay.locator('#pairwise-detail').textContent(),/1 distinct prompt condition\(s\), 10 unique sampled outputs/);
     await replay.locator('#pairwise-view').selectOption('ablations');
     assert.match(await replay.locator('#pairwise-detail').textContent(),/15 distinct prompt condition\(s\), 75 unique sampled outputs/);
    }
    if(id==='order') {
     const condition=phase==='condition-a' ? 0 : 1;
     assert.equal(snapshot.outputs.length,3,'all three actual outputs must be visible');
     const orders=[['Address','Cat only','Relevance','Opening hours'],['Relevance','Cat only','Opening hours','Address']];
     const source=JSON.parse(fixture).prompt_analysis.focus_order.results;
     const permutation=source.global_order_experiment.permutations.find(p=>JSON.stringify(p.ordered_focus_names)===JSON.stringify(orders[condition]));
     assert.deepEqual(snapshot.outputs.map(o=>o.raw),permutation.outputs);
     assert.equal(await replay.locator('.order-anchor-position').textContent(),'Cat only · position 2 in both');
     assert.match(await replay.locator(`[data-order-count="${condition}"]`).textContent(),condition ? /1 \/ 3 comply/ : /0 \/ 3 comply/);
     const active=replay.locator(`[data-order-outputs="${condition}"]`);
     assert.deepEqual(await active.locator('.recorded-verdict').allTextContents(),permutation.behavioral_judgments.map(j=>j.classification));
     assert.ok(await active.locator('mark').count()>=3);
     assert.equal(await replay.locator('.focus-order-full').getAttribute('open'),null);
     assert.equal(await replay.locator('.focus-order-position[data-order-focus="Cat only"]').count(),4,'full position sweep retained');
    }
    if(id==='jev' && phase==='selected')assert.equal(await replay.locator('.jev-decisions [data-included="false"]').count(),6);
    if(id==='jev' && phase==='outputs')assert.equal(snapshot.outputs.length,3);
    states.push(snapshot.frame);
    if(i<length-1)await replay.locator('#demo-next').click();
   }
   assert.equal(await replay.locator('#demo-next').isDisabled(),true);
   assert.deepEqual([...new Set(states.map(f=>f.id))],['problem','baseline','foci','singleton','dominance','ablation','order','jev','end']);
   for(let i=length-2;i>=0;i--){await replay.locator('#demo-previous').click();assert.deepEqual(await replay.evaluate(()=>FocalPromptDemo.frame),states[i]);}
   await replay.locator('#demo-location').selectOption('dominance');
   assert.equal(await replay.locator('#pairwise-view').inputValue(),'combined');
   assert.equal(await replay.locator('#pairwise-cell-4-15').getAttribute('aria-pressed'),'true');
   await replay.locator('#demo-explore').click();
   await replay.locator('#pairwise-view').selectOption('full');
   await replay.locator('#demo-explore').click();
   assert.equal(await replay.locator('#pairwise-view').inputValue(),'combined');
   assert.equal(await replay.locator('.pairwise-grid').isVisible(),true);
   await replay.locator('#demo-location').selectOption('foci');
   await replay.locator('#demo-layout').selectOption('context');assert.equal(await replay.locator('body').evaluate(el=>el.classList.contains('replay-spotlight')),false);
   await replay.locator('#demo-explore').click();assert.equal(await replay.evaluate(()=>FocalPromptDemo.exploring),true);
   // Genuine charts/inspectors outside the scripted path remain interactive offline.
   await replay.locator('[data-action="set-view"][data-view="focus-map"]').click();
   assert.equal(await replay.evaluate(()=>FocalPromptReport.getState().view),'focus-map');
   await replay.locator('#singleton-result-order').selectOption('influence');
   await replay.locator('#demo-explore').click();assert.equal(await replay.evaluate(()=>FocalPromptDemo.frame.id),'foci');
   await replay.locator('#demo-layout').selectOption('spotlight');
   await replay.locator('#demo-reset').click();assert.equal(await replay.evaluate(()=>FocalPromptDemo.index),0);
   await replay.locator('body').click({position:{x:4,y:130}});
   await replay.keyboard.press('ArrowRight');assert.equal(await replay.evaluate(()=>FocalPromptDemo.index),1);
   await replay.keyboard.press('Escape');assert.equal(await replay.evaluate(()=>FocalPromptDemo.exploring),true);
   const downloadEvent=replay.waitForEvent('download');await replay.locator('#export-workspace-btn').click();
   const download=await downloadEvent;assert.equal(sha(fs.readFileSync(await download.path())),sha(fixture));
   assert.equal(await replay.locator('#sample-baseline-btn').isDisabled(),true);
   const blocked=await replay.evaluate(async()=> (await fetch('/api/generate-output',{method:'POST'})).status);assert.equal(blocked,409);
   assert.equal(await replay.evaluate(()=>JSON.stringify(localStorage)),storageBefore);
   assert.equal(await replay.evaluate(()=>JSON.stringify(FocalPromptDemo.data.workspace)),original);
   const loaded=await replay.evaluate(()=>({baseline:FocalPromptWorkflow.collect().samples.map(s=>s.content),jev:FocalPromptJev.collect().state.arms.ordered.samples.map(s=>s.output),singleton:FocalPromptSingleton.collect().result.no_focus_outputs}));
   const pa=JSON.parse(fixture).prompt_analysis;
   assert.deepEqual(loaded.baseline,pa.focus_workflow.samples.map(s=>s.content));assert.deepEqual(loaded.jev,pa.jev_experiment.state.arms.ordered.samples.map(s=>s.output));assert.deepEqual(loaded.singleton,pa.singleton_experiment.result.no_focus_outputs);
   assert.deepEqual(await replay.evaluate(()=>FocalPromptSingleton.collect().result.pairwise_resemblance),pa.singleton_experiment.result.pairwise_resemblance);
   assert.deepEqual(offlineRequests,[]);assert.deepEqual(errors,[]);
   assert.equal(requests.some(url=>url.includes('/api/')),false);
   console.log(`PASS ${width}×${height}: real lab nodes; every guided state; explore/resume; exact source and samples; isolated storage; offline; no API calls.`);
   await context.close();
  }
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
