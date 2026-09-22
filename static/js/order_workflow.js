/* Bounded, resumable order sampling. No request runs the whole model experiment. */
(function (global) {
    'use strict';
    const clone = value => structuredClone(value);
    function canonical(value) {
        if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
        if (value && typeof value === 'object') return '{' + Object.keys(value).sort().map(k => JSON.stringify(k) + ':' + canonical(value[k])).join(',') + '}';
        return JSON.stringify(value);
    }
    const compatible = (state, context) => state?.protocol === 'focus-order-v1' && canonical(state.context) === canonical(context);
    function progress(state) {
        return {samples: Object.values(state?.samples || {}).flat().filter(Boolean).length,
            total: state?.plan?.planned_samples || 0,
            judged: Object.values(state?.judgments || {}).flat().filter(Boolean).length,
            judgeTotal: state?.context?.run_behavioral_judge ? (state.plan.planned_samples + state.context.baseline_outputs.length) : 0};
    }
    async function execute({context, previous, request, onUpdate, check = () => {}, wait}) {
        const snapshot = clone(context);
        if (previous && !compatible(previous, snapshot)) throw new Error('Inputs, baseline, model or settings changed. Start a new order run; saved work is retained.');
        let state = previous;
        const update = () => onUpdate(state);
        const call = (action, extra = {}) => global.FocalPromptQuality.retryRequest(
            () => request(action, {...clone(snapshot), ...extra}), {
                wait, onAttempt: check,
                onRetry: retry => {if (state) {state.retry = retry; update();}},
            });
        try {
            check();
            if (!state) {
                const plan = await call('plan');
                check();
                if (plan.protocol !== 'focus-order-v1' || !plan.conditions?.length
                    || canonical(plan.baseline_outputs) !== canonical(snapshot.baseline_outputs)
                    || new Set(plan.conditions.map(c => c.id)).size !== plan.conditions.length) {
                    throw new Error('Invalid order plan. No outputs were generated.');
                }
                state = {protocol: plan.protocol, context: snapshot, plan, created_at: new Date().toISOString(),
                    samples: Object.fromEntries(plan.conditions.map(c => [c.id, []])),
                    judgments: Object.fromEntries(['baseline', ...plan.conditions.map(c => c.id)].map(id => [id, []])), result: null};
            }
            if (state.result) {update(); return state;}
            state.error = null; state.retry = null; state.phase = 'sampling'; update();
            const jobs = state.plan.conditions.flatMap(c => Array.from({length: c.n_samples}, (_, index) => ({condition: c, index})))
                .filter(j => !state.samples[j.condition.id][j.index]);
            let next = 0, failure = null;
            async function worker() {
                while (!failure && next < jobs.length) {
                    const {condition, index} = jobs[next++];
                    try {
                        check();
                        const sample = await call('sample', {condition_id: condition.id});
                        if (sample.condition_id !== condition.id || typeof sample.content !== 'string' || !sample.content.trim()
                            || canonical(sample.scenario) !== canonical(condition.scenario)) throw new Error('The output does not match its planned order condition.');
                        // Save received work before honoring Stop or a changed setting.
                        state.samples[condition.id][index] = {...sample, received_at: new Date().toISOString()};
                        state.retry = null; update(); check();
                    } catch (error) {failure = failure || error;}
                }
            }
            await Promise.all(Array.from({length: Math.min(2, jobs.length)}, worker));
            if (failure) throw failure;
            check(); state.phase = 'judging'; update();
            if (snapshot.run_behavioral_judge) {
                const groups = [['baseline', snapshot.baseline_outputs], ...state.plan.conditions.map(c => [c.id, state.samples[c.id].map(s => s.content)])];
                for (const [id, outputs] of groups) for (let i = 0; i < outputs.length; i++) {
                    if (state.judgments[id][i]) continue;
                    const judgment = await call('judge', {condition_id: id, sample_index: i, output: outputs[i]});
                    if (judgment.sample_index !== i || !['COMPLIES','AMBIGUOUS','VIOLATES'].includes(judgment.classification)
                        || !Number.isFinite(judgment.score) || judgment.score < 0 || judgment.score > 100) throw new Error('Invalid behavioural judgment. Retry to finish this sample.');
                    state.judgments[id][i] = judgment; state.retry = null; update(); check();
                }
            }
            check(); state.phase = 'scoring'; update();
            const result = await call('score', {samples: state.samples, judgments: state.judgments});
            check();
            if (!result.ok || result.experiment_type !== 'focus_order_sensitivity') throw new Error(result.error || 'Order scoring did not complete.');
            state.result = result; state.phase = 'complete'; state.retry = null; update();
            return state;
        } catch (error) {
            if (state) {state.error = error.message; state.phase = 'incomplete'; state.retry = null; update();}
            throw error;
        }
    }
    global.FocalPromptOrder = {execute, compatible, progress};
})(window);
