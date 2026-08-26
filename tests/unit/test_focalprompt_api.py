"""Smoke tests for high-level focalprompt.api helpers (mocked assessor)."""

from unittest.mock import MagicMock, patch

from focalprompt.api import _compare_reported_vs_revealed, analyze


def test_compare_reported_vs_revealed():
    reported = {
        'foci': [
            {'focus': 'A', 'score': 40, 'explanation': 'x'},
            {'focus': 'B', 'score': 60, 'explanation': 'y'},
        ]
    }
    perturbation = {
        'influence_scores': [
            {
                'focus': 'A',
                't_obs': 0.1,
                'influence': 0.1,
                'normalized_influence': 1.0,
                'p_value': 0.01,
                'q_value': 0.02,
                'is_significant': True,
            }
        ]
    }
    cmp = _compare_reported_vs_revealed(reported, perturbation)
    assert cmp['rows'][0]['reported_score'] == 40
    assert cmp['rows'][0]['is_significant'] is True
    assert cmp['rows'][0]['concordance']['key'] == 'concordant_high'
    assert 'summary' in cmp
    assert 'transformer attention' in cmp['rows'][0]['note'].lower() or 'not' in cmp['rows'][0]['note'].lower()


def test_analyze_skip_live(monkeypatch):
    with patch('focalprompt.api.detect_foci') as df, \
         patch('focalprompt.api.assess_focus') as af, \
         patch('focalprompt.api.ablate') as ab:
        df.return_value = {'foci': [{'focus': 'Role', 'prompt_section': 'You are x.'}]}
        af.return_value = {'foci': [{'focus': 'Role', 'score': 100}]}
        ab.return_value = {
            'influence_scores': [{
                'focus': 'Role', 't_obs': 0.05, 'influence': 0.05,
                'normalized_influence': 1, 'p_value': 0.2, 'q_value': 0.2,
                'is_significant': False,
            }]
        }
        out = analyze('You are x.', output='hi', run_assess=True, run_ablation=True)
        assert out['comparison'] is not None
        assert out['meta']['model'] == 'gpt-4o-mini'
