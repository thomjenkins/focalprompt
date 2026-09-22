/* Run against a local server; no model credentials or live inference required. */
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const base = process.env.FOCALPROMPT_TEST_URL || 'http://127.0.0.1:5014';
const fixture = fs.readFileSync(require('node:path').join(__dirname,'../../examples/demos/lisbon/pup4ominiFull.json'));
const sha = value => crypto.createHash('sha256').update(value).digest('hex');

(async () => {
    const browser = await chromium.launch({channel:'chrome',headless:true});
    try {
        for (const [width,height] of [[1280,720],[1920,1080],[390,844]]) {
            const context = await browser.newContext({viewport:{width,height},reducedMotion:'reduce'});
            const errors = [], apiCalls = [];
            const entry = await context.newPage();
            await entry.goto(base+'/experiments');
            const opened = context.waitForEvent('page');
            await entry.locator('.lisbon-demo-card').click();
            const page = await opened;
            page.setDefaultTimeout(10000);
            page.on('pageerror',e=>errors.push(e.message));
            page.on('request',r=>{if(r.url().includes('/api/'))apiCalls.push(r.url());});
            await page.waitForFunction(()=>window.FocalPromptDemo);
            assert.equal(await page.title(),'The pup at the cat-only clinic · LisbonAI · FocalPrompt');
            assert.equal(await page.locator('#demo-model').textContent(),'GPT-4o mini');
            assert.equal(await page.locator('#demo-stage .demo-role').first().textContent(),'system');
            const frozenBefore = await page.evaluate(()=>JSON.stringify(FocalPromptDemo.data.workspace));
            assert.equal(frozenBefore,JSON.stringify(JSON.parse(fixture)));
            await context.setOffline(true);
            const offlineRequests=[];page.on('request',r=>offlineRequests.push(r.url()));
            const states = [];
            for(let i=0;i<15;i++) {
                const snapshot=await page.evaluate(()=>({index:FocalPromptDemo.index,frame:FocalPromptDemo.frame,
                    texts:[...document.querySelectorAll('[data-response]')].map(el=>({key:el.dataset.response,text:el.querySelector('blockquote').textContent,
                        selected:Number(el.querySelector('.demo-sample.selected').dataset.sample)})),
                    clipping:[...document.querySelectorAll('#demo-stage,.demo-panel,.demo-response blockquote,.demo-focus-catalog')]
                        .filter(e=>e.scrollHeight>e.clientHeight+2).map(e=>[e.className||e.id,e.scrollHeight,e.clientHeight]),
                    overflowX:document.documentElement.scrollWidth>innerWidth,overflowY:document.documentElement.scrollHeight>innerHeight}));
                assert.equal(snapshot.index,i);assert.equal(snapshot.overflowX,false,`horizontal overflow at ${width}, state ${i}`);
                if(width>=1280){assert.deepEqual(snapshot.clipping,[],`clipping at ${width}, state ${i}`);assert.equal(snapshot.overflowY,false);}
                for(const shown of snapshot.texts) {
                    const actual=await page.evaluate(({key,selected})=>FocalPromptDemo.data.series[key].samples[selected].text,shown);
                    assert.equal(shown.text,actual,'response text must stay verbatim');
                }
                if(i===1)assert.equal(await page.locator('.demo-sample').count(),10);
                if(i===6)assert.match(await page.locator('.demo-order-row').first().textContent(),/Cat only/);
                if(i===11)assert.equal(await page.locator('.demo-compose-focus.excluded').count(),6);
                if(i===12)assert.deepEqual(await page.locator('.demo-compose-focus .demo-focus-number').allTextContents(),['5','3','12','8','13','11','9','1','2','16','17']);
                if(i===13)assert.match(await page.locator('.demo-caveat').textContent(),/4 \/ 10/);
                states.push(snapshot.frame);
                if(i<14)await page.keyboard.press('ArrowRight');
            }
            assert.equal(await page.locator('#demo-next').isDisabled(),true);
            await page.keyboard.press('ArrowRight');assert.equal(await page.evaluate(()=>FocalPromptDemo.index),14);
            for(let i=13;i>=0;i--){await page.keyboard.press('ArrowLeft');assert.deepEqual(await page.evaluate(()=>FocalPromptDemo.frame),states[i]);}
            await page.keyboard.press(' ');assert.equal(await page.evaluate(()=>FocalPromptDemo.index),1);
            await page.locator('[data-inspect=baseline]').click();
            const beforeModal=await page.evaluate(()=>FocalPromptDemo.index);
            await page.keyboard.press('ArrowRight');assert.equal(await page.evaluate(()=>FocalPromptDemo.index),beforeModal);
            assert.match(await page.locator('#demo-detail-body').textContent(),/Stored behavioral judgment/);
            await page.keyboard.press('Escape');assert.equal(await page.locator('#demo-detail').isVisible(),false);
            await page.keyboard.press('Escape');assert.equal(await page.locator('#demo-exited').isVisible(),true);
            await page.locator('#demo-resume').click();assert.equal(await page.evaluate(()=>FocalPromptDemo.index),1);
            await page.locator('#demo-reset').click();assert.equal(await page.evaluate(()=>FocalPromptDemo.index),0);
            await page.locator('#demo-evidence').click();
            const downloadEvent=page.waitForEvent('download');await page.locator('#demo-download').click();
            const download=await downloadEvent;
            assert.equal(sha(fs.readFileSync(await download.path())),sha(fixture));
            await page.keyboard.press('Escape');
            assert.equal(await page.evaluate(()=>JSON.stringify(FocalPromptDemo.data.workspace)),frozenBefore);
            assert.deepEqual(apiCalls,[]);assert.deepEqual(offlineRequests,[]);assert.deepEqual(errors,[]);
            console.log(`PASS ${width}×${height}: all 15 replay states offline; exact outputs; keyboard/reset/exit; source download; no API calls or mutation.`);
            await context.close();
        }
        // Launching from a live lab must leave its current workspace intact.
        const context=await browser.newContext();const lab=await context.newPage();
        await lab.goto(base+'/lab');await lab.waitForFunction(()=>window.collectWorkspaceSession);
        await lab.evaluate(()=>{window.setInferenceScenario({version:1,messages:[{id:'draft',role:'user',analysis_mode:'analyse',content:'Unsaved experiment — preserve me.'}]});});
        const before=await lab.evaluate(()=>JSON.stringify(window.collectWorkspaceSession()));
        const tabEvent=context.waitForEvent('page');await lab.locator('a[href="/demo/lisbon"]').click();
        const replay=await tabEvent;await replay.waitForFunction(()=>window.FocalPromptDemo);
        // exported_at is the only wall-clock-dependent field in collection.
        const after=await lab.evaluate(()=>JSON.stringify(window.collectWorkspaceSession()));
        const a=JSON.parse(before),b=JSON.parse(after);delete a.exported_at;delete b.exported_at;assert.deepEqual(a,b);
        await context.close();console.log('PASS: launch preserves unsaved lab workspace.');
    } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
