/* Recorded evidence and the physical invariant behind the matched-position walkthrough. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert=require('node:assert/strict');
const base=process.env.FOCALPROMPT_TEST_URL || 'http://127.0.0.1:5014';
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try {
  const context=await browser.newContext({viewport:{width:1920,height:1080},reducedMotion:'no-preference'});
  const page=await context.newPage(),requests=[],errors=[];
  page.on('request',r=>requests.push(r.url()));page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base+'/demo/lisbon');await page.waitForFunction(()=>window.FocalPromptDemo);
  await context.setOffline(true);
  await page.locator('#demo-location').selectOption('order');
  await page.waitForTimeout(800); // Let the initial native selection settle before measuring A → B.
  assert.equal(await page.locator('[data-order-outputs="0"] [data-recorded-sample="1"]').getAttribute('aria-pressed'),'true');
  await page.locator('[data-order-outputs="0"] [data-recorded-sample="0"]').click();
  const sampleTransition=async button=>page.evaluate(async button=>{
   const root=document.querySelector('.order-comparison');
   const cat=root.querySelector('[data-order-focus-card="Cat only"]');
   const address=root.querySelector('[data-order-focus-card="Address"]');
   const before=cat.getBoundingClientRect();
   const positions=[];let start;
   document.querySelector(button).click();
   await new Promise(resolve=>{
    function frame(now) {
     start ??= now;
     const box=cat.getBoundingClientRect();positions.push({cat:box.y,address:address.getBoundingClientRect().y});
     if(now-start<850)requestAnimationFrame(frame);else resolve();
    }
    requestAnimationFrame(frame);
   });
   return {before:before.y,positions,sameNode:root.querySelector('[data-order-focus-card="Cat only"]')===cat,
    slot:cat.style.getPropertyValue('--order-slot'),order:root.querySelector('.order-moving-foci').getAttribute('aria-label')};
  },button);
  for(const button of ['#demo-next','#demo-previous','[data-order-condition="1"]','[data-order-condition="0"]']) {
   const motion=await sampleTransition(button);
   assert.equal(motion.sameNode,true);assert.equal(motion.slot,'1');
   assert.ok(motion.positions.every(p=>Math.abs(p.cat-motion.before)<.1),`Cat only must stay physically fixed throughout ${button}: before ${motion.before}; range ${Math.min(...motion.positions.map(p=>p.cat))}–${Math.max(...motion.positions.map(p=>p.cat))}`);
   const positions=motion.positions.map(p=>p.address),range=Math.max(...positions)-Math.min(...positions);
   assert.ok(range>100,`the surrounding focus must visibly move through ${button}: range ${range} across ${positions.length} frames`);
   assert.ok(new Set(positions.map(y=>y.toFixed(1))).size>4,`other foci animate, not jump: ${button}`);
  }
  assert.equal(await page.locator('[data-order-outputs="0"] [data-recorded-sample="1"]').getAttribute('aria-pressed'),'true','returning to condition A restores output 2');
  // Secondary evidence is still available directly in the same native product panel.
  await page.locator('.focus-order-full>summary').click();
  const first=page.locator('.focus-order-position[data-order-focus="Cat only"][data-order-slot="0"]');
  await first.locator(':scope>summary').click();
  assert.equal(await first.locator('[data-recorded-sample]').count(),3);
  assert.equal(await first.locator('.focus-order-sequence li').first().textContent(),'Cat only');
  // The actual product selectors remain usable beyond the script; Resume restores the chosen pair.
  await page.locator('.order-comparison-settings>summary').click();
  await page.locator('[data-order-choose="0"]').selectOption('0');
  assert.equal(await page.locator('.order-observation').count(),0,'no fixture-specific reading follows a different permutation');
  assert.equal(await page.evaluate(()=>FocalPromptDemo.exploring),true,'changing the comparison leaves the scripted interpretation');
  await page.locator('#demo-explore').click();
  assert.equal(await page.locator('[data-order-shuffle="0"]').textContent(),'4');
  assert.equal(await page.locator('[data-order-shuffle="1"]').textContent(),'2');
  assert.equal(await page.locator('.order-observation').count(),2);
  assert.equal(await page.locator('[data-order-outputs="0"] [data-recorded-sample="1"]').getAttribute('aria-pressed'),'true');
  await page.emulateMedia({reducedMotion:'reduce'});
  assert.equal(await page.locator('[data-order-focus-card="Address"]').evaluate(el=>getComputedStyle(el).transitionDuration),'0s');
  assert.equal(requests.some(url=>url.includes('/api/')),false);assert.deepEqual(errors,[]);
  console.log('PASS: matched permutations, fixed Cat only coordinates through four animated transitions, native exploration, retained sweep, reduced motion, offline and zero API calls.');
  await context.close();
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
