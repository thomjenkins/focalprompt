/**
 * Results presentation for ablation / permutation output.
 * Copy strings come from Flask (window.FOCALPROMPT_COPY). Do not hardcode
 * verdict, caution, excluded, power-banner, or methods prose here.
 */
(function (global) {
    'use strict';

    var DEFAULT_ALPHA = 0.05;
    var DEFAULT_N_PERMUTATIONS = 10000;

    function getCopy() {
        if (global.FOCALPROMPT_COPY) {
            return global.FOCALPROMPT_COPY;
        }
        var el = document.getElementById('focalprompt-copy');
        if (el && el.textContent) {
            global.FOCALPROMPT_COPY = JSON.parse(el.textContent);
            return global.FOCALPROMPT_COPY;
        }
        throw new Error('FocalPrompt results copy payload is missing.');
    }

    function escapeHtml(text) {
        if (text === null || text === undefined) {
            return '';
        }
        return String(text)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
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

    function minAchievablePvalue(nBaseline, nAblated, nPermutations) {
        nPermutations = nPermutations == null ? DEFAULT_N_PERMUTATIONS : nPermutations;
        var nExact = combinations(nBaseline + nAblated, nAblated);
        if (nExact === 0) return 1;
        if (nExact <= nPermutations) return 1 / nExact;
        return 1 / (1 + nPermutations);
    }

    function formatQValue(q) {
        if (q === null || q === undefined || Number.isNaN(Number(q))) return 'n/a';
        var n = Number(q);
        if (n === 0) return '0';
        return formatG(n, 3);
    }

    function formatEffectSize(z) {
        if (z === null || z === undefined || Number.isNaN(Number(z))) return 'n/a';
        var n = Number(z);
        if (!Number.isFinite(n)) return 'n/a';
        return n.toFixed(1);
    }

    function effectSizeBand(z) {
        if (z === null || z === undefined || Number.isNaN(Number(z))) return null;
        var n = Number(z);
        if (!Number.isFinite(n)) return null;
        var absZ = Math.abs(n);
        if (absZ > 5) return 'large';
        if (absZ >= 2) return 'moderate';
        return 'small';
    }

    function effectSizeQualifier(z) {
        var band = effectSizeBand(z);
        if (!band) return null;
        return band + ' effect (z = ' + formatEffectSize(z) + ')';
    }

    function significantStatsLine(q, z) {
        return '(q = ' + formatQValue(q) + ', effect size = ' + formatEffectSize(z) + ')';
    }

    function notSignificantStatsLine(q) {
        return '(q = ' + formatQValue(q) + ')';
    }

    function formatPowerBanner(nBaseline, nAblated, nFoci, minP, nPermutations) {
        var C = getCopy();
        if (minP == null) {
            minP = minAchievablePvalue(nBaseline, nAblated, nPermutations);
        }
        var minTxt = formatG(minP, 6);
        return C.POWER_BANNER_TEMPLATE
            .replace('{n_baseline}', String(nBaseline))
            .replace('{n_ablated}', String(nAblated))
            .replace('{min_p}', minTxt)
            .replace('{n_foci}', String(nFoci));
    }

    function formatG(value, precision) {
        var n = Number(value);
        if (!Number.isFinite(n)) return String(value);
        var txt = n.toPrecision(precision);
        if (txt.indexOf('e') !== -1) {
            return txt.replace(/\.?0+e/, 'e').replace('e+', 'e');
        }
        if (txt.indexOf('.') !== -1) {
            txt = txt.replace(/0+$/, '').replace(/\.$/, '');
        }
        return txt;
    }

    function formatOverlapNames(overlapWith) {
        if (!overlapWith || !overlapWith.length) return '';
        var names = [];
        for (var i = 0; i < overlapWith.length; i++) {
            var item = overlapWith[i];
            if (item && typeof item === 'object') {
                var name = item.focus || item.focus_name || item.name;
                if (name) names.push(String(name));
            } else if (item) {
                names.push(String(item));
            }
        }
        return names.join('; ');
    }

    function formatAffectedOverlappingWarning(focus) {
        var C = getCopy();
        var affected = focus.affected_overlapping_foci || [];
        if (!affected.length && !focus.has_overlap) return null;
        var bits = [];
        var extreme = false;
        for (var i = 0; i < affected.length; i++) {
            var item = affected[i];
            if (!item || typeof item !== 'object') continue;
            var name = item.focus || item.focus_name || 'another focus';
            var pct = Number(item.overlap_removed_pct);
            if (!Number.isFinite(pct) || pct <= 0) continue;
            if (pct >= 80) extreme = true;
            bits.push(name + ' (' + pct + '%)');
        }
        if (!bits.length && !focus.has_overlap) return null;
        var warn = C.OVERLAP_ABLATION_WARNING || (
            'This intervention also removed overlapping text from other foci. ' +
            'Revealed influences should not be interpreted as independent or additive.'
        );
        if (extreme) {
            warn = 'High overlap (>80% of a neighbouring focus was also removed). ' + warn;
        }
        if (bits.length) warn += ' Also removed: ' + bits.join('; ') + '.';
        return warn;
    }

    function excludedExplanation(focus) {
        var C = getCopy();
        var reason = focus.reason;
        if (reason === 'dynamic_slot') return C.EXCLUDED_DYNAMIC_SLOT;
        if (reason === 'overlap') {
            var names = formatOverlapNames(focus.overlap_with);
            if (names) return C.EXCLUDED_OVERLAP + ' Overlaps with: ' + names + '.';
            return C.EXCLUDED_OVERLAP;
        }
        if (focus.verified === false || reason === 'unverified') {
            return C.EXCLUDED_UNVERIFIED;
        }
        if (focus.attributable === false) {
            return C.EXCLUDED_UNVERIFIED;
        }
        return null;
    }

    function isNearThreshold(q, alpha) {
        if (q === null || q === undefined || Number.isNaN(Number(q))) return false;
        alpha = alpha == null ? DEFAULT_ALPHA : alpha;
        var n = Number(q);
        return n > alpha && n <= 2 * alpha;
    }

    function focusName(item, fallback) {
        return item.focus || item.focus_name || fallback || 'Untitled focus';
    }

    function asScoreList(influenceScores) {
        if (!influenceScores) return [];
        if (Array.isArray(influenceScores)) return influenceScores.slice();
        var rows = [];
        Object.keys(influenceScores).forEach(function (name) {
            var payload = influenceScores[name];
            var row = payload && typeof payload === 'object' ? Object.assign({}, payload) : { value: payload };
            if (!row.focus) row.focus = name;
            rows.push(row);
        });
        return rows;
    }

    function enrichFocusRecords(records, data) {
        var list = (data && data.foci_list) || [];
        return records.map(function (rec, i) {
            var copy = Object.assign({}, rec);
            if (copy.focus_index != null && copy.focus_index !== undefined) {
                return copy;
            }
            var name = focusName(rec);
            for (var j = 0; j < list.length; j++) {
                if (focusName(list[j], 'Focus ' + (j + 1)) === name) {
                    copy.focus_index = j;
                    return copy;
                }
            }
            copy.focus_index = i;
            return copy;
        });
    }

    function collectFocusRecords(data) {
        var ablation = data.ablation_results || [];
        var scores = asScoreList(data.influence_scores);
        var scoresByName = {};
        scores.forEach(function (s, i) {
            scoresByName[focusName(s, String(i))] = s;
        });
        var records = [];
        var seen = {};
        ablation.forEach(function (row, i) {
            var name = focusName(row, 'Focus ' + (i + 1));
            var merged = Object.assign({}, row, scoresByName[name] || {}, { focus: name });
            if (merged.focus_index == null || merged.focus_index === undefined) {
                merged.focus_index = row.focus_index != null ? row.focus_index : i;
            }
            records.push(merged);
            seen[name] = true;
        });
        scores.forEach(function (score, i) {
            var name = focusName(score, 'Focus ' + (i + 1));
            if (!seen[name]) {
                var row = Object.assign({}, score);
                if (row.focus_index == null || row.focus_index === undefined) {
                    row.focus_index = i;
                }
                records.push(row);
                seen[name] = true;
            }
        });
        return enrichFocusRecords(records, data);
    }

    function nFociTested(data) {
        var scores = asScoreList(data.influence_scores);
        if (scores.length) return scores.length;
        return collectFocusRecords(data).filter(function (r) {
            return r.attributable && !excludedExplanation(r);
        }).length;
    }

    function formatP(value) {
        if (value === null || value === undefined) return 'n/a';
        var n = Number(value);
        if (Number.isNaN(n)) return escapeHtml(value);
        return formatG(n, 6);
    }

    function nullDecilesHtml(deciles) {
        if (!deciles) return '<p>No null deciles reported.</p>';
        var keys = Object.keys(deciles);
        keys.sort(function (a, b) {
            return Number(a) - Number(b);
        });
        var rows = keys.map(function (k) {
            return '<tr><th>' + escapeHtml(k) + '</th><td>' + formatP(deciles[k]) + '</td></tr>';
        }).join('');
        return '<table class="null-deciles"><tbody>' + rows + '</tbody></table>';
    }

    function renderStatisticalDetail(focus) {
        var tObs = focus.t_obs != null ? focus.t_obs : focus.influence;
        return (
            '<details class="focus-verdict-details">' +
            '<summary>Statistical detail</summary>' +
            '<dl class="focus-stat-list">' +
            '<dt>t_obs</dt><dd>' + formatP(tObs) + '</dd>' +
            '<dt>p_value</dt><dd>' + formatP(focus.p_value) + '</dd>' +
            '<dt>q_value</dt><dd>' + formatP(focus.q_value) + '</dd>' +
            '</dl>' +
            '<p class="focus-stat-label">Null deciles</p>' +
            nullDecilesHtml(focus.null_deciles) +
            '</details>'
        );
    }


    function differenceBand(score) {
        var s = Number(score);
        if (Number.isNaN(s)) return 'not assessed';
        if (s <= 0) return 'None';
        if (s <= 2) return 'Weak';
        if (s <= 3) return 'Moderate';
        return 'Strong';
    }

    function renderShuffleRobustness(focus, data) {
        if (excludedExplanation(focus)) return '';
        if (focus.attributable === false) return '';
        var C = getCopy();
        var idx = focus.focus_index;
        if (idx == null && data) {
            var enriched = enrichFocusRecords([focus], data)[0];
            idx = enriched.focus_index;
        }
        if (idx == null) idx = 0;
        var focusKey = focusName(focus);
        var sr = focus.shuffle_robustness;
        var html = (
            '<div class="shuffle-robustness" data-focus-index="' + escapeHtml(String(idx)) + '">' +
            '<p class="shuffle-robustness-title"><strong>' +
            escapeHtml(C.SHUFFLE_ROBUSTNESS_TITLE || 'Shuffle-order robustness check') + '</strong></p>' +
            '<p class="shuffle-robustness-explainer">' +
            escapeHtml(C.SHUFFLE_ROBUSTNESS_EXPLAINER || '') + '</p>'
        );
        if (sr && sr.status === 'running') {
            html += '<p class="shuffle-robustness-status">Running shuffle re-test…</p>';
        } else if (sr && sr.status === 'failed') {
            html += '<p class="shuffle-robustness-error">' + escapeHtml(sr.error || 'Failed') + '</p>';
        } else if (sr && sr.t_obs != null) {
            var sigOrig = focus.is_significant === true ? 'significant' : (
                focus.is_significant === false ? 'not significant' : 'n/a'
            );
            var sigShuf = sr.is_significant_uncorrected ? 'significant (uncorrected)' : 'not significant (uncorrected)';
            var robust = (focus.is_significant === sr.is_significant_uncorrected);
            html += '<div class="shuffle-robustness-compare">';
            html += '<p><strong>Original (subtractive):</strong> ' + escapeHtml(sigOrig) +
                ' (q=' + formatQValue(focus.q_value) + ', T<sub>obs</sub>=' + formatP(focus.t_obs) + ')</p>';
            html += '<p><strong>Shuffled remaining order:</strong> ' + escapeHtml(sigShuf) +
                ' (p=' + formatP(sr.p_value) + ', T<sub>obs</sub>=' + formatP(sr.t_obs) + ')</p>';
            html += '<p class="shuffle-robustness-verdict' + (robust ? ' robust-yes' : ' robust-no') + '">' +
                (robust
                    ? 'Significance verdict matches under shuffled hierarchy.'
                    : 'Significance verdict differs under shuffled hierarchy — review both runs.') +
                '</p>';
            if (sr.remaining_foci_shuffled_order && sr.remaining_foci_shuffled_order.length) {
                html += '<p class="shuffle-robustness-order"><em>Remaining order used:</em> ' +
                    escapeHtml(sr.remaining_foci_shuffled_order.join(' → ')) + '</p>';
            }
            if (sr.order_changed === false) {
                html += '<p class="shuffle-robustness-note">' +
                    escapeHtml(C.SHUFFLE_ROBUSTNESS_ORDER_UNCHANGED || '') + '</p>';
            }
            html += '</div>';
        }
        html += (
            '<button type="button" class="btn btn-primary btn-shuffle-robustness" ' +
            'data-focus-index="' + escapeHtml(String(idx)) + '" ' +
            'data-focus="' + escapeHtml(focusKey) + '">' +
            '🔀 ' + escapeHtml(C.SHUFFLE_ROBUSTNESS_BUTTON || 'Re-test with shuffled remaining order') +
            '</button></div>'
        );
        return html;
    }

    function renderEvidenceLenses(focus) {
        var C = getCopy();
        var sem = focus.semantic_perturbation || {};
        var llm = focus.llm_behavioral_difference || {};
        var hum = focus.human_behavioral_difference || {};
        var rec = focus.review_recommendation || {};
        var sig = sem.is_significant !== undefined ? sem.is_significant : focus.is_significant;
        var q = sem.q_value !== undefined ? sem.q_value : focus.q_value;
        var qTxt = formatQValue(q);
        var semLine;
        if (sig === true) semLine = 'Detectable semantic perturbation (q = ' + qTxt + ')';
        else if (sig === false) semLine = 'No detectable semantic perturbation (q = ' + qTxt + ')';
        else semLine = 'Semantic perturbation not assessed';

        var llmStatus = llm.status || 'not_run';
        var llmLine;
        if (llmStatus === 'complete') {
            var band = differenceBand(llm.overall_difference_score);
            var dims = llm.dimensions || {};
            var dimBits = [];
            ['structure_format', 'instruction_compliance', 'content'].forEach(function (k) {
                if (dims[k]) dimBits.push(k.replace(/_/g, ' ') + ': ' + dims[k] + '/5');
            });
            llmLine = band;
            if (dimBits.length) llmLine += ' — ' + dimBits.join('; ');
            if (llm.summary) llmLine += '. ' + llm.summary;
            llmLine = escapeHtml(llmLine);
        } else if (llmStatus === 'failed') {
            llmLine = escapeHtml('Failed: ' + (llm.error || 'judge error'));
        } else {
            llmLine = 'Not run';
        }

        var humStatus = hum.status || 'not_run';
        var humLine;
        if (humStatus === 'complete') {
            var hBand = differenceBand(hum.overall_difference_score);
            if (hum.material_behavioral_difference === true) humLine = 'Difference confirmed (' + hBand + ')';
            else if (hum.material_behavioral_difference === false) humLine = 'No material difference (' + hBand + ')';
            else humLine = 'Uncertain (' + hBand + ')';
            if (hum.notes) humLine += '. ' + hum.notes;
            humLine = escapeHtml(humLine);
        } else if (humStatus === 'pending') {
            humLine = 'Pending human review';
        } else {
            humLine = 'Not run';
        }

        var focusKey = escapeHtml(focusName(focus));
        var recommend = '';
        if (rec.review_recommended) {
            var reasons = (rec.reasons || []).join(', ');
            recommend = '<p class="review-recommended">Review recommended'
                + (reasons ? ' (' + escapeHtml(reasons) + ')' : '')
                + ' — advisory only.</p>';
        }

        return (
            '<div class="evidence-lenses" data-focus="' + focusKey + '">' +
            '<p class="multi-lens-explainer">' + escapeHtml(C.MULTI_LENS_EXPLAINER || '') + '</p>' +
            '<div class="lens-row"><strong>' + escapeHtml(C.LENS_SEMANTIC_TITLE || 'Semantic perturbation') + ':</strong> ' + escapeHtml(semLine) + '</div>' +
            '<div class="lens-row"><strong>' + escapeHtml(C.LENS_LLM_TITLE || 'LLM behavioral difference') + ':</strong> ' + llmLine + '</div>' +
            '<div class="lens-row"><strong>' + escapeHtml(C.LENS_HUMAN_TITLE || 'Human-observed difference') + ':</strong> ' + humLine + '</div>' +
            recommend +
            '<div class="behavioral-review-actions">' +
            '<button type="button" class="btn btn-outline btn-review-llm-diff" data-focus="' + focusKey + '">' +
            escapeHtml(C.REVIEW_BEHAVIORAL_DIFFERENCE || 'Review behavioral difference') + ' (LLM)</button> ' +
            '<button type="button" class="btn btn-outline btn-review-human-diff" data-focus="' + focusKey + '">' +
            'Record human difference review</button>' +
            '</div></div>'
        );
    }

    function renderStandardizedEffectNote(focus) {
        var note = focus && focus.standardized_effect_note;
        if (!note) return '';
        return '<p class="focus-effect-degenerate" title="' + escapeHtml(note) + '">' +
            escapeHtml(note) + '</p>';
    }

    function renderFocusCard(focus, alpha, data) {
        var C = getCopy();
        alpha = alpha == null ? DEFAULT_ALPHA : alpha;
        var name = focusName(focus);
        var excluded = excludedExplanation(focus);
        var promptEmpty = !!focus.prompt_empty;
        var classes = ['focus-verdict-card'];
        var body = ['<h4 class="focus-verdict-name">' + escapeHtml(name) + '</h4>'];

        if (excluded) {
            classes.push('excluded');
            body.push('<p class="focus-verdict-primary">' + escapeHtml(excluded) + '</p>');
        } else if (focus.is_significant === true) {
            classes.push('significant');
            var z = focus.standardized_effect;
            body.push('<p class="focus-verdict-primary">' + escapeHtml(C.VERDICT_SIGNIFICANT) + '</p>');
            body.push('<p class="focus-verdict-stats">' + escapeHtml(significantStatsLine(focus.q_value, z)) + '</p>');
            var qualifier = effectSizeQualifier(z);
            if (qualifier) {
                body.push('<p class="focus-effect-qualifier">' + escapeHtml(qualifier) + '</p>');
            }
            var effectNote = renderStandardizedEffectNote(focus);
            if (effectNote) {
                body.push(effectNote);
            }
            if (promptEmpty) {
                body.push('<p class="focus-prompt-empty">' + escapeHtml(C.PROMPT_EMPTY_NOTE) + '</p>');
            }
            body.push(renderStatisticalDetail(focus));
        } else {
            classes.push('not-significant');
            body.push('<p class="focus-verdict-primary">' + escapeHtml(C.VERDICT_NOT_SIGNIFICANT) + '</p>');
            body.push('<p class="focus-verdict-stats">' + escapeHtml(notSignificantStatsLine(focus.q_value)) + '</p>');
            body.push('<p class="focus-verdict-caution">' + escapeHtml(C.NON_SIGNIFICANT_CAUTION) + '</p>');
            if (isNearThreshold(focus.q_value, alpha)) {
                body.push('<p class="focus-near-threshold">' + escapeHtml(C.NEAR_THRESHOLD_HINT) + '</p>');
            }
            if (promptEmpty) {
                body.push('<p class="focus-prompt-empty">' + escapeHtml(C.PROMPT_EMPTY_NOTE) + '</p>');
            }
            body.push(renderStatisticalDetail(focus));
        }

        if (!excluded) {
            var overlapWarn = formatAffectedOverlappingWarning(focus);
            if (overlapWarn) {
                body.push('<p class="focus-overlap-warning" role="status">' + escapeHtml(overlapWarn) + '</p>');
            }
            body.push(renderFocusAblationStability(focus, data));
            body.push(renderShuffleRobustness(focus, data));
            body.push(renderEvidenceLenses(focus));
        }

        return '<article class="' + classes.join(' ') + '">' + body.join('') + '</article>';
    }

    function renderDefinition() {
        return '<p class="results-definition">' + escapeHtml(getCopy().DEFINITION) + '</p>';
    }

    function renderRunHeader(data) {
        var text;
        if (global.FocalPromptExperiment && global.FocalPromptExperiment.formatRunHeaderFromData) {
            text = global.FocalPromptExperiment.formatRunHeaderFromData(data);
        } else {
            var nB = data.n_baseline || data.num_baseline_samples || 10;
            var nA = data.n_ablated || 5;
            var t = data.temperature != null ? data.temperature : 0.7;
            var kind = data.test_type || 'sampled';
            text = 'Run at temperature ' + Number(t).toFixed(1) + ', ' + nB + '+' + nA +
                ' samples per focus, ' + kind + ' test.';
        }
        return '<p class="results-run-header">' + escapeHtml(text) + '</p>';
    }

    function renderMethodsPanel() {
        var C = getCopy();
        var paragraphs = C.METHODS_PANEL.split(/\n\n/).filter(function (p) { return p.trim(); });
        var inner = paragraphs.map(function (p) {
            return '<p>' + escapeHtml(p.trim()) + '</p>';
        }).join('');
        return (
            '<details class="methods-panel">' +
            '<summary>' + escapeHtml(C.METHODS_PANEL_TITLE) + '</summary>' +
            '<div class="methods-panel-body">' + inner + '</div>' +
            '</details>'
        );
    }

    function renderPowerBannerHtml(data) {
        if (!data.power_warning) return '';
        var nBaseline = Number(data.n_baseline || data.num_baseline_samples || 10);
        var nAblated = Number(data.n_ablated || 5);
        var nPerm = Number(data.n_permutations || DEFAULT_N_PERMUTATIONS);
        var nFoci = nFociTested(data);
        var text = formatPowerBanner(nBaseline, nAblated, nFoci, null, nPerm);
        return '<div class="results-power-banner" role="status">' + escapeHtml(text) + '</div>';
    }

    function fmtDist(v) {
        if (v == null || Number.isNaN(Number(v))) return '—';
        return Number(v).toFixed(4);
    }

    function renderBaselineStabilityHtml(data) {
        var bs = data && data.baseline_stability;
        if (!bs) return '';
        var C = getCopy();
        var cls = (bs.classification && bs.classification.label) || 'insufficient_samples';
        var uiLabel = (bs.classification && bs.classification.ui_label) || cls;
        var html = '<section class="baseline-stability-panel" data-label="' + escapeHtml(cls) + '">';
        html += '<h3>' + escapeHtml(C.BASELINE_STABILITY_TITLE || 'Baseline stability / noise') + '</h3>';
        html += '<p class="info-text">' + escapeHtml(
            C.BASELINE_STABILITY_DISCLAIMER || bs.disclaimer || ''
        ) + '</p>';
        html += '<p class="baseline-stability-label"><strong>' + escapeHtml(uiLabel) + '</strong></p>';
        (bs.warnings || []).forEach(function (w) {
            html += '<p class="baseline-stability-warning" role="status">' + escapeHtml(w) + '</p>';
        });
        html += '<ul class="baseline-stability-metrics">';
        html += '<li>Mean pairwise cosine distance: ' + escapeHtml(fmtDist(bs.mean_pairwise_cosine_distance)) + '</li>';
        html += '<li>Median pairwise cosine distance: ' + escapeHtml(fmtDist(bs.median_pairwise_cosine_distance)) + '</li>';
        html += '<li>p95 pairwise cosine distance: ' + escapeHtml(fmtDist(bs.p95_pairwise_cosine_distance)) + '</li>';
        html += '<li>Mean distance from centroid: ' + escapeHtml(fmtDist(bs.mean_distance_from_centroid)) + '</li>';
        html += '<li>p95 distance from centroid: ' + escapeHtml(fmtDist(bs.p95_distance_from_centroid)) + '</li>';
        html += '</ul>';
        var multi = bs.multimodality || {};
        if (multi.potentially_multimodal) {
            html += '<p class="baseline-stability-multimodal"><em>Advisory multimodality flag</em> — ';
            html += escapeHtml(multi.note || 'PC1 median-split suggests possible distinct modes.') + '</p>';
        } else if (multi.note) {
            html += '<p class="info-text" style="font-size:0.9em">' + escapeHtml(multi.note) + '</p>';
        }
        html += '<p class="info-text" style="font-size:0.85em;color:#64748b">Per-focus descriptive SNR ';
        html += '(observed shift / baseline dispersion) is attached to each influence row in the JSON. ';
        html += 'It is not a significance test.</p>';
        html += '</section>';
        return html;
    }

    function fmtRatio(v) {
        if (v == null || Number.isNaN(Number(v))) return '—';
        return Number(v).toFixed(2) + '× baseline';
    }

    function semanticShiftLabel(focus) {
        var m = (focus.ablation_stability && focus.ablation_stability.mean_vs_variance_effect) || {};
        var level = m.semantic_shift_level || 'low';
        if (level === 'high') return 'high';
        if (level === 'moderate') return 'moderate';
        return 'low';
    }

    function renderStabilityScatterPlot(points) {
        if (!points || !points.length) return '';
        var width = 520;
        var height = 320;
        var padL = 48;
        var padR = 16;
        var padT = 16;
        var padB = 40;
        var plotW = width - padL - padR;
        var plotH = height - padT - padB;
        var xs = points.map(function (p) {
            var x = p.x_standardized_effect != null ? Number(p.x_standardized_effect) : Number(p.x_semantic_shift || 0);
            return Number.isFinite(x) ? x : 0;
        });
        var ys = points.map(function (p) {
            var y = p.y_dispersion_ratio;
            return y != null && Number.isFinite(Number(y)) ? Number(y) : null;
        }).filter(function (y) { return y != null; });
        if (!ys.length) return '';
        var xMin = Math.min.apply(null, xs);
        var xMax = Math.max.apply(null, xs);
        var yMin = Math.min.apply(null, ys.concat([0.5, 1.0]));
        var yMax = Math.max.apply(null, ys.concat([1.0, 1.5]));
        if (Math.abs(xMax - xMin) < 1e-6) { xMin -= 0.5; xMax += 0.5; }
        if (Math.abs(yMax - yMin) < 1e-6) { yMin -= 0.2; yMax += 0.2; }
        function sx(x) { return padL + ((x - xMin) / (xMax - xMin)) * plotW; }
        function sy(y) { return padT + plotH - ((y - yMin) / (yMax - yMin)) * plotH; }
        var refY = sy(1.0);
        var svg = '<svg class="ablation-stability-scatter" viewBox="0 0 ' + width + ' ' + height + '" role="img" aria-label="Semantic shift vs dispersion ratio">';
        svg += '<line x1="' + padL + '" y1="' + refY + '" x2="' + (width - padR) + '" y2="' + refY + '" stroke="#94a3b8" stroke-dasharray="4 3"/>';
        svg += '<text x="' + (width - padR) + '" y="' + (refY - 4) + '" text-anchor="end" font-size="10" fill="#64748b">y=1 unchanged</text>';
        points.forEach(function (p) {
            var y = p.y_dispersion_ratio;
            if (y == null || !Number.isFinite(Number(y))) return;
            var x = p.x_standardized_effect != null ? Number(p.x_standardized_effect) : Number(p.x_semantic_shift || 0);
            if (!Number.isFinite(x)) x = 0;
            var title = (p.focus || '') + ' | z=' + fmtDist(x) + ' | ratio=' + fmtDist(y) +
                ' | q=' + fmtDist(p.q_value) + ' | n=' + (p.n_ablated_samples || '');
            svg += '<circle cx="' + sx(x) + '" cy="' + sy(Number(y)) + '" r="6" fill="#2563eb" opacity="0.85">';
            svg += '<title>' + escapeHtml(title) + '</title></circle>';
            svg += '<text x="' + sx(x) + '" y="' + (sy(Number(y)) - 10) + '" text-anchor="middle" font-size="9" fill="#334155">' +
                escapeHtml(String(p.focus || '').slice(0, 12)) + '</text>';
        });
        svg += '<text x="' + (padL + plotW / 2) + '" y="' + (height - 8) + '" text-anchor="middle" font-size="11" fill="#475569">Semantic perturbation (standardized effect / centroid shift)</text>';
        svg += '<text transform="translate(12 ' + (padT + plotH / 2) + ') rotate(-90)" text-anchor="middle" font-size="11" fill="#475569">Ablation/baseline dispersion ratio</text>';
        svg += '</svg>';
        return svg;
    }

    function renderAblationStabilitySection(data) {
        var records = enrichFocusRecords(collectFocusRecords(data), data).filter(function (r) {
            return r.attributable !== false && r.ablation_stability;
        });
        if (!records.length) return '';
        var C = getCopy();
        var html = '<section class="ablation-stability-panel">';
        html += '<h3>' + escapeHtml(C.ABLATION_STABILITY_TITLE || 'Ablation stability (per focus)') + '</h3>';
        html += '<p class="info-text">' + escapeHtml(C.ABLATION_STABILITY_DISCLAIMER || '') + '</p>';
        html += '<p class="info-text" style="font-size:0.9em">' + escapeHtml(
            C.ABLATION_STABILITY_INTERPRETATION || ''
        ) + '</p>';
        var scatter = data.stability_scatter || [];
        if (scatter.length) {
            html += '<h4 style="margin-top:16px">' + escapeHtml(
                C.ABLATION_STABILITY_SCATTER_TITLE || 'Semantic shift vs dispersion ratio'
            ) + '</h4>';
            html += renderStabilityScatterPlot(scatter);
            html += '<p class="info-text" style="font-size:0.85em">Vertical distance from y=1 is descriptive only — not a significance test of variance change.</p>';
        }
        var summary = data.stability_summary || {};
        if (summary.most_stabilizing_after_ablation && summary.most_stabilizing_after_ablation.length) {
            html += '<p class="info-text"><strong>Most stabilizing after ablation (descriptive):</strong> ';
            html += escapeHtml(summary.most_stabilizing_after_ablation.map(function (r) {
                return r.focus + ' (' + fmtDist(r.value) + '×)';
            }).join(', ')) + '</p>';
        }
        if (summary.most_destabilizing_after_ablation && summary.most_destabilizing_after_ablation.length) {
            html += '<p class="info-text"><strong>Most destabilizing after ablation (descriptive):</strong> ';
            html += escapeHtml(summary.most_destabilizing_after_ablation.map(function (r) {
                return r.focus + ' (' + fmtDist(r.value) + '×)';
            }).join(', ')) + '</p>';
        }
        html += '<div class="ablation-stability-actions" style="margin-top:12px">';
        html += '<button type="button" class="btn btn-outline btn-ablation-outcome-dispersion" id="run-ablation-outcome-dispersion-btn">' +
            escapeHtml(C.ABLATION_STABILITY_JUDGE_BUTTON || 'Run task-specific outcome dispersion') + '</button>';
        html += '</div>';
        html += '<div id="ablation-outcome-dispersion-results"></div>';
        html += '</section>';
        return html;
    }

    function renderFocusAblationStability(focus, data) {
        var stab = focus.ablation_stability;
        if (!stab || focus.attributable === false) return '';
        var C = getCopy();
        var ratio = stab.mean_pairwise_noise_ratio;
        var html = '<div class="focus-ablation-stability">';
        html += '<h5 class="focus-ablation-stability-title">Ablation stability</h5>';
        html += '<ul class="baseline-stability-metrics" style="margin:8px 0">';
        html += '<li>Semantic shift: <strong>' + escapeHtml(semanticShiftLabel(focus)) + '</strong></li>';
        html += '<li>Ablated dispersion (mean pairwise): ' + escapeHtml(fmtDist(stab.mean_pairwise_distance)) + '</li>';
        html += '<li>Baseline dispersion (mean pairwise): ' + escapeHtml(fmtDist(stab.baseline_mean_pairwise_distance)) + '</li>';
        html += '<li>Dispersion ratio: <strong>' + escapeHtml(fmtRatio(ratio)) + '</strong></li>';
        html += '<li>Sample count: n=' + escapeHtml(String(stab.n_samples || '')) + '</li>';
        html += '</ul>';
        if (stab.dispersion_ratio_interpretation) {
            html += '<p class="info-text">"' + escapeHtml(stab.dispersion_ratio_interpretation) + '"</p>';
        }
        var mv = stab.mean_vs_variance_effect || {};
        if (mv.summary) {
            html += '<p class="info-text" style="font-size:0.9em">' + escapeHtml(mv.summary) + '</p>';
        }
        if (stab.sample_size_warning && stab.sample_size_note) {
            html += '<p class="baseline-stability-warning" role="status">' + escapeHtml(stab.sample_size_note) + '</p>';
        }
        (stab.dispersion_ratio_warnings || []).forEach(function (w) {
            html += '<p class="info-text" style="color:#b45309">' + escapeHtml(w) + '</p>';
        });
        var multi = stab.multimodality || {};
        if (multi.status === 'insufficient_samples') {
            html += '<p class="info-text" style="font-size:0.85em">' + escapeHtml(multi.note || 'Multimodality: insufficient samples.') + '</p>';
        } else if (multi.potentially_multimodal) {
            html += '<p class="baseline-stability-multimodal"><em>Advisory:</em> ablated condition potentially multimodal. ' +
                escapeHtml(multi.note || '') + '</p>';
        }
        var bo = stab.behavioral_outcome || focus.behavioral_outcome;
        if (bo && bo.ablated && bo.baseline) {
            html += '<p class="info-text"><strong>Task-specific outcomes</strong> (criterion judge)</p>';
            html += '<p style="font-size:0.9em">Baseline entropy: ' + escapeHtml(fmtDist(bo.baseline.outcome_entropy_bits)) +
                ' bits · Ablated: ' + escapeHtml(fmtDist(bo.ablated.outcome_entropy_bits)) +
                ' · Δ: ' + escapeHtml(fmtDist(bo.outcome_entropy_delta_bits)) + '</p>';
        }
        if (stab.sample_size_warning || (ratio != null && (ratio < 0.7 || ratio > 1.3))) {
            var idx = focus.focus_index != null ? focus.focus_index : '';
            html += '<button type="button" class="btn btn-outline btn-small btn-refine-ablation-stability" data-focus-index="' +
                escapeHtml(String(idx)) + '">' +
                escapeHtml(C.ABLATION_STABILITY_REFINE_BUTTON || 'Increase samples for stability estimate') +
                '</button>';
        }
        html += '<div class="refine-stability-result" data-focus-index="' + escapeHtml(String(focus.focus_index != null ? focus.focus_index : '')) + '"></div>';
        html += '</div>';
        return html;
    }

    function renderReportedFocusDynamicsShell() {
        var C = getCopy();
        return (
            '<section class="reported-focus-dynamics-panel" id="reported-focus-dynamics-panel">' +
            '<h3>' + escapeHtml(C.REPORTED_FOCUS_DYNAMICS_TITLE || 'Per-sample reported-focus dynamics') + '</h3>' +
            '<p class="info-text">' + escapeHtml(
                C.REPORTED_FOCUS_DYNAMICS_DISCLAIMER ||
                'Self-reported focus weights from an LLM judge — not attention weights.'
            ) + '</p>' +
            '<button type="button" class="btn btn-outline" id="run-reported-focus-dynamics-btn">' +
            escapeHtml(C.REPORTED_FOCUS_DYNAMICS_BUTTON || 'Run per-sample reported-focus dynamics') +
            '</button>' +
            '<div id="reported-focus-dynamics-results" class="reported-focus-dynamics-results"></div>' +
            '</section>'
        );
    }

    function renderReportedFocusDynamicsHtml(dyn) {
        if (!dyn) return '<p class="empty-state">No reported-focus dynamics yet.</p>';
        var html = '<p class="info-text">' + escapeHtml(dyn.disclaimer || '') + '</p>';
        var names = dyn.focus_names || [];
        var baseline = dyn.baseline || {};
        html += '<h4>Baseline (full prompt)</h4>';
        html += '<p>n=' + escapeHtml(String(
            baseline.n_scored != null ? baseline.n_scored
                : (baseline.n_samples != null ? baseline.n_samples : (baseline.samples || []).length)
        )) + '</p>';
        html += '<table class="reported-focus-table"><thead><tr><th>Focus</th><th>Mean</th><th>Median</th><th>SD</th><th>Range</th></tr></thead><tbody>';
        names.forEach(function (name) {
            var s = (baseline.per_focus && baseline.per_focus[name]) || {};
            html += '<tr><td>' + escapeHtml(name) + '</td>';
            html += '<td>' + escapeHtml(fmtDist(s.mean)) + '</td>';
            html += '<td>' + escapeHtml(fmtDist(s.median)) + '</td>';
            html += '<td>' + escapeHtml(fmtDist(s.sd)) + '</td>';
            html += '<td>' + escapeHtml(fmtDist(s.range)) + '</td></tr>';
        });
        html += '</tbody></table>';
        html += '<details class="reported-focus-samples"><summary>Inspect baseline samples</summary>';
        (baseline.samples || []).forEach(function (sample) {
            html += '<div class="reported-focus-sample">';
            html += '<p><strong>Sample ' + escapeHtml(String((sample.sample_index != null ? sample.sample_index : 0) + 1)) + '</strong>';
            if (sample.behavior_label != null) {
                html += ' · behaviour label: ' + escapeHtml(String(sample.behavior_label));
            }
            html += '</p>';
            html += '<pre class="output-text" style="white-space:pre-wrap">' + escapeHtml(sample.output || '') + '</pre>';
            html += '<ul>';
            names.forEach(function (name) {
                var w = (sample.weights && sample.weights[name]) || 0;
                html += '<li>' + escapeHtml(name) + ': ' + escapeHtml(Number(w).toFixed(1)) + '</li>';
            });
            html += '</ul></div>';
        });
        html += '</details>';

        (dyn.ablations || []).forEach(function (block) {
            html += '<h4>Ablation: ' + escapeHtml(block.focus || '') + '</h4>';
            html += '<p>JS divergence vs baseline mean weights: ' +
                escapeHtml(fmtDist(block.js_divergence_vs_baseline_mean)) +
                ' (bits; descriptive)</p>';
            html += '<p>Δ mean weights vs baseline:</p><ul>';
            names.forEach(function (name) {
                var d = (block.delta_vs_baseline_mean_weights || {})[name];
                html += '<li>' + escapeHtml(name) + ': ' + escapeHtml(fmtDist(d)) + '</li>';
            });
            html += '</ul>';
            var summary = block.summary || {};
            html += '<table class="reported-focus-table"><thead><tr><th>Focus</th><th>Mean</th><th>Median</th><th>SD</th><th>Range</th></tr></thead><tbody>';
            names.forEach(function (name) {
                var s = (summary.per_focus && summary.per_focus[name]) || {};
                html += '<tr><td>' + escapeHtml(name) + '</td>';
                html += '<td>' + escapeHtml(fmtDist(s.mean)) + '</td>';
                html += '<td>' + escapeHtml(fmtDist(s.median)) + '</td>';
                html += '<td>' + escapeHtml(fmtDist(s.sd)) + '</td>';
                html += '<td>' + escapeHtml(fmtDist(s.range)) + '</td></tr>';
            });
            html += '</tbody></table>';
            html += '<details class="reported-focus-samples"><summary>Inspect ablated samples</summary>';
            (summary.samples || []).forEach(function (sample) {
                html += '<div class="reported-focus-sample">';
                html += '<p><strong>Sample ' + escapeHtml(String((sample.sample_index != null ? sample.sample_index : 0) + 1)) + '</strong></p>';
                html += '<pre class="output-text" style="white-space:pre-wrap">' + escapeHtml(sample.output || '') + '</pre>';
                html += '<ul>';
                names.forEach(function (name) {
                    var w = (sample.weights && sample.weights[name]) || 0;
                    html += '<li>' + escapeHtml(name) + ': ' + escapeHtml(Number(w).toFixed(1)) + '</li>';
                });
                html += '</ul></div>';
            });
            html += '</details>';
        });
        return html;
    }

    function renderFocusOrderSensitivityHtml(data) {
        if (!data || !data.ok) {
            return '<p class="empty-state">' + escapeHtml(data && data.error ? data.error : 'No order sensitivity results.') + '</p>';
        }
        var copy = getCopy();
        var html = '<div class="focus-order-panel">';
        html += '<h3>' + escapeHtml(copy.FOCUS_ORDER_TITLE || 'Focus order sensitivity') + '</h3>';
        html += '<p class="info-text">' + escapeHtml(copy.FOCUS_ORDER_DISCLAIMER || '') + '</p>';
        (data.warnings || []).forEach(function (w) {
            html += '<p class="warning-text">' + escapeHtml(w) + '</p>';
        });
        var global = (data.global_order_experiment && data.global_order_experiment.summary) || {};
        var disp = global.displacement || {};
        html += '<h4>Global order sensitivity</h4>';
        html += '<p>Sampled permutations: ' + escapeHtml(String(global.n_permutations || 0)) + '. ';
        if (disp.median != null) {
            html += 'Median semantic displacement vs baseline: ' + escapeHtml(Number(disp.median).toFixed(4)) + '. ';
        }
        if (global.advisory_ui) {
            html += escapeHtml(global.advisory_ui);
        }
        html += '</p>';
        var perms = (data.global_order_experiment && data.global_order_experiment.permutations) || [];
        html += '<details class="focus-order-permutations"><summary>Inspect individual permutations (' +
            perms.length + ')</summary>';
        perms.forEach(function (p) {
            html += '<div class="focus-order-perm-card">';
            html += '<h5>Shuffle #' + escapeHtml(String(p.permutation_id)) + '</h5>';
            html += '<p>Semantic displacement: ' + escapeHtml(fmtDist(p.semantic_displacement)) +
                '. Relative to baseline noise: ' +
                escapeHtml(p.relative_to_baseline_noise != null ? Number(p.relative_to_baseline_noise).toFixed(2) + '×' : 'n/a') +
                ' (descriptive ratio, not a p-value)</p>';
            if (p.ordered_focus_names && p.ordered_focus_names.length) {
                html += '<p><strong>Ordering:</strong></p><ol>';
                p.ordered_focus_names.forEach(function (name) {
                    html += '<li>' + escapeHtml(name) + '</li>';
                });
                html += '</ol>';
            }
            html += '<details><summary>Sampled outputs</summary>';
            (p.outputs || []).forEach(function (t, i) {
                html += '<pre class="output-text" style="white-space:pre-wrap">' +
                    escapeHtml(String(t || '')) + '</pre>';
            });
            html += '</details></div>';
        });
        html += '</details>';
        (data.position_sweeps || []).forEach(function (sweep) {
            html += '<h4>Focus position sensitivity: ' + escapeHtml(sweep.focus || '') + '</h4>';
            var sum = sweep.summary || {};
            html += '<p>' + escapeHtml(sum.interpretation_note || '') + '</p>';
            (sweep.positions || []).forEach(function (pos) {
                html += '<div class="focus-order-sweep-row">';
                html += '<p><strong>Slot ' + escapeHtml(String(pos.slot_index)) + '</strong> — displacement ' +
                    escapeHtml(fmtDist(pos.semantic_displacement)) + '</p>';
                html += '</div>';
            });
        });
        if (data.baseline_behavioral_judgments) {
            html += '<h4>Task-specific behaviour (baseline)</h4><ul>';
            data.baseline_behavioral_judgments.forEach(function (j) {
                html += '<li>' + escapeHtml(j.classification || '') + ': ' + escapeHtml(j.rationale || '') + '</li>';
            });
            html += '</ul>';
        }
        if (data.cost_breakdown && data.cost_breakdown.total_cost != null) {
            html += '<p class="info-text">Cost: $' + Number(data.cost_breakdown.total_cost).toFixed(4) + '</p>';
        }
        html += '</div>';
        return html;
    }

    function renderAblationResultsHtml(data) {
        var alpha = data.alpha != null ? Number(data.alpha) : DEFAULT_ALPHA;
        var parts = [
            '<div class="ablation-summary">',
            '<h3>Behavioural sensitivity</h3>',
            renderDefinition(),
            renderRunHeader(data),
            '</div>',
            renderPowerBannerHtml(data),
            renderBaselineStabilityHtml(data),
            renderAblationStabilitySection(data)
        ];
        var records = enrichFocusRecords(collectFocusRecords(data), data);
        parts.push('<p class="info-text shuffle-robustness-hint">Each tested focus below includes a ' +
            '<strong>shuffle-order robustness</strong> check — re-run ablation with remaining spans in shuffled order.</p>');
        parts.push('<div class="focus-verdict-list">');
        records.forEach(function (rec) {
            parts.push(renderFocusCard(rec, alpha, data));
        });
        parts.push('</div>');
        parts.push(renderReportedFocusDynamicsShell());
        parts.push(renderMethodsPanel());

        if (data.baseline_output || (data.baseline_outputs && data.baseline_outputs.length) || (data.ablation_results && data.ablation_results.length)) {
            parts.push('<div class="ablation-outputs-section">');
            parts.push('<button id="toggle-all-outputs" class="btn btn-outline" type="button">Show sampled outputs</button>');
            parts.push('<div id="all-outputs-container" class="hidden">');
            var baselines = (data.baseline_outputs && data.baseline_outputs.length)
                ? data.baseline_outputs
                : (data.baseline_output ? [data.baseline_output] : []);
            if (baselines.length) {
                parts.push(
                    '<div class="output-comparison-item">' +
                    '<h4>Baseline outputs (full prompt, ' + baselines.length + ' sample' +
                    (baselines.length === 1 ? '' : 's') + ')</h4>'
                );
                baselines.forEach(function (text, idx) {
                    parts.push(
                        '<div class="output-text" style="margin-top:8px"><strong>Sample ' +
                        (idx + 1) + '</strong><pre style="white-space:pre-wrap;margin:4px 0 0">' +
                        escapeHtml(text) + '</pre></div>'
                    );
                });
                parts.push('</div>');
            }
            records.forEach(function (rec) {
                var outputs = rec.ablated_outputs;
                if (!outputs && rec.ablated_output) outputs = [rec.ablated_output];
                if (!outputs || !outputs.length) return;
                parts.push(
                    '<div class="output-comparison-item">' +
                    '<h4>Ablated outputs: ' + escapeHtml(focusName(rec)) +
                    ' (' + outputs.length + ')</h4>'
                );
                outputs.forEach(function (text, idx) {
                    parts.push(
                        '<div class="output-text" style="margin-top:8px"><strong>Sample ' +
                        (idx + 1) + '</strong><pre style="white-space:pre-wrap;margin:4px 0 0">' +
                        escapeHtml(text) + '</pre></div>'
                    );
                });
                parts.push('</div>');
            });
            parts.push('</div></div>');
        }

        if (data.cost_breakdown) {
            var cost = data.cost_breakdown;
            var chat = cost.chat_completions || {};
            var emb = cost.embeddings || {};
            parts.push(
                '<div class="cost-breakdown"><h4>Cost breakdown</h4>' +
                '<p>Chat completions: $' + Number(chat.cost || 0).toFixed(4) +
                '. Embeddings: $' + Number(emb.cost || 0).toFixed(4) +
                '. Total: $' + Number(cost.total_cost || 0).toFixed(4) +
                ' (model: ' + escapeHtml(cost.model || 'unknown') + ').</p></div>'
            );
        }

        parts.push(
            '<div class="ablation-download">' +
            '<button id="download-ablation-results" class="btn btn-primary" type="button">' +
            'Download all results (JSON)</button></div>'
        );
        return parts.join('');
    }

    global.FocalPromptResults = {
        getCopy: getCopy,
        escapeHtml: escapeHtml,
        formatQValue: formatQValue,
        formatEffectSize: formatEffectSize,
        effectSizeQualifier: effectSizeQualifier,
        formatPowerBanner: formatPowerBanner,
        excludedExplanation: excludedExplanation,
        isNearThreshold: isNearThreshold,
        collectFocusRecords: collectFocusRecords,
        renderFocusCard: renderFocusCard,
        renderEvidenceLenses: renderEvidenceLenses,
        renderDefinition: renderDefinition,
        renderRunHeader: renderRunHeader,
        renderMethodsPanel: renderMethodsPanel,
        renderPowerBannerHtml: renderPowerBannerHtml,
        renderBaselineStabilityHtml: renderBaselineStabilityHtml,
        renderAblationStabilitySection: renderAblationStabilitySection,
        renderFocusAblationStability: renderFocusAblationStability,
        renderStabilityScatterPlot: renderStabilityScatterPlot,
        renderFocusOrderSensitivityHtml: renderFocusOrderSensitivityHtml,
        renderReportedFocusDynamicsHtml: renderReportedFocusDynamicsHtml,
        renderAblationResultsHtml: renderAblationResultsHtml
    };
})(typeof window !== 'undefined' ? window : this);
