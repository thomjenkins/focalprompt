/**
 * Deterministic interpretability metrics for experiment results — browser mirror
 * of utils/insight_metrics.py. Thresholds, archetype keys, and function
 * behaviour MUST stay in sync with the Python module.
 */
(function (global) {
    'use strict';

    var THRESHOLDS = {
        high_revealed: 12.0,
        low_revealed: 10.0,
        high_reported: 15.0,
        low_reported: 8.0,
        mismatch_gap: 12.0,
        stabilizer_noise_delta: 0.08,
        destabilizer_noise_delta: 0.08,
        order_sensitive: 0.12,
        concentration_high: 0.60,
        concentration_medium: 0.40,
        agreement_high: 0.70,
        agreement_medium: 0.45,
        stability_high_noise: 0.35,
        stability_medium_noise: 0.20,
        order_high: 0.20,
        order_medium: 0.10
    };

    var ARCHETYPE_HELP = {
        anchor: 'High revealed influence with moderate/high reported attention.',
        hidden_driver: 'Low reported attention, high revealed behavioural influence.',
        claimed_but_inert: 'High reported attention, low revealed influence.',
        stabilizer: 'Removing this focus materially increases output noise.',
        destabilizer: 'Removing this focus materially decreases output noise.',
        order_sensitive: 'Behavioural effect depends on ordinal position.',
        redundant: 'Persistently low reported attention and low revealed influence.'
    };

    var ARCHETYPE_LABELS = {
        anchor: 'Anchor',
        hidden_driver: 'Hidden driver',
        claimed_but_inert: 'Claimed but inert',
        stabilizer: 'Stabilizer',
        destabilizer: 'Destabilizer',
        order_sensitive: 'Order-sensitive',
        redundant: 'Redundant'
    };

    function mergeThresholds(overrides) {
        var t = {};
        Object.keys(THRESHOLDS).forEach(function (k) { t[k] = THRESHOLDS[k]; });
        if (overrides) {
            Object.keys(overrides).forEach(function (k) { t[k] = overrides[k]; });
        }
        return t;
    }

    function toFloat(value, fallback) {
        fallback = fallback === undefined ? 0.0 : fallback;
        if (value === null || value === undefined) return fallback;
        var n = Number(value);
        return Number.isFinite(n) ? n : fallback;
    }

    function normalizeShare(values) {
        var cleaned = (values || []).map(function (v) { return Math.max(0.0, toFloat(v)); });
        var total = cleaned.reduce(function (a, b) { return a + b; }, 0);
        if (total <= 0) {
            var n = cleaned.length;
            if (!n) return [];
            var even = 100.0 / n;
            return cleaned.map(function () { return even; });
        }
        return cleaned.map(function (v) { return (v / total) * 100.0; });
    }

    function reportedRevealedGap(reported, revealed) {
        return toFloat(reported) - toFloat(revealed);
    }

    function classifyArchetypes(opts) {
        opts = opts || {};
        var t = mergeThresholds(opts.thresholds);
        var labels = [];

        var hasReported = opts.reported !== null && opts.reported !== undefined;
        var hasRevealed = opts.revealed !== null && opts.revealed !== undefined;
        var r = hasReported ? toFloat(opts.reported) : null;
        var v = hasRevealed ? toFloat(opts.revealed) : null;

        if (hasReported && hasRevealed && r !== null && v !== null) {
            if (v >= t.high_revealed && r >= t.low_reported) {
                labels.push('anchor');
            }
            if (r <= t.low_reported && v >= t.high_revealed) {
                labels.push('hidden_driver');
            }
            if (r >= t.high_reported && v <= t.low_revealed) {
                labels.push('claimed_but_inert');
            }
            if (r <= t.low_reported && v <= t.low_revealed) {
                labels.push('redundant');
            }
        }

        var baselineNoise = opts.baseline_noise;
        var ablatedNoise = opts.ablated_noise;
        if (baselineNoise !== null && baselineNoise !== undefined &&
            ablatedNoise !== null && ablatedNoise !== undefined) {
            var delta = toFloat(ablatedNoise) - toFloat(baselineNoise);
            if (delta >= t.stabilizer_noise_delta) {
                labels.push('stabilizer');
            }
            if ((-delta) >= t.destabilizer_noise_delta) {
                labels.push('destabilizer');
            }
        }

        var orderSensitivity = opts.order_sensitivity;
        if (orderSensitivity !== null && orderSensitivity !== undefined &&
            Math.abs(toFloat(orderSensitivity)) >= t.order_sensitive) {
            labels.push('order_sensitive');
        }

        var seen = {};
        var out = [];
        labels.forEach(function (lab) {
            if (!seen[lab]) {
                seen[lab] = true;
                out.push(lab);
            }
        });
        return out;
    }

    function bandFromThresholds(value, opts) {
        opts = opts || {};
        var highAt = opts.high_at;
        var mediumAt = opts.medium_at;
        var higherIsStronger = opts.higher_is_stronger !== false;
        var v = toFloat(value);
        if (higherIsStronger) {
            if (v >= highAt) return 'High';
            if (v >= mediumAt) return 'Medium';
            return 'Low';
        }
        if (v >= highAt) return 'Low';
        if (v >= mediumAt) return 'Medium';
        return 'High';
    }

    function statusStrip(opts) {
        opts = opts || {};
        var t = mergeThresholds(opts.thresholds);
        var out = {};

        var top3RevealedShare = opts.top3_revealed_share;
        if (top3RevealedShare !== null && top3RevealedShare !== undefined) {
            var share = toFloat(top3RevealedShare);
            if (share > 1.0) {
                share = share / 100.0;
            }
            out.influence_concentration = {
                level: bandFromThresholds(share, {
                    high_at: t.concentration_high,
                    medium_at: t.concentration_medium
                }),
                help: (
                    'Share of total revealed influence held by the top three foci. ' +
                    'High \u2265 ' + Math.round(t.concentration_high * 100) + '%, Medium \u2265 ' +
                    Math.round(t.concentration_medium * 100) + '%.'
                )
            };
        }

        var meanAbsGap = opts.mean_abs_gap;
        if (meanAbsGap !== null && meanAbsGap !== undefined) {
            var agreement = Math.max(0.0, Math.min(1.0, 1.0 - (toFloat(meanAbsGap) / 100.0)));
            out.reported_revealed_agreement = {
                level: bandFromThresholds(agreement, {
                    high_at: t.agreement_high,
                    medium_at: t.agreement_medium
                }),
                help: (
                    'Agreement between reported-focus scores and revealed influence shares. ' +
                    'Derived from mean absolute gap (percentage points).'
                )
            };
        }

        var baselineNoise = opts.baseline_noise;
        if (baselineNoise !== null && baselineNoise !== undefined) {
            out.baseline_stability = {
                level: bandFromThresholds(toFloat(baselineNoise), {
                    high_at: t.stability_high_noise,
                    medium_at: t.stability_medium_noise,
                    higher_is_stronger: false
                }),
                help: (
                    'Inverse of baseline sample dispersion. Higher noise \u21d2 lower stability. ' +
                    'Low stability when noise \u2265 ' + t.stability_high_noise + '.'
                )
            };
        }

        var meanOrderSensitivity = opts.mean_order_sensitivity;
        if (meanOrderSensitivity !== null && meanOrderSensitivity !== undefined) {
            out.order_sensitivity = {
                level: bandFromThresholds(Math.abs(toFloat(meanOrderSensitivity)), {
                    high_at: t.order_high,
                    medium_at: t.order_medium
                }),
                help: (
                    'Mean absolute order-sensitivity across foci when order/shuffle ' +
                    'analysis is available.'
                )
            };
        }

        return out;
    }

    function selectInsightCards(foci, opts) {
        opts = opts || {};
        var t = mergeThresholds(opts.thresholds);
        var maxCards = opts.max_cards === undefined || opts.max_cards === null ? 4 : opts.max_cards;

        var candidates = [];

        function add(name, kind, priority, interpretation, numbers) {
            candidates.push({
                priority: priority,
                card: {
                    kind: kind,
                    focus: name,
                    interpretation: interpretation,
                    numbers: numbers
                }
            });
        }

        (foci || []).forEach(function (row) {
            var name = String((row.name || row.focus || '')).trim();
            if (!name) return;
            var reported = row.reported === undefined ? null : row.reported;
            var revealed = row.revealed === undefined ? null : row.revealed;
            var gap = row.gap === undefined ? null : row.gap;
            if ((gap === null || gap === undefined) && reported !== null && reported !== undefined &&
                revealed !== null && revealed !== undefined) {
                gap = reportedRevealedGap(toFloat(reported), toFloat(revealed));
            }
            var archetypes = (row.archetypes || []).slice();
            if (!archetypes.length) {
                archetypes = classifyArchetypes({
                    reported: reported,
                    revealed: revealed,
                    baseline_noise: row.baseline_noise,
                    ablated_noise: row.ablated_noise,
                    order_sensitivity: row.order_sensitivity,
                    thresholds: t
                });
            }

            if (archetypes.indexOf('hidden_driver') !== -1 && revealed !== null && revealed !== undefined) {
                add(
                    name, 'hidden_driver', 100.0 + toFloat(revealed),
                    'Low reported attention but strong behavioural influence when removed.',
                    { reported: reported, revealed: revealed, gap: gap }
                );
            }
            if (archetypes.indexOf('claimed_but_inert') !== -1 && reported !== null && reported !== undefined) {
                add(
                    name, 'claimed_but_inert', 90.0 + toFloat(reported),
                    'High reported attention with little revealed behavioural influence.',
                    { reported: reported, revealed: revealed, gap: gap }
                );
            }
            if (gap !== null && gap !== undefined && Math.abs(toFloat(gap)) >= t.mismatch_gap) {
                add(
                    name, 'mismatch', 80.0 + Math.abs(toFloat(gap)),
                    'Large reported-vs-revealed disagreement for this focus.',
                    { reported: reported, revealed: revealed, gap: gap }
                );
            }
            if (archetypes.indexOf('stabilizer') !== -1) {
                var bn1 = row.baseline_noise;
                var an1 = row.ablated_noise;
                add(
                    name, 'stabilizer', 70.0 + (toFloat(an1) - toFloat(bn1)),
                    'Removing this focus increases output noise — likely a stabilizer.',
                    { baseline_noise: bn1, ablated_noise: an1 }
                );
            }
            if (archetypes.indexOf('destabilizer') !== -1) {
                var bn2 = row.baseline_noise;
                var an2 = row.ablated_noise;
                add(
                    name, 'destabilizer', 70.0 + (toFloat(bn2) - toFloat(an2)),
                    'Removing this focus decreases output noise — likely a destabilizer.',
                    { baseline_noise: bn2, ablated_noise: an2 }
                );
            }
            if (archetypes.indexOf('order_sensitive') !== -1) {
                var os_ = row.order_sensitivity;
                add(
                    name, 'order_sensitive', 60.0 + Math.abs(toFloat(os_)),
                    'Behavioural effect depends on where this focus sits in the prompt.',
                    { order_sensitivity: os_ }
                );
            }
            if (archetypes.indexOf('redundant') !== -1) {
                add(
                    name, 'redundant', 40.0,
                    'Low reported attention and low revealed influence — often inert.',
                    { reported: reported, revealed: revealed }
                );
            }
        });

        candidates.sort(function (a, b) { return b.priority - a.priority; });

        var selected = [];
        var usedKinds = {};
        var usedFoci = {};
        for (var i = 0; i < candidates.length; i++) {
            if (selected.length >= maxCards) break;
            var card = candidates[i].card;
            if (usedKinds[card.kind]) continue;
            if (usedFoci[card.focus]) continue;
            selected.push(card);
            usedKinds[card.kind] = true;
            usedFoci[card.focus] = true;
        }
        return selected;
    }

    function overviewHeadline(foci, opts) {
        opts = opts || {};
        var t = mergeThresholds(opts.thresholds);

        var rows = (foci || [])
            .filter(function (r) { return String(r.name || r.focus || '').trim(); })
            .map(function (r) { return Object.assign({}, r); });
        if (!rows.length) {
            return 'No focus-level results are available for this run yet.';
        }

        rows.forEach(function (row) {
            if ((row.gap === null || row.gap === undefined) &&
                row.reported !== null && row.reported !== undefined &&
                row.revealed !== null && row.revealed !== undefined) {
                row.gap = reportedRevealedGap(toFloat(row.reported), toFloat(row.revealed));
            }
        });

        var n = rows.length;
        var revealedVals = rows.map(function (r) { return toFloat(r.revealed); });
        var ranked = rows
            .map(function (r, i) { return { v: revealedVals[i], row: r }; })
            .sort(function (a, b) { return b.v - a.v; });
        var topK = Math.min(3, n);
        var topShare = revealedVals.length
            ? ranked.slice(0, topK).reduce(function (sum, item) { return sum + item.v; }, 0)
            : 0.0;
        var gaps = rows
            .filter(function (r) { return r.gap !== null && r.gap !== undefined; })
            .map(function (r) { return Math.abs(toFloat(r.gap)); });
        var meanGap = gaps.length ? (gaps.reduce(function (a, b) { return a + b; }, 0) / gaps.length) : null;

        var parts = [];
        if (meanGap !== null && meanGap >= t.mismatch_gap) {
            parts.push("The model's reported focus differs materially from its strongest behavioural drivers.");
        } else if (meanGap !== null) {
            parts.push('Reported focus and revealed influence are broadly aligned for this run.');
        } else {
            parts.push(
                'Revealed behavioural influence is available; reported-focus scores were not paired for every focus.'
            );
        }
        if (topShare > 0) {
            parts.push(
                topK + ' of ' + n + ' prompt sections account for ' + topShare.toFixed(0) + '% of revealed influence.'
            );
        }
        return parts.join(' ');
    }

    function nextExperimentSuggestions(foci, status) {
        status = status || {};
        var suggestions = [];
        var byKind = {};
        (foci || []).forEach(function (row) {
            var name = String(row.name || row.focus || '').trim();
            (row.archetypes || []).forEach(function (lab) {
                lab = String(lab);
                if (!byKind[lab]) byKind[lab] = [];
                byKind[lab].push(name);
            });
        });

        if (byKind.claimed_but_inert && byKind.claimed_but_inert.length) {
            var focusA = byKind.claimed_but_inert[0];
            suggestions.push(
                'Test shortening or relocating \u201c' + focusA + '\u201d (claimed but inert) and re-measure revealed influence.'
            );
        }
        if (byKind.hidden_driver && byKind.hidden_driver.length) {
            var focusB = byKind.hidden_driver[0];
            suggestions.push(
                'Try moving hidden driver \u201c' + focusB + '\u201d earlier in the prompt and compare order sensitivity.'
            );
        }
        if ((!byKind.claimed_but_inert || !byKind.claimed_but_inert.length) &&
            (!byKind.hidden_driver || !byKind.hidden_driver.length)) {
            var gaps = [];
            (foci || []).forEach(function (row) {
                var name = String(row.name || row.focus || '').trim();
                if (name && row.gap !== null && row.gap !== undefined) {
                    gaps.push({ abs: Math.abs(toFloat(row.gap)), name: name, signed: toFloat(row.gap) });
                }
            });
            if (gaps.length) {
                gaps.sort(function (a, b) { return b.abs - a.abs; });
                var top = gaps[0];
                if (top.signed > 0) {
                    suggestions.push(
                        'Test whether \u201c' + top.name + '\u201d is over-claimed: high reported attention vs lower revealed influence.'
                    );
                } else {
                    suggestions.push(
                        'Test elevating \u201c' + top.name + '\u201d: low reported attention vs higher revealed influence.'
                    );
                }
            }
        }
        if (byKind.destabilizer && byKind.destabilizer.length) {
            var focusC = byKind.destabilizer[0];
            suggestions.push(
                'Rewrite destabilizing section \u201c' + focusC + '\u201d while preserving its information; re-check baseline noise.'
            );
        }
        if ((status.baseline_stability || {}).level === 'Low') {
            suggestions.push(
                'Increase baseline sample count — current baseline dispersion is high relative to the signal.'
            );
        }
        if (['High', 'Medium'].indexOf((status.order_sensitivity || {}).level) !== -1) {
            suggestions.push(
                'Run or expand focus-order / shuffle analysis to confirm positional effects before rewriting.'
            );
        }
        if ((status.reported_revealed_agreement || {}).level === 'Low') {
            suggestions.push(
                'Compare two models on the same prompt to see whether reported/revealed disagreement is model-specific.'
            );
        }

        var out = [];
        for (var i = 0; i < suggestions.length; i++) {
            if (out.indexOf(suggestions[i]) === -1) {
                out.push(suggestions[i]);
            }
            if (out.length >= 4) break;
        }
        return out;
    }

    function buildFocusRows(opts) {
        opts = opts || {};
        var t = mergeThresholds(opts.thresholds);

        var reportedBy = {};
        (opts.assessment_foci || []).forEach(function (f) {
            var name = String((f.focus || f.name || '')).trim();
            if (name && f.score !== null && f.score !== undefined) {
                reportedBy[name.toLowerCase()] = toFloat(f.score);
            }
        });

        var rawRevealed = [];
        var names = [];
        var meta = [];
        (opts.influence_scores || []).forEach(function (item) {
            var name = String((item.focus || item.focus_name || '')).trim();
            if (!name) return;
            if (item.attributable === false) return;
            var ni = item.normalized_influence;
            if (ni === null || ni === undefined) {
                ni = item.influence !== null && item.influence !== undefined
                    ? item.influence
                    : (item.t_obs !== null && item.t_obs !== undefined ? item.t_obs : 0.0);
            }
            rawRevealed.push(toFloat(ni));
            names.push(name);
            meta.push(item);
        });

        var total = rawRevealed.reduce(function (a, b) { return a + b; }, 0);
        var shares;
        if (total <= 0) {
            shares = normalizeShare(rawRevealed);
        } else if (total >= 80.0 && total <= 120.0) {
            shares = rawRevealed.slice();
        } else {
            shares = normalizeShare(rawRevealed);
        }

        var orderByFocus = opts.order_by_focus || null;
        var baselineNoise = opts.baseline_noise === undefined ? null : opts.baseline_noise;

        var rows = [];
        for (var i = 0; i < names.length; i++) {
            var name = names[i];
            var share = shares[i];
            var item = meta[i];
            var reported = Object.prototype.hasOwnProperty.call(reportedBy, name.toLowerCase())
                ? reportedBy[name.toLowerCase()]
                : null;

            var ablatedNoise = null;
            var stab = item.ablation_stability || item.stability || null;
            if (stab && typeof stab === 'object') {
                ablatedNoise = stab.mean_pairwise_cosine_distance;
                if (ablatedNoise === null || ablatedNoise === undefined) {
                    ablatedNoise = stab.dispersion;
                }
            }

            var orderS = null;
            if (orderByFocus) {
                if (Object.prototype.hasOwnProperty.call(orderByFocus, name)) {
                    orderS = orderByFocus[name];
                } else if (Object.prototype.hasOwnProperty.call(orderByFocus, name.toLowerCase())) {
                    orderS = orderByFocus[name.toLowerCase()];
                }
            }

            var gap = (reported === null || reported === undefined) ? null : reportedRevealedGap(reported, share);
            var archetypes = classifyArchetypes({
                reported: reported,
                revealed: share,
                baseline_noise: baselineNoise,
                ablated_noise: (ablatedNoise === null || ablatedNoise === undefined) ? null : toFloat(ablatedNoise),
                order_sensitivity: (orderS === null || orderS === undefined) ? null : toFloat(orderS),
                thresholds: t
            });

            rows.push({
                name: name,
                focus: name,
                reported: reported,
                revealed: share,
                gap: gap,
                baseline_noise: baselineNoise,
                ablated_noise: (ablatedNoise === null || ablatedNoise === undefined) ? null : toFloat(ablatedNoise),
                order_sensitivity: (orderS === null || orderS === undefined) ? null : toFloat(orderS),
                archetypes: archetypes,
                prompt_section: item.prompt_section || item.focus_text || '',
                source: item
            });
        }
        return rows;
    }

    global.FocalPromptInsightMetrics = {
        THRESHOLDS: THRESHOLDS,
        ARCHETYPE_LABELS: ARCHETYPE_LABELS,
        ARCHETYPE_HELP: ARCHETYPE_HELP,
        normalizeShare: normalizeShare,
        reportedRevealedGap: reportedRevealedGap,
        classifyArchetypes: classifyArchetypes,
        bandFromThresholds: bandFromThresholds,
        statusStrip: statusStrip,
        selectInsightCards: selectInsightCards,
        overviewHeadline: overviewHeadline,
        nextExperimentSuggestions: nextExperimentSuggestions,
        buildFocusRows: buildFocusRows
    };
})(typeof window !== 'undefined' ? window : this);
