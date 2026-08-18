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
        if (!Number.isFinite(n)) return 'inf';
        return n.toFixed(1);
    }

    function effectSizeBand(z) {
        if (z === null || z === undefined || Number.isNaN(Number(z))) return null;
        var absZ = Math.abs(Number(z));
        if (!Number.isFinite(absZ)) absZ = Infinity;
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
            records.push(merged);
            seen[name] = true;
        });
        scores.forEach(function (score, i) {
            var name = focusName(score, 'Focus ' + (i + 1));
            if (!seen[name]) {
                records.push(Object.assign({}, score));
                seen[name] = true;
            }
        });
        return records;
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

    function renderFocusCard(focus, alpha) {
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

    function renderAblationResultsHtml(data) {
        var alpha = data.alpha != null ? Number(data.alpha) : DEFAULT_ALPHA;
        var parts = [
            '<div class="ablation-summary">',
            '<h3>Behavioural sensitivity</h3>',
            renderDefinition(),
            renderRunHeader(data),
            '</div>',
            renderPowerBannerHtml(data)
        ];
        var records = collectFocusRecords(data);
        parts.push('<div class="focus-verdict-list">');
        records.forEach(function (rec) {
            parts.push(renderFocusCard(rec, alpha));
        });
        parts.push('</div>');
        parts.push(renderMethodsPanel());

        if (data.baseline_output || (data.ablation_results && data.ablation_results.length)) {
            parts.push('<div class="ablation-outputs-section">');
            parts.push('<button id="toggle-all-outputs" class="btn btn-outline" type="button">Show sampled outputs</button>');
            parts.push('<div id="all-outputs-container" class="hidden">');
            if (data.baseline_output) {
                parts.push(
                    '<div class="output-comparison-item">' +
                    '<h4>Baseline output (full prompt, first sample)</h4>' +
                    '<div class="output-text">' + escapeHtml(data.baseline_output) + '</div>' +
                    '</div>'
                );
            }
            records.forEach(function (rec) {
                var outputs = rec.ablated_outputs;
                if (!outputs && rec.ablated_output) outputs = [rec.ablated_output];
                if (!outputs || !outputs.length) return;
                parts.push(
                    '<div class="output-comparison-item">' +
                    '<h4>Ablated output: ' + escapeHtml(focusName(rec)) + '</h4>' +
                    '<div class="output-text">' + escapeHtml(outputs[0]) + '</div>' +
                    '</div>'
                );
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
        renderDefinition: renderDefinition,
        renderRunHeader: renderRunHeader,
        renderMethodsPanel: renderMethodsPanel,
        renderPowerBannerHtml: renderPowerBannerHtml,
        renderAblationResultsHtml: renderAblationResultsHtml
    };
})(typeof window !== 'undefined' ? window : this);
