/**
 * Insight-led results report UI.
 *
 * Mounts into #ablation-results. Presents a "conclusion first" reading order:
 * deterministic headline + insight cards -> supporting evidence views ->
 * classic raw output. Built on top of window.FocalPromptInsightMetrics
 * (browser mirror of utils/insight_metrics.py) and, for the Raw tab, the
 * existing window.FocalPromptResults renderer.
 *
 * No external chart libraries — all charts are hand-rolled inline SVG / CSS.
 */
(function (global) {
    'use strict';

    var MOUNT_ID = 'ablation-results';

    var STATE = {
        ablation: null,
        bundle: null,
        selectedFocus: null,
        view: 'overview',
        dumbbellSort: 'revealed',
        dumbbellShowAll: false,
        inspectorOpen: false
    };

    var containerEl = null;

    // -----------------------------------------------------------------
    // Small helpers
    // -----------------------------------------------------------------

    function escapeHtml(text) {
        if (text === null || text === undefined) return '';
        return String(text)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function truncate(str, n) {
        str = str === null || str === undefined ? '' : String(str);
        str = str.replace(/\s+/g, ' ').trim();
        if (str.length <= n) return str;
        return str.slice(0, Math.max(0, n - 1)).trim() + '\u2026';
    }

    function clampNum(v, lo, hi) {
        var n = Number(v);
        if (!Number.isFinite(n)) return lo;
        return Math.max(lo, Math.min(hi, n));
    }

    function isNum(v) {
        return v !== null && v !== undefined && Number.isFinite(Number(v));
    }

    function fmtPct(v) {
        return isNum(v) ? Number(v).toFixed(1) + '%' : 'n/a';
    }

    function fmtPts(v) {
        if (!isNum(v)) return 'n/a';
        var n = Number(v);
        return (n >= 0 ? '+' : '') + n.toFixed(1) + ' pts';
    }

    function fmtNoise(v) {
        return isNum(v) ? Number(v).toFixed(4) : 'n/a';
    }

    function seriesClass(i) {
        return 'fp-series-' + (Math.abs(i) % 8);
    }

    function getMetrics() {
        return global.FocalPromptInsightMetrics || null;
    }

    function archetypeLabel(key) {
        var M = getMetrics();
        return (M && M.ARCHETYPE_LABELS && M.ARCHETYPE_LABELS[key]) || key;
    }

    function archetypeHelp(key) {
        var M = getMetrics();
        return (M && M.ARCHETYPE_HELP && M.ARCHETYPE_HELP[key]) || '';
    }

    function focusRowByName(name) {
        var rows = (STATE.bundle && STATE.bundle.focusRows) || [];
        for (var i = 0; i < rows.length; i++) {
            if (rows[i].name === name) return rows[i];
        }
        return null;
    }

    // -----------------------------------------------------------------
    // Derivation: build the insight bundle from raw ablation data
    // -----------------------------------------------------------------

    function collectInfluenceScores(ablation) {
        if (Array.isArray(ablation.influence_scores) && ablation.influence_scores.length) {
            return ablation.influence_scores;
        }
        if (global.FocalPromptResults && typeof global.FocalPromptResults.collectFocusRecords === 'function') {
            try {
                return global.FocalPromptResults.collectFocusRecords(ablation) || [];
            } catch (e) {
                return [];
            }
        }
        return Array.isArray(ablation.ablation_results) ? ablation.ablation_results : [];
    }

    function collectAssessmentFoci() {
        if (Array.isArray(global.assessmentFoci) && global.assessmentFoci.length) {
            return global.assessmentFoci;
        }
        if (global.lastAssessmentApiPayload && Array.isArray(global.lastAssessmentApiPayload.foci)) {
            return global.lastAssessmentApiPayload.foci;
        }
        return [];
    }

    function collectOrderResults(ablation) {
        if (global.focusOrderSensitivityResults) return global.focusOrderSensitivityResults;
        if (ablation && ablation.focus_order_sensitivity) return ablation.focus_order_sensitivity;
        return null;
    }

    function buildOrderByFocus(orderResults) {
        var map = {};
        var sweeps = (orderResults && Array.isArray(orderResults.position_sweeps))
            ? orderResults.position_sweeps
            : [];
        sweeps.forEach(function (sweep) {
            var name = sweep && sweep.focus;
            if (!name) return;
            var disp = (sweep.summary && sweep.summary.displacement) || {};
            var val = disp.median !== null && disp.median !== undefined ? disp.median : disp.mean;
            if (val !== null && val !== undefined) {
                map[name] = val;
            }
        });
        return map;
    }

    function hasOrderData(orderResults) {
        if (!orderResults || orderResults.ok === false) return false;
        var sweeps = orderResults.position_sweeps;
        if (Array.isArray(sweeps) && sweeps.length) return true;
        var global_ = orderResults.global_order_experiment;
        if (global_ && Array.isArray(global_.permutations) && global_.permutations.length) return true;
        return false;
    }

    function deriveBundle(ablation) {
        var empty = {
            focusRows: [],
            status: {},
            insightCards: [],
            headline: 'Run an ablation analysis to see the insight-led report.',
            suggestions: [],
            hasOrderData: false,
            orderData: null,
            meta: {}
        };
        if (!ablation) return empty;

        var M = getMetrics();
        if (!M) return empty;

        var influenceScores = collectInfluenceScores(ablation);
        var assessmentFoci = collectAssessmentFoci();
        var baselineNoise = (ablation.baseline_stability && ablation.baseline_stability.mean_pairwise_cosine_distance !== undefined)
            ? ablation.baseline_stability.mean_pairwise_cosine_distance
            : null;
        var orderResults = collectOrderResults(ablation);
        var orderByFocus = buildOrderByFocus(orderResults);

        var focusRows = M.buildFocusRows({
            influence_scores: influenceScores,
            assessment_foci: assessmentFoci,
            baseline_noise: baselineNoise,
            order_by_focus: Object.keys(orderByFocus).length ? orderByFocus : null
        });

        var revealedSorted = focusRows
            .map(function (r) { return isNum(r.revealed) ? Number(r.revealed) : 0; })
            .sort(function (a, b) { return b - a; });
        var top3RevealedShare = revealedSorted.slice(0, 3).reduce(function (a, b) { return a + b; }, 0);

        var gaps = focusRows
            .filter(function (r) { return isNum(r.gap); })
            .map(function (r) { return Math.abs(Number(r.gap)); });
        var meanAbsGap = gaps.length ? gaps.reduce(function (a, b) { return a + b; }, 0) / gaps.length : null;

        var orderVals = focusRows
            .filter(function (r) { return isNum(r.order_sensitivity); })
            .map(function (r) { return Math.abs(Number(r.order_sensitivity)); });
        var meanOrderSensitivity = orderVals.length
            ? orderVals.reduce(function (a, b) { return a + b; }, 0) / orderVals.length
            : null;

        var status = M.statusStrip({
            top3_revealed_share: focusRows.length ? top3RevealedShare : null,
            mean_abs_gap: meanAbsGap,
            baseline_noise: baselineNoise,
            mean_order_sensitivity: meanOrderSensitivity
        });

        var insightCards = M.selectInsightCards(focusRows);
        var headline = M.overviewHeadline(focusRows);
        var suggestions = M.nextExperimentSuggestions(focusRows, status);

        var assessmentByName = {};
        assessmentFoci.forEach(function (f) {
            var name = String((f.focus || f.name || '')).trim();
            if (name) assessmentByName[name.toLowerCase()] = f;
        });

        var promptText = ablation.prompt || ablation.original_prompt || '';
        var model = ablation.model || (ablation.cost_breakdown && ablation.cost_breakdown.model) || 'unknown model';
        var nBaseline = ablation.n_baseline || ablation.num_baseline_samples || (ablation.baseline_outputs || []).length || 0;
        var nAblated = ablation.n_ablated || 0;
        var datetime = ablation.completed_at || ablation.timestamp || new Date().toLocaleString();

        return {
            focusRows: focusRows,
            status: status,
            insightCards: insightCards,
            headline: headline,
            suggestions: suggestions,
            hasOrderData: hasOrderData(orderResults),
            orderData: orderResults,
            meta: {
                promptText: promptText,
                model: model,
                nBaseline: nBaseline,
                nAblated: nAblated,
                datetime: datetime,
                focusCount: focusRows.length,
                baselineNoise: baselineNoise,
                assessmentByName: assessmentByName
            }
        };
    }

    // -----------------------------------------------------------------
    // Rendering: header
    // -----------------------------------------------------------------

    function renderStatusStrip() {
        var status = (STATE.bundle && STATE.bundle.status) || {};
        var order = [
            ['influence_concentration', 'Influence concentration'],
            ['reported_revealed_agreement', 'Reported \u2194 revealed agreement'],
            ['baseline_stability', 'Baseline stability'],
            ['order_sensitivity', 'Order sensitivity']
        ];
        var pills = order.map(function (pair) {
            var key = pair[0];
            var label = pair[1];
            var s = status[key];
            if (!s) return '';
            var levelClass = 'fp-pill-' + String(s.level || '').toLowerCase();
            return (
                '<span class="fp-status-pill ' + levelClass + '" tabindex="0" title="' +
                escapeHtml(s.help || '') + '">' +
                '<span class="fp-status-pill-label">' + escapeHtml(label) + '</span>' +
                '<span class="fp-status-pill-level">' + escapeHtml(s.level) + '</span>' +
                '</span>'
            );
        }).join('');
        if (!pills) {
            return '<div class="fp-status-strip fp-status-strip-empty">Status metrics unavailable for this run.</div>';
        }
        return '<div class="fp-status-strip">' + pills + '</div>';
    }

    function renderHeader() {
        if (!STATE.ablation) {
            return (
                '<div class="fp-report-header fp-report-header-empty">' +
                '<p class="fp-empty">No ablation results yet. Run an ablation analysis to generate the insight report.</p>' +
                '</div>'
            );
        }
        var meta = STATE.bundle.meta || {};
        var snippet = truncate(meta.promptText, 110);
        return (
            '<div class="fp-report-header">' +
            '<div class="fp-report-header-top">' +
            '<h3 class="fp-report-title" title="' + escapeHtml(meta.promptText || '') + '">' +
            (snippet ? escapeHtml(snippet) : '<em>(untitled prompt)</em>') +
            '</h3>' +
            '<button type="button" class="btn btn-outline fp-export-btn" data-action="export-json">\u2913 Export JSON</button>' +
            '</div>' +
            '<div class="fp-report-header-meta">' +
            '<span class="fp-meta-item"><strong>Model</strong> ' + escapeHtml(meta.model) + '</span>' +
            '<span class="fp-meta-item"><strong>Samples</strong> ' + Number(meta.nBaseline || 0) + '+' + Number(meta.nAblated || 0) + '</span>' +
            '<span class="fp-meta-item"><strong>Foci</strong> ' + Number(meta.focusCount || 0) + '</span>' +
            '<span class="fp-meta-item"><strong>Run</strong> ' + escapeHtml(String(meta.datetime || '')) + '</span>' +
            '</div>' +
            renderStatusStrip() +
            '</div>'
        );
    }

    // -----------------------------------------------------------------
    // Rendering: nav
    // -----------------------------------------------------------------

    function renderNav() {
        var tabs = [
            ['overview', 'Overview'],
            ['focus-map', 'Focus map'],
            ['stability', 'Stability']
        ];
        if (STATE.bundle && STATE.bundle.hasOrderData) {
            tabs.push(['order', 'Order']);
        }
        tabs.push(['samples', 'Samples']);
        tabs.push(['raw', 'Raw']);

        var html = tabs.map(function (tab) {
            var active = STATE.view === tab[0] ? ' active' : '';
            return (
                '<button type="button" class="fp-tab' + active + '" role="tab" ' +
                'aria-selected="' + (STATE.view === tab[0] ? 'true' : 'false') + '" ' +
                'data-action="set-view" data-view="' + tab[0] + '">' + escapeHtml(tab[1]) + '</button>'
            );
        }).join('');
        return '<nav class="fp-nav" role="tablist" aria-label="Results report sections">' + html + '</nav>';
    }

    // -----------------------------------------------------------------
    // Rendering: Overview
    // -----------------------------------------------------------------

    function renderInsightCards() {
        var cards = (STATE.bundle && STATE.bundle.insightCards) || [];
        if (!cards.length) {
            return '<p class="fp-empty">No standout archetypes were detected for this run — reported and revealed influence look broadly consistent.</p>';
        }
        var html = cards.map(function (c) {
            var selected = STATE.selectedFocus === c.focus ? ' selected' : '';
            var bits = [];
            var n = c.numbers || {};
            if (isNum(n.reported)) bits.push('Reported ' + fmtPct(n.reported));
            if (isNum(n.revealed)) bits.push('Revealed ' + fmtPct(n.revealed));
            if (isNum(n.gap)) bits.push('Gap ' + fmtPts(n.gap));
            if (isNum(n.baseline_noise)) bits.push('Baseline noise ' + fmtNoise(n.baseline_noise));
            if (isNum(n.ablated_noise)) bits.push('Ablated noise ' + fmtNoise(n.ablated_noise));
            if (isNum(n.order_sensitivity)) bits.push('Order sensitivity ' + fmtNoise(n.order_sensitivity));
            return (
                '<button type="button" class="fp-insight-card fp-kind-' + escapeHtml(c.kind) + selected + '" ' +
                'data-action="select-focus" data-focus="' + escapeHtml(c.focus) + '">' +
                '<span class="fp-insight-kind">' + escapeHtml(archetypeLabel(c.kind)) + '</span>' +
                '<span class="fp-insight-focus">' + escapeHtml(c.focus) + '</span>' +
                '<p class="fp-insight-text">' + escapeHtml(c.interpretation) + '</p>' +
                (bits.length ? '<p class="fp-insight-numbers">' + escapeHtml(bits.join(' \u00b7 ')) + '</p>' : '') +
                '</button>'
            );
        }).join('');
        return '<div class="fp-insight-cards">' + html + '</div>';
    }

    function renderAnatomyBar() {
        var rows = (STATE.bundle && STATE.bundle.focusRows) || [];
        if (!rows.length) return '';
        var lengths = rows.map(function (r) { return Math.max(1, (r.prompt_section || '').length); });
        var total = lengths.reduce(function (a, b) { return a + b; }, 0) || 1;
        var segments = rows.map(function (r, i) {
            var pct = (lengths[i] / total) * 100;
            var selected = STATE.selectedFocus === r.name ? ' selected' : '';
            return (
                '<button type="button" class="fp-anatomy-segment ' + seriesClass(i) + selected + '" ' +
                'style="width:' + pct.toFixed(3) + '%" ' +
                'data-action="select-focus" data-focus="' + escapeHtml(r.name) + '" ' +
                'title="' + escapeHtml(r.name) + ' \u2014 ' + lengths[i] + ' characters (' + pct.toFixed(1) + '% of prompt)">' +
                '<span class="fp-anatomy-label">' + escapeHtml(truncate(r.name, 16)) + '</span>' +
                '</button>'
            );
        }).join('');
        return (
            '<div class="fp-anatomy-wrap">' +
            '<h4 class="fp-section-title">Prompt anatomy <span class="fp-section-hint">(segment width = source text length)</span></h4>' +
            '<div class="fp-anatomy-bar">' + segments + '</div>' +
            '</div>'
        );
    }

    function sortedDumbbellRows() {
        var rows = ((STATE.bundle && STATE.bundle.focusRows) || []).slice();
        var sort = STATE.dumbbellSort;
        rows.sort(function (a, b) {
            if (sort === 'reported') {
                var ar = isNum(a.reported) ? Number(a.reported) : -Infinity;
                var br = isNum(b.reported) ? Number(b.reported) : -Infinity;
                return br - ar;
            }
            if (sort === 'gap') {
                var ag = isNum(a.gap) ? Math.abs(Number(a.gap)) : -Infinity;
                var bg = isNum(b.gap) ? Math.abs(Number(b.gap)) : -Infinity;
                return bg - ag;
            }
            var av = isNum(a.revealed) ? Number(a.revealed) : -Infinity;
            var bv = isNum(b.revealed) ? Number(b.revealed) : -Infinity;
            return bv - av;
        });
        return rows;
    }

    function renderDumbbellChart() {
        var allRows = sortedDumbbellRows();
        if (!allRows.length) {
            return '<p class="fp-empty">No reported/revealed scores available yet.</p>';
        }
        var showAll = STATE.dumbbellShowAll;
        var rows = showAll ? allRows : allRows.slice(0, 8);

        var rowH = 30;
        var padTop = 24;
        var padBottom = 30;
        var padL = 168;
        var padR = 24;
        var plotW = 420;
        var width = padL + plotW + padR;
        var height = padTop + rows.length * rowH + padBottom;

        function sx(v) {
            return padL + (clampNum(v, 0, 100) / 100) * plotW;
        }

        var svgParts = [];
        svgParts.push(
            '<svg class="fp-dumbbell-svg" viewBox="0 0 ' + width + ' ' + height + '" role="img" ' +
            'aria-label="Reported versus revealed influence per focus">'
        );
        // gridlines at 0/25/50/75/100
        [0, 25, 50, 75, 100].forEach(function (tick) {
            var x = sx(tick);
            svgParts.push(
                '<line x1="' + x + '" y1="' + padTop + '" x2="' + x + '" y2="' + (height - padBottom) +
                '" class="fp-dumbbell-grid"/>'
            );
            svgParts.push(
                '<text x="' + x + '" y="' + (height - padBottom + 16) + '" class="fp-dumbbell-tick" text-anchor="middle">' +
                tick + '</text>'
            );
        });

        rows.forEach(function (r, i) {
            var y = padTop + i * rowH + rowH / 2;
            var idx = allRows.indexOf(r);
            var selected = STATE.selectedFocus === r.name;
            var hasReported = isNum(r.reported);
            var hasRevealed = isNum(r.revealed);

            svgParts.push(
                '<text x="' + (padL - 12) + '" y="' + (y + 4) + '" class="fp-dumbbell-label' +
                (selected ? ' selected' : '') + '" text-anchor="end">' + escapeHtml(truncate(r.name, 20)) + '</text>'
            );

            if (hasReported && hasRevealed) {
                svgParts.push(
                    '<line x1="' + sx(r.reported) + '" y1="' + y + '" x2="' + sx(r.revealed) + '" y2="' + y +
                    '" class="fp-dumbbell-line"/>'
                );
            }
            if (hasReported) {
                svgParts.push(
                    '<circle cx="' + sx(r.reported) + '" cy="' + y + '" r="6" class="fp-dot fp-dot-reported ' +
                    seriesClass(idx) + '" data-action="select-focus" data-focus="' + escapeHtml(r.name) + '">' +
                    '<title>' + escapeHtml(r.name) + ' \u2014 reported ' + fmtPct(r.reported) + '</title></circle>'
                );
            }
            if (hasRevealed) {
                svgParts.push(
                    '<circle cx="' + sx(r.revealed) + '" cy="' + y + '" r="6" class="fp-dot fp-dot-revealed ' +
                    seriesClass(idx) + '" data-action="select-focus" data-focus="' + escapeHtml(r.name) + '">' +
                    '<title>' + escapeHtml(r.name) + ' \u2014 revealed ' + fmtPct(r.revealed) + '</title></circle>'
                );
            }
        });

        svgParts.push('</svg>');

        var fallbackRows = allRows.map(function (r) {
            return (
                '<tr>' +
                '<td><button type="button" class="fp-link-btn" data-action="select-focus" data-focus="' +
                escapeHtml(r.name) + '">' + escapeHtml(r.name) + '</button></td>' +
                '<td>' + fmtPct(r.reported) + '</td>' +
                '<td>' + fmtPct(r.revealed) + '</td>' +
                '<td>' + fmtPts(r.gap) + '</td>' +
                '</tr>'
            );
        }).join('');

        return (
            '<div class="fp-dumbbell-wrap">' +
            '<div class="fp-dumbbell-controls">' +
            '<label class="fp-dumbbell-sort-label">Sort by ' +
            '<select class="fp-dumbbell-sort" data-role="dumbbell-sort">' +
            '<option value="revealed"' + (STATE.dumbbellSort === 'revealed' ? ' selected' : '') + '>Revealed</option>' +
            '<option value="reported"' + (STATE.dumbbellSort === 'reported' ? ' selected' : '') + '>Reported</option>' +
            '<option value="gap"' + (STATE.dumbbellSort === 'gap' ? ' selected' : '') + '>|Gap|</option>' +
            '</select></label>' +
            (allRows.length > 8
                ? '<button type="button" class="btn btn-outline btn-small fp-dumbbell-toggle" data-action="toggle-dumbbell-all">' +
                  (showAll ? 'Show top 8' : 'Show all ' + allRows.length) + '</button>'
                : '') +
            '<span class="fp-legend"><span class="fp-legend-dot fp-dot-reported"></span> Reported ' +
            '<span class="fp-legend-dot fp-dot-revealed"></span> Revealed</span>' +
            '</div>' +
            svgParts.join('') +
            '<details class="fp-chart-fallback"><summary>View as table (all ' + allRows.length + ' foci)</summary>' +
            '<table class="fp-fallback-table"><thead><tr><th>Focus</th><th>Reported</th><th>Revealed</th><th>Gap</th></tr></thead>' +
            '<tbody>' + fallbackRows + '</tbody></table>' +
            '</details>' +
            '</div>'
        );
    }

    function renderNextTests() {
        var list = (STATE.bundle && STATE.bundle.suggestions) || [];
        if (!list.length) return '';
        return (
            '<div class="fp-next-tests">' +
            '<h4 class="fp-section-title">What to test next</h4>' +
            '<ul>' + list.map(function (s) { return '<li>' + escapeHtml(s) + '</li>'; }).join('') + '</ul>' +
            '</div>'
        );
    }

    function renderConcordancePanel() {
        var cmp = global.experimentCComparison;
        if (!cmp || !cmp.summary) {
            return (
                '<div class="fp-concordance-panel fp-concordance-empty">' +
                '<p class="info-text">Run Experiment A (Assess Focus) before or after ablation to score reported↔revealed agreement. ' +
                'The chart above already compares available scores; concordance stats appear here once both lenses are present.</p>' +
                '<button type="button" class="btn btn-outline btn-small" data-action="refresh-concordance">Refresh concordance</button>' +
                '</div>'
            );
        }
        var summary = cmp.summary || {};
        var rho = summary.spearman_reported_vs_normalized_influence;
        var rhoTxt = (rho === null || rho === undefined || Number.isNaN(Number(rho)))
            ? 'n/a'
            : Number(rho).toFixed(2);
        var nDis = summary.n_disagreements || 0;
        var disagreements = (summary.disagreement_foci || []).slice(0, 4).join(', ');
        var explainDisabled = nDis === 0 ? ' disabled' : '';
        return (
            '<div class="fp-concordance-panel">' +
            '<h4 class="fp-section-title">Reported ↔ revealed concordance</h4>' +
            '<p class="fp-concordance-summary">Compared ' +
            escapeHtml(String(summary.n_foci_compared || (cmp.rows || []).length)) +
            ' foci · Agree (high) ' + escapeHtml(String(summary.n_concordant_high || 0)) +
            ' · Agree (quiet) ' + escapeHtml(String(summary.n_concordant_quiet || 0)) +
            ' · Disagreements ' + escapeHtml(String(nDis)) +
            (disagreements ? ' (' + escapeHtml(disagreements) + ')' : '') +
            ' · ρ = ' + escapeHtml(rhoTxt) + '</p>' +
            (summary.interpretation
                ? '<p class="info-text">' + escapeHtml(summary.interpretation) + '</p>'
                : '') +
            '<div class="fp-concordance-actions">' +
            '<button type="button" class="btn btn-outline btn-small" data-action="refresh-concordance">Refresh</button>' +
            '<button type="button" class="btn btn-primary btn-small" data-action="explain-concordance"' +
            explainDisabled + '>Explain disagreements</button>' +
            '<button type="button" class="btn btn-outline btn-small" data-action="set-view" data-view="raw">Full concordance table → Raw</button>' +
            '</div>' +
            (global.experimentCExplanationHtml
                ? '<div id="fp-concordance-explanation" class="fp-concordance-explanation">' +
                  global.experimentCExplanationHtml + '</div>'
                : '<div id="fp-concordance-explanation" class="fp-concordance-explanation"></div>') +
            '</div>'
        );
    }

    function renderOverview() {
        return (
            '<section class="fp-overview">' +
            '<p class="fp-headline">' + escapeHtml(STATE.bundle.headline) + '</p>' +
            renderInsightCards() +
            renderAnatomyBar() +
            '<div class="fp-dumbbell-section">' +
            '<h4 class="fp-section-title">Reported vs. revealed influence</h4>' +
            '<p class="info-text">This is the Experiment C comparison — reported attention (A) vs behavioural influence (B). Use Focus map for the same data as a scatter.</p>' +
            renderDumbbellChart() +
            '</div>' +
            renderConcordancePanel() +
            renderNextTests() +
            '</section>'
        );
    }

    // -----------------------------------------------------------------
    // Rendering: Focus map
    // -----------------------------------------------------------------

    function renderFocusMap() {
        var rows = (STATE.bundle && STATE.bundle.focusRows) || [];
        if (!rows.length) {
            return '<p class="fp-empty">No focus-level results are available for this run yet.</p>';
        }
        var M = getMetrics();
        var t = (M && M.THRESHOLDS) || {};
        var xMid = ((t.low_reported || 8) + (t.high_reported || 15)) / 2;
        var yMid = ((t.low_revealed || 10) + (t.high_revealed || 12)) / 2;

        var width = 600;
        var height = 440;
        var padL = 56;
        var padR = 24;
        var padT = 24;
        var padB = 48;
        var plotW = width - padL - padR;
        var plotH = height - padT - padB;

        function sx(v) { return padL + (clampNum(v, 0, 100) / 100) * plotW; }
        function sy(v) { return padT + plotH - (clampNum(v, 0, 100) / 100) * plotH; }

        var plottable = rows.filter(function (r) { return isNum(r.reported) && isNum(r.revealed); });
        var unplottable = rows.filter(function (r) { return !(isNum(r.reported) && isNum(r.revealed)); });

        var svg = [];
        svg.push(
            '<svg class="fp-focus-map-svg" viewBox="0 0 ' + width + ' ' + height + '" role="img" ' +
            'aria-label="Reported vs revealed influence scatter plot">'
        );
        svg.push(
            '<rect x="' + padL + '" y="' + padT + '" width="' + plotW + '" height="' + plotH + '" class="fp-map-plot-bg"/>'
        );
        svg.push(
            '<line x1="' + sx(xMid) + '" y1="' + padT + '" x2="' + sx(xMid) + '" y2="' + (padT + plotH) + '" class="fp-map-divider"/>'
        );
        svg.push(
            '<line x1="' + padL + '" y1="' + sy(yMid) + '" x2="' + (padL + plotW) + '" y2="' + sy(yMid) + '" class="fp-map-divider"/>'
        );
        // quadrant labels
        svg.push('<text x="' + (padL + 8) + '" y="' + (padT + 16) + '" class="fp-quadrant-label">Hidden driver</text>');
        svg.push('<text x="' + (width - padR - 8) + '" y="' + (padT + 16) + '" text-anchor="end" class="fp-quadrant-label">Anchor</text>');
        svg.push('<text x="' + (padL + 8) + '" y="' + (padT + plotH - 8) + '" class="fp-quadrant-label">Redundant</text>');
        svg.push('<text x="' + (width - padR - 8) + '" y="' + (padT + plotH - 8) + '" text-anchor="end" class="fp-quadrant-label">Claimed but inert</text>');
        // axes labels
        svg.push('<text x="' + (padL + plotW / 2) + '" y="' + (height - 10) + '" text-anchor="middle" class="fp-axis-label">Reported focus (%)</text>');
        svg.push(
            '<text x="14" y="' + (padT + plotH / 2) + '" text-anchor="middle" class="fp-axis-label" ' +
            'transform="rotate(-90 14 ' + (padT + plotH / 2) + ')">Revealed influence (%)</text>'
        );

        plottable.forEach(function (r) {
            var idx = rows.indexOf(r);
            var selected = STATE.selectedFocus === r.name;
            var archClass = r.archetypes && r.archetypes.length ? ' fp-arch-' + r.archetypes[0] : '';
            svg.push(
                '<circle cx="' + sx(r.reported) + '" cy="' + sy(r.revealed) + '" r="' + (selected ? 9 : 7) +
                '" class="fp-map-dot' + archClass + (selected ? ' selected' : '') + '" ' +
                'data-action="select-focus" data-focus="' + escapeHtml(r.name) + '">' +
                '<title>' + escapeHtml(r.name) + ' \u2014 reported ' + fmtPct(r.reported) + ', revealed ' + fmtPct(r.revealed) + '</title>' +
                '</circle>'
            );
            svg.push(
                '<text x="' + sx(r.reported) + '" y="' + (sy(r.revealed) - 12) + '" text-anchor="middle" class="fp-map-dot-label">' +
                escapeHtml(truncate(r.name, 14)) + '</text>'
            );
        });
        svg.push('</svg>');

        var fallbackRows = rows.map(function (r) {
            return (
                '<tr>' +
                '<td><button type="button" class="fp-link-btn" data-action="select-focus" data-focus="' +
                escapeHtml(r.name) + '">' + escapeHtml(r.name) + '</button></td>' +
                '<td>' + fmtPct(r.reported) + '</td>' +
                '<td>' + fmtPct(r.revealed) + '</td>' +
                '<td>' + fmtPts(r.gap) + '</td>' +
                '<td>' + (r.archetypes || []).map(archetypeLabel).map(escapeHtml).join(', ') + '</td>' +
                '</tr>'
            );
        }).join('');

        var unplottableNote = unplottable.length
            ? '<p class="fp-empty">' + unplottable.length + ' focus(es) lack a paired reported score and are not plotted above; see the table below.</p>'
            : '';

        return (
            '<section class="fp-focus-map-wrap">' +
            '<h4 class="fp-section-title">Focus map <span class="fp-section-hint">(reported vs. revealed)</span></h4>' +
            svg.join('') +
            unplottableNote +
            '<details class="fp-chart-fallback" open><summary>View as table (all ' + rows.length + ' foci)</summary>' +
            '<table class="fp-fallback-table"><thead><tr><th>Focus</th><th>Reported</th><th>Revealed</th><th>Gap</th><th>Archetypes</th></tr></thead>' +
            '<tbody>' + fallbackRows + '</tbody></table>' +
            '</details>' +
            '</section>'
        );
    }

    // -----------------------------------------------------------------
    // Rendering: Stability
    // -----------------------------------------------------------------

    function renderStability() {
        var rows = (STATE.bundle && STATE.bundle.focusRows) || [];
        var rowsWithNoise = rows.filter(function (r) { return isNum(r.ablated_noise); });
        if (!rowsWithNoise.length) {
            return '<p class="fp-empty">No ablation stability data is available for this run yet.</p>';
        }
        var baselineNoise = STATE.bundle.meta.baselineNoise;
        var maxVal = Math.max.apply(null, rowsWithNoise.map(function (r) { return r.ablated_noise; }).concat(isNum(baselineNoise) ? [baselineNoise] : [0])) * 1.25 || 1;

        var bars = rowsWithNoise.map(function (r, i) {
            var pct = clampNum((r.ablated_noise / maxVal) * 100, 0, 100);
            var basePct = isNum(baselineNoise) ? clampNum((baselineNoise / maxVal) * 100, 0, 100) : null;
            var selected = STATE.selectedFocus === r.name ? ' selected' : '';
            return (
                '<div class="fp-stability-row' + selected + '" data-action="select-focus" data-focus="' + escapeHtml(r.name) + '">' +
                '<div class="fp-stability-label">' + escapeHtml(truncate(r.name, 26)) + '</div>' +
                '<div class="fp-stability-bar-track">' +
                '<div class="fp-stability-bar-fill ' + seriesClass(i) + '" style="width:' + pct.toFixed(1) + '%"></div>' +
                (basePct !== null ? '<div class="fp-stability-baseline-marker" style="left:' + basePct.toFixed(1) + '%" title="Baseline noise ' + fmtNoise(baselineNoise) + '"></div>' : '') +
                '</div>' +
                '<div class="fp-stability-value">' + fmtNoise(r.ablated_noise) + '</div>' +
                '</div>'
            );
        }).join('');

        var stabilizers = rows.filter(function (r) { return (r.archetypes || []).indexOf('stabilizer') !== -1; });
        var destabilizers = rows.filter(function (r) { return (r.archetypes || []).indexOf('destabilizer') !== -1; });

        var notes = '';
        if (stabilizers.length || destabilizers.length) {
            notes += '<div class="fp-stability-notes">';
            if (stabilizers.length) {
                notes += '<p><strong>Stabilizers</strong> (' + escapeHtml(archetypeHelp('stabilizer')) + '): ' +
                    escapeHtml(stabilizers.map(function (r) { return r.name; }).join(', ')) + '</p>';
            }
            if (destabilizers.length) {
                notes += '<p><strong>Destabilizers</strong> (' + escapeHtml(archetypeHelp('destabilizer')) + '): ' +
                    escapeHtml(destabilizers.map(function (r) { return r.name; }).join(', ')) + '</p>';
            }
            notes += '</div>';
        }

        var samples = rowsWithNoise.map(function (r) {
            var src = r.source || {};
            var outputs = src.ablated_outputs || (src.ablated_output ? [src.ablated_output] : []);
            if (!outputs.length) return '';
            return (
                '<details class="fp-stability-samples"><summary>Sampled ablated outputs \u2014 ' + escapeHtml(r.name) + ' (' + outputs.length + ')</summary>' +
                outputs.map(function (text, idx) {
                    return '<pre class="fp-sample-text">Sample ' + (idx + 1) + '\n' + escapeHtml(text) + '</pre>';
                }).join('') +
                '</details>'
            );
        }).join('');

        return (
            '<section class="fp-stability-wrap">' +
            '<h4 class="fp-section-title">Baseline vs. ablated noise</h4>' +
            '<p class="fp-disclaimer">Bars show per-focus dispersion after ablation; the dashed marker is baseline dispersion. ' +
            'These are descriptive dispersion ratios, not significance tests \u2014 no claim of statistical significance is made here.</p>' +
            '<div class="fp-stability-rows">' + bars + '</div>' +
            notes +
            (samples ? '<div class="fp-stability-sample-list">' + samples + '</div>' : '') +
            '</section>'
        );
    }

    // -----------------------------------------------------------------
    // Rendering: Order
    // -----------------------------------------------------------------

    function renderOrder() {
        var orderData = STATE.bundle && STATE.bundle.orderData;
        if (!orderData) return '<p class="fp-empty">No order-sensitivity data is available for this run.</p>';

        var global_ = orderData.global_order_experiment || {};
        var summary = global_.summary || {};
        var disp = summary.displacement || {};
        var sweeps = orderData.position_sweeps || [];

        var overallHtml = (
            '<div class="fp-order-summary">' +
            '<p><strong>Overall displacement</strong> (global permutations, n=' + Number(global_.k_permutations || (global_.permutations || []).length || 0) + '): ' +
            'median ' + fmtNoise(disp.median) + ', mean ' + fmtNoise(disp.mean) + '.</p>' +
            (summary.advisory_ui ? '<p class="fp-disclaimer">' + escapeHtml(summary.advisory_ui) + '</p>' : '') +
            '</div>'
        );

        var heatmaps = sweeps.map(function (sweep) {
            var positions = sweep.positions || [];
            var vals = positions.map(function (p) { return Number(p.semantic_displacement || 0); });
            var min = vals.length ? Math.min.apply(null, vals) : 0;
            var max = vals.length ? Math.max.apply(null, vals) : 1;
            var range = (max - min) || 1;
            var cells = positions.map(function (p) {
                var alpha = 0.15 + 0.75 * ((Number(p.semantic_displacement || 0) - min) / range);
                return (
                    '<div class="fp-heat-cell" style="background-color: rgba(30, 58, 95, ' + alpha.toFixed(2) + ')" ' +
                    'title="Slot ' + escapeHtml(String(p.slot_index)) + ': displacement ' + fmtNoise(p.semantic_displacement) + '">' +
                    '<span class="fp-heat-cell-slot">' + escapeHtml(String(p.slot_index)) + '</span>' +
                    '<span class="fp-heat-cell-val">' + fmtNoise(p.semantic_displacement) + '</span>' +
                    '</div>'
                );
            }).join('');
            var sum = sweep.summary || {};
            return (
                '<div class="fp-heat-row" data-action="select-focus" data-focus="' + escapeHtml(sweep.focus || '') + '">' +
                '<div class="fp-heat-row-label">' + escapeHtml(sweep.focus || '') + '</div>' +
                '<div class="fp-heat-cells">' + cells + '</div>' +
                '<div class="fp-heat-row-note">' + escapeHtml((sum.interpretation_note || '').slice(0, 140)) + '</div>' +
                '</div>'
            );
        }).join('');

        return (
            '<section class="fp-order-wrap">' +
            '<h4 class="fp-section-title">Focus order sensitivity</h4>' +
            overallHtml +
            (heatmaps
                ? '<div class="fp-heatmap"><h5 class="fp-section-subtitle">Position sweeps (controlled, per focus)</h5>' + heatmaps + '</div>'
                : '<p class="fp-empty">No controlled per-focus position sweeps were run for this experiment.</p>') +
            '</section>'
        );
    }

    // -----------------------------------------------------------------
    // Rendering: Samples
    // -----------------------------------------------------------------

    function renderSamples() {
        var ablation = STATE.ablation;
        var rows = (STATE.bundle && STATE.bundle.focusRows) || [];
        if (!ablation) return '<p class="fp-empty">No sampled outputs available.</p>';

        var baselineOutputs = (Array.isArray(ablation.baseline_outputs) && ablation.baseline_outputs.length)
            ? ablation.baseline_outputs
            : (ablation.baseline_output ? [ablation.baseline_output] : []);

        var baselineHtml = baselineOutputs.length
            ? '<details class="fp-sample-details"><summary>Baseline outputs (full prompt, ' + baselineOutputs.length + ')</summary>' +
              baselineOutputs.map(function (t, i) {
                  return '<pre class="fp-sample-text">Sample ' + (i + 1) + '\n' + escapeHtml(t) + '</pre>';
              }).join('') + '</details>'
            : '';

        var assessmentByName = STATE.bundle.meta.assessmentByName || {};

        var cards = rows.map(function (r) {
            var src = r.source || {};
            var ablatedOutputs = src.ablated_outputs || (src.ablated_output ? [src.ablated_output] : []);
            var firstBaseline = baselineOutputs[0] || '';
            var firstAblated = ablatedOutputs[0] || '';
            var assessed = assessmentByName[String(r.name).toLowerCase()];

            var fullDetails = ablatedOutputs.length
                ? '<details class="fp-sample-details"><summary>All ablated outputs (' + ablatedOutputs.length + ')</summary>' +
                  ablatedOutputs.map(function (t, i) {
                      return '<pre class="fp-sample-text">Sample ' + (i + 1) + '\n' + escapeHtml(t) + '</pre>';
                  }).join('') + '</details>'
                : '<p class="fp-empty">No ablated outputs captured for this focus.</p>';

            var rationale = assessed && assessed.explanation
                ? '<details class="fp-sample-rationale"><summary>Evaluator rationale</summary><p>' + escapeHtml(assessed.explanation) + '</p></details>'
                : '';

            return (
                '<div class="fp-sample-card">' +
                '<div class="fp-sample-card-header">' +
                '<button type="button" class="fp-link-btn fp-sample-focus-name" data-action="select-focus" data-focus="' +
                escapeHtml(r.name) + '">' + escapeHtml(r.name) + '</button>' +
                '</div>' +
                '<div class="fp-sample-compare">' +
                '<div class="fp-sample-col"><h6>Baseline (compact)</h6><p class="fp-sample-compact">' + escapeHtml(truncate(firstBaseline, 220)) + '</p></div>' +
                '<div class="fp-sample-col"><h6>Ablated (compact)</h6><p class="fp-sample-compact">' + escapeHtml(truncate(firstAblated, 220)) + '</p></div>' +
                '</div>' +
                fullDetails +
                rationale +
                '</div>'
            );
        }).join('');

        return (
            '<section class="fp-samples-wrap">' +
            baselineHtml +
            '<div class="fp-sample-cards">' + (cards || '<p class="fp-empty">No per-focus sample data available.</p>') + '</div>' +
            '</section>'
        );
    }

    // -----------------------------------------------------------------
    // Rendering: Raw
    // -----------------------------------------------------------------

    function renderRaw() {
        var ablation = STATE.ablation;
        if (!ablation) return '<p class="fp-empty">No raw results to display.</p>';

        var classicHtml = '<p class="fp-empty">Classic renderer unavailable.</p>';
        if (global.FocalPromptResults && typeof global.FocalPromptResults.renderAblationResultsHtml === 'function') {
            try {
                classicHtml = global.FocalPromptResults.renderAblationResultsHtml(ablation);
            } catch (e) {
                classicHtml = '<p class="fp-empty">Classic renderer failed: ' + escapeHtml(e.message || String(e)) + '</p>';
            }
        }

        var concordanceMount = document.getElementById('experiment-c-results');
        var concordanceHtml = (concordanceMount && concordanceMount.innerHTML)
            ? concordanceMount.innerHTML
            : '<p class="fp-empty">No concordance table yet. Refresh from Overview after Experiments A and B.</p>';

        var explainHtml = global.experimentCExplanationHtml || '';

        var jsonStr;
        try {
            jsonStr = JSON.stringify({
                ablation: ablation,
                assessment: global.lastAssessmentApiPayload || null,
                experiment_c: global.experimentCComparison || null
            }, null, 2);
        } catch (e) {
            jsonStr = 'Unable to serialize results: ' + (e.message || String(e));
        }

        return (
            '<section class="fp-raw-wrap">' +
            '<div class="fp-raw-concordance">' +
            '<h4 class="fp-section-title">Concordance table (reported vs revealed)</h4>' +
            '<p class="info-text">Full Experiment C detail — Overview keeps the chart; this is the forensic table.</p>' +
            concordanceHtml +
            (explainHtml ? '<div class="fp-raw-explain">' + explainHtml + '</div>' : '') +
            '</div>' +
            '<div class="fp-raw-classic">' + classicHtml + '</div>' +
            '<div class="fp-raw-json">' +
            '<div class="fp-raw-json-header"><h4 class="fp-section-title">Raw JSON</h4>' +
            '<button type="button" class="btn btn-outline" data-action="export-json">\u2913 Export JSON</button></div>' +
            '<pre class="fp-json-dump">' + escapeHtml(jsonStr) + '</pre>' +
            '</div>' +
            '</section>'
        );
    }

    // -----------------------------------------------------------------
    // Rendering: view dispatch + inspector
    // -----------------------------------------------------------------

    function renderView() {
        switch (STATE.view) {
            case 'focus-map': return renderFocusMap();
            case 'stability': return renderStability();
            case 'order': return STATE.bundle.hasOrderData ? renderOrder() : renderOverview();
            case 'samples': return renderSamples();
            case 'raw': return renderRaw();
            case 'overview':
            default:
                return renderOverview();
        }
    }

    function renderInspector() {
        var row = STATE.selectedFocus ? focusRowByName(STATE.selectedFocus) : null;
        var openClass = (STATE.inspectorOpen && row) ? ' open' : '';

        if (!row) {
            return (
                '<aside class="fp-inspector' + openClass + '" aria-hidden="' + (STATE.inspectorOpen ? 'false' : 'true') + '">' +
                '<div class="fp-inspector-inner">' +
                '<button type="button" class="fp-inspector-close" data-action="close-inspector" aria-label="Close inspector">\u00d7</button>' +
                '<p class="fp-empty">Select a focus from any chart to inspect its metrics, source text, and samples.</p>' +
                '</div></aside>'
            );
        }

        var archetypesHtml = (row.archetypes || []).map(function (a) {
            return '<span class="fp-archetype-badge fp-arch-' + escapeHtml(a) + '" title="' + escapeHtml(archetypeHelp(a)) + '">' +
                escapeHtml(archetypeLabel(a)) + '</span>';
        }).join('');

        var src = row.source || {};
        var ablatedOutputs = src.ablated_outputs || (src.ablated_output ? [src.ablated_output] : []);
        var baselineOutputs = (STATE.ablation && Array.isArray(STATE.ablation.baseline_outputs) && STATE.ablation.baseline_outputs.length)
            ? STATE.ablation.baseline_outputs
            : (STATE.ablation && STATE.ablation.baseline_output ? [STATE.ablation.baseline_output] : []);

        var samplesHtml = (
            (baselineOutputs.length
                ? '<details class="fp-inspector-samples"><summary>Baseline outputs (' + baselineOutputs.length + ')</summary>' +
                  baselineOutputs.map(function (t, i) { return '<pre class="fp-sample-text">Sample ' + (i + 1) + '\n' + escapeHtml(t) + '</pre>'; }).join('') +
                  '</details>'
                : '') +
            (ablatedOutputs.length
                ? '<details class="fp-inspector-samples"><summary>Ablated outputs (' + ablatedOutputs.length + ')</summary>' +
                  ablatedOutputs.map(function (t, i) { return '<pre class="fp-sample-text">Sample ' + (i + 1) + '\n' + escapeHtml(t) + '</pre>'; }).join('') +
                  '</details>'
                : '') ||
            '<p class="fp-empty">No sample outputs captured for this focus.</p>'
        );

        var rawJson;
        try {
            rawJson = JSON.stringify(row.source || {}, null, 2);
        } catch (e) {
            rawJson = 'Unable to serialize.';
        }

        return (
            '<aside class="fp-inspector' + openClass + '" aria-hidden="' + (STATE.inspectorOpen ? 'false' : 'true') + '">' +
            '<div class="fp-inspector-inner">' +
            '<button type="button" class="fp-inspector-close" data-action="close-inspector" aria-label="Close inspector">\u00d7</button>' +
            '<h3 class="fp-inspector-title">' + escapeHtml(row.name) + '</h3>' +
            '<div class="fp-inspector-section">' +
            '<h4>Source text</h4>' +
            '<pre class="fp-inspector-source">' + escapeHtml(row.prompt_section || '(no source text captured)') + '</pre>' +
            '</div>' +
            '<div class="fp-inspector-section">' +
            '<h4>Metrics</h4>' +
            '<ul class="fp-inspector-metrics">' +
            '<li><span>Reported</span><strong>' + fmtPct(row.reported) + '</strong></li>' +
            '<li><span>Revealed</span><strong>' + fmtPct(row.revealed) + '</strong></li>' +
            '<li><span>Gap</span><strong>' + fmtPts(row.gap) + '</strong></li>' +
            '<li><span>Baseline noise</span><strong>' + fmtNoise(row.baseline_noise) + '</strong></li>' +
            '<li><span>Ablated noise</span><strong>' + fmtNoise(row.ablated_noise) + '</strong></li>' +
            '<li><span>Order sensitivity</span><strong>' + fmtNoise(row.order_sensitivity) + '</strong></li>' +
            '</ul>' +
            '</div>' +
            '<div class="fp-inspector-section">' +
            '<h4>Archetypes</h4>' +
            '<div class="fp-inspector-archetypes">' + (archetypesHtml || '<p class="fp-empty">None detected.</p>') + '</div>' +
            '</div>' +
            '<div class="fp-inspector-section">' +
            '<h4>Samples</h4>' +
            samplesHtml +
            '</div>' +
            '<details class="fp-inspector-raw"><summary>Raw scores (JSON)</summary><pre class="fp-json-dump">' + escapeHtml(rawJson) + '</pre></details>' +
            '</div></aside>'
        );
    }

    // -----------------------------------------------------------------
    // Top-level render + event wiring
    // -----------------------------------------------------------------

    function renderAll() {
        if (!containerEl) return;
        if (!STATE.ablation) {
            containerEl.innerHTML = '<div class="fp-report fp-report-empty">' + renderHeader() + '</div>';
            return;
        }
        var html = (
            '<div class="fp-report">' +
            renderHeader() +
            renderNav() +
            '<div class="fp-view-body">' + renderView() + '</div>' +
            '</div>' +
            renderInspector()
        );
        containerEl.innerHTML = html;
    }

    function exportJson() {
        if (!STATE.ablation) return;
        var baselineOutputs = (Array.isArray(STATE.ablation.baseline_outputs) && STATE.ablation.baseline_outputs.length)
            ? STATE.ablation.baseline_outputs
            : (STATE.ablation.baseline_output ? [STATE.ablation.baseline_output] : []);
        var downloadData = Object.assign({}, STATE.ablation, { baseline_outputs: baselineOutputs });
        var jsonStr;
        try {
            jsonStr = JSON.stringify(downloadData, null, 2);
        } catch (e) {
            return;
        }
        var blob = new Blob([jsonStr], { type: 'application/json' });
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = 'focalprompt-ablation-results.json';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(function () { URL.revokeObjectURL(url); }, 0);
    }

    function selectFocus(name) {
        STATE.selectedFocus = name || null;
        STATE.inspectorOpen = !!name;
        renderAll();
    }

    function handleAction(el) {
        var action = el.getAttribute('data-action');
        if (action === 'set-view') {
            STATE.view = el.getAttribute('data-view') || 'overview';
            renderAll();
        } else if (action === 'select-focus') {
            selectFocus(el.getAttribute('data-focus'));
        } else if (action === 'close-inspector') {
            STATE.inspectorOpen = false;
            renderAll();
        } else if (action === 'export-json') {
            exportJson();
        } else if (action === 'toggle-dumbbell-all') {
            STATE.dumbbellShowAll = !STATE.dumbbellShowAll;
            renderAll();
        } else if (action === 'refresh-concordance') {
            if (typeof global.refreshExperimentCComparison === 'function') {
                Promise.resolve(global.refreshExperimentCComparison({ scroll: false })).then(function () {
                    refresh();
                });
            }
        } else if (action === 'explain-concordance') {
            var hiddenExplain = document.getElementById('explain-experiment-c-btn');
            if (hiddenExplain && !hiddenExplain.disabled) {
                hiddenExplain.click();
            }
        }
    }

    function bindEvents() {
        if (!containerEl || containerEl.getAttribute('data-fp-bound') === 'true') return;
        containerEl.setAttribute('data-fp-bound', 'true');

        containerEl.addEventListener('click', function (e) {
            var actionEl = e.target.closest && e.target.closest('[data-action]');
            if (actionEl) {
                handleAction(actionEl);
                return;
            }
            // Cooperate with the classic FocalPromptResults raw markup when embedded
            // in the Raw tab so its controls remain functional standalone.
            var toggleOutputs = e.target.closest && e.target.closest('#toggle-all-outputs');
            if (toggleOutputs) {
                var box = containerEl.querySelector('#all-outputs-container');
                if (box) {
                    var nowHidden = box.classList.toggle('hidden');
                    toggleOutputs.textContent = nowHidden ? 'Show sampled outputs' : 'Hide sampled outputs';
                }
                return;
            }
            var dlBtn = e.target.closest && e.target.closest('#download-ablation-results');
            if (dlBtn) {
                exportJson();
            }
        });

        containerEl.addEventListener('change', function (e) {
            var sortSel = e.target.closest && e.target.closest('[data-role="dumbbell-sort"]');
            if (sortSel) {
                STATE.dumbbellSort = sortSel.value;
                renderAll();
            }
        });
    }

    // -----------------------------------------------------------------
    // Public API
    // -----------------------------------------------------------------

    function render(ablation) {
        containerEl = document.getElementById(MOUNT_ID);
        if (!containerEl) return;
        bindEvents();
        STATE.ablation = ablation || null;
        STATE.bundle = deriveBundle(STATE.ablation);
        STATE.selectedFocus = null;
        STATE.view = 'overview';
        STATE.dumbbellSort = 'revealed';
        STATE.dumbbellShowAll = false;
        STATE.inspectorOpen = false;
        renderAll();
    }

    function refresh(ablation) {
        containerEl = containerEl || document.getElementById(MOUNT_ID);
        if (!containerEl) return;
        bindEvents();
        if (ablation !== undefined) {
            STATE.ablation = ablation;
        }
        STATE.bundle = deriveBundle(STATE.ablation);
        if (STATE.view === 'order' && !STATE.bundle.hasOrderData) {
            STATE.view = 'overview';
        }
        if (STATE.selectedFocus && !focusRowByName(STATE.selectedFocus)) {
            STATE.selectedFocus = null;
            STATE.inspectorOpen = false;
        }
        renderAll();
    }

    function getState() {
        return {
            ablation: STATE.ablation,
            selectedFocus: STATE.selectedFocus,
            view: STATE.view,
            dumbbellSort: STATE.dumbbellSort,
            dumbbellShowAll: STATE.dumbbellShowAll,
            inspectorOpen: STATE.inspectorOpen,
            bundle: STATE.bundle
        };
    }

    global.FocalPromptReport = {
        render: render,
        refresh: refresh,
        selectFocus: selectFocus,
        getState: getState,
        _deriveBundle: deriveBundle
    };
})(typeof window !== 'undefined' ? window : this);
