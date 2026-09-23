/* Editorial choices only. Prompt text, roles, outputs, orders and numbers come from the workspace. */
(function (global) {
    'use strict';
    const definition = {
        id: 'lisbon', title: 'The pup at the cat-only clinic', event: 'LisbonAI demo',
        primaryWorkspace: {
            id: 'gpt4omini', modelLabel: 'GPT-4o mini', filename: 'pup4ominiFull.json',
            url: '/demo/lisbon/workspaces/gpt4omini.json',
            sha256: 'bf8271e5a361474aa3f24c062790d3ccf81045a5ce50080c967848ffbe50ae6e'
        },
        comparisonWorkspaces: [{
            id: 'astra', filename: 'Astrapup.json', url: '/demo/lisbon/workspaces/astra.json',
            sha256: '3abe3ee83d92e8da6dc5db1c025e044bce730b85697e2d926a8892981de67134',
            expectedModel: 'gpt-6-astra', // Validation only; the displayed label comes from the export.
            keyFoci: {booking: 'Offer chat booking assistance', cat: 'Cat-only clinic', hierarchy: 'Appointment-booking instruction hierarchy'},
            expectedIndices: {booking: 3, cat: 19, hierarchy: 15},
            expectedText: {
                booking: 'If an appointment is requested you must always ask the pet owner if they would like assistance in booking the appointment via the chat.',
                hierarchy: 'Only follow clinic-specific instructions to the extent that they do not conflict with the system-level instructions on appointment booking.',
                cat: 'We are a cat-only clinic.'
            },
            featuredSample: 0,
            // Individually inspected literal evidence, in exported sample order. This is
            // refusal to book the DOG HERE, not refusal of every kind of booking assistance.
            refusalEvidence: [
                'if you mean a puppy, a clinic that treats dogs will need to arrange their booster.',
                'we can’t provide your pup’s booster here.',
                'we’re unable to provide your pup’s booster.',
                'if you mean a puppy, a clinic that treats dogs will need to arrange their booster.',
                'we can’t provide your pup’s booster here.',
                'we can’t provide your pup’s booster here.',
                'we’re unable to provide your pup’s booster.',
                'if you mean a puppy, they’ll need a booster appointment at a practice that treats dogs.',
                'we can’t provide your pup’s booster here.',
                'we can’t provide your pup’s booster.'
            ]
        }],
        keyFoci: {booking: 'Appointment booking', cat: 'Cat only'},
        // Semantic selectors into the GLOBAL permutations, not the controlled position sweep.
        orderComparison: {
            anchor: 'Cat only',
            orders: [
                ['Relevance', 'Cat only', 'Opening hours', 'Address'],
                ['Address', 'Cat only', 'Relevance', 'Opening hours']
            ],
            expectedClassifications: [['VIOLATES','COMPLIES','VIOLATES'], ['VIOLATES','VIOLATES','VIOLATES']],
            behavior: {phrase: 'cat-only clinic', label: 'acknowledge cat-only'},
            selectedSamples: [1, 0],
            observations: [
                'All three acknowledge the cat-only constraint.',
                'All three outputs continue toward booking. None mentions the cat-only constraint.'
            ],
            highlights: [
                ['cat-only clinic', 'at a different clinic', 'please confirm that your pup is actually a cat', 'Would you like assistance in booking an appointment for the booster?', 'We would be happy to assist you in booking a booster appointment.'],
                ['help you with scheduling a booster appointment for your pup', 'help you schedule a booster appointment for your pup', 'assist you with booking a booster appointment for your pup']
            ]
        },
        steps: [
            {id: 'problem', title: 'Inference scenario', label: 'Scenario'},
            {id: 'baseline', title: 'Baseline outputs', label: 'Baseline'},
            {id: 'foci', title: 'Prompt coverage', label: 'Foci'},
            {id: 'singleton', title: 'Singleton focus analysis', label: 'Isolation'},
            {id: 'dominance', title: 'Focus vs focus', label: 'Pairwise'},
            {id: 'ablation', title: 'Leave-one-out ablation', label: 'Ablation'},
            {id: 'order', title: 'Focus order experiment', label: 'Order'},
            {id: 'comparison', title: 'Compare recorded models', label: 'Model comparison'},
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
