/* Shared lab output browser: exact decoded text, with the original output always inspectable. */
(function (global) {
    'use strict';
    const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    function text(raw) {
        try { const value = JSON.parse(raw); if (typeof value.suggestedMessage === 'string') return value.suggestedMessage; } catch (_) { /* Plain text is already displayable. */ }
        return String(raw);
    }
    function render(outputs, options = {}) {
        const entries = Array.from(outputs || []).flatMap((raw,index) => typeof raw === 'string' ? [{raw,index}] : []);
        if (!entries.length) return '<p class="empty-state">No saved outputs.</p>';
        const selected = entries.some(entry => entry.index === options.selected) ? options.selected : entries[0].index;
        return `<div class="recorded-samples" data-sample-set="${esc(options.id || '')}">
            <div class="recorded-sample-toolbar"><strong>${esc(options.title || 'Saved outputs')}</strong><span>${entries.length} samples</span></div>
            <div class="recorded-sample-buttons" aria-label="Choose a saved output">${entries.map(({index:i}) => `<button type="button" data-recorded-sample="${i}" aria-pressed="${i === selected}" aria-label="Output ${i+1}">${i+1}</button>`).join('')}</div>
            ${entries.map(({raw,index:i}) => {
                const judgment = options.judgments?.find(j => j.sample_index === i);
                return `<div class="recorded-sample-panel" data-recorded-panel="${i}" ${i === selected ? '' : 'hidden'}><p class="info-text">Output ${i+1}</p><blockquote class="recorded-output">${esc(text(raw))}</blockquote>
                    ${judgment ? `<p class="recorded-judgment"><strong>${esc(judgment.classification)}</strong> · ${esc(judgment.rationale)}<small>Stored LLM judgment · not ground truth</small></p>` : ''}
                    <details class="recorded-raw"><summary>Exact exported output</summary><pre>${esc(raw)}</pre></details></div>`;
            }).join('')}</div>`;
    }
    function select(root, index) {
        if (!root?.querySelector(`[data-recorded-panel="${index}"]`)) return;
        root.querySelectorAll('[data-recorded-sample]').forEach(el => el.setAttribute('aria-pressed', String(Number(el.dataset.recordedSample) === index)));
        root.querySelectorAll('[data-recorded-panel]').forEach(el => { el.hidden = Number(el.dataset.recordedPanel) !== index; });
    }
    global.FocalPromptSamples = {render, select, text};
    global.document?.addEventListener('click', event => {
        const button = event.target.closest('[data-recorded-sample]');
        if (button) select(button.closest('.recorded-samples'), Number(button.dataset.recordedSample));
    });
    if (typeof module !== 'undefined' && module.exports) module.exports = global.FocalPromptSamples;
})(typeof window !== 'undefined' ? window : globalThis);
