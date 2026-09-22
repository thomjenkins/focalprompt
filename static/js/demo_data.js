/* Pure, read-only adapters from exported workspaces to the guided lab walkthrough. */
(function (global) {
    'use strict';
    const format = global.FocalPromptWorkspaceFormat || (typeof require === 'function' ? require('./workspace_format.js') : null);
    const orderComparison = global.FocalPromptOrderComparison || (typeof require === 'function' ? require('./order_comparison.js') : null);
    function deepFreeze(value) {
        if (!value || typeof value !== 'object' || Object.isFrozen(value)) return value;
        Object.values(value).forEach(deepFreeze);
        return Object.freeze(value);
    }
    function outputText(raw) {
        try {
            const parsed = JSON.parse(raw);
            if (typeof parsed.suggestedMessage === 'string') return parsed.suggestedMessage;
        } catch (_) { /* Plain-text outputs remain verbatim. */ }
        return String(raw);
    }
    function prepare(input, definition) {
        const error = format.validate(input);
        if (error) throw new Error(typeof error === 'string' ? error : 'A complete workspace export is required.');
        // Own a detached immutable snapshot: never restore into the active lab or mutate experiment objects.
        const workspace = deepFreeze(format.migrate(JSON.parse(JSON.stringify(input))));
        const pa = workspace.prompt_analysis;
        if (!pa?.scenario?.messages?.length || !Array.isArray(pa.foci)) throw new Error('The workspace has no scenario or focus catalog.');
        const scenario = pa.scenario, messages = new Map(scenario.messages.map(m => [m.id, m]));
        const foci = pa.foci.map((focus, index) => {
            // The production importer also supports the older, message-relative
            // single-span fields. Read them without rewriting the supplied export.
            const sourceSpans = focus.spans?.length ? focus.spans :
                Number.isInteger(focus.char_start) && Number.isInteger(focus.char_end)
                    ? [{message_id:focus.message_id,char_start:focus.char_start,char_end:focus.char_end,text_snapshot:focus.prompt_section}] : [];
            const spans = sourceSpans.map(span => {
                const message = messages.get(span.message_id || focus.message_id);
                if (!message || !Number.isInteger(span.char_start) || !Number.isInteger(span.char_end)
                    || span.char_start < 0 || span.char_end <= span.char_start || span.char_end > message.content.length) {
                    throw new Error(`Invalid source range for “${focus.focus}”.`);
                }
                const text = message.content.slice(span.char_start, span.char_end);
                if ((span.text_snapshot ?? span.text ?? text) !== text) throw new Error(`Source text mismatch for “${focus.focus}”.`);
                return {...span, text, role: message.role, message_id: message.id};
            });
            return {index, name: focus.focus, spans, source: focus};
        });
        const find = name => {
            const matches = foci.filter(f => f.name === name);
            if (matches.length !== 1 || !matches[0].spans.length) throw new Error(`Expected one grounded focus named “${name}”.`);
            return matches[0];
        };
        const booking = find(definition.keyFoci.booking), cat = find(definition.keyFoci.cat);
        const order = pa.focus_order?.results;
        const judgeMatches = order?.behavioral_criterion === definition.criterion;
        const series = {};
        function add(key, outputs, judgments, source) {
            if (!Array.isArray(outputs) || !outputs.length || outputs.some(o => typeof o !== 'string')) return null;
            const annotations = definition.annotations?.[key];
            const labels = annotations?.length === outputs.length ? annotations : [];
            const judges = new Map(judgeMatches ? (judgments || []).map(j => [j.sample_index, j]) : []);
            const samples = outputs.map((raw, index) => {
                const judgment = judges.get(index);
                return {index, raw, text: outputText(raw), judgment,
                    behavior: judgment ? (definition.judgeLabels?.[judgment.classification] || 'unclassified') : (labels[index] || 'unclassified')};
            });
            const counts = samples.reduce((out, sample) => { out[sample.behavior] = (out[sample.behavior] || 0) + 1; return out; }, {});
            series[key] = {key, samples, counts, n: samples.length, source,
                evidence: judges.size ? 'Stored LLM judgments · not ground truth' : labels.length ? 'Editorial reading of stored outputs · inspect every sample' : 'Stored outputs · not behaviorally classified',
                featured: Math.min(definition.featured?.[key] || 0, samples.length - 1)};
            return series[key];
        }
        const baseline = pa.focus_workflow?.samples?.map(s => s.content) || pa.single_ablation?.baseline_outputs;
        const baselineJudged = JSON.stringify(baseline) === JSON.stringify(order?.baseline_outputs);
        add('baseline', baseline, baselineJudged ? order?.baseline_behavioral_judgments : null, 'prompt_analysis.focus_workflow.samples');
        const ablations = pa.single_ablation?.ablation_results || [];
        const singleton = pa.singleton_experiment?.result;
        function byFocus(rows, focus) { return (rows || []).find(r => r.focus_index === focus.index && r.focus === focus.name); }
        add('removeCat', byFocus(ablations, cat)?.ablated_outputs, null, 'prompt_analysis.single_ablation.ablation_results');
        add('removeBooking', byFocus(ablations, booking)?.ablated_outputs, null, 'prompt_analysis.single_ablation.ablation_results');
        add('noFocus', singleton?.no_focus_outputs, null, 'prompt_analysis.singleton_experiment.result.no_focus_outputs');
        add('bookingOnly', byFocus(singleton?.focus_results, booking)?.singleton_outputs, null, 'prompt_analysis.singleton_experiment.result.focus_results');
        add('catOnly', byFocus(singleton?.focus_results, cat)?.singleton_outputs, null, 'prompt_analysis.singleton_experiment.result.focus_results');
        const sweep = order?.position_sweeps?.find(s => s.focus === cat.name);
        const focusMap = order?.scenario_metadata?.focus_index_map || {};
        const positions = (sweep?.positions || []).flatMap(position => {
            const indices = position.assignment?.map(i => focusMap[String(i)]);
            if (!indices?.length || indices.some(i => !foci[i])) return [];
            const key = 'order-' + position.slot_index;
            if (!add(key, position.outputs, position.behavioral_judgments, 'prompt_analysis.focus_order.results.position_sweeps')) return [];
            return [{...position, indices, series: key}];
        }).sort((a, b) => a.slot_index - b.slot_index);
        const orderMessage = messages.get(order?.scenario_metadata?.ordering_message_id);
        const originalOrder = orderMessage ? foci.filter(f => f.spans.some(s => s.message_id === orderMessage.id)).map(f => f.index) : [];
        let matchedOrders = [];
        if (order && definition.orderComparison) {
            matchedOrders = definition.orderComparison.orders.map(names => orderComparison.findPermutationByOrder(order.global_order_experiment?.permutations, names));
            if (matchedOrders[0] === matchedOrders[1] || !judgeMatches) throw new Error('The matched order comparison needs distinct global permutations and the recorded behavioral criterion.');
            matchedOrders.forEach((p, i) => {
                if (p.focus_positions[cat.name] !== 1 || p.model !== order.model || p.provider !== order.provider || p.temperature !== order.temperature
                    || orderMessage?.role !== cat.spans[0].role || order.scenario_metadata.ordering_role !== orderMessage.role) {
                    throw new Error('Matched global orders must keep Cat only second, with the same model, sampling settings and message role.');
                }
                const template = p.reconstruction?.template;
                if (!template || JSON.stringify(template) !== JSON.stringify(matchedOrders[0].reconstruction?.template)
                    || template.focus_texts?.[String(p.assignment[1])] !== cat.spans[0].text) throw new Error('Matched global orders have inconsistent source text.');
                const classifications = p.outputs.map((_, index) => p.behavioral_judgments?.find(j => j.sample_index === index)?.classification);
                if (JSON.stringify(classifications) !== JSON.stringify(definition.orderComparison.expectedClassifications[i])) throw new Error('The recorded matched-order judgments differ from the Lisbon comparison.');
                const texts = p.outputs.map(outputText);
                for (const phrase of definition.orderComparison.highlights[i]) {
                    if (!texts.some(text => text.includes(phrase))) throw new Error(`Missing recorded order highlight: ${phrase}`);
                }
            });
        }
        const jev = pa.jev_experiment?.state;
        add('jevFull', jev?.arms?.full?.samples?.map(s => s.output), null, 'prompt_analysis.jev_experiment.state.arms.full');
        add('jevSelected', jev?.arms?.selected?.samples?.map(s => s.output), null, 'prompt_analysis.jev_experiment.state.arms.selected');
        add('jevOrdered', jev?.arms?.ordered?.samples?.map(s => s.output), null, 'prompt_analysis.jev_experiment.state.arms.ordered');
        const selected = jev?.selection?.selected_indices;
        const hasJev = Array.isArray(selected) && selected.every(i => foci[i])
            && series.jevFull && series.jevSelected && series.jevOrdered;
        const groups = hasJev ? (jev.selection.order_groups || []).map(group => {
            const ordered = jev.orders?.[group.message_id];
            const original = group.focus_indices.filter(i => selected.includes(i));
            // Never fabricate an order if the optional ordered arm is incomplete.
            const validOrder = Array.isArray(ordered) && ordered.length === original.length
                && new Set(ordered).size === ordered.length && ordered.every(i => original.includes(i));
            return {...group, original, ordered: validOrder ? ordered : null};
        }) : [];
        const model = pa.focus_workflow?.context?.model || workspace.model;
        return deepFreeze({workspace, scenario, foci, booking, cat, series, positions, matchedOrders, orderMessage, originalOrder,
            model, modelLabel: definition.primaryWorkspace.modelLabel || model?.model,
            temperature: pa.focus_workflow?.context?.temperature,
            jev: hasJev ? {source: jev, selected, groups, hasOrder: groups.length > 0 && groups.every(g => g.ordered)} : null,
            selfReport: pa.focus_workflow?.summary?.comparison || [],
            ablations, singleton});
    }
    function prepareComparison(input, recording) {
        // A separate definition prevents the first model's labels or order experiment
        // from being accidentally applied to another recording.
        const data = prepare(input, {primaryWorkspace: {}, keyFoci: recording.keyFoci,
            annotations: {baseline: recording.refusalEvidence?.map(() => 'refusal')},
            featured: {baseline: recording.featuredSample || 0}});
        const fail = message => { throw new Error(`Invalid model-comparison recording: ${message}`); };
        if (data.model?.model !== recording.expectedModel) fail('unexpected baseline model');
        const hierarchy = data.foci.filter(f => f.name === recording.keyFoci.hierarchy);
        if (hierarchy.length !== 1 || !hierarchy[0].spans.length) fail('missing grounded hierarchy focus');
        for (const [key, focus] of [['booking', data.booking], ['cat', data.cat], ['hierarchy', hierarchy[0]]]) {
            if (recording.expectedIndices[key] != null && focus.index !== recording.expectedIndices[key]) fail(`unexpected ${key} focus index`);
            if (!focus.spans.some(span => span.text === recording.expectedText[key])) fail(`changed ${key} instruction text`);
        }
        if (data.booking.spans[0].role !== 'system' || !data.booking.spans[0].text.includes('must always')) fail('missing strengthened system booking instruction');
        if (hierarchy[0].spans[0].message_id !== data.cat.spans[0].message_id
            || hierarchy[0].spans[0].message_id === data.booking.spans[0].message_id) fail('hierarchy must be a separate focus in the clinic-specific message');
        const samples = data.series.baseline?.samples;
        if (samples?.length !== 10 || recording.refusalEvidence?.length !== 10) fail('expected ten reviewed baseline outputs');
        samples.forEach((sample, index) => {
            // Literal, individually reviewed evidence, bound to the fixture checksum.
            // This is an editorial output audit, not a new classifier or judge score.
            const phrase = recording.refusalEvidence[index];
            if (!phrase || !sample.text.includes(phrase)) fail(`refusal evidence changed for sample ${index + 1}`);
        });
        const pair = data.singleton?.pairwise_resemblance?.pairs?.find(p =>
            p.row_index === Math.min(data.booking.index, data.cat.index)
            && p.column_index === Math.max(data.booking.index, data.cat.index));
        const score = pair?.views?.combined;
        if (!score || !Number.isFinite(score.row_share) || score.row_share < 0 || score.row_share > 1) fail('missing booking/cat-only matrix pair');
        const bookingShare = data.booking.index < data.cat.index ? score.row_share : 1 - score.row_share;
        if (bookingShare >= .5) fail('the recorded matrix does not favor Cat-only');
        const singletonModel = data.workspace.prompt_analysis.singleton_experiment.context?.model;
        if (singletonModel?.model !== data.model.model) fail('baseline and pairwise experiment models differ');
        return deepFreeze({...data, hierarchy: hierarchy[0], pair, bookingShare});
    }
    function frames(data, definition, comparisons = []) {
        const list = [];
        definition.steps.forEach(step => {
            if (step.id === 'baseline' && !data.series.baseline) return;
            if (step.id === 'ablation' && (!data.series.removeCat || !data.series.removeBooking)) return;
            if (step.id === 'singleton' && (!data.series.noFocus || !data.series.bookingOnly || !data.series.catOnly)) return;
            if (step.id === 'dominance' && !data.singleton?.pairwise_resemblance?.pairs?.length) return;
            if (step.id === 'order') {
                if (!data.matchedOrders.length) return;
                list.push({...step, phase: 'condition-a'}, {...step, phase: 'condition-b'});
            } else if (step.id === 'comparison') {
                comparisons.forEach((comparison, comparisonIndex) => {
                    ['prompt', 'baseline', 'dominance'].forEach(phase => list.push({...step, phase, comparisonIndex,
                        workspaceId: definition.comparisonWorkspaces[comparisonIndex].id}));
                });
            } else if (step.id === 'jev') {
                if (!data.jev) return;
                ['catalog', 'selected', ...(data.jev.hasOrder ? ['ordered'] : []), 'outputs'].forEach(phase => list.push({...step, phase}));
            } else {
                list.push({...step});
            }
        });
        return list;
    }
    function navigator(list) {
        let index = 0;
        return {get index() { return index; }, get frame() { return list[index]; }, get length() { return list.length; },
            next() { index = Math.min(list.length - 1, index + 1); return this.frame; },
            previous() { index = Math.max(0, index - 1); return this.frame; }, reset() { index = 0; return this.frame; },
            go(next) { if (Number.isInteger(next)) index = Math.max(0, Math.min(list.length - 1, next)); return this.frame; }};
    }
    const api = {prepare, prepareComparison, frames, navigator, outputText, deepFreeze};
    global.FocalPromptDemoData = api;
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
