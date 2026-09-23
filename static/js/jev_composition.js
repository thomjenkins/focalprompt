/* Read-only provenance view of the actual composed messages; never composes new text. */
(function (global) {
    'use strict';
    const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const color = (value, fallback) => /^#[0-9a-f]{6}$/i.test(value || '') ? value : fallback;

    function describe(scenario, preview, sources) {
        if (!preview || !Array.isArray(preview.foci) || JSON.stringify(preview.scenario) !== JSON.stringify(scenario)) {
            throw new Error('The saved focus mapping does not match these prompt messages.');
        }
        const ranges = new Map(scenario.messages.map(m => [m.id, []]));
        for (const focus of preview.foci) {
            const index = focus.source_focus_index, source = sources[index];
            if (!Number.isInteger(index) || !source || source.focus !== focus.focus) throw new Error('Unknown source focus.');
            const label = {index, name: source.focus, color: color(source.color, '#dbeafe'), dark: color(source.colorDark, '#64748b')};
            const spans = focus.spans?.length ? focus.spans : [{...focus, text_snapshot: focus.prompt_section}];
            for (const span of spans) {
                const messageId = span.message_id || focus.message_id;
                const message = scenario.messages.find(m => m.id === messageId);
                const start = span.char_start, end = span.char_end, snapshot = span.text_snapshot ?? span.text;
                if (!message || message.analysis_mode !== 'analyse' || !Number.isInteger(start) || !Number.isInteger(end)
                    || start < 0 || end <= start || end > message.content.length || typeof snapshot !== 'string'
                    || message.content.slice(start, end) !== snapshot) throw new Error('A composed focus span cannot be verified.');
                ranges.get(messageId).push({start, end, label});
            }
        }
        return scenario.messages.map(message => {
            const spans = ranges.get(message.id);
            const points = [...new Set([0, message.content.length, ...spans.flatMap(s => [s.start, s.end])])].sort((a,b) => a-b);
            const segments = [];
            for (let i=0; i<points.length-1; i++) {
                const start=points[i], end=points[i+1];
                const foci=[...new Map(spans.filter(s => s.start<=start && s.end>=end).map(s => [s.label.index,s.label])).values()];
                const previous=segments.at(-1), text=message.content.slice(start,end);
                if (previous && JSON.stringify(previous.foci)===JSON.stringify(foci)) previous.text+=text;
                else segments.push({text, foci});
            }
            return {message, segments};
        });
    }
    function chip(focus) {
        return `<span class="jev-focus-chip" data-jev-source-focus="${focus.index}" title="${focus.index+1}. ${esc(focus.name)}" style="--jev-focus-bg:${focus.color};--jev-focus-edge:${focus.dark}"><span class="jev-focus-number">${focus.index+1}</span><span class="jev-focus-name">. ${esc(focus.name)}</span></span>`;
    }
    function render(scenario, preview, sources) {
        let messages;
        try { messages=describe(scenario,preview,sources); } catch (_) { return null; }
        return '<div class="jev-composed-scenario">' + messages.map(({message,segments}) => {
            const fragments=segments.filter(s => s.foci.length), count=new Set(fragments.flatMap(s => s.foci.map(f => f.index))).size;
            const retained=message.analysis_mode==='retain';
            const sequence=fragments.length ? `<ol class="jev-focus-thread" aria-label="Focus sequence in this message">${fragments.map(s => `<li>${s.foci.map(chip).join('')}</li>`).join('')}</ol>` : '';
            let prefix='';
            const content=segments.map(s => {
                if (!s.foci.length) {
                    if (s.text.trim()) { prefix+=s.text; return ''; }
                    return `<span class="jev-join" data-jev-text>${esc(s.text)}</span>`;
                }
                const backgrounds=s.foci.map(f => f.color), background=backgrounds.length===1 ? backgrounds[0] : `linear-gradient(90deg,${backgrounds.join(',')})`;
                const kept=prefix ? `<span class="jev-kept-text" data-jev-text>${esc(prefix)}</span>` : '';prefix='';
                return `<div class="jev-stitched-focus" data-jev-focus-indices="${s.foci.map(f=>f.index).join(',')}" style="--jev-focus-bg:${background};--jev-focus-edge:${s.foci[0].dark}"><div class="jev-fragment-label">${s.foci.map(chip).join('')} ${s.foci.length>1 ? '<span class="jev-shared-text">Shared text</span>' : ''}</div>${kept}<span data-jev-text>${esc(s.text)}</span></div>`;
            }).join('') + (prefix ? `<span class="jev-kept-text" data-jev-text>${esc(prefix)}</span>` : '');
            return `<section class="jev-composed-message" data-jev-message="${esc(message.id)}" data-retained="${retained}"><header><strong>${esc(message.id)} <span>· ${esc(message.role)}</span></strong><span>${retained ? 'Retained chat · unchanged' : `${count} ${count===1?'focus':'foci'} joined into this message`}</span></header>${sequence}<div class="jev-assembled-text">${content}</div></section>`;
        }).join('') + '</div>';
    }
    const api={describe,render};
    global.FocalPromptJevComposition=api;
    if (typeof module!=='undefined' && module.exports) module.exports=api;
})(typeof window!=='undefined' ? window : globalThis);
