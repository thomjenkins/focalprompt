/* Transfer a fresh workspace to a separate same-origin tab without persisting prompt data. */
(function (global) {
    'use strict';
    const prefix = 'focalprompt-workspace-';

    async function open(prepare) {
        const token = crypto.randomUUID(), url = new URL(global.location.href);
        url.search = ''; url.hash = 'analysis=' + token;
        const child = global.open(url.href, '_blank');
        if (!child) throw new Error('The browser blocked the new tab. Allow pop-ups or use Download analysis workspace.');
        let receive, timer;
        try {
            const delivery = new Promise((resolve, reject) => {
                let ready = false, workspace;
                const send = () => {
                    if (ready && workspace) child.postMessage({type: prefix + 'load', token, workspace}, url.origin);
                };
                receive = event => {
                    if (event.origin !== url.origin || event.source !== child || event.data?.token !== token) return;
                    if (event.data.type === prefix + 'ready') { ready = true; send(); }
                    if (event.data.type === prefix + 'loaded') resolve();
                    if (event.data.type === prefix + 'error') reject(new Error(event.data.error));
                };
                global.addEventListener('message', receive);
                timer = setTimeout(() => reject(new Error('The new tab did not finish loading. Try again or download the analysis workspace.')), 60000);
                Promise.resolve().then(prepare).then(data => { workspace = data; send(); }, reject);
            });
            await delivery;
        } catch (error) {
            child.close();
            throw error;
        } finally {
            clearTimeout(timer);
            global.removeEventListener('message', receive);
        }
    }

    function download(workspace, name) {
        const url = URL.createObjectURL(new Blob([JSON.stringify(workspace, null, 2)], {type: 'application/json'}));
        const anchor = document.createElement('a');
        anchor.href = url; anchor.download = name;
        document.body.appendChild(anchor); anchor.click(); anchor.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
    }

    function renderOrigin(origin) {
        const target = document.getElementById('analysis-origin');
        if (!target) return;
        target.hidden = !origin;
        const next = origin?.source_focus_indices?.length === 0
            ? 'Label any remaining instructions in step 1 before analysis. '
            : 'Begin with Predict focus in step 2. ';
        target.textContent = origin ? `${origin.title}. Fresh analysis using the composed prompt and selected foci. `
            + next + 'No previous outputs or scores are reused. ' + (origin.notes || []).join(' ') : '';
    }

    global.FocalPromptWorkspaceTransfer = {open, download, renderOrigin};
    const match = /^#analysis=([a-zA-Z0-9-]+)$/.exec(global.location.hash);
    if (!match || !global.opener) return;
    const token = match[1], parent = global.opener, origin = global.location.origin;
    const receive = event => {
        if (event.origin !== origin || event.source !== parent || event.data?.token !== token
            || event.data.type !== prefix + 'load') return;
        global.removeEventListener('message', receive);
        try {
            const workspace = event.data.workspace;
            const error = validateWorkspaceSession(workspace);
            if (error) throw new Error(typeof error === 'string' ? error : 'Expected a complete workspace.');
            global.restoreWorkspaceSession(workspace);
            global.history.replaceState(null, '', global.location.pathname + '#lab-prospective');
            document.getElementById('analysis-origin')?.scrollIntoView({block: 'center'});
            parent.postMessage({type: prefix + 'loaded', token}, origin);
            global.opener = null;
        } catch (error) {
            parent.postMessage({type: prefix + 'error', token, error: error.message}, origin);
        }
    };
    global.addEventListener('message', receive);
    const ready = () => parent.postMessage({type: prefix + 'ready', token}, origin);
    if (global.focalPromptWorkspaceReady) ready();
    else global.addEventListener('focalprompt:ready', ready, {once: true});
})(window);
