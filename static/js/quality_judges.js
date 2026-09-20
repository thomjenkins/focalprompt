/* Independent quality judges share an immutable input snapshot. */
(function (global) {
    'use strict';

    function modelOf(run) {
        const recorded = run?.model ? run : run?.focus_workflow?.context?.model;
        if (!recorded?.model || !recorded?.provider) {
            throw new Error('The original generation model is not recorded. Run ablation before self-assessment.');
        }
        return {model: recorded.model, provider: recorded.provider};
    }

    function modelKey(selection) {
        const provider = String(selection.provider || '').trim().toLowerCase();
        let model = String(selection.model || '').trim().toLowerCase();
        if (model.startsWith(provider + '/')) model = model.slice(provider.length + 1);
        return provider + '/' + model;
    }

    function judgesFor(run, secondEnabled, secondModel) {
        const self = {id: 'self', title: 'Self-assessment', ...modelOf(run)};
        if (!secondEnabled) return [self];
        if (!secondModel?.model || !secondModel?.provider || modelKey(secondModel) === modelKey(self)) {
            throw new Error('Choose a different model for the optional second judge.');
        }
        return [self, {id: 'external', title: 'Second judge', model: secondModel.model, provider: secondModel.provider}];
    }

    function canonical(value) {
        return JSON.stringify(value, (_key, item) => {
            if (!item || typeof item !== 'object' || Array.isArray(item)) return item;
            return Object.fromEntries(Object.keys(item).sort().map(key => [key, item[key]]));
        });
    }

    function scored(row) {
        return typeof row?.overall_score === 'number' && Number.isFinite(row.overall_score)
            && row.overall_score >= 0 && row.overall_score <= 100;
    }

    function progress(data, judge) {
        const labels = data.plan?.outputs?.map(item => item.label)
            || judge.result?.sampled_labels || data.context?.outputs?.map(item => item.label) || [];
        const valid = new Set((judge.result?.evaluations || []).filter(scored).map(row => row.label));
        const count = labels.filter(label => valid.has(label)).length;
        return {scored: count, total: labels.length, complete: labels.length > 0 && count === labels.length};
    }

    const retryStatuses = new Set([408, 429, 500, 502, 503, 504]);
    const retryDelays = [2000, 5000];
    const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

    function requestError(message, response, kind) {
        const error = new Error(message);
        error.kind = kind || 'http';
        error.status = response?.status;
        error.retryable = retryStatuses.has(response?.status);
        const retryAfter = response?.headers?.get('Retry-After');
        if (retryAfter) {
            const seconds = Number(retryAfter);
            const delay = Number.isFinite(seconds) ? seconds * 1000 : Date.parse(retryAfter) - Date.now();
            if (Number.isFinite(delay) && delay >= 0) error.retryAfterMs = Math.min(delay, 30000);
        }
        return error;
    }

    async function readResponse(response) {
        const text = await response.text();
        let data;
        try { data = JSON.parse(text); } catch (_) {
            const timeout = [408, 504].includes(response.status) || /FUNCTION_INVOCATION_TIMEOUT/.test(text);
            throw requestError(timeout ? 'The request timed out. Completed work is retained.'
                : 'The server returned a non-JSON response (HTTP ' + response.status + '). Completed work is retained.',
                response, timeout ? 'timeout' : 'http');
        }
        if (!data || typeof data !== 'object' || Array.isArray(data)) throw requestError('The server returned an invalid response. Completed work is retained.', response);
        if (!response.ok) {
            const error = requestError(data.error || 'Request failed (HTTP ' + response.status + ').', response);
            const seconds = Number(data.retry_after);
            if (Number.isFinite(seconds) && seconds > 0) {
                error.retryAfterMs = Math.max(error.retryAfterMs || 0, Math.min(seconds * 1000, 30000));
            }
            throw error;
        }
        return data;
    }

    async function fetchJson(path, options) {
        // Only TypeErrors at the fetch/body-reading boundary are transport errors;
        // programming and validation errors elsewhere must not trigger paid retries.
        try { return await readResponse(await fetch(path, options)); }
        catch (error) {
            if (error instanceof TypeError || error.name === 'NetworkError') {
                const failure = new Error('The browser could not receive a complete response from the server. Completed work is retained.');
                failure.kind = 'network';
                failure.retryable = true;
                throw failure;
            }
            throw error;
        }
    }

    async function retryRequest(task, {wait = sleep, onRetry, onAttempt} = {}) {
        for (let attempt = 1; ; attempt++) {
            onAttempt?.(attempt);
            try { return await task(); }
            catch (error) {
                error.attempts = attempt;
                if (error.retryable !== true || attempt > retryDelays.length) throw error;
                const delay = Math.max(retryDelays[attempt - 1], error.retryAfterMs || 0);
                onRetry?.({attempt: attempt + 1, max_attempts: retryDelays.length + 1,
                    delay_ms: delay, error: error.message, kind: error.kind, status: error.status});
                await wait(delay);
            }
        }
    }

    function addNumbers(base, extra) {
        const result = {...base};
        for (const [key, value] of Object.entries(extra || {})) {
            if (typeof value === 'number' && Number.isFinite(value)) result[key] = (Number(result[key]) || 0) + value;
            else if (!(key in result)) result[key] = value;
        }
        return result;
    }

    async function evaluate({context, judges, previous, prepare, request, onUpdate, wait = sleep}) {
        const snapshot = structuredClone(context);
        const sameContext = previous?.version === 2 && canonical(previous.context) === canonical(snapshot);
        const plan = sameContext && previous.plan?.version === 1
            ? structuredClone(previous.plan) : await retryRequest(() => prepare(structuredClone(snapshot)), {wait});
        if (plan?.version !== 1 || plan.batch_size !== 4 || !Array.isArray(plan.outputs) || !plan.outputs.length) {
            throw new Error('Invalid quality evaluation plan. Please retry.');
        }
        const labels = new Set(plan.outputs.map(item => item.label));
        const source = new Map(snapshot.outputs.map(item => [item.label, String(item.text).trim()]));
        if (labels.size !== plan.outputs.length || plan.outputs.some(item => source.get(item.label) !== item.text)) {
            throw new Error('The evaluation plan does not match the saved outputs. Please retry.');
        }
        const retained = judge => sameContext && previous.judges?.find(row =>
            row.id === judge.id && modelKey(row) === modelKey(judge));
        // Missing scores make an old "complete" result resumable too. A fully
        // finished pair is evaluated afresh when the user explicitly reruns it.
        const resume = judges.some(judge => !progress({plan}, retained(judge) || {}).complete);
        const state = {version: 2, evaluation_type: 'task_quality', context: snapshot, plan,
            judges: judges.map(judge => {
                const old = resume && retained(judge);
                const next = old ? structuredClone(old) : {...judge};
                next.result = next.result || {evaluations: []};
                if (old && !old.batches) next.retained_result = structuredClone(old.result);
                next.batches = next.batches || [];
                next.status = progress({plan}, next).complete ? 'complete' : 'pending';
                delete next.error;
                delete next.retry;
                delete next.active_attempt;
                return next;
            })};
        const emit = () => onUpdate?.(structuredClone(state));
        emit();
        await Promise.all(state.judges.map(async judge => {
            if (judge.status === 'complete') return;
            const selection = judges.find(item => item.id === judge.id);
            const rows = new Map((judge.result.evaluations || []).filter(scored).map(row => [row.label, row]));
            const updateResult = () => {
                const result = judge.result;
                result.evaluations = plan.outputs.filter(item => rows.has(item.label)).map(item => rows.get(item.label));
                Object.assign(result, {n_outputs: plan.outputs.length, n_outputs_total: plan.n_outputs_total,
                    n_outputs_evaluated: result.evaluations.length, n_outputs_scored: result.evaluations.length,
                    sampled_labels: [...labels], missing_labels: [...labels].filter(label => !rows.has(label)),
                    sample_fraction: plan.sample_fraction, sample_seed: plan.sample_seed,
                    n_batches: judge.batches.filter(batch => batch.result).length,
                    complete: result.evaluations.length === plan.outputs.length});
                const protocols = new Set(judge.batches.filter(batch => batch.result)
                    .map(batch => batch.result.assessment_protocol || 'legacy'));
                if (judge.retained_result?.evaluations?.length) protocols.add(judge.retained_result.assessment_protocol || 'legacy');
                result.assessment_protocols = [...protocols];
                result.assessment_protocol = protocols.size === 1 ? [...protocols][0] : 'mixed-resumed';
            };
            for (let i = 0; i < plan.outputs.length; i += plan.batch_size) {
                const batch = plan.outputs.slice(i, i + plan.batch_size);
                if (batch.every(item => rows.has(item.label))) continue;
                judge.active_batch = Math.floor(i / plan.batch_size) + 1;
                emit();
                try {
                    // Reuse the original batch on retry so each judge sees the
                    // same neighbouring outputs. Never send either judge's scores.
                    const result = await retryRequest(() => request({...structuredClone(snapshot), outputs: structuredClone(batch),
                        sample_pct: 100, sample_fraction: 1, batch_mode: true}, {...selection}), {
                        wait,
                        onAttempt: attempt => {
                            judge.active_attempt = attempt;
                            delete judge.retry;
                            emit();
                        },
                        onRetry: retry => {
                            judge.retry = retry;
                            judge.batches.push({batch_index: judge.active_batch, attempt: retry.attempt - 1,
                                error: retry.error, error_kind: retry.kind, status: retry.status,
                                retry_delay_ms: retry.delay_ms, will_retry: true});
                            emit();
                        }});
                    const actual = result.judge;
                    if (!actual || actual.role !== judge.id || modelKey(actual) !== modelKey(judge)) {
                        throw new Error('The evaluation returned a different judge identity. Please retry.');
                    }
                    judge.batches.push({batch_index: judge.active_batch, attempt: judge.active_attempt, result: structuredClone(result)});
                    const batchLabels = new Set(batch.map(item => item.label));
                    for (const row of result.evaluations || []) {
                        if (batchLabels.has(row.label) && scored(row) && !rows.has(row.label)) rows.set(row.label, row);
                    }
                    judge.result.usage = addNumbers(judge.result.usage, result.usage);
                    judge.result.cost_breakdown = addNumbers(judge.result.cost_breakdown, result.cost_breakdown);
                    judge.result.judge = result.judge;
                    judge.result.task_context_source = result.task_context_source;
                    if (result.comparative_notes) judge.result.comparative_notes =
                        [judge.result.comparative_notes, result.comparative_notes].filter(Boolean).join(' ');
                    updateResult();
                    emit();
                } catch (error) {
                    judge.status = 'error';
                    judge.error = error.message || 'Evaluation failed. Please retry.';
                    if (error.attempts > 1) judge.error += ' Stopped after ' + error.attempts + ' attempts.';
                    judge.batches.push({batch_index: judge.active_batch, error: judge.error,
                        attempt: judge.active_attempt, error_kind: error.kind, status: error.status, will_retry: false});
                    break;
                }
            }
            updateResult();
            delete judge.active_batch;
            delete judge.active_attempt;
            delete judge.retry;
            if (judge.status !== 'error') judge.status = judge.result.complete ? 'complete' : 'partial';
            emit();
        }));
        return state;
    }

    function comparisonRows(data) {
        const self = data.judges.find(judge => judge.id === 'self')?.result;
        const external = data.judges.find(judge => judge.id === 'external')?.result;
        const selfRows = new Map((self?.evaluations || []).map(row => [row.label, row]));
        const externalRows = new Map((external?.evaluations || []).map(row => [row.label, row]));
        const score = row => scored(row) ? row.overall_score : null;
        const outputs = data.plan?.outputs || (data.context.outputs || []).filter(item => selfRows.has(item.label) || externalRows.has(item.label));
        return outputs
            .map(item => {
                const own = score(selfRows.get(item.label)), other = score(externalRows.get(item.label));
                return {label: item.label, self: own, external: other,
                    difference: own !== null && other !== null ? other - own : null};
            });
    }

    function comparisonHtml(data, esc) {
        if (!data.judges.some(judge => judge.id === 'external')) return '';
        const rows = comparisonRows(data);
        if (!rows.length) return '';
        const number = value => value === null ? '—' : value.toFixed(1);
        return '<div class="workflow-table-wrap"><table class="workflow-table"><thead><tr>'
            + '<th>Output</th><th>Self-assessment /100</th><th>Second judge /100</th><th>Second − self (points)</th>'
            + '</tr></thead><tbody>' + rows.map(row => '<tr><td>' + esc(row.label) + '</td><td>'
                + number(row.self) + '</td><td>' + number(row.external) + '</td><td>'
                + (row.difference !== null && row.difference > 0 ? '+' : '') + number(row.difference) + '</td></tr>').join('')
            + '</tbody></table></div>';
    }

    global.FocalPromptQuality = {modelOf, judgesFor, evaluate, progress, readResponse, fetchJson, retryRequest, comparisonRows, comparisonHtml};
})(window);
