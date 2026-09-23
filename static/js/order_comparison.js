/* A native, read-only comparator for any pair of saved global order permutations. */
(function (global) {
    'use strict';
    const samples = global.FocalPromptSamples || (typeof require === 'function' ? require('./recorded_samples.js') : null);
    const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const states = new WeakMap();
    function findPermutationByOrder(permutations, names) {
        const matches = (permutations || []).filter(p => JSON.stringify(p.ordered_focus_names) === JSON.stringify(names));
        if (matches.length !== 1) throw new Error(`Expected one recorded global permutation: ${names.join(' → ')}. Found ${matches.length}.`);
        const match = matches[0];
        if (names.some((name, i) => match.focus_positions?.[name] !== i)) throw new Error('Recorded global permutation has inconsistent focus positions.');
        return match;
    }
    function counts(permutation) {
        const outputs = permutation.outputs || [];
        const judgments = outputs.map((_, i) => permutation.behavioral_judgments?.find(j => j.sample_index === i));
        return {n: outputs.length, judged: judgments.filter(Boolean).length, complies: judgments.filter(j => j?.classification === 'COMPLIES').length};
    }
    function summary(permutation) {
        const count = counts(permutation);
        if (!count.judged) return `${count.n} outputs · not judged`;
        return `${count.complies} / ${count.n} comply${count.judged < count.n ? ` · ${count.judged} judged` : ''}`;
    }
    function behaviorSummary(permutation, config) {
        const {phrase, label} = config.behavior || {};
        if (!phrase || !label) return null;
        const outputs = permutation.outputs || [];
        const matches = outputs.filter(raw => samples.text(raw).includes(phrase)).length;
        return `${matches} / ${outputs.length} ${label}`;
    }
    function judgeSummary(permutation) {
        const count=counts(permutation);
        return `Recorded LLM judge: ${count.complies} / ${count.n} compliant`;
    }
    function payload(result) {
        return {model: result.model, provider: result.provider, temperature: result.temperature,
            role: result.scenario_metadata?.ordering_role, criterion: result.behavioral_criterion,
            permutations: (result.global_order_experiment?.permutations || []).filter(p => p.ordered_focus_names?.length && p.outputs?.length)};
    }
    function options(data, selected) {
        return data.permutations.map((p, i) => `<option value="${i}" ${i === selected ? 'selected' : ''}>Shuffle #${esc(p.permutation_id)} · ${esc(p.ordered_focus_names.join(' → '))}</option>`).join('');
    }
    function outputGroups(pair, config = {}) {
        return pair.map((p, i) => `<section class="order-condition-outputs" data-order-outputs="${i}" ${i ? 'hidden' : ''} aria-label="Condition ${i ? 'B' : 'A'} outputs">
            ${config.observations?.[i] ? `<p class="order-observation">${esc(config.observations[i])} <small>Reading of these stored outputs</small></p>` : ''}
            ${config.selectedSamples
                ? samples.render(p.outputs, {id:'order-condition-'+i, title:'Recorded outputs', selected:config.selectedSamples[i],
                    judgments:p.behavioral_judgments, highlights:config.highlights?.[i], judgmentDetails:true})
                : samples.renderAll(p.outputs, {judgments: p.behavioral_judgments, highlights: config.highlights?.[i]})}</section>`).join('');
    }
    function render(result) {
        const data = payload(result);
        if (data.permutations.length < 2) return '';
        const pair = data.permutations.slice(0, 2), names = pair[0].ordered_focus_names;
        const anchor = names.find(name => pair[1].focus_positions?.[name] === pair[0].focus_positions?.[name]) || names[0];
        // Only a compact detached view payload; script text cannot terminate its own element.
        const json = JSON.stringify(data).replace(/</g, '\\u003c');
        const html = `<div class="order-comparison" data-order-anchor="${esc(anchor)}">
            <script type="application/json" class="order-comparison-data">${json}</script>
            <div class="order-comparison-heading"><h3>Compare recorded orders</h3><details class="order-comparison-settings"><summary>Compare other permutations</summary>
                <label>Condition A <select data-order-choose="0">${options(data,0)}</select></label><label>Condition B <select data-order-choose="1">${options(data,1)}</select></label>
                <label>Track focus <select data-order-anchor-select>${names.map(name=>`<option ${name === anchor ? 'selected' : ''}>${esc(name)}</option>`).join('')}</select></label></details></div>
            <p class="order-recording-meta">${esc(data.provider ? data.provider + '/' : '')}${esc(data.model)} · ${esc(data.role || 'prompt')} · temperature ${esc(data.temperature)}</p>
            <div class="order-condition-controls" aria-label="View recorded condition">${pair.map((p,i)=>`<button type="button" data-order-condition="${i}" aria-pressed="${i===0}"><span>Condition ${i ? 'B' : 'A'} · Shuffle #<b data-order-shuffle="${i}">${esc(p.permutation_id)}</b></span><strong data-order-count="${i}">${esc(summary(p))}</strong><small data-order-neighbor="${i}"></small><small data-order-judge="${i}" hidden></small></button>`).join('')}</div>
            <div class="order-comparison-body"><div class="order-context"><p class="order-anchor-position"></p>
                <ol class="order-moving-foci" style="--order-length:${names.length}">${names.map((name, i)=>`<li data-order-focus-card="${esc(name)}" data-pinned="${name === anchor}" style="--order-slot:${i}"><span class="order-slot-number">${i+1}</span><strong>${esc(name)}</strong></li>`).join('')}</ol>
                <p class="order-anchor-text"></p><details class="order-focus-texts"><summary>Inspect focus text</summary><div></div></details></div>
                <div class="order-comparison-outputs">${outputGroups(pair)}</div></div>
            <details class="order-comparison-method"><summary>Behavioral criterion &amp; evidence</summary><p>${esc(data.criterion || 'No behavioral criterion was recorded.')}</p><p data-order-count-method>Counts use stored COMPLIES judgments, not ground truth. They describe these sampled outputs, not estimated success rates. Ordering comparisons do not identify a mechanism.</p></details>
            <p class="order-comparison-status sr-only" aria-live="polite"></p>
        </div>`;
        if (!global.document) return html;
        const holder=global.document.createElement('div');holder.innerHTML=html;
        show(holder.firstElementChild,0);
        return holder.innerHTML;
    }
    function state(root) {
        if (!states.has(root)) {
            const data = JSON.parse(root.querySelector('.order-comparison-data').textContent);
            states.set(root,{data, pair:data.permutations.slice(0,2), anchor:root.dataset.orderAnchor, active:0, config:{}});
        }
        return states.get(root);
    }
    function show(root, active) {
        const s = state(root), permutation = s.pair[active];
        s.active = active;
        const positions = s.pair.map(p => p.ordered_focus_names.indexOf(s.anchor));
        const fixed = positions[0] >= 0 && positions[0] === positions[1];
        root.dataset.orderActive = String(active);
        root.dataset.orderFixed = String(fixed);
        root.querySelectorAll('[data-order-condition]').forEach((button,i)=>button.setAttribute('aria-pressed',String(i===active)));
        root.querySelectorAll('[data-order-outputs]').forEach(el=>{el.hidden=Number(el.dataset.orderOutputs)!==active;});
        // Keep the same physical nodes: a shared slot produces exactly the same transform.
        root.querySelectorAll('[data-order-focus-card]').forEach(card=>{
            const slot = permutation.ordered_focus_names.indexOf(card.dataset.orderFocusCard);
            card.style.setProperty('--order-slot',slot);
            card.dataset.pinned = String(card.dataset.orderFocusCard === s.anchor);
            card.querySelector('.order-slot-number').textContent=slot+1;
            card.setAttribute('aria-posinset',slot+1);
            card.setAttribute('aria-setsize',permutation.ordered_focus_names.length);
        });
        root.querySelector('.order-moving-foci').setAttribute('aria-label',permutation.ordered_focus_names.join(' → '));
        root.querySelector('.order-anchor-position').textContent = `${s.anchor} · position ${positions[active]+1}${fixed ? ' in both' : ''}`;
        const observed=behaviorSummary(permutation,s.config);
        root.querySelector('.order-comparison-status').textContent=`Condition ${active ? 'B' : 'A'}. ${permutation.ordered_focus_names.join(', ')}. ${observed ? observed+'. '+judgeSummary(permutation) : summary(permutation)}.`;
        root.querySelector('[data-order-count-method]').textContent=observed
            ? `Acknowledgement counts show how many outputs contain “${s.config.behavior.phrase}”. Compliance is the recorded LLM judge’s separate assessment of the refusal criterion above. These judgments are not ground truth.`
            : 'Counts use stored COMPLIES judgments, not ground truth. They describe these sampled outputs, not estimated success rates. Ordering comparisons do not identify a mechanism.';
        s.pair.forEach((p,i)=>{
            const behavior=behaviorSummary(p,s.config);
            root.querySelector(`[data-order-count="${i}"]`).textContent=behavior || summary(p);
            const judge=root.querySelector(`[data-order-judge="${i}"]`);
            judge.hidden=!behavior;
            judge.textContent=behavior ? judgeSummary(p) : '';
            root.querySelector(`[data-order-shuffle="${i}"]`).textContent=p.permutation_id;
            const slot = p.ordered_focus_names.indexOf(s.anchor);
            root.querySelector(`[data-order-neighbor="${i}"]`).textContent=slot > 0 ? `${s.anchor} after ${p.ordered_focus_names[slot-1]}` : `${s.anchor} first`;
        });
        if (s.config.selectedSamples) samples.select(root.querySelector(`[data-order-outputs="${active}"] .recorded-samples`),s.config.selectedSamples[active]);
        const template=permutation.reconstruction?.template;
        const textFor=name=>template?.focus_texts?.[String(permutation.assignment?.[permutation.ordered_focus_names.indexOf(name)])] || '';
        root.querySelector('.order-anchor-text').textContent=textFor(s.anchor);
        root.querySelector('.order-focus-texts>div').innerHTML=permutation.ordered_focus_names.map(name=>`<h4>${esc(name)}</h4><p>${esc(textFor(name))}</p>`).join('');
    }
    function configure(root, config, active) {
        if (!root) throw new Error('The recorded order comparison is unavailable.');
        const s=state(root), pair=config.orders.map(names=>findPermutationByOrder(s.data.permutations,names));
        if (pair.length !== 2 || pair[0] === pair[1]) throw new Error('Choose two distinct recorded global permutations.');
        if (pair.some(p=>!p.ordered_focus_names.includes(config.anchor))) throw new Error('The tracked focus is missing from a recorded order.');
        const signature=JSON.stringify(config);
        if(s.signature !== signature) {
            s.pair=pair;s.anchor=config.anchor;s.config=config;s.signature=signature;
            root.querySelector('.order-comparison-outputs').innerHTML=outputGroups(pair,config);
            root.querySelectorAll('[data-order-choose]').forEach((el,i)=>{el.value=s.data.permutations.indexOf(pair[i]);});
            root.querySelector('[data-order-anchor-select]').value=s.anchor;
        }
        show(root,active ?? s.active);
    }
    global.document?.addEventListener('click',event=>{
        const button=event.target.closest('[data-order-condition]');
        if(button) show(button.closest('.order-comparison'),Number(button.dataset.orderCondition));
    });
    global.document?.addEventListener('change',event=>{
        if(!event.target.matches('[data-order-choose],[data-order-anchor-select]'))return;
        const root=event.target.closest('.order-comparison'),s=state(root);
        const pair=[...root.querySelectorAll('[data-order-choose]')].map(select=>s.data.permutations[Number(select.value)]);
        // Exploring other conditions uses no fixture-specific interpretations or highlights.
        s.pair=pair;s.anchor=root.querySelector('[data-order-anchor-select]').value;s.config={};s.signature=null;
        root.querySelector('.order-comparison-outputs').innerHTML=outputGroups(pair);
        show(root,s.active);
    });
    const api={findPermutationByOrder,counts,render,configure,show};
    global.FocalPromptOrderComparison=api;
    if(typeof module !== 'undefined' && module.exports)module.exports=api;
})(typeof window !== 'undefined' ? window : globalThis);
