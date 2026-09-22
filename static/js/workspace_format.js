/* Shared workspace import validation and v1 migration; no UI or network effects. */
(function (global) {
    'use strict';
    const VERSION = 2;
    function legacyScenario(prompt) {
        return {version: 1, messages: [{id: 'legacy-prompt', role: 'user', content: String(prompt || ''), analysis_mode: 'analyse'}]};
    }
function validate(data) {
    if (!data || typeof data !== 'object') {
        return 'Invalid file: not a JSON object.';
    }
    if (data.focalprompt_workspace !== true) {
        if (data.protocol === 'singleton-focus-v1' && data.context && data.plan && data.samples
            && Array.isArray(data.focus_results)) {
            return { singleton_analysis: true };
        }
        if (data.baseline_outputs || data.influence_scores || data.ablation_results) {
            return { legacy_ablation: true };
        }
        return 'Unrecognized file: expected a FocalPrompt workspace export.';
    }
    if (data.version != null && data.version !== 1 && data.version !== VERSION) {
        return 'Unsupported workspace version ' + data.version +
            ' (expected ' + VERSION + ').';
    }
    return null;
}

function migrate(data) {
    if (!data || data.version !== 1) return data;
    const migrated = JSON.parse(JSON.stringify(data));
    function assignLegacyMessage(focusList) {
        return (focusList || []).map(function (focus) {
            const next = Object.assign({}, focus, {
                message_id: 'legacy-prompt',
                is_dynamic: false,
                dynamic_type: null,
            });
            if (Array.isArray(next.spans)) {
                next.spans = next.spans.map(function (span) {
                    return Object.assign({}, span, { message_id: 'legacy-prompt' });
                });
            }
            return next;
        });
    }
    if (migrated.prompt_analysis) {
        migrated.prompt_analysis.scenario = legacyScenario(migrated.prompt_analysis.prompt || ' ');
        migrated.prompt_analysis.foci = assignLegacyMessage(migrated.prompt_analysis.foci);
    }
    if (migrated.batch_analysis) {
        migrated.batch_analysis.scenario = legacyScenario(migrated.batch_analysis.prompt || ' ');
        migrated.batch_analysis.foci = assignLegacyMessage(migrated.batch_analysis.foci);
    }
    migrated.version = VERSION;
    migrated.migrated_from_version = 1;
    return migrated;
}

    const api = {VERSION, validate, migrate};
    global.FocalPromptWorkspaceFormat = api;
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
