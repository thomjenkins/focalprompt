/* Full / no-focus / singleton / leave-one-out graph, resumable and workspace-owned. */
(function (global) {
    'use strict';
    let state = null, busy = false, stopped = false;
    const el = id => document.getElementById(id);
    const clone = value => structuredClone(value);
    const same = (a, b) => global.FocalPromptWorkflow.matches(a, b);
    const esc = value => escapeHtml(String(value ?? ''));
    const num = value => value == null ? 'Unavailable'
        : value !== 0 && Math.abs(value) < 0.0001 ? Number(value).toExponential(2) : Number(value).toFixed(4);
    const status = text => { if (el('singleton-status')) el('singleton-status').textContent = text; };
    function context() {
        const cfg = global.FocalPromptExperiment.getState();
        const rejection = global.FocalPromptExperiment.temperatureRejection(cfg.temperature);
        if (rejection) throw new Error(rejection);
        if (!foci.length) throw new Error('Label the foci in step 1 first.');
        return clone({scenario: readMainScenario(), foci, model: getSectionModel('output'),
            temperature: cfg.temperature, n_baseline: cfg.n_baseline, n_ablated: cfg.n_ablated});
    }
    function current() {
        if (!state || !same(state.context, context())) throw new Error('Inputs or sampling settings changed. Start a new singleton analysis; saved results remain below.');
        return state;
    }
    function check(active) {
        if (state !== active) throw new Error('Workspace changed during this run.');
        current();
        if (stopped) throw new Error('Stopped. Completed samples are retained; resume to continue.');
    }
    function post(path, body, model) {
        return global.FocalPromptQuality.retryRequest(() => global.FocalPromptQuality.fetchJson(path, {
            method: 'POST', headers: getApiHeaders(), body: JSON.stringify(getApiBody(body, 'mut', model)),
        }), {onRetry: r => status(`Retry ${r.attempt}/${r.max_attempts}; completed samples are retained.`)});
    }
    const focusSignature = list => (list || []).map(f => ({focus: f.focus, id: f.id ?? null,
        spans: (f.spans || []).map(s => ({message_id: s.message_id, char_start: s.char_start,
            char_end: s.char_end, text_snapshot: s.text_snapshot ?? s.text}))}));

    function seedExisting(active) {
        const c = active.context, variants = active.plan.variants;
        function seed(id, entries, source) {
            const variant = variants.find(v => v.id === id);
            const pool = active.plan.pools.find(p => p.id === variant.pool_id);
            const saved = active.samples[pool.id];
            if (!Array.isArray(entries)) return;
            const prefix = entries.slice(0, pool.n_samples);
            prefix.forEach((s, i) => {
                if (!saved[i] && typeof s?.content === 'string' && s.content.trim()
                    && (!s.scenario || same(s.scenario, pool.scenario))) {
                    saved[i] = {...clone(s), scenario: clone(pool.scenario), reused_from: source, source_sample_index: i};
                }
            });
        }
        const previous = global.singleAblationResults;
        if (previous && same(previous.scenario, c.scenario)
            && previous.model === c.model.model && previous.provider === c.model.provider
            && Number(previous.temperature) === c.temperature
            && same(focusSignature(previous.foci_list), focusSignature(c.foci))) {
            if (previous.n_baseline === c.n_baseline) seed('full', previous.baseline_outputs?.map(content => ({content})), 'ablation.full');
            if (previous.n_ablated === c.n_ablated) {
                for (const row of previous.ablation_results || []) {
                    const i = row.focus_index;
                    const arm = variants.find(v => v.id === 'leave_one_out_' + i);
                    if (arm && same(row.ablated_scenario, arm.scenario)) {
                        seed(arm.id, row.ablated_outputs?.map(content => ({content})), 'ablation.leave_one_out_' + i);
                    }
                }
            }
        }
        const workflow = global.FocalPromptWorkflow.collect();
        const {n_ablated, ...baselineContext} = c;
        if (workflow && same(workflow.context, baselineContext)) seed('full', workflow.samples, 'baseline_workflow');
    }

    async function prepare() {
        if (state) return current();
        const c = context();
        status('Preparing exact prompt variants and checking reusable samples…');
        const plan = await post('/api/singleton-plan', {...c, model: undefined}, c.model);
        if (!same(c, context())) throw new Error('Inputs changed while preparing the experiment.');
        state = {protocol: 'singleton-focus-v1', created_at: new Date().toISOString(), context: c,
            plan, samples: Object.fromEntries(plan.pools.map(p => [p.id, []])), result: null};
        seedExisting(state);
        // Interleave the unique conditions by sampling round. Save the schedule so
        // retries resume the same execution graph rather than choosing a new order.
        state.schedule = [];
        for (let i = 0; i < Math.max(...plan.pools.map(p => p.n_samples)); i++) {
            const round = plan.pools.filter(p => i < p.n_samples);
            for (let j = round.length - 1; j > 0; j--) {
                const k = Math.floor(Math.random() * (j + 1)); [round[j], round[k]] = [round[k], round[j]];
            }
            state.schedule.push(...round.map(p => ({pool_id: p.id, slot: i})));
        }
        return state;
    }
    async function runAnalysis() {
        const active = await prepare(), c = active.context;
        if (active.result) { status('This run is complete. Start a new run for new samples.'); return; }
        check(active);
        const jobs = active.schedule.filter(j => !active.samples[j.pool_id][j.slot]);
        let next = 0, failure = null;
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 600000);
        async function worker() {
            while (!failure && next < jobs.length) {
                const job = jobs[next++], pool = active.plan.pools.find(p => p.id === job.pool_id);
                try {
                    check(active);
                    const sample = await fetchAblationSample(
                        c.scenario, c.foci, pool.kind, pool.focus_index, c.temperature, controller, null, c.model, {
                            onAttempt: () => check(active),
                            onRetry: r => status(`Temporary sampling failure. Retrying this sample (${r.attempt}/${r.max_attempts}); completed samples are retained.`),
                        });
                    // Keep completed work even when Stop was clicked mid-request.
                    if (state !== active) throw new Error('Workspace changed during sampling.');
                    if (typeof sample.content !== 'string' || !sample.content.trim() || !same(sample.scenario, pool.scenario)) {
                        throw new Error('The returned output does not match its planned scenario.');
                    }
                    active.samples[pool.id][job.slot] = {...sample, received_at: new Date().toISOString()};
                    status(`${Object.values(active.samples).flat().filter(Boolean).length}/${active.plan.planned_calls} unique samples available (including reused samples).`);
                    check(active);
                } catch (error) { failure = error; }
            }
        }
        try { await Promise.allSettled(Array.from({length: Math.min(6, jobs.length)}, worker)); }
        finally { clearTimeout(timeout); }
        if (failure) throw failure;
        check(active);
        status('Comparing influence, sufficiency and necessity with the existing embedding evaluator…');
        const result = await post('/api/singleton-score', {...c, model: undefined, samples: active.samples}, c.model);
        check(active);
        active.result = result;
        status('Analysis complete. Export workspace preserves prompts, samples, provenance and results.');
    }
    function outputDetails(title, arm) {
        return `<details><summary>${esc(title)} · ${arm.outputs.length} outputs</summary>
            <details><summary>Scenario messages</summary><p>Blank messages are omitted from model requests; all nonblank content is sent unchanged.</p>
            <pre style="white-space:pre-wrap">${esc(JSON.stringify(arm.scenario, null, 2))}</pre></details>`
            + arm.outputs.map((text, i) => `<details><summary>Output ${i + 1}</summary><pre style="white-space:pre-wrap;overflow-wrap:anywhere">${esc(text)}</pre></details>`).join('') + '</details>';
    }
    function render() {
        if (!el('singleton-results')) return;
        let valid = true;
        try { if (state) current(); } catch (_) { valid = false; }
        el('singleton-run-btn').disabled = busy || !valid || !!state?.result;
        el('singleton-run-btn').textContent = state?.result ? 'Analysis complete' : state ? 'Resume analysis' : 'Run analysis';
        el('singleton-stop-btn').hidden = !busy;
        el('singleton-new-btn').hidden = !state;
        el('singleton-new-btn').disabled = busy;
        el('singleton-export-btn').disabled = !state?.result;
        for (const id of ['singleton-n-baseline', 'singleton-n-ablated', 'singleton-temperature']) {
            if (el(id)) el(id).disabled = busy;
        }
        try {
            const c = context();
            el('singleton-settings').textContent = `Model: ${c.model.provider}/${c.model.model}. Sample counts and temperature are shared with steps 3 and 5. Changing settings requires a new run; saved samples retain their original settings.`;
        } catch (error) { el('singleton-settings').textContent = error.message; }
        if (!state) { el('singleton-results').innerHTML = ''; return; }
        let html = valid ? '' : '<p class="info-text"><strong>Saved run uses different inputs.</strong> Start a new run to analyse the current scenario.</p>';
        const count = Object.values(state.samples).flat().filter(Boolean).length;
        html += `<p>${count}/${state.plan.planned_calls} unique samples available across ${state.plan.variants.length} conditions (${state.plan.pools.length} distinct prompts). Identical prompt conditions share sample pools.</p>`;
        const omitted = [...new Set(state.plan.variants.flatMap(v => v.omitted_blank_message_ids || []))];
        if (omitted.length) html += `<p class="info-text">Blank messages omitted from model requests where empty: ${omitted.map(esc).join(', ')}. The saved scenario is unchanged.</p>`;
        const r = state.result;
        if (!r) { el('singleton-results').innerHTML = html + '<p>Completed samples are saved in workspace exports. Resume to finish missing samples and scoring.</p>'; return; }
        html += `<p><strong>Full vs no-focus distance:</strong> ${num(r.full_no_focus_distance)} · <strong>Low behavioral contrast:</strong> ${r.low_behavioral_contrast ? 'Yes' : 'No'} · threshold ${num(r.contrast_threshold)}.</p>`;
        if (r.low_behavioral_contrast) html += `<p class="info-text" role="status">${esc(r.normalized_metrics_note)}</p>`;
        html += '<p>Influence adds one focus to the no-focus prompt. Sufficiency measures progress toward full-prompt behavior; it can be negative. Necessity removes one focus from the full prompt. Ratios are not focus-budget percentages.</p>';
        html += '<div class="workflow-table-wrap"><table class="workflow-table"><thead><tr><th>Focus</th><th>Influence<br>singleton ↔ no-focus</th><th>Normalized influence<br>ratio</th><th>Sufficiency</th><th>Singleton ↔ full<br>distance</th><th>Necessity<br>leave-one-out ↔ full</th></tr></thead><tbody>'
            + r.focus_results.map(f => `<tr><th>${f.focus_index + 1}. ${esc(f.focus)}</th><td>${num(f.influence)}<br>q ${num(f.influence_comparison.q_value)}</td><td>${num(f.normalized_influence)}</td><td>${num(f.sufficiency)}</td><td>${num(f.singleton_full_distance)}</td><td>${num(f.necessity)}<br>q ${num(f.necessity_comparison.q_value)}</td></tr>`).join('') + '</tbody></table></div>';
        html += '<p class="info-text">Influence and necessity use separate permutation/BH test families. Sufficiency is descriptive. High sufficiency with low necessity can suggest redundancy; low sufficiency with strong necessity can suggest context dependence. These runs do not uniquely identify interaction effects.</p>';
        for (const f of r.focus_results) {
            html += `<details><summary>${f.focus_index + 1}. ${esc(f.focus)} — inspect all four conditions</summary>`;
            if (f.shared_text_retained_for_excluded.length) html += '<p class="info-text">Some excluded foci share text with this focus; their shared text remains in the singleton. Leave-one-out retains the existing behavior of deleting all target spans.</p>';
            html += outputDetails('No-focus', r.arms.no_focus) + outputDetails('Singleton', r.arms['singleton_' + f.focus_index])
                + outputDetails('Full prompt', r.arms.full) + outputDetails('Leave-one-out', r.arms['leave_one_out_' + f.focus_index]) + '</details>';
        }
        html += `<details><summary>Method, normalization and execution details</summary><p>${r.notes.map(esc).join('</p><p>')}</p><p>Contrast rule: ${esc(r.contrast_threshold_method)}</p><p>${r.reused_samples} existing samples reused; ${r.new_samples} new received samples. Failed requests may have incurred usage.</p><pre style="white-space:pre-wrap">${esc(JSON.stringify({evaluator:r.evaluator,full_no_focus_comparison:r.full_no_focus_comparison},null,2))}</pre></details>`;
        el('singleton-results').innerHTML = html;
    }
    async function run() {
        if (busy) return;
        busy = true; stopped = false; render();
        try { await runAnalysis(); }
        catch (error) { status(error.message + ' Completed work is retained.'); }
        finally { busy = false; render(); }
    }
    global.FocalPromptSingleton = {
        collect: () => state ? clone(state) : null,
        restore: data => { state = data ? clone(data) : null; status(state ? 'Restored saved singleton analysis.' : ''); render(); },
        restoreResult: result => {
            const c = result.context;
            global.restoreWorkspaceSession({focalprompt_workspace:true,version:2,active_tab:'prompt-analysis',
                model_settings:{global:c.model,sections:{output:c.model,ablation:c.model}},
                prompt_analysis:{scenario:c.scenario,foci:c.foci,output:'',ablation_config:c}});
            state = {protocol:result.protocol, context:context(),plan:clone(result.plan),samples:clone(result.samples),result:clone(result)};
            render();
        },
        prepare, runAnalysis, render, context,
    };
    el('singleton-run-btn')?.addEventListener('click', run);
    el('singleton-stop-btn')?.addEventListener('click', () => { stopped = true; status('Stopping after in-flight samples finish…'); });
    el('singleton-new-btn')?.addEventListener('click', () => {
        if (!busy && confirm('Start a new singleton analysis? Export workspace first to keep the current run.')) {
            state = null; status('Ready for a new run.'); render();
        }
    });
    el('singleton-export-btn')?.addEventListener('click', () => {
        if (state?.result) global.FocalPromptWorkspaceTransfer.download(state.result, 'focalprompt-singleton-analysis.json');
    });
    el('singleton-checkpoint-btn')?.addEventListener('click', () => displayCheckpointList('singleton_analysis').catch(e => status(e.message)));
    document.addEventListener('change', () => { if (!busy) render(); });
    document.addEventListener('input', () => { if (!busy && state) render(); });
    render();
})(window);
