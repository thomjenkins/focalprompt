#!/usr/bin/env python3
"""Tests for per-sample reported-focus dynamics."""

from utils.reported_focus_dynamics import (
    DISCLAIMER,
    associate_with_behavior_labels,
    build_reported_focus_dynamics,
    jensen_shannon_divergence,
    summarize_numeric,
    weight_vector_from_assessment,
)


def test_weight_vector_normalizes_and_fills():
    assessment = {
        'foci': [
            {'focus': 'Cats', 'score': 60},
            {'focus': 'Dogs', 'score': 40},
        ]
    }
    vec = weight_vector_from_assessment(assessment, ['Cats', 'Dogs', 'Birds'])
    assert vec['Cats'] == 60.0
    assert vec['Dogs'] == 40.0
    assert vec['Birds'] == 0.0


def test_summarize_numeric_stats():
    s = summarize_numeric([10.0, 20.0, 30.0])
    assert s['n'] == 3
    assert s['mean'] == 20.0
    assert s['median'] == 20.0
    assert s['min'] == 10.0
    assert s['max'] == 30.0
    assert s['range'] == 20.0
    assert s['sd'] is not None


def test_jensen_shannon_identical_is_zero():
    names = ['A', 'B']
    p = {'A': 50.0, 'B': 50.0}
    assert jensen_shannon_divergence(p, p, names) == 0.0


def test_jensen_shannon_distinct_positive():
    names = ['A', 'B']
    p = {'A': 90.0, 'B': 10.0}
    q = {'A': 10.0, 'B': 90.0}
    assert jensen_shannon_divergence(p, q, names) > 0.2


def test_build_reported_focus_dynamics_end_to_end():
    def assess_fn(prompt, output, foci):
        names = [f['focus'] for f in foci]
        high_cats = 'cat' in output.lower()
        scores = []
        for i, name in enumerate(names):
            if i == 0:
                scores.append(80.0 if high_cats else 20.0)
            else:
                scores.append(20.0 if high_cats else 80.0)
        return {
            'foci': [
                {'focus': n, 'score': s, 'explanation': 'stub'}
                for n, s in zip(names, scores)
            ],
            'overall_summary': 'ok',
        }

    out = build_reported_focus_dynamics(
        prompt='system',
        foci=[{'focus': 'Cats'}, {'focus': 'Dogs'}],
        baseline_outputs=['I prefer cats', 'cats again'],
        ablated_outputs={0: ['dogs only', 'more dogs']},
        assess_fn=assess_fn,
        behavior_labels={
            'baseline': ['refuse_dog', 'refuse_dog'],
            'focus:0': ['accept_dog', 'accept_dog'],
        },
        association_focus='Cats',
    )
    assert DISCLAIMER in out['disclaimer'] or 'self-reported' in out['disclaimer'].lower()
    assert out['focus_names'] == ['Cats', 'Dogs']
    assert out['baseline']['n_scored'] == 2
    assert abs(out['baseline']['mean_weights']['Cats'] - 80.0) < 1e-6
    assert len(out['ablations']) == 1
    block = out['ablations'][0]
    assert block['focus'] == 'Cats'
    assert block['js_divergence_vs_baseline_mean'] > 0
    assert block['delta_vs_baseline_mean_weights']['Cats'] < 0
    assert 'behavior_association' in block
    # Individual samples inspectable
    assert len(out['baseline']['samples']) == 2
    assert out['baseline']['samples'][0]['weights']['Cats'] == 80.0
    assert out['baseline']['samples'][0]['behavior_label'] == 'refuse_dog'


def test_behavior_association_buckets():
    samples = [
        {'weights': {'Cats': 70.0}, 'behavior_label': 'refuse'},
        {'weights': {'Cats': 75.0}, 'behavior_label': 'refuse'},
        {'weights': {'Cats': 20.0}, 'behavior_label': 'accept'},
    ]
    assoc = associate_with_behavior_labels(samples, 'Cats')
    assert assoc['by_label']['refuse']['mean'] == 72.5
    assert assoc['by_label']['accept']['mean'] == 20.0


def test_ablation_service_reported_focus_dynamics_uses_assessment_service():
    from unittest.mock import Mock
    from services.ablation_service import AblationService

    assessment = Mock()
    assessment.assess_focus.side_effect = lambda prompt, output, user_foci=None: {
        'foci': [
            {'focus': 'Role', 'score': 55.0, 'explanation': 'x'},
            {'focus': 'Cite', 'score': 45.0, 'explanation': 'y'},
        ],
        'overall_summary': 'ok',
    }
    svc = AblationService(Mock(), 'gpt-4o-mini', provider_name='openai')
    result = svc.run_reported_focus_dynamics(
        'prompt text',
        [{'focus': 'Role'}, {'focus': 'Cite'}],
        ['b1', 'b2'],
        {0: ['a1']},
        assessment_service=assessment,
    )
    assert assessment.assess_focus.call_count == 3
    assert result['baseline']['n_scored'] == 2
    assert result['optional_behavior_labels_supported'] is True
