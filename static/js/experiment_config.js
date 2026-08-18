/**
 * Experiment configuration preview.
 * Power / exact-vs-sampled math matches utils/permutation_test.py (power_guardrail).
 * Copy strings come from window.FOCALPROMPT_COPY when present.
 */
(function (global) {
    'use strict';

    var DEFAULT_N_PERMUTATIONS = 10000;
    var DEFAULT_ALPHA = 0.05;
    var DEFAULT_TEMPERATURE = 0.7;
    var DEFAULT_N_BASELINE = 10;
    var DEFAULT_N_ABLATED = 5;
    var N_BASELINE_MIN = 5;
    var N_BASELINE_MAX = 50;
    var N_ABLATED_MIN = 3;
    var N_ABLATED_MAX = 25;

    function copy() {
        return global.FOCALPROMPT_COPY || {};
    }

    function combinations(n, k) {
        if (k < 0 || k > n) return 0;
        k = Math.min(k, n - k);
        var r = 1;
        for (var i = 1; i <= k; i++) {
            r = r * (n - k + i) / i;
        }
        return Math.round(r);
    }

    function nLabelAssignments(nBaseline, nAblated) {
        nBaseline = Number(nBaseline);
        nAblated = Number(nAblated);
        var n = nBaseline + nAblated;
        if (nBaseline < 0 || nAblated < 0 || n === 0) return 0;
        return combinations(n, nAblated);
    }

    function minAchievablePvalue(nBaseline, nAblated, nPermutations) {
        nPermutations = nPermutations == null ? DEFAULT_N_PERMUTATIONS : nPermutations;
        var nExact = nLabelAssignments(nBaseline, nAblated);
        if (nExact === 0) return 1;
        if (nExact <= nPermutations) return 1 / nExact;
        return 1 / (1 + nPermutations);
    }

    function usesExactEnumeration(nBaseline, nAblated, nPermutations) {
        nPermutations = nPermutations == null ? DEFAULT_N_PERMUTATIONS : nPermutations;
        var nExact = nLabelAssignments(nBaseline, nAblated);
        return nExact > 0 && nExact <= nPermutations;
    }

    function testTypeForDesign(nBaseline, nAblated, nPermutations) {
        return usesExactEnumeration(nBaseline, nAblated, nPermutations) ? 'exact' : 'sampled';
    }

    function monteCarloPvalueSe(p, nPermutations) {
        p = p == null ? 0.05 : p;
        nPermutations = nPermutations == null ? DEFAULT_N_PERMUTATIONS : nPermutations;
        if (nPermutations <= 0) return 1;
        return Math.sqrt(p * (1 - p) / nPermutations);
    }

    function powerGuardrail(nBaseline, nAblated, nFoci, alpha, nPermutations) {
        alpha = alpha == null ? DEFAULT_ALPHA : alpha;
        nPermutations = nPermutations == null ? DEFAULT_N_PERMUTATIONS : nPermutations;
        nBaseline = Number(nBaseline);
        nAblated = Number(nAblated);
        nFoci = Number(nFoci);
        var minP = minAchievablePvalue(nBaseline, nAblated, nPermutations);
        var nAssignments = nLabelAssignments(nBaseline, nAblated);
        var exact = usesExactEnumeration(nBaseline, nAblated, nPermutations);
        var testType = exact ? 'exact' : 'sampled';
        if (nFoci <= 0) {
            return {
                min_p: minP,
                threshold: null,
                can_reach_significance: null,
                n_foci: nFoci,
                exact: exact,
                n_assignments: nAssignments,
                test_type: testType
            };
        }
        var threshold = alpha / nFoci;
        return {
            min_p: minP,
            threshold: threshold,
            can_reach_significance: minP <= threshold,
            n_foci: nFoci,
            exact: exact,
            n_assignments: nAssignments,
            test_type: testType
        };
    }

    function stochasticTemperatureMessage(temperature) {
        var C = copy();
        if (C.STOCHASTIC_TEMPERATURE_TEMPLATE) {
            return C.STOCHASTIC_TEMPERATURE_TEMPLATE.replace('{temperature}', String(temperature));
        }
        return (
            'Permutation test requires output stochasticity: temperature must be > 0 (got ' +
            temperature +
            '). Repeated samples of the same prompt must be allowed to vary; set temperature above 0.'
        );
    }

    function temperatureRejection(temperature) {
        if (temperature === null || temperature === undefined || temperature === '') {
            return stochasticTemperatureMessage(temperature);
        }
        var t = Number(temperature);
        if (!Number.isFinite(t) || t <= 0) {
            return stochasticTemperatureMessage(Number.isFinite(t) ? t : temperature);
        }
        return null;
    }

    function suggestedSampleSizes(temperature) {
        var t = Number(temperature);
        if (t > 1.0) return { n_baseline: 15, n_ablated: 8 };
        return { n_baseline: 10, n_ablated: 5 };
    }

    function clampNBaseline(value) {
        var n = parseInt(value, 10);
        if (!Number.isFinite(n)) n = DEFAULT_N_BASELINE;
        return Math.max(N_BASELINE_MIN, Math.min(N_BASELINE_MAX, n));
    }

    function clampNAblated(value) {
        var n = parseInt(value, 10);
        if (!Number.isFinite(n)) n = DEFAULT_N_ABLATED;
        return Math.max(N_ABLATED_MIN, Math.min(N_ABLATED_MAX, n));
    }

    function modelCallCount(nBaseline, nAblated, nAttributableFoci) {
        return Number(nBaseline) + Number(nAblated) * Number(nAttributableFoci);
    }

    function countPreviewAttributable(foci) {
        if (!foci || !foci.length) return 0;
        var n = 0;
        for (var i = 0; i < foci.length; i++) {
            if (!foci[i].is_dynamic) n += 1;
        }
        return n;
    }

    function formatCostLine(nBaseline, nAblated, nAttributableFoci, fociTagged) {
        var C = copy();
        if (!fociTagged) {
            return (C.COST_LINE_FORMULA || 'This experiment will make {n_baseline} + {n_ablated} × n_foci model calls.')
                .replace('{n_baseline}', String(nBaseline))
                .replace('{n_ablated}', String(nAblated));
        }
        var nCalls = modelCallCount(nBaseline, nAblated, nAttributableFoci || 0);
        return (C.COST_LINE_COUNTED || 'This experiment will make {n_calls} model calls.')
            .replace('{n_calls}', String(nCalls));
    }

    function formatPermutationDisclosure(nBaseline, nAblated, nPermutations) {
        var C = copy();
        nPermutations = nPermutations == null ? DEFAULT_N_PERMUTATIONS : nPermutations;
        if (usesExactEnumeration(nBaseline, nAblated, nPermutations)) {
            var nAssign = nLabelAssignments(nBaseline, nAblated);
            return (C.EXACT_DISCLOSURE_TEMPLATE ||
                'Significance: exact test ({n_assignments} enumerated group assignments)')
                .replace('{n_assignments}', nAssign.toLocaleString('en-US'));
        }
        var se = monteCarloPvalueSe(0.05, nPermutations);
        return (C.SAMPLED_DISCLOSURE_TEMPLATE ||
            'Significance: 10,000 sampled permutations (p-value margin ~±{se})')
            .replace('{se}', se.toFixed(3));
    }

    function formatPowerPreviewLine(nBaseline, nAblated, nFoci, alpha, nPermutations) {
        var C = copy();
        var info = powerGuardrail(nBaseline, nAblated, nFoci, alpha, nPermutations);
        if (info.can_reach_significance === null) return null;
        if (info.can_reach_significance) {
            return C.POWER_OK || 'This design can detect effects at your significance level';
        }
        return (C.POWER_FAIL ||
            'With {n_foci} foci, this design cannot reach significance after correction. Increase samples.')
            .replace('{n_foci}', String(nFoci));
    }

    function formatTemperature(t) {
        return Number(t).toFixed(1);
    }

    function formatAblationLoading(temperature, nBaseline, nAblated, nFoci) {
        var C = copy();
        nFoci = Number(nFoci) || 0;
        var fociWord = nFoci === 1 ? 'focus' : 'foci';
        return (C.ABLATION_LOADING_TEMPLATE ||
            'Running ablation analysis at temperature {temperature}: {n_baseline} baseline samples and {n_ablated} ablated samples for each of {n_foci} {foci_word} ({n_calls} model calls). This may take several minutes.')
            .replace('{temperature}', formatTemperature(temperature))
            .replace('{n_baseline}', String(nBaseline))
            .replace('{n_ablated}', String(nAblated))
            .replace('{n_foci}', String(nFoci))
            .replace('{foci_word}', fociWord)
            .replace('{n_calls}', String(modelCallCount(nBaseline, nAblated, nFoci)));
    }

    function formatBatchLoading(nPairs, temperature, nBaseline, nAblated) {
        var C = copy();
        nPairs = Number(nPairs) || 0;
        var pairsWord = nPairs === 1 ? 'pair' : 'pairs';
        return (C.BATCH_LOADING_TEMPLATE ||
            'Running batch analysis on {n_pairs} {pairs_word} at temperature {temperature}: {n_baseline} baseline samples and {n_ablated} ablated samples per focus per pair. This may take a long time.')
            .replace('{n_pairs}', String(nPairs))
            .replace('{pairs_word}', pairsWord)
            .replace('{temperature}', formatTemperature(temperature))
            .replace('{n_baseline}', String(nBaseline))
            .replace('{n_ablated}', String(nAblated));
    }

    function formatRunHeader(temperature, nBaseline, nAblated, testType) {
        var C = copy();
        var kind = testType === 'exact' ? 'exact' : 'sampled';
        return (C.RUN_HEADER_TEMPLATE ||
            'Run at temperature {t}, {n_baseline}+{n_ablated} samples per focus, {test_type} test.')
            .replace('{t}', formatTemperature(temperature))
            .replace('{n_baseline}', String(nBaseline))
            .replace('{n_ablated}', String(nAblated))
            .replace('{test_type}', kind);
    }

    function formatRunHeaderFromData(data) {
        data = data || {};
        var nBaseline = Number(data.n_baseline || data.num_baseline_samples || 10);
        var nAblated = Number(data.n_ablated || 5);
        var nPerm = Number(data.n_permutations || DEFAULT_N_PERMUTATIONS);
        var temperature = data.temperature != null ? data.temperature : DEFAULT_TEMPERATURE;
        var testType = data.test_type || testTypeForDesign(nBaseline, nAblated, nPerm);
        return formatRunHeader(temperature, nBaseline, nAblated, testType);
    }

    function readStateFromRoot(root) {
        var tempEl = root.querySelector('.exp-temperature');
        var baseEl = root.querySelector('.exp-n-baseline');
        var ablEl = root.querySelector('.exp-n-ablated');
        return {
            temperature: tempEl ? Number(tempEl.value) : DEFAULT_TEMPERATURE,
            n_baseline: baseEl ? clampNBaseline(baseEl.value) : DEFAULT_N_BASELINE,
            n_ablated: ablEl ? clampNAblated(ablEl.value) : DEFAULT_N_ABLATED
        };
    }

    var sharedState = {
        temperature: DEFAULT_TEMPERATURE,
        n_baseline: DEFAULT_N_BASELINE,
        n_ablated: DEFAULT_N_ABLATED
    };

    function fociForRoot(root) {
        var source = root.getAttribute('data-foci-source');
        if (source === 'batch') return global.batchFoci || [];
        return global.foci || [];
    }

    function refreshRoot(root) {
        var C = copy();
        var state = sharedState;
        var tempEl = root.querySelector('.exp-temperature');
        var baseEl = root.querySelector('.exp-n-baseline');
        var ablEl = root.querySelector('.exp-n-ablated');
        if (tempEl && document.activeElement !== tempEl) tempEl.value = formatTemperature(state.temperature);
        if (baseEl && document.activeElement !== baseEl) baseEl.value = String(state.n_baseline);
        if (ablEl && document.activeElement !== ablEl) ablEl.value = String(state.n_ablated);

        var help = root.querySelector('.exp-temperature-help');
        if (help) help.textContent = C.TEMPERATURE_HELP || '';
        var high = root.querySelector('.exp-temperature-high');
        if (high) {
            high.textContent = C.TEMPERATURE_HIGH || '';
            if (Number(state.temperature) >= 1.0) high.classList.remove('hidden');
            else high.classList.add('hidden');
        }
        var tempErr = root.querySelector('.exp-temperature-error');
        var rejection = temperatureRejection(state.temperature);
        if (tempErr) {
            if (rejection) {
                tempErr.textContent = rejection;
                tempErr.classList.remove('hidden');
            } else {
                tempErr.textContent = '';
                tempErr.classList.add('hidden');
            }
        }

        var foci = fociForRoot(root);
        var fociTagged = !!(foci && foci.length);
        var nAttr = countPreviewAttributable(foci);
        var costEl = root.querySelector('.exp-cost-line');
        if (costEl) {
            costEl.textContent = formatCostLine(state.n_baseline, state.n_ablated, nAttr, fociTagged);
        }

        var sug = suggestedSampleSizes(state.temperature);
        var chip = root.querySelector('.exp-suggestion-chip');
        if (chip) {
            chip.textContent = (C.SUGGESTION_LABEL || 'suggested for this temperature') +
                ' (' + sug.n_baseline + ' / ' + sug.n_ablated + ')';
            chip.setAttribute('title', C.SUGGESTION_TOOLTIP || '');
            chip.setAttribute('aria-label', (C.SUGGESTION_TOOLTIP || '') + ' Apply ' + sug.n_baseline + ' baseline and ' + sug.n_ablated + ' ablated.');
            chip.dataset.nBaseline = String(sug.n_baseline);
            chip.dataset.nAblated = String(sug.n_ablated);
        }
        var tip = root.querySelector('.exp-suggestion-tooltip');
        if (tip) tip.textContent = C.SUGGESTION_TOOLTIP || '';

        var powerEl = root.querySelector('.exp-power-line');
        if (powerEl) {
            var line = formatPowerPreviewLine(state.n_baseline, state.n_ablated, nAttr);
            if (!line) {
                powerEl.textContent = '';
                powerEl.className = 'exp-power-line hidden';
            } else {
                powerEl.textContent = line;
                powerEl.className = 'exp-power-line ' +
                    (line === (C.POWER_OK || 'This design can detect effects at your significance level')
                        ? 'exp-power-ok'
                        : 'exp-power-fail');
            }
        }

        var disc = root.querySelector('.exp-permutation-disclosure');
        if (disc) {
            disc.textContent = formatPermutationDisclosure(state.n_baseline, state.n_ablated);
        }
    }

    function refreshAll() {
        var roots = document.querySelectorAll('.experiment-config');
        for (var i = 0; i < roots.length; i++) refreshRoot(roots[i]);
    }

    function applyState(partial) {
        if (partial.temperature != null) sharedState.temperature = Number(partial.temperature);
        if (partial.n_baseline != null) sharedState.n_baseline = clampNBaseline(partial.n_baseline);
        if (partial.n_ablated != null) sharedState.n_ablated = clampNAblated(partial.n_ablated);
        refreshAll();
    }

    function getState() {
        return {
            temperature: sharedState.temperature,
            n_baseline: sharedState.n_baseline,
            n_ablated: sharedState.n_ablated,
            n_permutations: DEFAULT_N_PERMUTATIONS,
            test_type: testTypeForDesign(sharedState.n_baseline, sharedState.n_ablated)
        };
    }

    function bind() {
        if (typeof document === 'undefined') return;
        var roots = document.querySelectorAll('.experiment-config');
        for (var i = 0; i < roots.length; i++) {
            (function (root) {
                root.addEventListener('input', function (e) {
                    var t = e.target;
                    if (t.classList.contains('exp-temperature')) {
                        sharedState.temperature = Number(t.value);
                    } else if (t.classList.contains('exp-n-baseline')) {
                        sharedState.n_baseline = clampNBaseline(t.value);
                    } else if (t.classList.contains('exp-n-ablated')) {
                        sharedState.n_ablated = clampNAblated(t.value);
                    }
                    refreshAll();
                });
                root.addEventListener('change', function (e) {
                    var t = e.target;
                    if (t.classList.contains('exp-n-baseline')) {
                        t.value = String(clampNBaseline(t.value));
                        sharedState.n_baseline = clampNBaseline(t.value);
                    }
                    if (t.classList.contains('exp-n-ablated')) {
                        t.value = String(clampNAblated(t.value));
                        sharedState.n_ablated = clampNAblated(t.value);
                    }
                    refreshAll();
                });
                var chip = root.querySelector('.exp-suggestion-chip');
                if (chip && !chip._bound) {
                    chip._bound = true;
                    chip.addEventListener('click', function () {
                        var sug = suggestedSampleSizes(sharedState.temperature);
                        sharedState.n_baseline = sug.n_baseline;
                        sharedState.n_ablated = sug.n_ablated;
                        refreshAll();
                    });
                }
            })(roots[i]);
        }
        refreshAll();
    }

    var api = {
        DEFAULT_N_PERMUTATIONS: DEFAULT_N_PERMUTATIONS,
        nLabelAssignments: nLabelAssignments,
        minAchievablePvalue: minAchievablePvalue,
        usesExactEnumeration: usesExactEnumeration,
        testTypeForDesign: testTypeForDesign,
        monteCarloPvalueSe: monteCarloPvalueSe,
        powerGuardrail: powerGuardrail,
        temperatureRejection: temperatureRejection,
        stochasticTemperatureMessage: stochasticTemperatureMessage,
        suggestedSampleSizes: suggestedSampleSizes,
        clampNBaseline: clampNBaseline,
        clampNAblated: clampNAblated,
        modelCallCount: modelCallCount,
        countPreviewAttributable: countPreviewAttributable,
        formatCostLine: formatCostLine,
        formatPermutationDisclosure: formatPermutationDisclosure,
        formatPowerPreviewLine: formatPowerPreviewLine,
        formatAblationLoading: formatAblationLoading,
        formatBatchLoading: formatBatchLoading,
        formatRunHeader: formatRunHeader,
        formatRunHeaderFromData: formatRunHeaderFromData,
        getState: getState,
        applyState: applyState,
        refreshAll: refreshAll,
        bind: bind
    };

    global.FocalPromptExperiment = api;
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = api;
    }
})(typeof window !== 'undefined' ? window : global);
