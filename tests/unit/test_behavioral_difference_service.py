#!/usr/bin/env python3
"""Tests for behavioral-difference lenses (difference only — not quality)."""

from __future__ import annotations

import json

import pytest

from focalprompt.api import _compare_reported_vs_revealed
from services.behavioral_difference_service import (
    DIFFERENCE_DIMENSIONS,
    LLM_DIFFERENCE_SYSTEM,
    HumanBehavioralDifferenceRecord,
    LLMBehavioralDifferenceEvaluator,
    aggregate_behavioral_batch_stats,
    attach_evidence_lenses,
    build_judge_user_prompt,
    enrich_influence_item_for_review,
    estimate_judge_cost_units,
    multi_lens_faithfulness_label,
    parse_difference_judgment,
    recommend_behavioral_review,
    sample_outputs_for_judge,
    select_foci_for_behavioral_review,
)
from utils.results_copy import (
    LENS_HUMAN_TITLE,
    LENS_LLM_TITLE,
    LENS_SEMANTIC_TITLE,
    render_focus_card,
)


def test_rubric_prohibits_quality_and_preference():
    sys_l = LLM_DIFFERENCE_SYSTEM.lower()
    assert 'better' in sys_l
    assert 'quality' in sys_l
    assert 'prefer' in sys_l
    assert 'do not' in sys_l or "don't" in sys_l
    assert 'better_output' not in sys_l
    assert 'which output is better' not in sys_l


def test_parse_valid_judgment():
    parsed = parse_difference_judgment({
        'material_behavioral_difference': True,
        'overall_difference_score': 4,
        'confidence': 0.88,
        'dimensions': {
            'task_outcome': 0,
            'content': 1,
            'information_coverage': 2,
            'structure_format': 5,
            'instruction_compliance': 5,
            'tool_behavior': 0,
            'safety_behavior': 0,
            'tone_style': 1,
        },
        'other_dimensions': [],
        'summary': 'Structure breaks; content similar.',
    })
    assert parsed['material_behavioral_difference'] is True
    assert parsed['overall_difference_score'] == 4
    assert parsed['dimensions']['structure_format'] == 5
    assert 'winner' not in parsed
    assert 'better_output' not in parsed


def test_parse_missing_dimensions_and_invalid_scores():
    parsed = parse_difference_judgment({
        'material_behavioral_difference': 'yes',
        'overall_difference_score': 99,
        'confidence': 2.5,
        'dimensions': {'structure_format': -3, 'content': 'x'},
        'summary': 'x',
    })
    assert parsed['overall_difference_score'] == 5
    assert parsed['confidence'] == 1.0
    assert parsed['dimensions']['structure_format'] == 0
    assert parsed['dimensions']['content'] == 0
    for key in DIFFERENCE_DIMENSIONS:
        assert key in parsed['dimensions']


def test_parse_refusal_or_garbage_fails():
    with pytest.raises(ValueError):
        parse_difference_judgment('I refuse to judge.')
    with pytest.raises(ValueError):
        parse_difference_judgment('')


def test_parse_fenced_json():
    text = """```json
{"material_behavioral_difference": false, "overall_difference_score": 1,
 "confidence": 0.4, "dimensions": {}, "summary": "Nearly identical."}
```"""
    parsed = parse_difference_judgment(text)
    assert parsed['material_behavioral_difference'] is False
    assert parsed['overall_difference_score'] == 1


def test_sample_outputs_records_metadata():
    sampled = sample_outputs_for_judge(
        [f'b{i}' for i in range(10)],
        [f'a{i}' for i in range(8)],
        max_per_group=3,
        seed=7,
    )
    assert sampled['n_baseline_shown'] == 3
    assert sampled['n_ablated_shown'] == 3
    assert sampled['n_baseline_available'] == 10
    assert sampled['sampling_method']['baseline'] == 'random_subset'
    assert sampled['sampling_method']['seed'] == 7


def test_blinding_swaps_groups_with_recorded_mapping():
    class FakeProvider:
        def __init__(self):
            self.last = None

        def chat_completion(self, **kwargs):
            self.last = kwargs
            return {
                'content': json.dumps({
                    'material_behavioral_difference': True,
                    'overall_difference_score': 3,
                    'confidence': 0.7,
                    'dimensions': {k: 0 for k in DIFFERENCE_DIMENSIONS},
                    'summary': 'Differ.',
                })
            }

    for seed in range(40):
        provider = FakeProvider()
        evaluator = LLMBehavioralDifferenceEvaluator(
            provider, 'gpt-test', provider_name='openai'
        )
        out = evaluator.evaluate(
            focus='JSON schema',
            removed_span='Return JSON',
            baseline_outputs=['BASELINE_UNIQUE_AAA'],
            ablated_outputs=['ABLATED_UNIQUE_BBB'],
            blind=True,
            seed=seed,
        )
        assert out['status'] == 'complete'
        judgment = out['judgments'][0]
        if judgment.get('group_a_is') != 'ablated':
            continue
        user = provider.last['messages'][1]['content']
        a_part = user.split('Group B')[0]
        assert 'ABLATED_UNIQUE_BBB' in a_part
        assert 'BASELINE_UNIQUE_AAA' in user.split('Group B', 1)[1]
        assert out['blinded'] is True
        break
    else:
        pytest.fail('No seed produced a blinded A/B swap')


def test_judge_user_prompt_is_set_comparison():
    user = build_judge_user_prompt(
        focus='f',
        removed_span='span',
        group_a=['a1', 'a2'],
        group_b=['b1'],
        prompt_context='Original prompt',
    )
    assert 'Group A' in user
    assert 'Group B' in user
    assert 'material behavioral difference' in user.lower()
    assert 'which is better' not in user.lower()


def test_enrich_attaches_three_lenses_without_auto_llm():
    item = enrich_influence_item_for_review({
        'focus': 'JSON schema',
        'prompt_section': 'Return valid JSON only',
        'is_significant': False,
        'q_value': 0.4,
        'standardized_effect': 0.2,
        't_obs': 0.01,
        'normalized_influence': 5.0,
    })
    assert item['semantic_perturbation']['is_significant'] is False
    assert item['llm_behavioral_difference']['status'] == 'not_run'
    assert item['human_behavioral_difference']['status'] == 'not_run'
    assert item['review_recommendation']['review_recommended'] is True
    assert 'structural_focus' in item['review_recommendation']['reasons']


def test_recommend_reported_revealed_disagreement():
    rec = recommend_behavioral_review(
        {'focus': 'Tone', 'is_significant': False, 'standardized_effect': 0.1},
        reported_score=28.0,
    )
    assert 'reported_revealed_disagreement' in rec['reasons']
    assert rec['advisory_only'] is True


def test_human_record_uncertain_and_not_preference():
    human = HumanBehavioralDifferenceRecord().evaluate({
        'material_behavioral_difference': 'uncertain',
        'overall_difference_score': 2,
        'dimensions': {'tone_style': 2},
        'notes': 'hard to tell',
    })
    assert human['status'] == 'complete'
    assert human['material_behavioral_difference'] == 'uncertain'
    assert human['explicitly_not_quality_evaluation'] is True


def test_selective_escalation_respects_cap():
    rows = [
        enrich_influence_item_for_review({
            'focus': f'JSON schema {i}',
            'prompt_section': 'Return JSON',
            'is_significant': False,
            'q_value': 0.5,
            't_obs': 0.01,
            'normalized_influence': 1.0,
            'standardized_effect': 0.1,
        })
        for i in range(10)
    ]
    rows.append(enrich_influence_item_for_review({
        'focus': 'Tone',
        'prompt_section': 'Be friendly',
        'is_significant': False,
        'q_value': 0.8,
        't_obs': 0.0,
        'normalized_influence': 1.0,
        'standardized_effect': 0.0,
    }))
    out = select_foci_for_behavioral_review(
        rows,
        max_reviews=3,
        include_manual=['Tone'],
        only_recommended=True,
    )
    assert out['n_selected'] <= 3
    assert out['truncated_by_max_reviews'] is True
    assert out['cost_estimate']['n_reviews'] == out['n_selected']
    assert out['selected'][0]['focus'] == 'Tone'


def test_cost_estimate_scales():
    low = estimate_judge_cost_units(2)
    high = estimate_judge_cost_units(4)
    assert high['estimated_input_tokens'] > low['estimated_input_tokens']


def test_batch_aggregate_candidate_language():
    stats = aggregate_behavioral_batch_stats([
        {
            'is_significant': False,
            'semantic_perturbation': {'is_significant': False},
            'llm_behavioral_difference': {
                'status': 'complete',
                'material_behavioral_difference': True,
            },
            'human_behavioral_difference': {
                'status': 'complete',
                'material_behavioral_difference': True,
            },
        },
        {
            'is_significant': True,
            'semantic_perturbation': {'is_significant': True},
            'llm_behavioral_difference': {
                'status': 'complete',
                'material_behavioral_difference': False,
            },
            'human_behavioral_difference': {'status': 'not_run'},
        },
    ])
    assert stats['semantic_false_negative_candidates'] == 1
    assert stats['semantic_false_positive_candidates'] == 1
    assert 'ground truth' in stats['note'].lower()


def test_experiment_c_semantic_blind_spot_not_naive_over_reported():
    item = enrich_influence_item_for_review({
        'focus': 'JSON schema',
        'is_significant': False,
        'q_value': 0.4,
        't_obs': 0.01,
        'normalized_influence': 5.0,
        'standardized_effect': 0.2,
    })
    item['llm_behavioral_difference'] = {
        'status': 'complete',
        'material_behavioral_difference': True,
        'overall_difference_score': 4,
    }
    item['human_behavioral_difference'] = {
        'status': 'complete',
        'material_behavioral_difference': True,
        'overall_difference_score': 5,
    }
    comparison = _compare_reported_vs_revealed(
        {'foci': [{'focus': 'JSON schema', 'score': 28, 'explanation': 'format'}]},
        {'influence_scores': [item]},
    )
    row = comparison['rows'][0]
    assert row['faithfulness']['primary_label'] == 'semantic_blind_spot'
    assert 'over_reported' not in row['faithfulness']['primary_label']
    assert row['faithfulness']['lenses']['semantic_faithfulness']['semantic_significant'] is False
    assert row['faithfulness']['lenses']['qualitative_behavioral_faithfulness'][
        'llm_material_difference'
    ] is True


def test_experiment_c_handles_missing_qualitative_cleanly():
    item = enrich_influence_item_for_review({
        'focus': 'Tone',
        'is_significant': False,
        'q_value': 0.5,
        't_obs': 0.0,
        'normalized_influence': 2.0,
        'standardized_effect': 0.0,
    })
    comparison = _compare_reported_vs_revealed(
        {'foci': [{'focus': 'Tone', 'score': 30}]},
        {'influence_scores': [item]},
    )
    assert comparison['rows'][0]['faithfulness']['primary_label'] == (
        'possibly_over_reported_semantic_only'
    )
    assert comparison['rows'][0]['llm_behavioral_difference']['status'] == 'not_run'


def test_ui_renders_lenses_and_failed_judge():
    html = render_focus_card({
        'focus': 'JSON schema',
        'is_significant': False,
        'q_value': 0.31,
        'semantic_perturbation': {'is_significant': False, 'q_value': 0.31},
        'llm_behavioral_difference': {
            'status': 'complete',
            'overall_difference_score': 4,
            'dimensions': {'structure_format': 5, 'instruction_compliance': 5},
            'summary': 'Structure breaks while meaning stays similar.',
        },
        'human_behavioral_difference': {'status': 'not_run'},
        'review_recommendation': {
            'review_recommended': True,
            'reasons': ['structural_focus'],
        },
    })
    assert LENS_SEMANTIC_TITLE in html
    assert LENS_LLM_TITLE in html
    assert LENS_HUMAN_TITLE in html
    assert 'Not run' in html

    failed = render_focus_card({
        'focus': 'X',
        'is_significant': True,
        'q_value': 0.01,
        'standardized_effect': 3.0,
        'semantic_perturbation': {'is_significant': True, 'q_value': 0.01},
        'llm_behavioral_difference': {'status': 'failed', 'error': 'parse error'},
        'human_behavioral_difference': {'status': 'pending'},
    })
    assert 'Failed' in failed
    assert 'Pending' in failed


def test_attach_evidence_lenses_idempotent():
    once = attach_evidence_lenses({
        'focus': 'A',
        'is_significant': True,
        't_obs': 0.2,
        'q_value': 0.01,
    })
    twice = attach_evidence_lenses(dict(once))
    assert twice['llm_behavioral_difference']['status'] == 'not_run'
    assert 'semantic_perturbation' in twice


def test_multi_lens_label_concordance():
    label = multi_lens_faithfulness_label(
        reported_score=20,
        semantic_significant=True,
        llm_material=True,
        human_material=True,
    )
    assert label['primary_label'] == 'multi_lens_concordance'
