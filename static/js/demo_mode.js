/* Stage controls and sparse views over an immutable workspace snapshot. No inference endpoints. */
(function () {
    'use strict';
    const definition = window.FocalPromptDemoDefinition, adapter = window.FocalPromptDemoData;
    const $ = id => document.getElementById(id);
    const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
    const behavior = {booking: 'Offers / progresses booking', refusal: 'Refuses / redirects the dog', 'cat-substitution': 'Switches the request to a cat', unclassified: 'Unclassified'};
    let data, navigation, timeline, originalText, active = true, selections = {}, comparisons = [];
    const optionalWarnings = [];
    const dialog = $('demo-detail');
    const tag = (focus, extra = '') => `<span class="demo-focus ${focus.index === data.cat.index ? 'cat' : focus.index === data.booking.index ? 'booking' : ''} ${extra}" data-motion="focus-${focus.index}"><span class="demo-focus-number">${focus.index + 1}</span>${esc(focus.name)}</span>`;
    const count = (key, category) => data.series[key]?.counts[category] || 0;
    const ratio = (key, category) => `${count(key, category)}<span> / ${data.series[key].n}</span>`;
    function openDetail(title, html) {
        $('demo-detail-title').textContent = title;
        $('demo-detail-body').innerHTML = html;
        dialog.showModal();
        $('demo-close-detail').focus();
    }
    function heading(frame, subtitle) {
        return `<header class="demo-heading"><p class="demo-eyebrow">${esc(frame.label)} <span>· recorded experiment</span></p><h1>${esc(frame.title)}</h1>${subtitle ? `<p>${subtitle}</p>` : ''}</header>`;
    }
    function indicators(series, selected) {
        return `<div class="demo-samples" aria-label="${series.n} stored samples">${series.samples.map(s => `<button type="button" class="demo-sample ${esc(s.behavior)} ${s.index === selected ? 'selected' : ''}" data-series="${series.key}" data-sample="${s.index}" aria-pressed="${s.index === selected}" aria-label="Sample ${s.index + 1}: ${esc(behavior[s.behavior])}">${s.index + 1}</button>`).join('')}</div>`;
    }
    function response(key, options = {}) {
        const series = data.series[key];
        if (!series) return '<p>Optional result not included in this export.</p>';
        const selected = selections[key] ?? series.featured, sample = series.samples[selected];
        return `<div class="demo-response ${options.compact ? 'compact' : ''}" data-response="${key}">
            ${indicators(series, selected)}
            <div class="demo-response-label"><span>Sample ${selected + 1} of ${series.n}${options.exception ? ' · featured exception' : ''}</span><button type="button" data-inspect="${key}" data-index="${selected}">Inspect ↗</button></div>
            <blockquote>${esc(sample.text)}</blockquote>
            <span class="demo-outcome ${esc(sample.behavior)}">${esc(behavior[sample.behavior])}</span>
        </div>`;
    }
    function evidence(key) { return `<p class="demo-evidence-note">${esc(data.series[key]?.evidence || '')}</p>`; }
    function excerpt(focus, context = false) {
        const span = focus.spans[0], message = data.scenario.messages.find(m => m.id === span.message_id);
        const before = context ? message.content.slice(Math.max(0, span.char_start - 150), span.char_start) : '';
        const after = context ? message.content.slice(span.char_end, span.char_end + 65) : '';
        return `<div class="demo-source-excerpt">${before ? `<span class="demo-surrounding">…${esc(before)}</span>` : ''}<mark class="${focus.index === data.cat.index ? 'cat' : 'booking'}">${esc(span.text)}</mark>${after ? `<span class="demo-surrounding">${esc(after)}…</span>` : ''}</div>`;
    }
    function problem(frame) {
        const retained = data.scenario.messages.find(m => m.analysis_mode === 'retain');
        const query = retained?.content || '';
        // Show the verbatim message, with its existing transcript prefix de-emphasized.
        const colon = query.indexOf(': ', query.indexOf('}}'));
        const prefix = colon >= 0 ? query.slice(0, colon + 2) : '';
        const body = prefix ? query.slice(prefix.length) : query;
        return heading(frame, 'A booking request meets two competing instructions.') + `<div class="demo-problem-grid">
            <article class="demo-panel demo-main-prompt"><div class="demo-panel-heading"><span>Main instructions</span><span class="demo-role">${esc(data.booking.spans[0].role)}</span></div>${tag(data.booking)}${excerpt(data.booking, true)}<button class="demo-text-button" data-message="${esc(data.booking.spans[0].message_id)}">Read complete message ↗</button></article>
            <article class="demo-query"><span class="demo-eyebrow">Pet-owner message · ${esc(retained?.role)} · retained</span><p class="demo-transcript-prefix">${esc(prefix)}</p><blockquote>“${esc(body)}”</blockquote></article>
            <article class="demo-panel demo-clinic-prompt"><div class="demo-panel-heading"><span>Clinic-specific instructions</span><span class="demo-role">${esc(data.cat.spans[0].role)}</span></div>${tag(data.cat)}${excerpt(data.cat, true)}<button class="demo-text-button" data-message="${esc(data.cat.spans[0].message_id)}">Read complete message ↗</button></article>
        </div><p class="demo-takeaway">Will the model offer this pup an appointment?</p>`;
    }
    function baseline(frame) {
        return heading(frame, `Unchanged scenario · temperature ${esc(data.temperature)} · independent samples`) + `<div class="demo-two-up demo-baseline-layout"><section class="demo-stat-panel"><div class="demo-big-number">${ratio('baseline', 'booking')}</div><h2>offer to book the pup</h2><p>The cat-only instruction is present in every request.</p>${evidence('baseline')}</section><article class="demo-panel">${response('baseline')}</article></div><p class="demo-takeaway">Repeated sampling makes the pattern visible.</p>`;
    }
    function catalog(frame) {
        const primary = new Set([data.booking.index, data.cat.index]);
        return heading(frame, `${data.foci.length} tagged foci · exact source spans · two instructions in tension`) + `<div class="demo-focus-catalog">${data.foci.map(f => `<button type="button" class="demo-focus-cell ${primary.has(f.index) ? 'key-focus' : 'dimmed'}" data-focus="${f.index}">${tag(f)}${primary.has(f.index) ? `<span class="demo-focus-quote">${esc(f.spans.map(s => s.text).join('\n'))}</span><small>${esc(f.spans[0].role)} message</small>` : ''}</button>`).join('')}</div><div class="demo-takeaway-row"><p class="demo-takeaway">From prompt prose to units we can test.</p>${data.selfReport.length ? '<button type="button" id="demo-self-report">Self-report ↗</button>' : ''}</div>`;
    }
    function ablation(frame) {
        return heading(frame, 'The retained chat and remaining instructions stay in place.') + `<div class="demo-two-up demo-experiments">
            <article class="demo-panel"><div class="demo-panel-heading"><h2>Remove Cat only</h2>${tag(data.cat, 'removed')}</div><p class="demo-condition-stat">${ratio('removeCat', 'booking')} <span>still offer booking</span></p>${response('removeCat', {compact: true})}</article>
            <article class="demo-panel"><div class="demo-panel-heading"><h2>Remove Appointment booking</h2>${tag(data.booking, 'removed')}</div><p class="demo-condition-stat">${ratio('removeBooking', 'refusal')} <span>refuse / redirect</span></p>${response('removeBooking', {compact: true, exception: true})}</article>
        </div><p class="demo-takeaway">Removing “Cat only” leaves booking intact. Removing “Appointment booking” can change it.</p><p class="demo-evidence-note">Editorial reading of all stored samples · behavioral perturbation evidence, not an internal mechanism. <button data-statistics="ablation">Statistics ↗</button></p>`;
    }
    function singletons(frame) {
        const cards = [['noFocus', 'No focal instruction', 'booking', null], ['bookingOnly', 'Appointment booking only', 'booking', data.booking], ['catOnly', 'Cat only — in isolation', 'refusal', data.cat]];
        return heading(frame, 'Retained chat, output contract and text outside labelled spans are preserved.') + `<div class="demo-three-up demo-experiments">${cards.map(([key,title,category,focus]) => `<article class="demo-panel"><h2>${title}</h2><p class="demo-condition-stat">${ratio(key, category)} <span>${category === 'booking' ? 'progress booking' : 'refuse / redirect'}</span></p>${response(key, {compact: true})}</article>`).join('')}</div><p class="demo-takeaway">“Cat only” is strong in isolation. Its behavioral expression changes in context.</p><p class="demo-evidence-note">Editorial reading of stored outputs · these samples measure behavior, not transformer attention. <button data-statistics="singleton">Statistics ↗</button></p>`;
    }
    function ordering(frame) {
        const originalPosition = data.originalOrder.indexOf(data.cat.index);
        const position = data.positions.find(p => p.slot_index === (frame.phase === 'original' ? originalPosition : frame.position)) || data.positions[0];
        const indices = frame.phase === 'original' ? data.originalOrder : position.indices;
        const series = data.series[position.series];
        return heading(frame, `Same model · same words · same ${esc(data.orderMessage?.role)} message role`) + `<div class="demo-two-up demo-order-layout"><section class="demo-panel"><div class="demo-panel-heading"><h2>${frame.phase === 'original' ? 'Original sequence' : `Cat only → position ${position.slot_index + 1}`}</h2><span class="demo-role">${esc(data.orderMessage?.role)}</span></div><div class="demo-order-stack">${indices.map((index, slot) => `<div class="demo-order-row" data-motion="order-${index}"><span class="demo-slot">${slot + 1}</span>${tag(data.foci[index])}<span aria-hidden="true" class="demo-grip">⠿</span></div>`).join('')}</div><div class="demo-position-buttons" aria-label="Recorded positions">${data.positions.map(p => `<button type="button" data-position="${p.slot_index}" aria-pressed="${p.slot_index === position.slot_index}">Position ${p.slot_index + 1}<span>${count(p.series,'refusal')}/${data.series[p.series].n} refuse</span></button>`).join('')}</div></section><article class="demo-panel"><p class="demo-condition-stat">${ratio(position.series,'refusal')} <span>refuse / redirect</span></p>${response(position.series, {compact:true})}</article></div><p class="demo-takeaway">${frame.phase === 'original' ? 'Move one instruction. Replay the recorded result.' : position.slot_index === 0 ? 'At the first position, the behavior flips.' : 'At this position, booking returns.'}</p><p class="demo-evidence-note">${esc(series.evidence)} · n = ${series.n} at this position; one scenario, not a general ordering rule.</p>`;
    }
    function composition(frame) {
        if (frame.phase === 'outputs') {
            return heading(frame, 'Selection and ordering are both interventions. Inspect the separate arms.') + `<div class="demo-three-up demo-experiments demo-jev-results">
                ${[['jevFull','Full prompt','booking','offer booking'],['jevSelected','Selected foci','refusal','clear refusals'],['jevOrdered','Selected + ordered','refusal','clear refusals']].map(([key,title,category,label]) => `<article class="demo-panel"><h2>${title}</h2><p class="demo-condition-stat">${ratio(key,category)} <span>${label}</span></p>${response(key,{compact:true})}${key === 'jevOrdered' ? `<button type="button" class="demo-caveat" data-inspect="jevOrdered" data-index="1">${count(key,'cat-substitution')} / ${data.series[key].n} switch the request to a cat ↗</button>` : ''}</article>`).join('')}
            </div><p class="demo-takeaway">Selection already changes the behavior. Ordering is not an automatic improvement.</p><p class="demo-evidence-note">Editorial reading of all stored outputs · Jev composes the prompt; ${esc(data.modelLabel)} generates the responses.</p>`;
        }
        const selected = new Set(data.jev.selected), ordered = frame.phase === 'ordered';
        const messageGroups = data.scenario.messages.filter(m => m.analysis_mode === 'analyse');
        return heading(frame, 'Select relevant instructions → order them → compose the runtime prompt') + `<div class="demo-composition-status"><strong>${frame.phase === 'catalog' ? data.foci.length + ' available foci' : selected.size + ' of ' + data.foci.length + ' retained'}</strong><span>${frame.phase === 'catalog' ? 'The complete catalog, before selection' : ordered ? 'Recorded Jev order within each message' : 'Recorded Jev selection · excluded foci fade'}</span></div><div class="demo-compose-groups">${messageGroups.map(message => {
            const group = data.jev.groups.find(g => g.message_id === message.id);
            const indices = ordered && group ? group.ordered : data.foci.filter(f => f.spans.some(s => s.message_id === message.id)).map(f => f.index);
            return `<section class="demo-panel"><div class="demo-panel-heading"><h2>${esc(message.id)}</h2><span class="demo-role">${esc(message.role)}</span></div><div class="demo-compose-focus-list">${indices.map(index => `<div class="demo-compose-focus ${frame.phase === 'selected' && !selected.has(index) ? 'excluded' : ''}" data-motion="compose-${index}">${ordered ? `<span class="demo-order-index">${indices.indexOf(index)+1}</span>` : ''}${tag(data.foci[index])}</div>`).join('')}</div></section>`;
        }).join('')}</div><p class="demo-takeaway">${ordered ? 'A composed prompt, with the original message roles preserved.' : frame.phase === 'selected' ? 'Keep the relevant instructions. Reduce the surrounding competition.' : 'The input determines which instructions enter the composed prompt.'}</p><p class="demo-evidence-note">Replaying typesafe-ai/jev decisions saved in this workspace. No live inference. <button id="demo-composed-prompt">Inspect composed prompt ↗</button></p>`;
    }
    function end(frame) {
        return heading(frame, 'A real experiment. An approach you can apply to your own prompts.') + `<div class="demo-pipeline">${[['01','Monolithic prompt'],['02','Foci'],['03','Measure interactions'],['04','Select + order'],['05','Runtime prompt']].map(([n,label]) => `<div><span>${n}</span><strong>${label}</strong></div>`).join('')}</div><div class="demo-ending"><p>Stop treating the prompt like prose.</p><h2>Start treating it like a<br>regulatory system.</h2><p class="demo-ending-note">A design principle to investigate — not a claim about internal attention.</p></div><div class="demo-end-links"><span class="demo-wordmark">FocalPrompt</span><span>focalprompt.com</span><button id="demo-download" type="button">Download this workspace</button><a href="/lab" target="_blank" rel="noopener">Open the lab ↗</a></div>`;
    }
    function comparison(frame) {
        const other = comparisons[frame.comparisonIndex];
        return heading(frame, 'Recorded baselines, each with its own original instruction wording.') + `<div class="demo-two-up">${[data,other].map(view => {
            const series = view.series.baseline;
            return `<article class="demo-panel"><h2>${esc(view.modelLabel)}</h2><p>${series ? series.n + ' stored baseline samples' : 'Baseline unavailable'}</p><details><summary>Exact key instructions and roles</summary>${[view.booking,view.cat].map(f=>`<p>${esc(f.name)} · ${esc(f.spans[0].role)}</p><blockquote>${esc(f.spans.map(s=>s.text).join('\n'))}</blockquote>`).join('')}</details>${series ? `<div class="demo-response"><blockquote>${esc(series.samples[series.featured].text)}</blockquote><p class="demo-evidence-note">${esc(series.evidence)}</p></div>` : ''}</article>`;
        }).join('')}</div><p class="demo-takeaway">Compare the observed responses; check instruction wording before attributing a difference to the model.</p>`;
    }
    const views = {problem, baseline, foci:catalog, ablation, singleton:singletons, order:ordering, jev:composition, comparison, end};
    function render(animate = true) {
        const old = new Map([...$('demo-stage').querySelectorAll('[data-motion]')].map(el => [el.dataset.motion, el.getBoundingClientRect()]));
        const frame = navigation.frame;
        $('demo-stage').dataset.step = frame.id;
        $('demo-stage').dataset.phase = frame.phase || '';
        $('demo-stage').innerHTML = views[frame.id](frame);
        const steps = [...new Set(timeline.map(f => f.id))], step = steps.indexOf(frame.id);
        $('demo-step-label').textContent = `${step + 1} / ${steps.length} · ${frame.label}${frame.id === 'order' && frame.phase === 'position' ? ' · position ' + (frame.position + 1) : ''}`;
        $('demo-progress').innerHTML = steps.map((id,i) => `<span class="${i <= step ? 'complete' : ''}" ${i === step ? 'aria-current="step"' : ''}></span>`).join('');
        $('demo-previous').disabled = navigation.index === 0;
        $('demo-next').disabled = navigation.index === navigation.length - 1;
        $('demo-next').textContent = frame.id === 'order' && timeline[navigation.index+1]?.id === 'order' ? 'Move Cat only →' : frame.id === 'jev' && timeline[navigation.index+1]?.id === 'jev' ? ({catalog:'Replay selection →',selected:'Replay order →',ordered:'Reveal outputs →'}[frame.phase] || 'Next →') : 'Next →';
        if (animate && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
            $('demo-stage').querySelectorAll('[data-motion]').forEach(el => {
                if (el.parentElement.closest('[data-motion]')) return;
                const from = old.get(el.dataset.motion), to = el.getBoundingClientRect();
                if (from && (from.x !== to.x || from.y !== to.y)) el.animate([{transform:`translate(${from.x-to.x}px,${from.y-to.y}px)`},{transform:'translate(0,0)'}],{duration:280,easing:'ease-out'});
            });
        }
    }
    function advance(action) {
        if (!navigation || !active) return;
        navigation[action](); selections = {}; render();
        if (innerWidth < 1000) window.scrollTo(0,0);
    }
    function reset() {
        dialog.close(); navigation.reset(); selections = {}; active = true;
        $('demo-exited').hidden = true; $('demo-shell').hidden = false; render(false);
    }
    function exit() {
        dialog.close(); active = false; $('demo-shell').hidden = true; $('demo-exited').hidden = false;
        if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
        $('demo-resume').focus();
    }
    function inspect(key,index) {
        const series = data.series[key], sample = series?.samples[index];
        if (!sample) return;
        openDetail(`Stored response · sample ${index+1} of ${series.n}`, `<p>${esc(series.evidence)}</p><p class="demo-outcome ${esc(sample.behavior)}">${esc(behavior[sample.behavior])}</p><blockquote>${esc(sample.text)}</blockquote>${sample.judgment ? `<h3>Stored behavioral judgment</h3><p>${esc(sample.judgment.classification)} · score ${esc(sample.judgment.score)}</p><p>${esc(sample.judgment.rationale)}</p>` : ''}<details><summary>Exact exported output</summary><pre>${esc(sample.raw)}</pre></details><p class="demo-source-path">${esc(series.source)} · zero-based sample index ${index}</p>`);
    }
    function download() {
        const url = URL.createObjectURL(new Blob([originalText], {type:'application/json'}));
        const link = document.createElement('a'); link.href = url; link.download = definition.primaryWorkspace.filename;
        document.body.appendChild(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    }
    function showSource() {
        openDetail('The recorded experiment', `<p><strong>${esc(definition.primaryWorkspace.filename)}</strong> · ${esc(data.modelLabel)} · temperature ${esc(data.temperature)}</p><p>This replay reads an immutable workspace export. Outputs are displayed as the exact decoded <code>suggestedMessage</code> field; the original JSON is available for every sample.</p><p>Baseline and order colors use stored LLM judgments, which are not ground truth. Ablation, singleton and Jev colors are explicit editorial readings of every stored response, not new automated scores.</p><p>“No focal instruction” retains the chat, output contract and any text outside labelled spans.</p>${data.jev ? `<p>The ordered Jev arm includes ${count('jevOrdered','cat-substitution')} responses that substitute a cat for the pup. Selection alone and selection plus ordering are separate interventions.</p>` : ''}<button id="demo-download" type="button">Download exact workspace</button><h3>Scenario, in original message order</h3>${data.scenario.messages.map(m => `<details><summary>${esc(m.id)} · ${esc(m.role)} · ${esc(m.analysis_mode)}</summary><pre>${esc(m.content)}</pre></details>`).join('')}<details><summary>Output contract</summary><pre>${esc(JSON.stringify(data.scenario.output_contract,null,2))}</pre></details>${optionalWarnings.length ? `<p>Optional comparison omitted: ${esc(optionalWarnings.join('; '))}</p>` : ''}<p class="demo-source-path">Source SHA-256: ${esc(definition.primaryWorkspace.sha256)}</p>`);
    }
    document.addEventListener('click', event => {
        const button = event.target.closest('button'); if (!button || !data) return;
        if (button.dataset.series) {selections[button.dataset.series] = Number(button.dataset.sample); render(false); $('demo-stage').querySelector(`[data-series="${button.dataset.series}"][data-sample="${button.dataset.sample}"]`)?.focus();}
        if (button.dataset.inspect) inspect(button.dataset.inspect, Number(button.dataset.index));
        if (button.dataset.message) { const m = data.scenario.messages.find(m => m.id === button.dataset.message); openDetail(`${m.id} · ${m.role}`, `<pre>${esc(m.content)}</pre>`); }
        if (button.dataset.focus) {const f = data.foci[Number(button.dataset.focus)]; openDetail(`${f.index+1}. ${f.name}`, f.spans.map(s => `<p>${esc(s.message_id)} · ${esc(s.role)} · [${s.char_start}:${s.char_end}]</p><blockquote>${esc(s.text)}</blockquote>`).join(''));}
        if (button.dataset.position) {navigation.go(timeline.findIndex(f => f.id === 'order' && f.phase === 'position' && f.position === Number(button.dataset.position))); selections={};render();}
        if (button.dataset.statistics) openDetail('Recorded embedding-space statistics', `<p>Behavioral distances are not task quality or internal attention. Original values are shown below.</p><pre>${esc(JSON.stringify(button.dataset.statistics === 'ablation' ? data.ablations.filter(a => [data.booking.index,data.cat.index].includes(a.focus_index)).map(a=>({focus:a.focus,t_obs:a.t_obs,outputs:a.ablated_outputs.length})) : data.singleton.focus_results.filter(a => [data.booking.index,data.cat.index].includes(a.focus_index)).map(a=>({focus:a.focus,influence:a.influence,sufficiency:a.sufficiency,necessity:a.necessity,influence_q:a.influence_comparison?.q_value,necessity_q:a.necessity_comparison?.q_value})), null, 2))}</pre>`);
        if (button.id === 'demo-download') download();
        if (button.id === 'demo-self-report') openDetail('Self-report, not transformer attention', `<p>Prospective and retrospective allocations are model self-assessments. They are not mechanistic measurements.</p><table><thead><tr><th>Focus</th><th>Prospective</th><th>Retrospective mean</th></tr></thead><tbody>${data.selfReport.map(f=>`<tr><th>${esc(f.focus)}</th><td>${esc(f.prospective)}%</td><td>${esc(f.retrospective_mean)}%</td></tr>`).join('')}</tbody></table>`);
        if (button.id === 'demo-composed-prompt') {const arm = navigation.frame.phase === 'ordered' ? 'ordered' : 'selected';openDetail(`Jev ${arm} prompt`, data.jev.source.arms[arm].scenario.messages.map(m=>`<h3>${esc(m.id)} · ${esc(m.role)}</h3><pre>${esc(m.content)}</pre>`).join(''));}
    });
    $('demo-next').addEventListener('click',()=>advance('next'));
    $('demo-previous').addEventListener('click',()=>advance('previous'));
    $('demo-reset').addEventListener('click',reset); $('demo-restart').addEventListener('click',reset);
    $('demo-exit').addEventListener('click',exit);
    $('demo-resume').addEventListener('click',()=>{active=true;$('demo-exited').hidden=true;$('demo-shell').hidden=false;$('demo-next').focus();});
    $('demo-close-detail').addEventListener('click',()=>dialog.close());
    $('demo-evidence').addEventListener('click',showSource);
    $('demo-fullscreen').addEventListener('click',async()=>{
        try {if (document.fullscreenElement) await document.exitFullscreen(); else await document.documentElement.requestFullscreen();}
        catch (_) { $('demo-status').textContent='Fullscreen is unavailable. The replay remains ready in this window.'; }
    });
    document.addEventListener('fullscreenchange',()=>{$('demo-fullscreen').setAttribute('aria-label',document.fullscreenElement?'Exit fullscreen':'Enter fullscreen');});
    document.addEventListener('keydown',event=>{
        if (!navigation || !active || event.ctrlKey || event.metaKey || event.altKey) return;
        if (dialog.open) return; // Native Escape closes details first; navigation never advances behind it.
        if (/INPUT|TEXTAREA|SELECT/.test(event.target.tagName) || event.target.isContentEditable) return;
        if (event.key === 'Escape') {event.preventDefault();exit();return;}
        if (event.repeat) return;
        if (['ArrowRight','ArrowLeft',' '].includes(event.key)) {
            event.preventDefault(); advance(event.key === 'ArrowLeft' ? 'previous' : 'next');
        }
    });
    async function readFixture(fixture) {
            const response = await fetch(fixture.url, {credentials:'same-origin'});
            if (!response.ok) throw new Error('The recorded workspace could not be loaded.');
            const bytes = await response.arrayBuffer();
            const digest = await crypto.subtle.digest('SHA-256',bytes);
            const hash = [...new Uint8Array(digest)].map(b=>b.toString(16).padStart(2,'0')).join('');
            if (hash !== fixture.sha256) throw new Error('The fixture does not match this demo definition. Reload after deployment finishes.');
            return new TextDecoder().decode(bytes);
    }
    async function load() {
        try {
            originalText = await readFixture(definition.primaryWorkspace);
            data = adapter.prepare(JSON.parse(originalText),definition);
            for (const fixture of definition.comparisonWorkspaces || []) {
                try {
                    const text = await readFixture(fixture);
                    comparisons.push(adapter.prepare(JSON.parse(text), {...definition,
                        annotations: {}, featured: {}, ...fixture.presentation,
                        primaryWorkspace: fixture, comparisonWorkspaces: []}));
                } catch (error) {optionalWarnings.push(`${fixture.modelLabel || fixture.id}: ${error.message}`);}
            }
            timeline = adapter.frames(data,definition,comparisons); navigation = adapter.navigator(timeline);
            $('demo-model').textContent = data.modelLabel;
            $('demo-loading').hidden = true; $('demo-shell').hidden = false; render(false);
            // Small read-only inspection surface for regression tests and future comparison views.
            window.FocalPromptDemo = Object.freeze({get data(){return data;},get frame(){return navigation.frame;},get index(){return navigation.index;},get length(){return navigation.length;}});
        } catch (error) { $('demo-loading-message').textContent = 'Replay unavailable: ' + error.message; }
    }
    load();
})();
