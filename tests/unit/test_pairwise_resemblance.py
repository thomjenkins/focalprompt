"""Eligibility, weighting and degeneracies of descriptive pairwise resemblance."""
from copy import deepcopy
import json

import numpy as np
import pytest

from services.singleton_service import build_plan, score_pairwise
from utils.pairwise_resemblance import pairwise_resemblance, summarize_conditions
from tests.unit.test_singleton_analysis import fixture, samples_for, service


class Embeddings:
    def __init__(self, vectors):
        self.vectors = vectors

    def array(self, texts):
        return np.asarray([self.vectors[text] for text in texts], dtype=float)


def experiment():
    scenario = {'version': 1, 'messages': [
        {'id': 'rules', 'role': 'developer', 'analysis_mode': 'analyse', 'content': 'A. B. C. D.'},
        {'id': 'chat', 'role': 'user', 'analysis_mode': 'retain', 'content': 'Question'},
    ]}
    foci = [{'focus': label, 'spans': [{'message_id': 'rules', 'char_start': 3 * i,
             'char_end': 3 * i + 2, 'text_snapshot': label + '.'}]} for i, label in enumerate('ABCD')]
    plan = build_plan(scenario, foci, n_baseline=4, n_ablated=2)
    arms = {v['id']: {**v, 'outputs': [v['id']] * v['n_samples']} for v in plan['variants']}
    vectors = {key: [1, 1] for key in arms}
    vectors.update(full=[1, 0], singleton_0=[1, 0], singleton_1=[0, 1],
                   leave_one_out_2=[0, 1], leave_one_out_3=[1, 1])
    return plan, arms, Embeddings(vectors)


def pair(result, i, j):
    return next(p for p in result['pairs'] if (p['row_index'], p['column_index']) == (i, j))


def eligible_ids(result, i, j):
    return [c['id'] for c in result['conditions']
            if i in c['intact_focus_indices'] and j in c['intact_focus_indices']]


def test_only_shared_contexts_count_with_equal_prompt_weight_and_half_ties():
    plan, arms, cache = experiment()
    original = deepcopy((plan, arms))
    result = pairwise_resemblance(plan, arms, cache)
    p = pair(result, 0, 1)
    assert eligible_ids(result, 0, 1) == ['full', 'leave_one_out_2', 'leave_one_out_3']
    assert p['views']['full']['row_share'] == 1
    assert p['views']['ablations']['row_share'] == .25
    combined = p['views']['combined']
    assert combined['row_share'] == .5  # not .625 from naive output pooling
    assert combined['tie_share'] == pytest.approx(1 / 3)
    assert combined['mean_gap'] == pytest.approx(0)
    assert combined['condition_count'] == 3 and combined['output_count'] == 8
    assert (plan, arms) == original
    json.dumps(result, allow_nan=False)


def test_reversing_the_comparison_complements_share_and_negates_gap():
    condition = {'pool_id': 'one', 'distances': [[.1, .9], [.4, .40000001], [.8, .2]]}
    forward = summarize_conditions([condition], 0, 1)
    reverse = summarize_conditions([condition], 1, 0)
    assert forward['row_share'] + reverse['row_share'] == 1
    assert forward['mean_gap'] == pytest.approx(-reverse['mean_gap'])
    assert forward['row_distance'] == reverse['column_distance']
    assert forward['tie_share'] == pytest.approx(1 / 3)


def test_equivalent_conditions_count_longest_sample_prefix_once():
    a = {'pool_id': 'same', 'distances': [[0, 1], [1, 0]]}
    b = {'pool_id': 'same', 'distances': [[0, 1]]}
    score = summarize_conditions([b, a, b], 0, 1)
    assert score['condition_count'] == 1 and score['output_count'] == 2
    assert score['row_share'] == .5


def test_third_focus_ablation_that_damages_either_member_is_excluded():
    plan, arms, cache = experiment()
    # The intervention on C also deletes part of A, including across spans.
    arms['leave_one_out_2']['deleted_spans'].append({'message_id': 'rules', 'char_start': 1, 'char_end': 2})
    result = pairwise_resemblance(plan, arms, cache)
    assert eligible_ids(result, 0, 1) == ['full', 'leave_one_out_3']
    # The same offsets in another message do not damage A.
    arms['leave_one_out_2']['deleted_spans'][-1]['message_id'] = 'elsewhere'
    result = pairwise_resemblance(plan, arms, cache)
    assert 'leave_one_out_2' in eligible_ids(result, 0, 1)


def test_overlapping_pair_and_indistinguishable_references_are_unavailable():
    plan, arms, cache = experiment()
    assert 'indistinguishable' in pair(pairwise_resemblance(plan, arms, cache), 2, 3)['unavailable_reason']
    plan['foci'][1]['spans'] = deepcopy(plan['foci'][0]['spans'])
    p = pair(pairwise_resemblance(plan, arms, cache), 0, 1)
    assert 'share labelled' in p['unavailable_reason']
    assert all(v is None for v in p['views'].values())


def test_zero_centroid_is_unavailable_without_poisoning_other_pairs():
    plan, arms, cache = experiment()
    cache.vectors['opposite'] = [-1, 0]
    arms['singleton_0']['outputs'] = ['singleton_0', 'opposite']
    result = pairwise_resemblance(plan, arms, cache)
    assert 'undefined' in pair(result, 0, 1)['unavailable_reason']
    assert pair(result, 1, 2)['views']['full'] is not None
    assert all(row[0] is None for c in result['conditions'] for row in c['distances'])
    json.dumps(result, allow_nan=False)


def test_saved_run_upgrade_embeds_once_and_never_generates_outputs():
    scenario, foci = fixture()
    plan = build_plan(scenario, foci, n_baseline=3, n_ablated=3)
    samples = samples_for(plan)
    original = deepcopy(samples)
    svc = service()
    result = score_pairwise(svc, scenario, foci, samples, n_baseline=3, n_ablated=3)
    assert len(result['pairs']) == 1
    assert result['pairs'][0]['views']['ablations'] is None
    assert result['embedding_tokens'] == 4
    assert svc.embedding_service.batch_embeddings_with_usage.call_count == 1
    assert not svc.provider.mock_calls
    assert samples == original
    with pytest.raises(ValueError, match='sample pools'):
        score_pairwise(svc, scenario, foci, {}, n_baseline=3, n_ablated=3)
    assert svc.embedding_service.batch_embeddings_with_usage.call_count == 1
