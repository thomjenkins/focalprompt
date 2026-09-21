/* Pairwise output resemblance; percentages are descriptive, not focus budgets. */
(function (global) {
    'use strict';
    const esc = value => escapeHtml(String(value ?? ''));
    const num = value => value == null ? 'Unavailable'
        : value !== 0 && Math.abs(value) < .0001 ? value.toExponential(2) : value.toFixed(4);
    const percent = value => (100 * value).toFixed(1) + '%';
    const views = {full: 'Full prompt', ablations: 'Eligible ablations', combined: 'Full + eligible ablations'};
    function oriented(summary, reverse) {
        if (!summary || !reverse) return summary;
        return {...summary, row_share: 1 - summary.row_share, mean_gap: -summary.mean_gap,
            row_distance: summary.column_distance, column_distance: summary.row_distance};
    }
    function conditionScore(condition, i, j, tolerance) {
        let wins = 0, ties = 0, rowDistance = 0, columnDistance = 0;
        for (const distances of condition.distances) {
            const gap = distances[j] - distances[i];
            if (Math.abs(gap) <= tolerance) ties++;
            else if (gap > tolerance) wins++;
            rowDistance += distances[i]; columnDistance += distances[j];
        }
        const n = condition.distances.length;
        return {row_share: (wins + ties / 2) / n, ties, wins, n,
            mean_gap: (columnDistance - rowDistance) / n,
            row_distance: rowDistance / n, column_distance: columnDistance / n};
    }
    function conditionName(condition, rows) {
        return condition.kind === 'baseline' ? 'Full prompt'
            : `Remove ${condition.removed_focus_index + 1}. ${rows.find(f => f.focus_index === condition.removed_focus_index)?.focus || ''}`;
    }
    function detail(result, rows, view, selection) {
        if (!selection) return '<p class="info-text">Select a cell to inspect its comparisons and outputs.</p>';
        const data = result.pairwise_resemblance, [i, j] = selection;
        const row = rows.find(f => f.focus_index === i), column = rows.find(f => f.focus_index === j);
        const pair = data.pairs.find(p => p.row_index === Math.min(i, j) && p.column_index === Math.max(i, j));
        if (!pair || !row || !column) return '';
        let html = `<h4>${esc(row.focus)} (row) vs ${esc(column.focus)} (column)</h4>`;
        if (pair.unavailable_reason) return html + `<p>${esc(pair.unavailable_reason)}</p>`;
        const score = oriented(pair.views[view], i > j);
        if (!score) return html + '<p>No eligible ablations retain both complete foci. The full-prompt view may still be available.</p>';
        html += `<p><strong>${percent(score.row_share)} closer to ${esc(row.focus)}</strong>, counting each tie as half. ${esc(score.condition_count)} distinct prompt condition(s), ${esc(score.output_count)} unique sampled outputs. Mean similarity gap: ${num(score.mean_gap)} (positive favors the row).</p>
            <p class="info-text">Singleton centroid separation: ${num(pair.singleton_distance)}. Mean singleton distance to its own centroid: ${num(data.singleton_dispersion[i])} for the row; ${num(data.singleton_dispersion[j])} for the column. Small gaps or variable singletons warrant inspecting the outputs.</p>`;
        const keepsBoth = c => c.intact_focus_indices.includes(i) && c.intact_focus_indices.includes(j);
        const eligible = data.conditions.filter(c => keepsBoth(c)
            && (view === 'combined' || (view === 'full' ? c.kind === 'baseline' : c.kind === 'ablated')));
        const pools = new Map();
        for (const c of eligible) {
            const saved = pools.get(c.pool_id);
            if (!saved || c.distances.length > saved.distances.length) pools.set(c.pool_id, c);
        }
        html += '<div class="workflow-table-wrap"><table class="workflow-table"><thead><tr><th scope="col">Context</th><th scope="col">Closer to row</th><th scope="col">Row / column / tied</th><th scope="col">Mean distance to row</th><th scope="col">Mean distance to column</th><th scope="col">Mean gap</th></tr></thead><tbody>';
        for (const c of pools.values()) {
            const s = conditionScore(c, i, j, data.tie_tolerance);
            html += `<tr><th scope="row">${esc(conditionName(c, rows))}</th><td>${percent(s.row_share)}</td><td>${s.wins} / ${s.n - s.wins - s.ties} / ${s.ties}</td><td>${num(s.row_distance)}</td><td>${num(s.column_distance)}</td><td>${num(s.mean_gap)}</td></tr>`;
        }
        html += '</tbody></table></div><p class="info-text">Each distinct prompt has equal weight. Equivalent prompts share samples and count once. A share near 50% can mean ties or a mixture of opposing outputs; use the counts above.</p>';
        const excluded = data.conditions.filter(c => !keepsBoth(c));
        if (excluded.length) html += `<details><summary>${excluded.length} excluded conditions</summary><ul>${excluded.map(c => `<li>${esc(conditionName(c, rows))}: removes some or all of one of these foci.</li>`).join('')}</ul></details>`;
        for (const index of [i, j]) {
            const f = rows.find(item => item.focus_index === index);
            html += `<details><summary>Singleton reference: ${esc(f.focus)}</summary>`;
            if (f.shared_text_retained_for_excluded?.length) html += '<p>This singleton retains text shared with other labelled foci.</p>';
            html += result.arms['singleton_' + index].outputs.map((output, k) => `<details><summary>Output ${k + 1}</summary><pre class="pairwise-output">${esc(output)}</pre></details>`).join('') + '</details>';
        }
        html += '<details><summary>Compared outputs and individual distances</summary>';
        for (const c of pools.values()) {
            html += `<details><summary>${esc(conditionName(c, rows))}</summary>`;
            for (const [k, distances] of c.distances.entries()) {
                html += `<details><summary>Output ${k + 1} · row distance ${num(distances[i])} · column distance ${num(distances[j])}</summary><pre class="pairwise-output">${esc(result.arms[c.id].outputs[k])}</pre></details>`;
            }
            html += '</details>';
        }
        return html + '</details>';
    }
    function render(result, rows, view, selection, busy) {
        const data = result.pairwise_resemblance;
        let html = '<section class="pairwise-results" aria-labelledby="pairwise-heading"><h3 id="pairwise-heading">Pairwise behavioral resemblance</h3>';
        if (!data) return html + `<p>Compare saved outputs with each focus’s singleton pattern in contexts where both foci remain present.</p><button type="button" class="btn btn-outline" id="singleton-pairwise-btn"${busy ? ' disabled' : ''}>Build grid from saved outputs</button><p class="info-text">No new outputs are generated. Computing embeddings may incur a charge.</p></section>`;
        if (rows.length < 2) return html + '<p>At least two foci are needed for a pairwise grid.</p></section>';
        html += `<p>Each cell shows the share closer to the <strong>row’s singleton</strong> than the column’s singleton. The small Δ is the mean cosine-distance gap; positive favors the row. Ties count as half. Only contexts retaining both complete foci count.</p>
            <div class="singleton-result-controls"><label for="pairwise-view">Compare outputs from</label><select id="pairwise-view">${Object.entries(views).map(([key, label]) => `<option value="${key}"${view === key ? ' selected' : ''}>${label}</option>`).join('')}</select></div>
            <p class="pairwise-legend"><span class="pairwise-column-key">0%: column closer</span><span>50%: balanced or tied</span><span class="pairwise-row-key">100%: row closer</span></p>
            <p class="info-text">Descriptive resemblance, not a focus budget, confidence score, or proof of causal dominance. A high share with a tiny gap can reflect only a slight difference. Rows and columns follow the selected result order.</p>
            <div class="pairwise-grid-wrap" tabindex="0" role="region" aria-label="Pairwise focus resemblance grid"><table class="pairwise-grid"><thead><tr><th scope="col">Row ↓ / Column →</th>${rows.map(f => `<th scope="col" title="${esc(f.focus)}"><span class="pairwise-column-name">${f.focus_index + 1}. ${esc(f.focus)}</span></th>`).join('')}</tr></thead><tbody>`;
        const lookup = new Map(data.pairs.map(p => [`${p.row_index}:${p.column_index}`, p]));
        for (const row of rows) {
            const i = row.focus_index;
            html += `<tr><th scope="row">${i + 1}. ${esc(row.focus)}</th>`;
            for (const column of rows) {
                const j = column.focus_index;
                if (i === j) { html += '<td class="pairwise-diagonal" aria-label="Same focus">—</td>'; continue; }
                const pair = lookup.get(`${Math.min(i,j)}:${Math.max(i,j)}`);
                const score = oriented(pair?.views[view], i > j);
                const label = `${row.focus} vs ${column.focus}: ` + (score ? `${percent(score.row_share)} closer to row; mean gap ${num(score.mean_gap)}` : pair?.unavailable_reason || 'No eligible conditions');
                const strength = score ? .06 + .38 * Math.abs(2 * score.row_share - 1) : 0;
                const color = score ? `rgba(${score.row_share >= .5 ? '38,119,180' : '216,128,49'},${strength})` : '#f1f5f9';
                html += `<td><button type="button" id="pairwise-cell-${i}-${j}" class="pairwise-cell" data-pairwise-row="${i}" data-pairwise-column="${j}" aria-label="${esc(label)}" title="${esc(label)}" aria-pressed="${selection?.[0] === i && selection?.[1] === j}" style="background:${color}">${score ? `${percent(score.row_share)}<small>Δ ${num(score.mean_gap)}</small>` : '—'}</button></td>`;
            }
            html += '</tr>';
        }
        html += '</tbody></table></div><p class="info-text">— means the pair is unavailable: shared labelled text, indistinguishable or undefined singleton centroids, or no eligible contexts. Select the cell for its reason.</p>';
        html += `<div id="pairwise-detail" class="pairwise-detail" aria-live="polite">${detail(result, rows, view, selection)}</div>`;
        html += `<details><summary>How this grid is calculated</summary><p>Evaluator: ${esc(data.evaluator_model || result.evaluator?.model)}. Numerical tie tolerance: ${esc(data.tie_tolerance)}.</p>${data.notes.map(note => `<p>${esc(note)}</p>`).join('')}</details></section>`;
        return html;
    }
    global.FocalPromptPairwise = {render, conditionScore, oriented};
})(window);
