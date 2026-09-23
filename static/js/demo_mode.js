/* Thin guide over the real lab DOM. No prompts, outputs, charts or experiment pages are rendered here. */
(function () {
    'use strict';
    const $ = id => document.getElementById(id);
    const definition = window.FocalPromptDemoDefinition, adapter = window.FocalPromptDemoData;
    let data, nav, timeline, sourceText, activeWorkspaceId, exploring = false;
    const recordings = new Map();
    const savedDetails = new Map();
    const sections = {problem:'lab-prompt', baseline:'lab-baseline', foci:'lab-prompt', ablation:'lab-experiment-b',
        singleton:'lab-singleton', dominance:'lab-singleton', order:'lab-focus-order', jev:'lab-jev', end:'lab-experiment-b'};
    const names = {problem:'Inference scenario',baseline:'Baseline outputs',foci:'Prompt coverage',ablation:'Ablation',
        singleton:'Singleton analysis',dominance:'Focus vs focus',order:'Focus order',comparison:'Model comparison',jev:'Jev composition',end:'Explore the results'};
    const sectionId = frame => frame.id === 'comparison'
        ? ({prompt:'lab-prompt',baseline:'lab-baseline',dominance:'lab-singleton'}[frame.phase]) : sections[frame.id];
    function switchWorkspace(id) {
        if (activeWorkspaceId === id) return false;
        const recording = recordings.get(id);
        if (!recording) throw new Error('The selected recorded workspace is unavailable.');
        sourceText = recording.sourceText;data = recording.data;
        window.restoreWorkspaceSession(JSON.parse(sourceText));
        activeWorkspaceId = id;
        $('demo-workspace').value = id;
        $('demo-ready').textContent = `${data.modelLabel} · recorded workspace · offline ready · clinic location redacted`;
        document.body.dataset.demoWorkspace = id;
        return true;
    }
    // Only display controls remain active in the saved workspace. The fetch guard is an independent backstop.
    const allowedButtons = '[data-order-condition],[data-recorded-sample],[data-coverage-focus],[data-singleton-chart-toggle],[data-singleton-chart-focus],[data-singleton-inspect],[data-pairwise-row],.tab-btn,'
        + '[data-action="set-view"],[data-action="select-focus"],[data-action="close-inspector"],[data-action="toggle-dumbbell-all"],[data-action="export-json"],'
        + '#export-workspace-btn,#singleton-export-btn,#toggle-visualization,#toggle-all-outputs,#download-ablation-results,#error-modal-close,#error-modal-ok';
    const allowedInputs = '#singleton-result-order,#pairwise-view,[data-role="dumbbell-sort"],[data-order-choose],[data-order-anchor-select]';
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
        document.querySelectorAll('.demo-section,.demo-featured,.demo-spotlight,.demo-key-focus,.demo-intent-focus').forEach(el => el.classList.remove('demo-section','demo-featured','demo-spotlight','demo-key-focus','demo-intent-focus'));
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
    function positionScenarioFoci() {
        if (exploring || nav?.frame.id !== 'problem') return;
        for (const focus of [data.booking,data.cat]) {
            const span = focus.spans[0];
            const input = document.querySelector(`[data-message-id="${CSS.escape(span.message_id)}"] .scenario-content`);
            if (!input?.clientHeight) continue;
            // Textarea selections do not reliably scroll without taking keyboard focus.
            // Measure the saved span with the editor's current font and wrapping instead.
            const style = getComputedStyle(input), mirror = document.createElement('div');
            for (const property of ['font','line-height','letter-spacing','word-spacing','text-indent','text-transform',
                'tab-size','white-space','overflow-wrap','word-break','padding-top','padding-right','padding-bottom','padding-left']) {
                mirror.style.setProperty(property,style.getPropertyValue(property));
            }
            Object.assign(mirror.style,{position:'fixed',left:'0',top:'0',visibility:'hidden',pointerEvents:'none',
                boxSizing:'border-box',width:input.clientWidth+'px'});
            mirror.setAttribute('aria-hidden','true');
            const text = document.createTextNode(input.value);mirror.append(text);document.body.append(mirror);
            const range = document.createRange();
            range.setStart(text,span.char_start);range.setEnd(text,span.char_end);
            const bounds = range.getBoundingClientRect();
            const top = bounds.top - mirror.getBoundingClientRect().top;
            input.scrollTop = top - parseFloat(style.paddingTop);
            mirror.remove();
        }
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
            case 'dominance': return 'When both foci are present, which singleton do the outputs resemble? Compare the full prompt and eligible ablations. Blue favors the row; orange favors the column. Select any pair to inspect the evidence. This is behavioral resemblance, not a focus budget or proof of causal dominance.';
            case 'order': {
                return frame.phase === 'condition-a'
                    ? 'Position isn’t the whole story. Cat only has a strong effect in isolation. Here it is second, yet all three outputs continue toward booking. Next: keep it second and change the surrounding order.'
                    : 'Same model. Same words. Same position. Different context. Different behavior. The cat-only constraint appears in all three outputs, but only 1/3 is judged compliant. One scenario, three samples per condition; this does not establish a mechanism.';
            }
            case 'comparison': return frame.phase === 'prompt'
                ? `${data.modelLabel}: stronger system-level booking instruction; an additional, explicit hierarchy focus in the clinic instructions. The cat-only constraint remains. The prompt changed too: this is not a model-only controlled comparison.`
                : frame.phase === 'baseline'
                    ? `${count('baseline','refusal')} refuse to book the dog at this cat-only clinic. Some offer another clinic or booking if the animal is a cat. Editorial reading of all ten stored outputs; select any sample.`
                    : `${recordings.get(definition.primaryWorkspace.id).data.modelLabel}: booking is closer. ${data.modelLabel}: Cat-only is closer. The same matrix shows the behavioral relationship flipped. These are different recorded prompts as well as different models, not evidence of an internal mechanism.`;
            case 'jev': return frame.phase === 'catalog' ? 'Back to the original GPT-4o mini workspace. Now change the prompt environment before inference: the actual Jev decision table gives an inclusion probability for every focus. These are not focus-budget percentages.'
                : frame.phase === 'selected' ? `${data.jev.selected.length}/${data.foci.length} foci selected. Excluded rows are dimmed. The full table and saved decision audit remain available.`
                : frame.phase === 'ordered' ? 'The same selected foci, stitched together in two orders. Follow each coloured focus from the sequence into the assembled message. Compare source order with Jev order. Retained chat and output contract are unchanged.'
                : `Selected foci: ${count('jevSelected','refusal')} clear refusals. Selected + ordered: ${count('jevOrdered','refusal')} clear refusals; ${count('jevOrdered','cat-substitution')} switch the request to a cat. Editorial reading; ordering is not an automatic improvement.`;
            default: return 'The complete research workspace is loaded. Explore the charts, focus inspector, task-quality judgments and saved outputs, or resume any part of the guide. These experiments measure behavior, not internal attention.';
        }
    }
    function prepareView(frame) {
        window.switchTab('prompt-analysis');
        const section = $(sectionId(frame));
        section?.classList.add('demo-section');
        let target = section;
        if (frame.id === 'problem') {
            target = $('scenario-messages');
        } else if (frame.id === 'foci' || (frame.id === 'comparison' && frame.phase === 'prompt')) {
            $('prompt-highlighted').classList.remove('hidden');
            $('prompt-visualization').classList.remove('hidden');
            $('toggle-visualization').textContent = 'Hide';
            window.FocalPromptCoverage.select(data.booking.index);
            target = $('prompt-visualization');
            if (frame.id === 'comparison') {
                for (const focus of [data.booking,data.hierarchy,data.cat]) {
                    const label = target.querySelector(`[data-coverage-focus="${focus.index}"] .legend-item-name`);
                    if (label) label.textContent = `${focus.index+1}. ${focus.name}`;
                }
                // Emphasize literal words in the production source view without changing its text.
                for (const mark of target.querySelectorAll('[data-focus-indices]')) {
                    const indices = mark.dataset.focusIndices.split(',').map(Number);
                    if (indices.some(i => i === data.booking.index || i === data.hierarchy.index)) mark.classList.add('demo-intent-focus');
                    if (indices.includes(data.booking.index)) {
                        const text = mark.textContent, start = text.indexOf('must always');
                        if (start >= 0) {
                            const emphasis = document.createElement('strong');emphasis.className='demo-must-always';emphasis.textContent='must always';
                            mark.replaceChildren(document.createTextNode(text.slice(0,start)),emphasis,document.createTextNode(text.slice(start+11)));
                        }
                    }
                }
            }
        } else if (frame.id === 'baseline' || (frame.id === 'comparison' && frame.phase === 'baseline')) {
            target = document.querySelector('#baseline-results .recorded-samples'); sample(target, data.series.baseline.featured);
            if (frame.id === 'comparison') target.querySelector('.recorded-sample-toolbar strong').textContent = `${data.series.baseline.counts.refusal} / ${data.series.baseline.n} refuse to book the dog at this clinic`;
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
        } else if (frame.id === 'dominance' || (frame.id === 'comparison' && frame.phase === 'dominance')) {
            target = $('singleton-results');
            // Drive the genuine product controls; revisiting this stop resets the comparison.
            for (const [id,value] of [['singleton-result-order','focus_index'],['pairwise-view','combined']]) {
                const control = $(id);
                if (control) {control.value=value;control.dispatchEvent(new Event('change',{bubbles:true}));}
            }
            $(`pairwise-cell-${data.booking.index}-${data.cat.index}`)?.click();
        } else if (frame.id === 'order') {
            target = $('focus-order-results');
            const comparison = target.querySelector('.order-comparison');
            window.FocalPromptOrderComparison.configure(comparison, definition.orderComparison, frame.phase === 'condition-a' ? 0 : 1);
            open(target.querySelector('.focus-order-full'),false);
            open(comparison.querySelector('.order-comparison-settings'),false);
            comparison.querySelectorAll('.recorded-output-card').forEach(el=>open(el));
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
            el.classList.toggle('demo-key-focus',indices.some(i=>i===data.booking.index || i===data.cat.index || i===data.hierarchy?.index));
        });
        if (frame.id === 'end') return $('demo-resources');
        return frame.id === 'dominance' || (frame.id === 'comparison' && frame.phase === 'dominance') ? target.querySelector('.pairwise-results') : target;
    }
    function applyLayout() {
        document.body.classList.toggle('replay-guided', !exploring);
        document.body.classList.toggle('replay-spotlight', !exploring && $('demo-layout').value === 'spotlight');
        document.body.classList.toggle('replay-exploring', exploring);
        $('demo-explore').textContent = exploring ? 'Resume guide' : 'Explore workspace';
    }
    function measureLayout() {
        const body = document.body;
        body.style.setProperty('--demo-top', Math.ceil(document.querySelector('.demo-guide-top').getBoundingClientRect().height) + 'px');
        body.style.setProperty('--demo-bottom', Math.ceil($('demo-guide-controls').getBoundingClientRect().height + 14) + 'px');
        if (body.classList.contains('replay-spotlight') && innerWidth >= 1000) {
            // Use the actual header/nav footprint, including wrapped controls and zoom.
            const bottom = document.querySelector('.lab-jump-nav').getBoundingClientRect().bottom;
            body.style.setProperty('--demo-stage-top', Math.ceil(bottom + 12) + 'px');
        }
    }
    function go(index) {
        const stayingInOrder = !exploring && nav.index !== index && nav.frame.id === 'order' && timeline[index]?.id === 'order'
            && $('lab-focus-order').classList.contains('demo-section');
        if (!stayingInOrder) clearSpotlight();
        nav.go(index);exploring=false;
        const switched = switchWorkspace(nav.frame.workspaceId || definition.primaryWorkspace.id);
        document.body.dataset.demoStep = nav.frame.id;
        document.body.dataset.demoPhase = nav.frame.phase || '';
        applyLayout();
        // A/B is a change inside the existing experiment. Keep its DOM, disclosures and
        // viewport in place instead of removing/reapplying the whole workspace spotlight.
        const target = stayingInOrder ? $('focus-order-results') : prepareView(nav.frame);
        if (switched && !matchMedia('(prefers-reduced-motion: reduce)').matches) target?.animate([{opacity:0},{opacity:1}],{duration:240});
        if (stayingInOrder) window.FocalPromptOrderComparison.show(target.querySelector('.order-comparison'),nav.frame.phase === 'condition-a' ? 0 : 1);
        $('demo-location').value = nav.frame.id;
        $('demo-step-label').textContent = nav.frame.id === 'order' ? (nav.frame.phase === 'condition-a' ? 'Condition A' : 'Condition B')
            : nav.frame.id === 'jev' ? ({catalog:'All decisions',selected:'Selection',ordered:'Ordering',outputs:'Outputs'}[nav.frame.phase])
            : nav.frame.id === 'comparison' ? ({prompt:'Stronger instructions',baseline:'10 recorded outputs',dominance:'Dominance flip'}[nav.frame.phase]) : '';
        $('demo-guide-note').textContent = note(nav.frame);
        $('demo-previous').disabled = nav.index === 0;
        $('demo-next').disabled = nav.index === nav.length-1;
        const next = timeline[nav.index+1];
        $('demo-next').textContent = !next ? 'Guide complete'
            : next.workspaceId && next.workspaceId !== activeWorkspaceId ? `Switch to ${recordings.get(next.workspaceId).data.modelLabel} →`
            : nav.frame.id === 'comparison' && next.id === 'jev' ? `Back to ${recordings.get(definition.primaryWorkspace.id).data.modelLabel}: Jev →`
            : `Next: ${next.id === 'comparison' ? ({prompt:'Stronger instructions',baseline:'Baseline outputs',dominance:'Focus vs focus'}[next.phase]) : names[next.id]} →`;
        if (!stayingInOrder) lockRecording();
        requestAnimationFrame(()=>{
            if (stayingInOrder) return;
            if (document.body.classList.contains('replay-spotlight') && innerWidth >= 1000) { window.scrollTo(0,0); document.querySelector('.demo-section').scrollTop=0; }
            else target?.scrollIntoView({block:'start',behavior:'instant'});
            measureLayout();
            positionScenarioFoci();
            // Position both key source spans within their existing coverage message windows.
            if (nav.frame.id === 'foci' || (nav.frame.id === 'comparison' && nav.frame.phase === 'prompt')) for (const focus of [data.booking,data.cat]) {
                const mark = [...document.querySelectorAll('#prompt-highlighted [data-focus-indices]')].find(el=>el.dataset.focusIndices.split(',').includes(String(focus.index)));
                const pane = mark?.closest('.coverage-message');
                if (pane) pane.scrollTop = nav.frame.id === 'comparison' && focus === data.cat ? 0
                    : mark.offsetTop - pane.offsetTop - pane.clientHeight / 3;
            }
            if (nav.frame.id === 'dominance' || (nav.frame.id === 'comparison' && nav.frame.phase === 'dominance')) {
                const grid = document.querySelector('.pairwise-grid-wrap');
                const cell = grid?.querySelector('[aria-pressed="true"]');
                if (cell) {
                    const box = grid.getBoundingClientRect(), selected = cell.getBoundingClientRect();
                    const headerHeight = grid.querySelector('thead').getBoundingClientRect().height;
                    grid.scrollTop += selected.top - box.top - headerHeight - (grid.clientHeight-headerHeight-selected.height)/2;
                    grid.scrollLeft += selected.left - box.left - grid.clientWidth / 2;
                }
            }
        });
    }
    function explore() {
        exploring = true;applyLayout();clearSpotlight();
        $('demo-guide-note').textContent = 'Explore the real lab: every recorded result is available. Editing and new model calls are disabled in this copy. Resume guide returns to the current comparison.';
        $(sectionId(nav.frame))?.scrollIntoView({block:'start',behavior:'instant'});
    }
    function reset() {
        clearSpotlight();activeWorkspaceId = null;
        go(0);
    }
    async function loadRecording(recording, comparison = false) {
        const response = await fetch(recording.url);
        if (!response.ok) throw new Error('Could not load the recorded workspace.');
        const bytes = await response.arrayBuffer();
        const digest = await crypto.subtle.digest('SHA-256',bytes);
        const hash = [...new Uint8Array(digest)].map(b=>b.toString(16).padStart(2,'0')).join('');
        if (hash !== recording.sha256) throw new Error('Source checksum mismatch. Reload after deployment finishes.');
        const sourceText = new TextDecoder().decode(bytes);
        const data = comparison ? adapter.prepareComparison(JSON.parse(sourceText),recording) : adapter.prepare(JSON.parse(sourceText),definition);
        recordings.set(recording.id,{sourceText,data,definition:recording});
        return data;
    }
    async function load() {
        try {
            if (!window.focalPromptWorkspaceReady) await new Promise(resolve=>window.addEventListener('focalprompt:ready',resolve,{once:true}));
            // Preload and validate every fixture before declaring the sequence offline-ready.
            const [primary,...comparisons] = await Promise.all([loadRecording(definition.primaryWorkspace),
                ...definition.comparisonWorkspaces.map(recording=>loadRecording(recording,true))]);
            if (comparisons.length) {
                const pair = primary.singleton?.pairwise_resemblance?.pairs?.find(p =>
                    p.row_index === Math.min(primary.booking.index,primary.cat.index)
                    && p.column_index === Math.max(primary.booking.index,primary.cat.index));
                const rowShare = pair?.views?.combined?.row_share;
                const bookingShare = primary.booking.index < primary.cat.index ? rowShare : 1-rowShare;
                if (!Number.isFinite(bookingShare) || bookingShare <= .5) throw new Error('The original recording no longer supports the booking-dominant comparison.');
            }
            timeline = adapter.frames(primary,definition,comparisons);nav=adapter.navigator(timeline);
            $('demo-workspace').replaceChildren(...[definition.primaryWorkspace,...definition.comparisonWorkspaces].map(({id})=>{
                const option=document.createElement('option');option.value=id;option.textContent=recordings.get(id).data.modelLabel;return option;
            }));
            $('demo-workspace-label').hidden = !comparisons.length;
            $('demo-location').replaceChildren(...[...new Set(timeline.map(f=>f.id))].map(id=>{const option=document.createElement('option');option.value=id;option.textContent=names[id];return option;}));
            $('demo-guide-controls').hidden=false;$('demo-explore').disabled=false;$('demo-reset').disabled=false;
            document.body.classList.add('replay-ready');
            const layoutObserver = new ResizeObserver(measureLayout);
            for (const element of [$('demo-guide-controls'),document.querySelector('.demo-guide-top'),
                document.querySelector('.app-header'),document.querySelector('.lab-jump-nav')]) layoutObserver.observe(element);
            // Reposition after width/zoom changes, but leave manual scrolling and exploration alone.
            new ResizeObserver(()=>requestAnimationFrame(positionScenarioFoci)).observe($('scenario-messages'));
            document.fonts.ready.then(()=>requestAnimationFrame(positionScenarioFoci));
            // Re-rendered product controls retain their normal browsing behavior but cannot launch a run.
            new MutationObserver(records=>{
                // Text/judgment updates add no controls. Avoid rescanning the entire workspace
                // during each animation frame; newly rendered controls still get locked.
                const controls='button,input,select,textarea';
                if(records.some(record=>[...record.addedNodes].some(node=>node.nodeType===1 && (node.matches(controls) || node.querySelector(controls))))) lockRecording();
            }).observe(document.querySelector('.container'),{childList:true,subtree:true});
            go(0);
            window.FocalPromptDemo=Object.freeze({get data(){return data;},get workspaceId(){return activeWorkspaceId;},get frame(){return nav.frame;},get index(){return nav.index;},get length(){return nav.length;},get exploring(){return exploring;}});
        } catch (error) {
            $('demo-ready').textContent='Replay unavailable';$('demo-load-error').hidden=false;$('demo-load-error').textContent=error.message;
        }
    }
    $('demo-next').addEventListener('click',()=>go(nav.index+1));
    $('demo-previous').addEventListener('click',()=>go(nav.index-1));
    // Guide preferences are not experiment settings: do not trigger the lab's settings listeners.
    $('demo-location').addEventListener('change',event=>{event.stopPropagation();go(timeline.findIndex(frame=>frame.id===event.target.value));});
    $('demo-workspace').addEventListener('change',event=>{
        event.stopPropagation();
        go(event.target.value === definition.primaryWorkspace.id
            ? timeline.findIndex(frame=>frame.id==='jev') : timeline.findIndex(frame=>frame.workspaceId===event.target.value));
    });
    $('demo-layout').addEventListener('change',event=>{event.stopPropagation();go(nav.index);});
    $('demo-explore').addEventListener('click',()=>exploring ? go(nav.index) : explore());
    $('demo-reset').addEventListener('click',reset);
    $('demo-fullscreen').addEventListener('click',async()=>{try {if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen();}catch(_){$('demo-ready').textContent='Fullscreen unavailable · recorded workspace ready';}});
    // Normal navigation visibly leaves the scripted path; no duplicate product navigation.
    document.querySelector('.lab-jump-nav').addEventListener('click',event=>{if(event.target.closest('a') && nav)explore();});
    // Native comparison toggles and the guide must describe the same recorded condition.
    document.addEventListener('click',event=>{
        if (nav?.frame.id==='comparison' && nav.frame.phase==='prompt' && !exploring && event.target.closest('[data-coverage-focus]')) explore();
        const button=event.target.closest('#focus-order-results [data-order-condition]');
        if(button && nav?.frame.id==='order' && !exploring) {
            event.preventDefault();event.stopPropagation();
            const phase=button.dataset.orderCondition==='0' ? 'condition-a' : 'condition-b';
            go(timeline.findIndex(frame=>frame.id==='order' && frame.phase===phase));
        }
    },true);
    document.addEventListener('change',event=>{
        if(nav?.frame.id==='order' && !exploring && event.target.matches('[data-order-choose],[data-order-anchor-select]')) explore();
    });
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
            const url=URL.createObjectURL(new Blob([sourceText],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=recordings.get(activeWorkspaceId).definition.filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
        }
    },true);
    load();
})();
