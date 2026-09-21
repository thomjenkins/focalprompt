/* Saved singleton metrics rendered locally; no generation or rescoring. */
(function (global) {
    'use strict';
    const esc = value => escapeHtml(String(value ?? ''));
    const finite = Number.isFinite;
    const num = value => !finite(value) ? 'Unavailable'
        : value !== 0 && Math.abs(value) < .0001 ? value.toExponential(2) : value.toFixed(4);
    const pct = value => !finite(value) ? 'Unavailable' : `${value > 0 ? '+' : ''}${(value * 100).toFixed(1)}%`;
    function niceStep(value) {
        const power = 10 ** Math.floor(Math.log10(value || 1));
        return [1, 2, 2.5, 5, 10].find(step => step * power >= value) * power;
    }
    function axes(min, max, step, format, references = []) {
        const values = [min, max, ...references];
        for (let value = Math.ceil(min / step) * step; value < max; value += step) values.push(value);
        const ticks = [...new Set(values.map(v => Number(v.toPrecision(10))))].sort((a, b) => a - b);
        let previous = -Infinity;
        return `<div class="singleton-chart-axis"><span></span><div>${ticks.map(value => {
            const position = 100 * (value - min) / (max - min);
            // Keep labels readable when a reference nearly coincides with a tick.
            if (position - previous < 10 || (position > 90 && position < 99.99)) return '';
            previous = position;
            return `<span style="left:${position}%" class="${position < 1 ? 'at-start' : position > 99 ? 'at-end' : ''}">${esc(format(value))}</span>`;
        }).join('')}</div></div>`;
    }
    function label(focus, chart, selected) {
        return `<button type="button" class="singleton-chart-label" id="singleton-${chart}-label-${Number(focus.focus_index)}" data-singleton-chart-focus="${Number(focus.focus_index)}" aria-pressed="${selected === focus.focus_index}">${esc(focus.focus_index + 1)}. ${esc(focus.focus)}</button>`;
    }
    function render(result, rows, options) {
        if (!rows.length) return '';
        const alpha = finite(result.alpha) ? result.alpha : .05;
        const maxEffect = Math.max(0, ...rows.flatMap(f => [f.influence, f.necessity]).filter(finite));
        const effectStep = niceStep((maxEffect || .1) / 4);
        const effectMax = Math.max(effectStep, Math.ceil(maxEffect / effectStep) * effectStep);
        const gaps = rows.map(f => f.sufficiency).filter(finite);
        const gapStep = niceStep((Math.max(1, ...gaps) - Math.min(0, ...gaps)) / 4);
        const gapMin = Math.floor(Math.min(0, ...gaps) / gapStep) * gapStep;
        const gapMax = Math.ceil(Math.max(1, ...gaps) / gapStep) * gapStep;
        const gapPosition = value => 100 * (value - gapMin) / (gapMax - gapMin);
        const selected = rows.find(f => f.focus_index === options.selected);
        const unknownQ = rows.some(f => !finite(f.influence_comparison?.q_value) || !finite(f.necessity_comparison?.q_value));
        const series = [
            {key: 'influence', label: 'Added alone', visible: options.influence},
            {key: 'necessity', label: 'Removed from full', visible: options.necessity},
        ];
        let html = '<section class="singleton-charts" aria-labelledby="singleton-charts-heading"><h3 id="singleton-charts-heading">Focus effects at a glance</h3><p class="info-text">Select a focus or a plotted point for exact scores and output examples. Both charts use the order selected above.</p><div class="singleton-chart-panels">';
        html += '<figure class="singleton-effect-chart"><figcaption><h4>How much does the output change?</h4><p>Added alone vs no-focus; removed vs full prompt.</p></figcaption>';
        html += `<div class="singleton-chart-legend">${series.map(s => `<button type="button" id="singleton-chart-toggle-${s.key}" data-singleton-chart-toggle="${s.key}" class="singleton-chart-toggle ${s.key}" aria-pressed="${s.visible}"><span class="singleton-legend-dot"></span>${s.label}</button>`).join('')}</div>`;
        html += `<p class="singleton-chart-evidence">Filled: q &lt; ${alpha}. Outlined: q ≥ ${alpha}.${unknownQ ? ' Dashed: q unavailable.' : ''}</p>`;
        html += axes(0, effectMax, effectStep, v => Number(v.toPrecision(3)).toString());
        html += '<div class="singleton-chart-rows">';
        for (const f of rows) {
            html += `<div class="singleton-chart-row${selected === f ? ' is-selected' : ''}" data-singleton-chart-row="${Number(f.focus_index)}">${label(f, 'effect', options.selected)}<div class="singleton-effect-track" style="background-size:${100 * effectStep / effectMax}% 100%">`;
            for (const s of series) {
                if (!s.visible) continue;
                const value = f[s.key], q = f[s.key + '_comparison']?.q_value;
                if (!finite(value)) {
                    html += `<span class="singleton-point-unavailable ${s.key}">Unavailable</span>`;
                    continue;
                }
                const position = 100 * value / effectMax;
                const info = `${f.focus}: ${s.label} ${num(value)}; q ${num(q)}`;
                html += `<span class="singleton-effect-stem ${s.key}" style="width:${position}%"></span><button type="button" id="singleton-point-${s.key}-${Number(f.focus_index)}" class="singleton-effect-point ${s.key}${finite(q) ? q < alpha ? ' detected' : '' : ' unknown'}" style="left:${position}%" data-singleton-chart-focus="${Number(f.focus_index)}" data-series="${s.key}" data-value="${value}" title="${esc(info)}" aria-label="${esc(info)}" aria-pressed="${selected === f}"></button>`;
            }
            html += '</div></div>';
        }
        html += '</div><p class="singleton-chart-axis-label">Cosine distance between output centroids · larger = more change</p></figure>';
        html += '<figure class="singleton-gap-chart"><figcaption><h4>How close does one focus get to the full prompt?</h4><p>Full-prompt distance gap closed (sufficiency).</p></figcaption><p class="singleton-gap-key">0%: no progress · 100%: no measured gap<br>Negative: farther away than the no-focus baseline.</p><p class="singleton-chart-evidence">Descriptive distance ratio; no significance test.</p>';
        html += axes(gapMin, gapMax, gapStep, value => `${Math.round(value * 100)}%`, [0, 1]);
        html += '<div class="singleton-chart-rows">';
        for (const f of rows) {
            const value = f.sufficiency;
            html += `<div class="singleton-chart-row${selected === f ? ' is-selected' : ''}" data-singleton-chart-row="${Number(f.focus_index)}">${label(f, 'gap', options.selected)}<div class="singleton-gap-track"><span class="singleton-gap-zero" style="left:${gapPosition(0)}%"></span><span class="singleton-gap-full" title="100%: no measured gap from the full prompt" style="left:${gapPosition(1)}%"></span>`;
            if (finite(value)) {
                const start = Math.min(gapPosition(0), gapPosition(value));
                const width = Math.abs(gapPosition(value) - gapPosition(0));
                html += `<button type="button" id="singleton-gap-${Number(f.focus_index)}" class="singleton-gap-target" data-singleton-chart-focus="${Number(f.focus_index)}" data-value="${value}" aria-label="${esc(f.focus)}: ${pct(value)} of the full-prompt distance gap closed" title="${pct(value)} gap closed; singleton/full distance ${num(f.singleton_full_distance)}" aria-pressed="${selected === f}"><span class="singleton-gap-bar" style="left:${start}%;width:${width}%"></span><span class="singleton-gap-value">${pct(value)}</span></button>`;
            } else html += '<span class="singleton-gap-value">Unavailable</span>';
            html += '</div></div>';
        }
        html += '</div><p class="singleton-chart-axis-label">Distance gap closed · descriptive percentage, not a focus budget</p></figure></div>';
        if (!gaps.length) html += `<p class="info-text">Gap-closed values are unavailable. ${esc(result.normalized_metrics_note || 'The saved run has no valid sufficiency values.')}</p>`;
        html += '<div class="singleton-chart-readout" aria-live="polite">';
        if (selected) {
            html += `<strong>${esc(selected.focus_index + 1)}. ${esc(selected.focus)}</strong><p>Added alone: ${num(selected.influence)} (q ${num(selected.influence_comparison?.q_value)}) · Removed from full: ${num(selected.necessity)} (q ${num(selected.necessity_comparison?.q_value)}) · Gap closed: ${pct(selected.sufficiency)} · Singleton/full distance: ${num(selected.singleton_full_distance)}.</p><button type="button" class="btn btn-outline" data-singleton-inspect="${Number(selected.focus_index)}">Inspect all four output conditions</button>`;
        } else html += '<p>Select a focus to see its values and inspect its outputs.</p>';
        return html + '</div><p class="info-text">These charts measure changes in output meaning. Task quality needs separate evaluation; an outlined point does not establish that a focus is irrelevant.</p></section>';
    }
    global.FocalPromptSingletonCharts = {render};
})(window);
