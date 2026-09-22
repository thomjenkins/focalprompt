/* Loaded only by the replay route, before the unmodified lab initializers. */
(function (global) {
    'use strict';
    global.FOCALPROMPT_REPLAY = true;
    const memory = new Map();
    // Model restoration and UI preferences must never touch another lab tab's storage.
    global.FocalPromptReplayStorage = {
        getItem: key => memory.get(key) ?? null,
        setItem: (key, value) => memory.set(key, String(value)),
        removeItem: key => memory.delete(key)
    };
    const fetchOriginal = global.fetch.bind(global);
    global.fetch = (resource, options) => {
        const url = new URL(typeof resource === 'string' || resource instanceof URL ? resource : resource.url, global.location.href);
        if (url.origin === global.location.origin && /^\/demo\/lisbon\/workspaces\/[a-z0-9_-]+\.json$/.test(url.pathname)
            && (options?.method || resource?.method || 'GET').toUpperCase() === 'GET') return fetchOriginal(resource, options);
        // A final guard for programmatic calls and any newly added run control.
        // No network request leaves the browser in recorded mode.
        return Promise.resolve(new Response(JSON.stringify({error: 'Recorded workspace: live requests are disabled. Open the lab for a new analysis.'}),
            {status: 409, headers: {'Content-Type':'application/json'}}));
    };
})(window);
