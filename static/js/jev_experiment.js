/* Jev decisions, prompt composition and comparison samples live in an isolated snapshot. */
(function (global) {
    'use strict';
    let state = null, busy = false, stopped = false;
    const el = id => document.getElementById(id);
    const esc = value => escapeHtml(String(value ?? ''));
    const clone = value => structuredClone(value);
    const same = (a, b) => global.FocalPromptWorkflow.matches(a, b);
    const titles = {full: 'Full prompt', selected: 'Jev selection · source order', ordered: 'Jev selection · Jev order'};

    function controls() {
        return {threshold: Number(el('jev-threshold').value), count: Number(el('jev-count').value),
            temperature: Number(el('jev-temperature').value), order: el('jev-order').checked};
    }
    function context() {
        const c = controls();
        if (!Number.isFinite(c.threshold) || c.threshold < 0 || c.threshold > 1) throw new Error('Choose an inclusion threshold from 0 to 1.');
        if (!Number.isInteger(c.count) || c.count < 1 || c.count > 50) throw new Error('Choose 1–50 outputs per arm.');
        if (!Number.isFinite(c.temperature) || c.temperature < 0 || c.temperature > 2) throw new Error('Choose a generation temperature from 0 to 2.');
        if (!foci.length) throw new Error('Label the prompt foci in step 1 first.');
        const model = getSectionModel('jev-output');
        if (model.provider === 'typesafe-ai' || model.model === 'typesafe-ai/jev') throw new Error('Choose a chat model to generate outputs. Jev handles the selection decisions automatically.');
        return clone({...c, scenario: readMainScenario(), foci, model});
    }
    function current() {
        if (!state || state.protocol !== 'jev-focus-v1') throw new Error('Select foci to start a Jev experiment.');
        if (!same(state.context, context())) throw new Error('Inputs or settings changed. Start a new Jev experiment; the saved results below use the previous inputs.');
        return state;
    }
    function status(message) { if (el('jev-status')) el('jev-status').textContent = message; }
    async function post(path, body, model) {
        return global.FocalPromptQuality.retryRequest(() => global.FocalPromptQuality.fetchJson(path, {
            method: 'POST', headers: getApiHeaders(), body: JSON.stringify(getApiBody(body, 'mut', model)),
        }), {onRetry: r => status(`Connection or service failure. Retry ${r.attempt}/${r.max_attempts}; completed work is retained.`)});
    }
    function check() {
        current();
        if (stopped) throw new Error('Stopped. Completed decisions and outputs are retained; resume to continue.');
    }
    async function preview() {
        const c = context();
        if (!state) state = {protocol: 'jev-focus-v1', created_at: new Date().toISOString(), context: c,
            selection: null, orders: {}, order_decisions: [], arms: null};
        current();
        if (!state.selection) {
            status('Jev is assessing inclusion of each focus…');
            const result = await post('/api/jev-focus/select', {scenario: c.scenario, foci: c.foci, threshold: c.threshold}, c.model);
            current();
            state.selection = result;
            render();
        }
        check();
        if (c.order) {
            for (const group of state.selection.order_groups) {
                const prefix = state.orders[group.message_id] ||= [];
                while (prefix.length < group.focus_indices.length) {
                    check();
                    const remaining = group.focus_indices.filter(i => !prefix.includes(i));
                    if (remaining.length === 1) { prefix.push(remaining[0]); break; }
                    status(`Jev is ordering ${group.message_id}: position ${prefix.length + 1}/${group.focus_indices.length}…`);
                    const decision = await post('/api/jev-focus/order-next', {scenario: c.scenario, foci: c.foci,
                        selected_indices: state.selection.selected_indices, message_id: group.message_id, prefix: [...prefix]}, c.model);
                    current();
                    if (!remaining.includes(decision.focus_index)) throw new Error('Invalid ordering choice returned.');
                    state.order_decisions.push(decision);
                    prefix.push(decision.focus_index);
                    render();
                }
            }
        }
        check();
        const body = {scenario: c.scenario, foci: c.foci, selected_indices: state.selection.selected_indices};
        state.selected_preview = await post('/api/jev-focus/compose', body, c.model);
        check();
        if (c.order) state.ordered_preview = await post('/api/jev-focus/compose', {...body, orders: state.orders}, c.model);
        check();
        if (!state.arms) {
            state.arms = {full: {scenario: clone(c.scenario), samples: []},
                selected: {scenario: state.selected_preview.scenario, samples: []}};
            if (c.order) state.arms.ordered = {scenario: state.ordered_preview.scenario, samples: []};
            // Randomize arm order per round and save it, reducing temporal/provider drift confounding.
            state.schedule = [];
            for (let i = 0; i < c.count; i++) {
                const arms = Object.keys(state.arms);
                for (let j = arms.length - 1; j > 0; j--) {
                    const k = Math.floor(Math.random() * (j + 1)); [arms[j], arms[k]] = [arms[k], arms[j]];
                }
                state.schedule.push(...arms.map(arm => ({arm, index: i})));
            }
        }
        status('Prompts are ready to inspect. Generate comparison runs all arms with matching settings.');
    }
    async function generate() {
        const s = current(), c = s.context;
        if (!s.arms) throw new Error('Finish selection and prompt preview first.');
        for (const item of s.schedule) {
            check();
            const arm = s.arms[item.arm];
            if (arm.samples[item.index]) continue;
            status(`${titles[item.arm]}: generating output ${item.index + 1}/${c.count}…`);
            const sample = await post('/api/generate-agent-response', {scenario: arm.scenario, temperature: c.temperature}, c.model);
            current();
            if (typeof sample.output !== 'string' || !sample.output.trim()) throw new Error('An empty output was returned; retry to complete this sample.');
            arm.samples[item.index] = {output: sample.output, scenario_metadata: sample.scenario_metadata,
                parsed_output: sample.parsed_output, received_at: new Date().toISOString()};
            render();
        }
        state.completed_at = new Date().toISOString();
        status('Comparison complete. Inspect outputs by arm below. Export workspace includes prompts, decisions and all outputs.');
    }
    async function analysisWorkspace(id) {
        // Use the saved arm even if the main editor has since changed.
        const saved = clone(state), arm = saved?.arms?.[id];
        if (!arm || !['selected', 'ordered'].includes(id)) throw new Error('Finish the Jev prompt preview first.');
        const c = saved.context;
        const original = global.collectWorkspaceSession();
        const composed = await post('/api/jev-focus/compose', {scenario: c.scenario, foci: c.foci,
            selected_indices: saved.selection.selected_indices, orders: id === 'ordered' ? saved.orders : undefined}, c.model);
        if (!same(composed.scenario, arm.scenario)) throw new Error('The composed prompt differs from this saved arm. Start a new Jev preview before analysing it.');
        if (!Array.isArray(composed.foci)) throw new Error('Could not prepare focus spans for this prompt. Please refresh and try again.');
        const settings = clone(original.model_settings);
        settings.sections = {...settings.sections, output: c.model, ablation: c.model, reported: c.model, 'jev-output': c.model};
        const quality = original.prompt_analysis.quality_eval;
        const config = {...original.prompt_analysis.ablation_config, n_baseline: Math.max(5, c.count),
            temperature: c.temperature > 0 ? c.temperature : 0.7};
        const notes = [];
        if (c.count < 5) notes.push('Baseline count set to 5, the minimum for ablation.');
        if (c.temperature === 0) notes.push('Generation temperature set to 0.7 because ablation requires stochastic outputs.');
        if (!composed.foci.length) notes.push('Jev selected no foci. Label any remaining instructions in step 1 before analysing them.');
        return {
            focalprompt_workspace: true, version: 2, exported_at: new Date().toISOString(), active_tab: 'prompt-analysis',
            model_settings: settings,
            prompt_analysis: {scenario: composed.scenario, foci: composed.foci, output: '', ablation_config: config,
                analysis_origin: {type: 'jev', arm: id, title: titles[id], created_at: new Date().toISOString(),
                    source_created_at: saved.created_at, threshold: c.threshold, orders: composed.orders,
                    source_focus_indices: composed.foci.map(f => f.source_focus_index), notes},
                quality_eval: {criteria: quality?.criteria || '', sample_pct: quality?.sample_pct || '100',
                    second_judge_enabled: quality?.second_judge_enabled === true}},
            batch_analysis: {foci: [], pairs: [], prompt: ''}, agent_builder: {foci: [], chat_input: ''},
            optimization: {html: '', visible: false},
        };
    }
    function scenarioHtml(scenario) {
        return scenario.messages.map(m => `<h4>${esc(m.id)} · ${esc(m.role)} · ${esc(m.analysis_mode)}</h4><pre style="white-space:pre-wrap;overflow-wrap:anywhere">${esc(m.content)}</pre>`).join('')
            + (scenario.output_contract ? `<h4>Output contract (preserved)</h4><pre>${esc(JSON.stringify(scenario.output_contract, null, 2))}</pre>` : '');
    }
    function render() {
        if (!el('jev-results')) return;
        let valid = true;
        try { if (state) current(); } catch (_) { valid = false; }
        el('jev-select-btn').disabled = busy || !!state?.arms;
        el('jev-select-btn').textContent = state?.selection ? 'Resume selection & preview' : 'Select foci & preview';
        el('jev-generate-btn').disabled = busy || !state?.arms || !valid || !!state?.completed_at;
        el('jev-generate-btn').textContent = state?.arms ? 'Generate / resume comparison' : 'Generate comparison';
        el('jev-stop-btn').hidden = !busy;
        el('jev-new-btn').hidden = !state;
        el('jev-new-btn').disabled = busy;
        if (!state) { el('jev-results').innerHTML = '<p class="empty-state">Label foci in step 1, then select and preview here. Steps 2–7 are not required.</p>'; return; }
        const c = state.context;
        let html = `<p><strong>Saved experiment:</strong> ${esc(c.model.provider + '/' + c.model.model)} · ${c.count} outputs per arm · temperature ${c.temperature} · inclusion threshold ${c.threshold}</p>`;
        if (!valid) html += '<p class="info-text"><strong>Inputs changed.</strong> These results belong to the saved experiment. Start a new Jev experiment to use the current inputs.</p>';
        if (state.selection) {
            html += `<p><strong>${state.selection.selected_indices.length}/${c.foci.length} foci selected.</strong> These are inclusion probabilities, not focus shares. They do not sum to 100%.</p>`;
            const decisions = [state.selection, ...state.order_decisions];
            const costs = decisions.map(d => d.response?.providerMetadata?.gateway?.cost);
            if (costs.every(c => c !== undefined && c !== null && Number.isFinite(Number(c)))) {
                html += `<p class="info-text">Jev decisions: ${decisions.length} calls · Gateway-reported charge $${costs.reduce((sum, c) => sum + Number(c), 0).toFixed(6)}. Generation charges are separate.</p>`;
            }
            const shared = state.selected_preview?.shared_text_retained_for_excluded || [];
            html += '<div class="workflow-table-wrap"><table class="workflow-table"><thead><tr><th>Focus</th><th>Include probability</th><th>Decision</th></tr></thead><tbody>'
                + state.selection.decisions.map(d => `<tr><td>${d.focus_index + 1}. ${esc(d.focus)}</td><td>${(d.probability * 100).toFixed(1)}%</td><td>${d.included ? 'Include' : 'Exclude'}${shared.includes(d.focus_index) ? ' · shared text retained by another focus' : ''}</td></tr>`).join('') + '</tbody></table></div>';
            if (!state.selection.selected_indices.length) html += '<p>No foci were selected. The composed prompt still contains retained messages and unlabelled text.</p>';
            if (c.order) {
                const groups = state.selection.order_groups;
                html += '<p><strong>Ordering:</strong> Jev chooses the next focus from the remaining candidates, one position at a time. The final remaining focus fills the last slot.</p>';
                html += groups.map(g => `<p>${esc(g.message_id)}: ${esc((state.orders[g.message_id] || []).map(i => `${i + 1}. ${c.foci[i].focus}`).join(' → '))}</p>`).join('');
                const movable = new Set(groups.flatMap(g => g.focus_indices));
                const fixed = state.selection.selected_indices.filter(i => !movable.has(i));
                if (fixed.length) html += `<p class="info-text">Kept at source positions (overlap, multiple spans, or no movable peer): ${esc(fixed.map(i => c.foci[i].focus).join(', '))}.</p>`;
                if (!groups.length) html += '<p>No selected group can be reordered. The third arm uses the same prompt as the second.</p>';
            }
        }
        if (state.arms) {
            html += '<p class="info-text">Outputs are independently sampled in a saved, randomized arm order. Character counts measure prompt length, not token cost. Differences in wording or length do not establish better task quality.</p>';
            for (const [id, arm] of Object.entries(state.arms)) {
                const samples = arm.samples.filter(Boolean), chars = arm.scenario.messages.reduce((n, m) => n + m.content.length, 0);
                html += `<h3>${titles[id]} · ${samples.length}/${c.count} outputs · ${chars.toLocaleString()} prompt characters</h3>`;
                html += `<details><summary>Inspect exact prompt messages</summary>${scenarioHtml(arm.scenario)}</details>`;
                if (id !== 'full') {
                    html += `<div class="button-group" style="margin:12px 0"><button type="button" class="btn btn-primary" data-jev-analyse="${id}" ${busy ? 'disabled' : ''}>Analyse this prompt ↗</button>
                        <button type="button" class="btn btn-outline" data-jev-download="${id}" ${busy ? 'disabled' : ''}>Download analysis workspace</button></div>`;
                    html += '<p class="info-text">Opens a separate lab with this exact prompt and its selected foci. Start at step 2 with fresh predictions and outputs, then run ablation and quality evaluation. Your original analysis stays in this tab.</p>';
                }
                html += arm.samples.map((sample, i) => sample ? `<details><summary>Output ${i + 1}</summary><pre style="white-space:pre-wrap;overflow-wrap:anywhere">${esc(sample.output)}</pre></details>` : '').join('');
            }
        }
        html += `<details style="margin-top:16px"><summary>Method and Jev request / response audit</summary><p>The complete scenario and source spans are sent to Jev, with no new generated output. Selection probabilities use the displayed threshold. There is no Jev sampling temperature. Unlabelled text is kept; excluded overlapping text may survive where a selected focus needs it. This experiment measures the behavior of constructed prompts, not internal model attention. Jev probabilities require calibration on representative labelled examples.</p><pre style="white-space:pre-wrap;overflow-wrap:anywhere">${esc(JSON.stringify({protocol: state.protocol, selection: state.selection, order_decisions: state.order_decisions}, null, 2))}</pre></details>`;
        el('jev-results').innerHTML = html;
    }
    async function run(fn) {
        if (busy) return;
        busy = true; stopped = false; render();
        try { await fn(); }
        catch (error) { status(error.message + ' Completed work is retained.'); }
        finally { busy = false; render(); }
    }
    global.FocalPromptJev = {
        collect: () => clone({controls: controls(), state}),
        restore: data => {
            const c = data?.controls || {threshold: 0.5, count: 10, temperature: 0.7, order: false};
            for (const key of ['threshold', 'count', 'temperature']) el('jev-' + key).value = c[key];
            el('jev-order').checked = !!c.order;
            state = data?.state ? clone(data.state) : null;
            status(state ? 'Restored saved Jev experiment. Completed work is retained.' : ''); render();
        }, preview, generate, render, context, analysisWorkspace,
    };
    el('jev-select-btn')?.addEventListener('click', () => run(preview));
    el('jev-generate-btn')?.addEventListener('click', () => run(generate));
    el('jev-stop-btn')?.addEventListener('click', () => { stopped = true; status('Stopping after the current request finishes…'); });
    el('jev-new-btn')?.addEventListener('click', async () => {
        if (busy) return;
        if (confirm('Start a new Jev experiment? Export workspace first to keep a copy of these Jev results.')) {
            state = null; status('Ready for a new Jev experiment.'); render();
        }
    });
    el('jev-results')?.addEventListener('click', event => {
        const analyse = event.target.closest('[data-jev-analyse]');
        const download = event.target.closest('[data-jev-download]');
        if (busy || (!analyse && !download)) return;
        const id = (analyse || download).dataset[analyse ? 'jevAnalyse' : 'jevDownload'];
        // Open synchronously inside the click to preserve the browser's user gesture.
        const action = analyse
            ? global.FocalPromptWorkspaceTransfer.open(() => analysisWorkspace(id))
            : analysisWorkspace(id).then(data => global.FocalPromptWorkspaceTransfer.download(data, 'focalprompt-jev-' + id + '.json'));
        run(async () => {
            await action;
            status(analyse ? 'New analysis opened in a separate tab. The original experiment is preserved here.'
                : 'Analysis workspace downloaded. Import it into a separate lab tab to begin.');
        });
    });
    document.addEventListener('change', () => { if (!busy && state) render(); });
})(window);
