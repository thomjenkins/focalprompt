/* Thin guide over the real lab DOM. No prompts, outputs, charts or experiment pages are rendered here. */
(function () {
    'use strict';
    const $ = id => document.getElementById(id);
    const definition = window.FocalPromptDemoDefinition, adapter = window.FocalPromptDemoData;
    let data, nav, timeline, sourceText, exploring = false;
    const savedDetails = new Map();
    const sections = {problem:'lab-prompt', baseline:'lab-baseline', foci:'lab-prompt', ablation:'lab-experiment-b',
        singleton:'lab-singleton', order:'lab-focus-order', jev:'lab-jev', end:'lab-experiment-b'};
    const names = {problem:'Inference scenario',baseline:'Baseline outputs',foci:'Prompt coverage',ablation:'Ablation',
        singleton:'Singleton analysis',order:'Focus order',jev:'Jev composition',end:'Explore the results'};
    // Only display controls remain active in the saved workspace. The fetch guard is an independent backstop.
    const allowedButtons = '[data-recorded-sample],[data-coverage-focus],[data-singleton-chart-toggle],[data-singleton-chart-focus],[data-singleton-inspect],[data-pairwise-row],.tab-btn,'
        + '[data-action="set-view"],[data-action="select-focus"],[data-action="close-inspector"],[data-action="toggle-dumbbell-all"],[data-action="export-json"],'
        + '#export-workspace-btn,#singleton-export-btn,#toggle-visualization,#toggle-all-outputs,#download-ablation-results,#error-modal-close,#error-modal-ok';
    const allowedInputs = '#singleton-result-order,#pairwise-view,[data-role="dumbbell-sort"]';
    function lockRecording() {
        document.querySelectorAll('.container button').forEach(button => {
            if (!button.matches(allowedButtons) && !button.disabled) {
                button.disabled = true;
                button.title = 'Recorded workspace — open the lab to edit or run a new analysis.';
            }
        });
        document.querySelectorAll('.container input,.container select,.container textarea').forEach(input => {
            if (input.matches(allowedInputs)) return;
            if (input.tagName === 'TEXTAREA' || (input.tagName === 'INPUT' && ['text',''].includes(input.type))) input.readOnly = true;
            else input.disabled = true;
        });
    }
    function clearSpotlight() {
        document.querySelectorAll('.demo-section,.demo-featured,.demo-spotlight,.demo-key-focus').forEach(el => el.classList.remove('demo-section','demo-featured','demo-spotlight','demo-key-focus'));
        for (const [details, open] of savedDetails) if (details.isConnected) details.open = open;
        savedDetails.clear();
    }
    function open(details, value = true) {
        if (!details) return;
        if (!savedDetails.has(details)) savedDetails.set(details, details.open);
        details.open = value;
    }
    function sample(root, index) {
        if (root) window.FocalPromptSamples.select(root, index || 0);
    }
    function feature(el) {el?.classList.add('demo-featured'); return el;}
    function note(frame) {
        const count = (key, behavior) => `${data.series[key].counts[behavior] || 0}/${data.series[key].n}`;
        switch(frame.id) {
            case 'problem': return 'The actual scenario: main instructions, retained pet-owner chat, and clinic instructions. The source roles and wording are unchanged.';
            case 'baseline': return `${count('baseline','booking')} offer or progress booking. Select any stored output below. This is repeated sampling of the unchanged prompt, not one completion.`;
            case 'foci': return `${data.foci.length} labelled source spans. Choose a focus in the coverage legend to find it in the original prompt. Appointment booking and Cat only are the instructions we will test.`;
            case 'ablation': return `Featured comparison: without Cat only, ${count('removeCat','booking')} offer booking; without Appointment booking, ${count('removeBooking','refusal')} refuse or redirect. The displayed refusal is the exception. Editorial reading; inspect all samples.`;
            case 'singleton': return `Featured singleton comparisons: no focus ${count('noFocus','booking')} progress booking; booking only ${count('bookingOnly','booking')} progress booking; cat only ${count('catOnly','refusal')} refuse or redirect. Editorial reading of saved outputs.`;
            case 'order': {
                const slot = frame.phase === 'original' ? data.originalOrder.indexOf(data.cat.index) : frame.position;
                return `${frame.phase === 'original' ? 'Original order' : 'Recorded position ' + (slot+1)}: ${count('order-' + slot,'refusal')} refuse or redirect. Same words, same message role; only the order changes. Stored LLM judgments, not ground truth; one scenario.`;
            }
            case 'jev': return frame.phase === 'catalog' ? 'The actual Jev decision table: an inclusion probability for every focus, conditioned on the input. These probabilities are not focus-budget percentages.'
                : frame.phase === 'selected' ? `${data.jev.selected.length}/${data.foci.length} foci selected. Excluded rows are dimmed. The full table and saved decision audit remain available.`
                : frame.phase === 'ordered' ? 'The recorded within-message order and exact composed prompts. Message roles, retained input and output contract are preserved.'
                : `Selected foci: ${count('jevSelected','refusal')} clear refusals. Selected + ordered: ${count('jevOrdered','refusal')} clear refusals; ${count('jevOrdered','cat-substitution')} switch the request to a cat. Editorial reading; ordering is not an automatic improvement.`;
            default: return 'The complete research workspace is loaded. Explore the charts, focus inspector, task-quality judgments and saved outputs, or resume any part of the guide. These experiments measure behavior, not internal attention.';
        }
    }
    function prepareView(frame) {
        window.switchTab('prompt-analysis');
        const section = $(sections[frame.id]);
        section?.classList.add('demo-section');
        let target = section;
        if (frame.id === 'problem') {
            target = $('scenario-messages');
            // The source editor itself, scrolled to the booking instruction; no replacement excerpt.
            const message = document.querySelector(`[data-message-id="${data.booking.spans[0].message_id}"] .scenario-content`);
            if (message) {message.setSelectionRange(data.booking.spans[0].char_start,data.booking.spans[0].char_end);}
        } else if (frame.id === 'foci') {
            $('prompt-highlighted').classList.remove('hidden');
            $('prompt-visualization').classList.remove('hidden');
            $('toggle-visualization').textContent = 'Hide';
            window.FocalPromptCoverage.select(data.booking.index);
            target = $('prompt-visualization');
        } else if (frame.id === 'baseline') {
            target = document.querySelector('#baseline-results .recorded-samples'); sample(target, definition.featured.baseline);
        } else if (frame.id === 'ablation' || frame.id === 'end') {
            window.FocalPromptReport.selectFocus(null);
            document.querySelector(`#ablation-results [data-action="set-view"][data-view="${frame.id === 'end' ? 'overview' : 'samples'}"]`)?.click();
            target = $('ablation-results');
            if (frame.id === 'ablation') {
                for (const [focus,key] of [[data.cat,'removeCat'],[data.booking,'removeBooking']]) {
                    const card = [...target.querySelectorAll('[data-sample-focus]')].find(el=>el.dataset.sampleFocus === focus.name);
                    feature(card);sample(card?.querySelector('.recorded-samples'),definition.featured[key]);
                }
            }
        } else if (frame.id === 'singleton') {
            target = $('singleton-results');
            for (const focus of [data.booking,data.cat]) {
                const details = feature($('singleton-focus-details-' + focus.index)); open(details);
                details?.querySelectorAll('.singleton-arm').forEach(arm => {
                    const show = arm.dataset.singletonArm === 'Singleton' || (focus === data.booking && arm.dataset.singletonArm === 'No-focus');
                    open(arm, show);if(show)feature(arm);
                    sample(arm.querySelector('.recorded-samples'),arm.dataset.singletonArm === 'Singleton' && focus === data.cat ? definition.featured.catOnly : 0);
                });
            }
        } else if (frame.id === 'order') {
            const slot = frame.phase === 'original' ? data.originalOrder.indexOf(data.cat.index) : frame.position;
            target = $('focus-order-results');
            target.querySelectorAll('.focus-order-position').forEach(el => {
                const selected = el.dataset.orderFocus === data.cat.name && Number(el.dataset.orderSlot) === slot;
                open(el, selected);if(selected)feature(el);
                sample(el.querySelector('.recorded-samples'),definition.featured['order-' + slot]);
            });
        } else if (frame.id === 'jev') {
            target = $('jev-results');
            if (frame.phase === 'ordered') target.querySelectorAll('.jev-arm:not([data-jev-arm="full"])>details').forEach(el=>open(el));
            if (frame.phase === 'outputs') {
                for (const [arm,key] of [['full','jevFull'],['selected','jevSelected'],['ordered','jevOrdered']]) sample(target.querySelector(`[data-jev-arm="${arm}"] .recorded-samples`),definition.featured[key]);
            }
        }
        target?.classList.add('demo-spotlight');
        document.querySelectorAll('#prompt-highlighted [data-focus-indices],#legend-items [data-coverage-focus]').forEach(el => {
            const indices = (el.dataset.focusIndices || el.dataset.coverageFocus || '').split(',').map(Number);
            el.classList.toggle('demo-key-focus',indices.some(i=>i===data.booking.index || i===data.cat.index));
        });
        return target;
    }
    function applyLayout() {
        document.body.classList.toggle('replay-guided', !exploring);
        document.body.classList.toggle('replay-spotlight', !exploring && $('demo-layout').value === 'spotlight');
        document.body.classList.toggle('replay-exploring', exploring);
        $('demo-explore').textContent = exploring ? 'Resume guide' : 'Explore workspace';
    }
    function go(index) {
        clearSpotlight();nav.go(index);exploring=false;
        document.body.dataset.demoStep = nav.frame.id;
        document.body.dataset.demoPhase = nav.frame.phase || '';
        applyLayout();
        const target = prepareView(nav.frame);
        $('demo-location').value = nav.frame.id;
        $('demo-step-label').textContent = nav.frame.id === 'order' ? (nav.frame.phase === 'original' ? 'Original order' : `Position ${nav.frame.position+1}`)
            : nav.frame.id === 'jev' ? ({catalog:'All decisions',selected:'Selection',ordered:'Ordering',outputs:'Outputs'}[nav.frame.phase]) : '';
        $('demo-guide-note').textContent = note(nav.frame);
        $('demo-previous').disabled = nav.index === 0;
        $('demo-next').disabled = nav.index === nav.length-1;
        $('demo-next').textContent = nav.index === nav.length-1 ? 'Guide complete' : `Next: ${names[timeline[nav.index+1].id]} →`;
        lockRecording();
        requestAnimationFrame(()=>{
            if (document.body.classList.contains('replay-spotlight') && innerWidth >= 1000) { window.scrollTo(0,0); document.querySelector('.demo-section').scrollTop=0; }
            else target?.scrollIntoView({block:'start',behavior:'instant'});
            // Position both key source spans within their existing coverage message windows.
            if (nav.frame.id === 'foci') for (const focus of [data.booking,data.cat]) {
                const mark = [...document.querySelectorAll('#prompt-highlighted [data-focus-indices]')].find(el=>el.dataset.focusIndices.split(',').includes(String(focus.index)));
                const pane = mark?.closest('.coverage-message');
                if (pane) pane.scrollTop = mark.offsetTop - pane.offsetTop - pane.clientHeight / 3;
            }
        });
    }
    function explore() {
        exploring = true;applyLayout();clearSpotlight();
        $('demo-guide-note').textContent = 'Explore the real lab: every recorded result is available. Editing and new model calls are disabled in this copy. Resume guide returns to the current comparison.';
        $(sections[nav.frame.id])?.scrollIntoView({block:'start',behavior:'instant'});
    }
    function reset() {
        window.restoreWorkspaceSession(JSON.parse(sourceText));
        go(0);
    }
    async function load() {
        try {
            if (!window.focalPromptWorkspaceReady) await new Promise(resolve=>window.addEventListener('focalprompt:ready',resolve,{once:true}));
            const response = await fetch(definition.primaryWorkspace.url);
            if (!response.ok) throw new Error('Could not load the recorded workspace.');
            const bytes = await response.arrayBuffer();
            const digest = await crypto.subtle.digest('SHA-256',bytes);
            const hash = [...new Uint8Array(digest)].map(b=>b.toString(16).padStart(2,'0')).join('');
            if (hash !== definition.primaryWorkspace.sha256) throw new Error('Source checksum mismatch. Reload after deployment finishes.');
            sourceText = new TextDecoder().decode(bytes);
            data = adapter.prepare(JSON.parse(sourceText),definition);
            window.restoreWorkspaceSession(JSON.parse(sourceText));
            timeline = adapter.frames(data,definition);nav=adapter.navigator(timeline);
            $('demo-location').replaceChildren(...[...new Set(timeline.map(f=>f.id))].map(id=>{const option=document.createElement('option');option.value=id;option.textContent=names[id];return option;}));
            $('demo-ready').textContent = `${data.modelLabel} · recorded workspace · offline ready`;
            $('demo-guide-controls').hidden=false;$('demo-explore').disabled=false;$('demo-reset').disabled=false;
            document.body.classList.add('replay-ready');
            new ResizeObserver(()=>{
                document.body.style.setProperty('--demo-bottom', ($('demo-guide-controls').getBoundingClientRect().height + 14) + 'px');
            }).observe($('demo-guide-controls'));
            // Re-rendered product controls retain their normal browsing behavior but cannot launch a run.
            new MutationObserver(lockRecording).observe(document.querySelector('.container'),{childList:true,subtree:true});
            go(0);
            window.FocalPromptDemo=Object.freeze({get data(){return data;},get frame(){return nav.frame;},get index(){return nav.index;},get length(){return nav.length;},get exploring(){return exploring;}});
        } catch (error) {
            $('demo-ready').textContent='Replay unavailable';$('demo-load-error').hidden=false;$('demo-load-error').textContent=error.message;
        }
    }
    $('demo-next').addEventListener('click',()=>go(nav.index+1));
    $('demo-previous').addEventListener('click',()=>go(nav.index-1));
    $('demo-location').addEventListener('change',event=>go(timeline.findIndex(frame=>frame.id===event.target.value)));
    $('demo-layout').addEventListener('change',()=>go(nav.index));
    $('demo-explore').addEventListener('click',()=>exploring ? go(nav.index) : explore());
    $('demo-reset').addEventListener('click',reset);
    $('demo-fullscreen').addEventListener('click',async()=>{try {if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen();}catch(_){$('demo-ready').textContent='Fullscreen unavailable · recorded workspace ready';}});
    // Normal navigation visibly leaves the scripted path; no duplicate product navigation.
    document.querySelector('.lab-jump-nav').addEventListener('click',event=>{if(event.target.closest('a') && nav)explore();});
    document.addEventListener('keydown',event=>{
        if(!nav || event.ctrlKey || event.altKey || event.metaKey || event.repeat) return;
        if(document.querySelector('dialog[open]') || $('error-modal').style.display === 'block') return;
        if(event.key==='Escape'){event.preventDefault();explore();return;}
        if(exploring || /INPUT|TEXTAREA|SELECT/.test(event.target.tagName) || event.target.isContentEditable) return;
        if(event.key===' ' && event.target.closest('button,summary,a')) return;
        if(['ArrowLeft','ArrowRight',' '].includes(event.key)){event.preventDefault();go(nav.index+(event.key==='ArrowLeft'?-1:1));}
    });
    // The replay export is the byte-identical source, not a newly serialized lab view.
    document.addEventListener('click',event=>{
        if(event.target.closest('#export-workspace-btn') && sourceText){event.preventDefault();event.stopImmediatePropagation();
            const url=URL.createObjectURL(new Blob([sourceText],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=definition.primaryWorkspace.filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
        }
    },true);
    load();
})();
