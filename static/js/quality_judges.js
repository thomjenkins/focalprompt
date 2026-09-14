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

    async function evaluate({context, judges, previous, request, onUpdate}) {
        const snapshot = structuredClone(context);
        const sameContext = previous?.version === 2 && canonical(previous.context) === canonical(snapshot);
        const retained = judge => sameContext && previous.judges?.find(row =>
            row.id === judge.id && row.status === 'complete' && modelKey(row) === modelKey(judge));
        // A retry or newly enabled judge can reuse the completed peer. An explicit
        // rerun of a fully completed selection evaluates both afresh.
        const resume = judges.some(judge => !retained(judge));
        const state = {version: 2, evaluation_type: 'task_quality', context: snapshot,
            judges: judges.map(judge => resume && retained(judge)
                ? structuredClone(retained(judge)) : {...judge, status: 'pending'})};
        const emit = () => onUpdate?.(structuredClone(state));
        emit();
        await Promise.all(state.judges.map(async judge => {
            if (judge.status === 'complete') return;
            try {
                // Only the common task data is sent. Peer scores and judge labels
                // never enter the evaluator prompt.
                judge.result = await request(structuredClone(snapshot), {...judge});
                const actual = judge.result.judge;
                if (!actual || actual.role !== judge.id || modelKey(actual) !== modelKey(judge)) {
                    throw new Error('The evaluation returned a different judge identity. Please retry.');
                }
                judge.status = 'complete';
            } catch (error) {
                delete judge.result;
                judge.status = 'error';
                judge.error = error.message || 'Evaluation failed. Please retry.';
            }
            emit();
        }));
        return state;
    }

    function comparisonRows(data) {
        const self = data.judges.find(judge => judge.id === 'self')?.result;
        const external = data.judges.find(judge => judge.id === 'external')?.result;
        const selfRows = new Map((self?.evaluations || []).map(row => [row.label, row]));
        const externalRows = new Map((external?.evaluations || []).map(row => [row.label, row]));
        const score = row => typeof row?.overall_score === 'number' && Number.isFinite(row.overall_score)
            ? row.overall_score : null;
        return (data.context.outputs || []).filter(item => selfRows.has(item.label) || externalRows.has(item.label))
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

    global.FocalPromptQuality = {modelOf, judgesFor, evaluate, comparisonRows, comparisonHtml};
})(window);
