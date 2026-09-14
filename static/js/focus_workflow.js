/* Ordered focus workflow. The existing single-output and batch tools remain available. */
(function (global) {
    'use strict';
    let state = null;
    let busy = false;
    const assessmentProtocol = 'joint-budget-v3';
    const el = id => document.getElementById(id);
    const esc = value => escapeHtml(String(value == null ? '' : value));
    const number = (value, places = 1) => value == null ? '—' : Number(value).toFixed(places);
    const delta = value => value == null ? '—' : (value > 0 ? '+' : '') + number(value) + ' pp';

    function context() {
        const config = global.FocalPromptExperiment.getState();
        const error = global.FocalPromptExperiment.temperatureRejection(config.temperature);
        if (error) throw new Error(error);
        if (!foci.length) throw new Error('Label the prompt foci in step 1 first.');
        return structuredClone({scenario: readMainScenario(), foci,
            model: getSectionModel('output'), temperature: config.temperature, n_baseline: config.n_baseline});
    }

    function matches(left, right) {
        // Flask/export round-trips can reorder object keys; only values and array order matter.
        const canonical = value => JSON.stringify(value, (_key, item) => {
            if (!item || typeof item !== 'object' || Array.isArray(item)) return item;
            return Object.fromEntries(Object.keys(item).sort().map(key => [key, item[key]]));
        });
        return canonical(left) === canonical(right);
    }

    function requireCurrent() {
        if (!state?.prospective) throw new Error('Predict focus in step 2 first.');
        if (!matches(state.context, context())) {
            throw new Error('The scenario, foci, baseline model or sampling settings changed. Start a new prediction in step 2.');
        }
        return state;
    }

    function refreshValidity() {
        const status = el('focus-workflow-status');
        if (!status) return;
        try {
            if (!state) { status.textContent = ''; return; }
            requireCurrent();
            status.textContent = 'Current run: ' + state.context.model.provider + '/' + state.context.model.model
                + ' · ' + state.context.n_baseline + ' baseline outputs · generation temperature ' + state.context.temperature;
            if (state.prospective.assessment_protocol !== assessmentProtocol) {
                status.textContent += ' · Saved prediction uses an earlier assessment method. Predict again to start a new run.';
            }
        } catch (error) { status.textContent = error.message; }
    }

    function requireCurrentMethod(current) {
        if (current.prospective.assessment_protocol !== assessmentProtocol) {
            throw new Error('The assessment method has been updated. Start a new prediction in step 2 before continuing. Your saved results remain available.');
        }
    }

    async function post(path, payload, model) {
        const response = await fetch(path, {method: 'POST', headers: getApiHeaders(),
            body: JSON.stringify(getApiBody(payload, 'mut', model))});
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || 'Request failed.');
        return result;
    }

    async function run(message, fn) {
        if (busy) return;
        busy = true;
        showLoading(message);
        try { await fn(); }
        catch (error) { showErrorModal(error.message); }
        finally { busy = false; render(); hideLoading(); }
    }

    // Settle all workers before returning a failure; retain successful calls for retry.
    async function collectMissing(items, count, task, label) {
        let next = 0, failure = null;
        async function worker() {
            while (!failure && next < count) {
                const index = next++;
                if (items[index]) continue;
                try { items[index] = await task(index); }
                catch (error) { failure = error; }
                showLoading(label + ' (' + items.filter(Boolean).length + ' of ' + count + ')…');
            }
        }
        await Promise.allSettled(Array.from({length: Math.min(3, count)}, worker));
        if (failure) throw new Error(failure.message + ' Successful samples are saved; retry to finish this step.');
    }

    async function predict() {
        const initial = context();
        const prospective = await post('/api/focus-self-assessment', {
            scenario: initial.scenario, foci: initial.foci, phase: 'prospective',
        }, initial.model);
        if (!matches(initial, context())) throw new Error('Inputs changed while predicting. Please predict again.');
        state = {context: initial, prospective, samples: [], diagnostics: null, retrospective: [], summary: null};
        // A new experiment must not inherit the earlier run's comparisons.
        global.singleAblationResults = null;
        global.lastAssessmentApiPayload = null;
        global.assessmentFoci = [];
        assessmentFoci = [];
        global.experimentCComparison = null;
        el('ablation-results').innerHTML = '<p class="empty-state">Complete steps 3 and 4, then run ablation.</p>';
        el('assessment-results').innerHTML = '';
        el('focus-control-section').classList.add('hidden');
    }

    async function sampleBaseline() {
        const current = requireCurrent();
        requireCurrentMethod(current);
        // Clicking again after a completed run explicitly starts a fresh sample set.
        if (current.diagnostics) {
            current.samples = [];
            current.diagnostics = null;
        }
        current.retrospective = [];
        current.summary = null;
        global.singleAblationResults = null;
        global.lastAssessmentApiPayload = null;
        global.assessmentFoci = [];
        assessmentFoci = [];
        el('assessment-results').innerHTML = '';
        el('ablation-results').innerHTML = '<p class="empty-state">Run ablation after retrospective assessment.</p>';
        el('focus-control-section').classList.add('hidden');
        const c = current.context;
        const controller = new AbortController();
        await collectMissing(current.samples, c.n_baseline, async () => {
            const sample = await fetchAblationSample(c.scenario, c.foci, 'baseline', null,
                c.temperature, controller, null, c.model);
            if (typeof sample.content !== 'string' || !sample.content.trim()) {
                throw new Error('The model returned an empty baseline output.');
            }
            requireCurrent();
            return sample;
        }, 'Generating baseline outputs');
        showLoading('Measuring baseline noise and output similarities…');
        current.diagnostics = await post('/api/baseline-diagnostics', {
            baseline_outputs: current.samples.map(sample => sample.content),
        }, c.model);
        requireCurrent();
        outputInput.value = current.samples[0].content;
    }

    async function retrospective() {
        const current = requireCurrent();
        requireCurrentMethod(current);
        const c = current.context;
        if (!current.diagnostics || current.samples.filter(Boolean).length !== c.n_baseline) {
            throw new Error('Finish baseline sampling and diagnostics in step 3 first.');
        }
        await collectMissing(current.retrospective, c.n_baseline, async index => {
            const assessment = await post('/api/focus-self-assessment', {
                scenario: c.scenario, foci: c.foci, phase: 'retrospective', output: current.samples[index].content,
            }, c.model);
            requireCurrent();
            return {...assessment, output_index: index};
        }, 'Assessing retrospective focus');
        current.summary = await post('/api/focus-comparison', {
            foci: c.foci, prospective: current.prospective, retrospective: current.retrospective,
        }, c.model);
        requireCurrent();
        renderAssessment(current.summary.average);
    }

    function allocationTable(assessment) {
        const applicability = {direct: 'Direct contribution', background: 'Background constraint', inactive: 'Inactive for this response'};
        const request = assessment.request_summary ? '<p><strong>Current request (model interpretation):</strong> '
            + esc(assessment.request_summary) + '</p>' : '';
        const evidence = assessment.request_evidence?.length ? '<details><summary>Evidence used to identify the request</summary>'
            + assessment.request_evidence.map(item => '<p><strong>' + esc(item.message_id) + ':</strong> “'
                + esc(item.quote) + '”</p>').join('') + '</details>' : '';
        const temperature = assessment.assessment_temperature != null ? '<p class="info-text">Assessment temperature: '
            + esc(assessment.assessment_temperature) + '</p>' : '';
        const normalized = assessment.budget_normalized ? '<p class="info-text">The model’s scores totaled '
            + esc(assessment.raw_score_total) + '. Rescaled proportionally to 100%; relative weights and zero scores are unchanged.</p>' : '';
        const recoveryCalls = (assessment.allocation_recovery?.calls || 0) + (assessment.allocation_recovery?.budget_retries || 0);
        const recovery = recoveryCalls > 0 ? '<p class="info-text">Completed with '
            + esc(recoveryCalls) + ' follow-up model call(s) to repair an incomplete or invalid assessment.</p>' : '';
        const scores = assessment.foci.map(row => Number(row.score));
        const uniform = scores.length > 1 && scores.every(Number.isFinite) && Math.max(...scores) - Math.min(...scores) < 1e-8;
        const warnings = assessment.assessment_warnings?.length ? assessment.assessment_warnings
            : uniform ? ['The model assigned identical weights to every focus. This result does not distinguish their contributions. Equal weights may be intentional or a model limitation; they are not evidence of equal causal influence. Consider a new run with a different baseline model.'] : [];
        const warning = warnings.map(message => '<p class="info-text" role="status"><strong>Assessment limitation:</strong> '
            + esc(message) + '</p>').join('');
        const rationale = assessment.overall_summary ? '<p><strong>Allocation rationale:</strong> '
            + esc(assessment.overall_summary) + '</p>' : '';
        return warning + request + evidence + rationale + temperature + normalized + recovery
            + '<div class="workflow-table-wrap"><table class="workflow-table"><thead><tr><th>Focus</th><th>Budget</th><th>Justification</th></tr></thead><tbody>'
            + assessment.foci.map(row => '<tr><th scope="row">' + (row.focus_index + 1) + '. ' + esc(row.focus)
                + (applicability[row.applicability] ? '<br><span class="info-text">' + applicability[row.applicability] + '</span>' : '')
                + '</th><td><strong>' + number(row.score) + '%</strong><div class="workflow-budget"><span style="width:'
                + Math.min(100, Math.max(0, Number(row.score))) + '%"></span></div></td><td>' + esc(row.explanation) + '</td></tr>').join('')
            + '</tbody></table></div>';
    }

    function comparisonTable(summary, ablation = false) {
        return '<div class="workflow-table-wrap"><table class="workflow-table"><thead><tr><th>Focus</th><th>Prospective</th><th>Retrospective mean ± SD</th><th>Retro − prospective</th>'
            + (ablation ? '<th>Ablation shift share</th><th>Share − prospective</th><th>Share − retro</th><th>Raw shift / q</th>' : '')
            + '</tr></thead><tbody>' + summary.comparison.map(row => '<tr><th scope="row">' + (row.focus_index + 1) + '. ' + esc(row.focus)
                + '</th><td>' + number(row.prospective) + '%</td><td>' + number(row.retrospective_mean) + '% ± '
                + number(row.retrospective_stddev) + '</td><td>' + delta(row.retrospective_minus_prospective_pp) + '</td>'
                + (ablation ? '<td>' + (row.ablation_shift_share == null ? '—' : number(row.ablation_shift_share) + '%')
                    + '</td><td>' + delta(row.ablation_minus_prospective_pp) + '</td><td>' + delta(row.ablation_minus_retrospective_pp)
                    + '</td><td>' + number(row.ablation?.t_obs, 4) + ' / ' + number(row.ablation?.q_value, 4) + '</td>' : '') + '</tr>').join('')
            + '</tbody></table></div>' + (ablation ? '<p class="info-text">' + esc(summary.ablation_share_definition) + '</p>' : '');
    }

    function distributionView(diagnostics) {
        const d = diagnostics.output_distribution, b = diagnostics.baseline_stability;
        const points = d.projection.coordinates;
        const xs = points.map(p => p[0]), ys = points.map(p => p[1]);
        const minX = Math.min(...xs), minY = Math.min(...ys);
        const spanX = Math.max(...xs) - minX, spanY = Math.max(...ys) - minY;
        const colors = ['#4f46e5', '#d97706', '#059669', '#db2777', '#0284c7'];
        const x = value => spanX < 1e-10 ? 300 : 35 + (value - minX) / spanX * 530;
        const y = value => spanY < 1e-10 ? 140 : 245 - (value - minY) / spanY * 210;
        const buckets = new Map();
        points.forEach((p, i) => {
            const key = Math.round(x(p[0])) + ':' + Math.round(y(p[1]));
            if (!buckets.has(key)) buckets.set(key, {x: x(p[0]), y: y(p[1]), members: [], group: d.membership[i]});
            buckets.get(key).members.push(i + 1);
        });
        const svg = '<svg viewBox="0 0 600 280" class="workflow-scatter" role="img" aria-label="Baseline output similarity projected to two principal components">'
            + [...buckets.values()].map(p => {
                const label = p.members.length > 5 ? p.members[0] + ' +' + (p.members.length - 1) : p.members.join(', ');
                return '<g><title>Outputs ' + p.members.join(', ') + ' · group ' + (p.group + 1)
                    + '</title><circle cx="' + p.x + '" cy="' + p.y + '" r="' + Math.min(18, 6 + p.members.length)
                    + '" fill="' + colors[p.group] + '"/><text text-anchor="' + (p.x > 450 ? 'end' : 'start')
                    + '" x="' + (p.x + (p.x > 450 ? -20 : 20)) + '" y="' + (p.y - 14) + '">' + label + '</text></g>';
            }).join('') + '</svg>';
        return '<div class="workflow-metrics"><p>Mean pairwise distance <strong>' + number(b.mean_pairwise_cosine_distance, 4)
            + '</strong></p><p>95th percentile distance <strong>' + number(b.p95_pairwise_cosine_distance, 4)
            + '</strong></p><p>Mean distance to centroid <strong>' + number(b.mean_distance_from_centroid, 4)
            + '</strong></p></div><p><strong>' + esc(d.label.replaceAll('_', ' '))
            + (d.candidate_mode_count ? ' · ' + d.candidate_mode_count + ' candidate modes' : '') + '</strong></p>'
            + svg + '<p class="info-text">Labels identify outputs; coincident points are grouped.</p>'
            + (d.clusters || []).map(group => '<p>Group ' + (group.cluster_id + 1) + ': <strong>' + group.size + ' outputs ('
                + number(group.size / points.length * 100, 0) + '%)</strong> · outputs ' + group.output_indices.map(i => i + 1).join(', ') + '</p>').join('')
            + '<p class="info-text">' + esc(d.note) + '</p>'
            + '<details><summary>Pairwise cosine distances (smaller = more similar)</summary><div class="workflow-table-wrap"><table class="workflow-table"><thead><tr><th>Output</th>'
            + points.map((_, i) => '<th>' + (i + 1) + '</th>').join('') + '</tr></thead><tbody>'
            + d.pairwise_cosine_distances.map((row, i) => '<tr><th>' + (i + 1) + '</th>' + row.map(v => '<td>' + number(v, 3) + '</td>').join('') + '</tr>').join('')
            + '</tbody></table></div></details>';
    }

    function render() {
        refreshValidity();
        if (el('prospective-results')) el('prospective-results').innerHTML = state?.prospective ? allocationTable(state.prospective) : '';
        if (el('baseline-results')) el('baseline-results').innerHTML = state ?
            (state.diagnostics ? distributionView(state.diagnostics) : '<p class="info-text">' + state.samples.filter(Boolean).length + ' baseline outputs collected.</p>')
            + state.samples.map((sample, i) => sample ? '<details class="workflow-output"><summary>Output ' + (i + 1)
                + (state.diagnostics ? ' · group ' + (state.diagnostics.output_distribution.membership[i] + 1) : '')
                + '</summary><pre>' + esc(sample.content) + '</pre></details>' : '').join('') : '';
        if (el('retrospective-results')) el('retrospective-results').innerHTML = state ?
            (state.summary ? '<p class="info-text">Retrospective assessments use temperature 0.2; generation temperature is shown above.</p>'
                + comparisonTable(state.summary) : '<p class="info-text">' + state.retrospective.filter(Boolean).length + ' outputs assessed.</p>')
            + state.retrospective.map((assessment, i) => assessment ? '<details class="workflow-output"><summary>Output ' + (i + 1)
                + ' · retrospective allocation</summary><pre>' + esc(state.samples[i].content) + '</pre>' + allocationTable(assessment) + '</details>' : '').join('') : '';
        renderAblationComparison(global.singleAblationResults);
    }

    function renderAblationComparison(result) {
        const target = el('focus-ablation-comparison');
        if (target) target.innerHTML = result?.focus_comparison
            ? '<h3>Prospective, retrospective and ablation comparison</h3>' + comparisonTable(result.focus_comparison, true) : '';
    }

    function forAblation(scenario, fociList, cfg, model) {
        const current = requireCurrent();
        if (!current.summary) throw new Error('Assess every baseline output in step 4 before ablation.');
        const expected = {...current.context, scenario, foci: fociList, model,
            temperature: cfg.temperature, n_baseline: cfg.n_baseline};
        if (!matches(current.context, expected)) {
            throw new Error('Ablation must use the same scenario, foci, model, temperature and baseline count as steps 2–4. Match those settings or start a new prediction.');
        }
        return structuredClone(current);
    }

    global.FocalPromptWorkflow = {
        collect: () => state ? structuredClone(state) : null,
        restore: data => { state = data ? structuredClone(data) : null; render(); },
        forAblation, renderAblationComparison, refreshValidity,
        // Exposed to support deterministic, mocked workflow integration checks.
        predict, sampleBaseline, retrospective, matches, collectMissing,
    };
    el('predict-focus-btn')?.addEventListener('click', () => run('Predicting focus before generation…', predict));
    el('sample-baseline-btn')?.addEventListener('click', () => run('Generating baseline outputs…', sampleBaseline));
    el('retrospective-focus-btn')?.addEventListener('click', () => run('Assessing each baseline output…', retrospective));
    document.addEventListener('input', refreshValidity);
    document.addEventListener('change', refreshValidity);
})(window);
