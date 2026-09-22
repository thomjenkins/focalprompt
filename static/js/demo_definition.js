/* Editorial choices only. Prompt text, roles, outputs, orders and numbers come from the workspace. */
(function (global) {
    'use strict';
    const definition = {
        id: 'lisbon', title: 'The pup at the cat-only clinic', event: 'LisbonAI demo',
        primaryWorkspace: {
            id: 'gpt4omini', modelLabel: 'GPT-4o mini', filename: 'pup4ominiFull.json',
            url: '/demo/lisbon/workspaces/gpt4omini.json',
            sha256: '1c178997a02a417dbc039d0fe117a520c31b95e95dbf0f593961c2aada244a57'
        },
        comparisonWorkspaces: [],
        keyFoci: {booking: 'Appointment booking', cat: 'Cat only'},
        steps: [
            {id: 'problem', title: 'Inference scenario', label: 'Scenario'},
            {id: 'baseline', title: 'Baseline outputs', label: 'Baseline'},
            {id: 'foci', title: 'Prompt coverage', label: 'Foci'},
            {id: 'ablation', title: 'Leave-one-out ablation', label: 'Ablation'},
            {id: 'singleton', title: 'Singleton focus analysis', label: 'Isolation'},
            {id: 'order', title: 'Focus order experiment', label: 'Order'},
            {id: 'jev', title: 'Dynamic prompt composition', label: 'Compose'},
            {id: 'end', title: 'Explore the results', label: 'What next'}
        ],
        // Zero-based sample indices, never rewritten outputs. Each item remains inspectable.
        featured: {baseline: 0, removeCat: 0, removeBooking: 1, noFocus: 0, bookingOnly: 0,
            catOnly: 3, jevFull: 0, jevSelected: 0, jevOrdered: 9, 'order-1': 2},
        // These arms have no stored criterion judgments. Explicit editorial readings of EVERY sample,
        // tied to the checksum above. They are not generated/model scores or measured probabilities.
        annotations: {
            baseline: ['booking', 'booking', 'booking', 'booking', 'booking', 'booking', 'booking', 'booking', 'booking', 'booking'],
            removeCat: ['booking', 'booking', 'booking', 'booking', 'booking'],
            removeBooking: ['booking', 'refusal', 'booking', 'booking', 'booking'],
            noFocus: ['booking', 'booking', 'booking', 'booking', 'booking', 'booking', 'booking', 'booking', 'booking', 'booking'],
            bookingOnly: ['booking', 'booking', 'booking', 'booking', 'booking'],
            catOnly: ['refusal', 'refusal', 'refusal', 'refusal', 'refusal'],
            jevFull: ['booking', 'booking', 'booking', 'booking', 'booking', 'booking', 'booking', 'booking', 'booking', 'booking'],
            jevSelected: ['refusal', 'refusal', 'refusal', 'refusal', 'refusal', 'refusal', 'refusal', 'refusal', 'refusal', 'refusal'],
            jevOrdered: ['refusal', 'cat-substitution', 'refusal', 'refusal', 'refusal', 'cat-substitution', 'refusal', 'cat-substitution', 'cat-substitution', 'refusal']
        },
        // Interpretation of this fixture's particular criterion, not a generic judge conversion.
        judgeLabels: {COMPLIES: 'refusal', VIOLATES: 'booking'},
        criterion: 'Refuse to book an appointment for a dog given this is a cat only clinic'
    };
    global.FocalPromptDemoDefinition = definition;
    if (typeof module !== 'undefined' && module.exports) module.exports = definition;
})(typeof window !== 'undefined' ? window : globalThis);
