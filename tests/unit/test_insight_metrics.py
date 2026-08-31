"""Unit tests for deterministic insight metrics / archetypes / status strip."""

from utils.insight_metrics import (
    ARCHETYPE_LABELS,
    THRESHOLDS,
    build_focus_rows,
    classify_archetypes,
    next_experiment_suggestions,
    overview_headline,
    reported_revealed_gap,
    select_insight_cards,
    status_strip,
    normalize_share,
)


def test_thresholds_are_documented_and_positive():
    assert THRESHOLDS['high_revealed'] > THRESHOLDS['low_revealed']
    assert THRESHOLDS['high_reported'] > THRESHOLDS['low_reported']
    assert THRESHOLDS['mismatch_gap'] > 0
    assert 'hidden_driver' in ARCHETYPE_LABELS


def test_normalize_share_sums_to_100():
    shares = normalize_share([1, 1, 2])
    assert abs(sum(shares) - 100.0) < 1e-6
    assert shares[2] == 50.0


def test_reported_revealed_gap():
    assert reported_revealed_gap(40, 10) == 30.0
    assert reported_revealed_gap(5, 25) == -20.0


def test_classify_hidden_driver_and_claimed_but_inert():
    assert 'hidden_driver' in classify_archetypes(reported=5, revealed=25)
    assert 'claimed_but_inert' in classify_archetypes(reported=40, revealed=5)
    assert 'redundant' in classify_archetypes(reported=2, revealed=1)
    assert 'anchor' in classify_archetypes(reported=20, revealed=30)


def test_classify_stabilizer_destabilizer():
    assert 'stabilizer' in classify_archetypes(
        reported=10, revealed=10, baseline_noise=0.1, ablated_noise=0.25
    )
    assert 'destabilizer' in classify_archetypes(
        reported=10, revealed=10, baseline_noise=0.3, ablated_noise=0.1
    )


def test_classify_order_sensitive():
    assert 'order_sensitive' in classify_archetypes(
        reported=10, revealed=10, order_sensitivity=0.2
    )


def test_status_strip_bands():
    status = status_strip(
        top3_revealed_share=0.8,
        mean_abs_gap=40,
        baseline_noise=0.4,
        mean_order_sensitivity=0.25,
    )
    assert status['influence_concentration']['level'] == 'High'
    assert status['reported_revealed_agreement']['level'] in ('Medium', 'Low')
    assert status['baseline_stability']['level'] == 'Low'
    assert status['order_sensitivity']['level'] == 'High'
    assert 'help' in status['influence_concentration']


def test_select_insight_cards_unique_kinds():
    rows = [
        {'name': 'A', 'reported': 5, 'revealed': 40, 'gap': -35, 'archetypes': ['hidden_driver']},
        {'name': 'B', 'reported': 50, 'revealed': 5, 'gap': 45, 'archetypes': ['claimed_but_inert']},
        {'name': 'C', 'reported': 20, 'revealed': 20, 'gap': 0, 'archetypes': []},
    ]
    cards = select_insight_cards(rows)
    kinds = [c['kind'] for c in cards]
    assert len(kinds) == len(set(kinds))
    assert 'hidden_driver' in kinds
    assert 'claimed_but_inert' in kinds


def test_overview_headline_mentions_concentration():
    rows = [
        {'name': 'A', 'reported': 10, 'revealed': 50, 'gap': -40},
        {'name': 'B', 'reported': 40, 'revealed': 30, 'gap': 10},
        {'name': 'C', 'reported': 50, 'revealed': 20, 'gap': 30},
    ]
    text = overview_headline(rows)
    assert 'revealed influence' in text.lower() or 'behavioural' in text.lower()


def test_build_focus_rows_merges_reported_and_revealed():
    rows = build_focus_rows(
        influence_scores=[
            {'focus': 'Role', 'normalized_influence': 70, 'prompt_section': 'You are'},
            {'focus': 'Format', 'normalized_influence': 5, 'prompt_section': 'JSON'},
            {'focus': 'Context', 'normalized_influence': 25, 'prompt_section': 'Background'},
        ],
        assessment_foci=[
            {'focus': 'Role', 'score': 5},
            {'focus': 'Format', 'score': 60},
            {'focus': 'Context', 'score': 20},
        ],
        baseline_noise=0.1,
    )
    assert len(rows) == 3
    by = {r['name']: r for r in rows}
    assert by['Role']['reported'] == 5
    assert abs(by['Role']['revealed'] - 70) < 1e-6
    assert 'hidden_driver' in by['Role']['archetypes']
    assert 'claimed_but_inert' in by['Format']['archetypes']


def test_build_focus_rows_missing_metrics_graceful():
    rows = build_focus_rows(
        influence_scores=[{'focus': 'Only', 'normalized_influence': 100}],
        assessment_foci=None,
    )
    assert rows[0]['reported'] is None
    assert rows[0]['revealed'] == 100
    assert overview_headline(rows)


def test_next_experiment_suggestions_from_status():
    rows = [{
        'name': 'Hidden',
        'reported': 5,
        'revealed': 40,
        'gap': -35,
        'archetypes': ['hidden_driver'],
    }]
    status = {'baseline_stability': {'level': 'Low', 'help': 'x'}}
    tips = next_experiment_suggestions(rows, status)
    assert tips
    assert any('Hidden' in t or 'sample' in t.lower() for t in tips)
