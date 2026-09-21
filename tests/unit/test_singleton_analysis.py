"""End-to-end variant construction and the three separate behavioral metrics."""
from copy import deepcopy
import json
from unittest.mock import Mock

from flask import Flask
import numpy as np
import pytest

from routes.singleton_routes import singleton_bp
from services.ablation_service import AblationService
from services.singleton_service import build_plan, score_samples
from utils.inference_scenario import ablate_scenario, ScenarioValidationError
from utils.json_safe import sanitize_non_finite
from utils.hosted_mode import path_requires_live


def fixture():
    text = 'Unlabelled prefix. AAA. | BBB. Unlabelled suffix.'
    scenario = {'version': 1, 'messages': [
        {'id': 'rules', 'role': 'developer', 'analysis_mode': 'analyse', 'content': text},
        {'id': 'history', 'role': 'assistant', 'analysis_mode': 'retain', 'content': 'Prior answer.'},
        {'id': 'chat', 'role': 'user', 'analysis_mode': 'retain', 'content': 'What is 2 + 2?', 'input_name': 'question'},
    ], 'output_contract': {'type': 'json_schema', 'name': 'answer', 'strict': True,
                          'schema': {'type': 'object', 'properties': {'answer': {'type': 'string'}},
                                     'required': ['answer'], 'additionalProperties': False}}}
    foci = [{'focus': name, 'id': name.lower(), 'spans': [{'message_id': 'rules', 'char_start': text.index(t),
             'char_end': text.index(t) + len(t), 'text_snapshot': t}]} for name, t in [('A', 'AAA.'), ('B', 'BBB.')]]
    return scenario, foci


def service(vectors=None):
    vectors = vectors or {'full': [1, 0], 'empty': [0, 1], 'a': [1, 0], 'b': [-1, 0]}
    emb = Mock()
    emb.model = 'synthetic-embedding'
    emb.batch_embeddings_with_usage.side_effect = lambda texts: ([np.array(vectors[t], float) for t in texts], len(texts))
    return AblationService(Mock(), 'test-model', provider_name='openai', embedding_service=emb)


def samples_for(plan):
    words = {'full': 'full', 'no_focus': 'empty', 'singleton_0': 'a', 'singleton_1': 'b', 'leave_one_out_0': 'b', 'leave_one_out_1': 'a'}
    return {pool['id']: [{'content': words[pool['variants'][0]], 'scenario': pool['scenario'],
                         'usage': {'prompt_tokens': 2, 'completion_tokens': 1}} for _ in range(pool['n_samples'])]
            for pool in plan['pools']}


def test_all_four_variants_exact_preservation_and_equivalent_request_pools():
    scenario, foci = fixture()
    original = deepcopy(scenario)
    plan = build_plan(scenario, foci)
    arms = {v['id']: v for v in plan['variants']}
    assert arms['full']['scenario'] == original
    assert arms['no_focus']['scenario']['messages'][0]['content'] == 'Unlabelled prefix.  |  Unlabelled suffix.'
    for i, text in enumerate(['AAA.', 'BBB.']):
        single = arms[f'singleton_{i}']['scenario']
        assert text in single['messages'][0]['content']
        assert ['BBB.', 'AAA.'][i] not in single['messages'][0]['content']
        assert arms[f'leave_one_out_{i}']['scenario'] == ablate_scenario(original, foci[i])[0]
        assert arms[f'singleton_{i}']['pool_id'] == arms[f'leave_one_out_{1-i}']['pool_id']
    for arm in arms.values():
        assert arm['scenario']['messages'][1:] == original['messages'][1:]
        assert arm['scenario']['output_contract'] == original['output_contract']
    assert len(arms) == 6 and len(plan['pools']) == 4
    assert plan['planned_calls'] == 30 and plan['calls_without_reuse'] == 40
    assert scenario == original


def test_whitespace_multispan_and_overlaps_preserve_selected_and_retained_content():
    scenario, foci = fixture()
    scenario['messages'][0]['content'] = 'AAA. \n BBB.'
    foci[0]['spans'][0].update(char_start=0, char_end=4)
    foci[1]['spans'][0].update(char_start=7, char_end=11)
    plan = build_plan(scenario, foci)
    assert plan['variants'][1]['scenario']['messages'][0]['content'] == ' \n '
    foci.append({'focus': 'envelope', 'spans': [{'message_id': 'rules', 'char_start': 0,
                                             'char_end': 11, 'text_snapshot': 'AAA. \n BBB.'}]})
    arms = {v['id']: v for v in build_plan(scenario, foci)['variants']}
    assert arms['singleton_0']['scenario']['messages'][0]['content'] == 'AAA.'
    assert arms['singleton_0']['shared_text_retained_for_excluded'] == [2]
    assert arms['singleton_2']['scenario'] == scenario
    assert [m['id'] for m in arms['no_focus']['scenario']['messages']] == ['history', 'chat']
    scenario, foci = fixture()
    scenario['messages'].insert(1, {'id': 'extra', 'role': 'developer', 'analysis_mode': 'analyse', 'content': 'CCC. Residual.'})
    foci[0]['spans'].append({'message_id': 'extra', 'char_start': 0, 'char_end': 4, 'text_snapshot': 'CCC.'})
    arms = {v['id']: v for v in build_plan(scenario, foci)['variants']}
    assert arms['singleton_0']['scenario']['messages'][1]['content'] == 'CCC. Residual.'
    assert arms['singleton_1']['scenario']['messages'][1]['content'] == ' Residual.'


def test_sampling_uses_existing_execution_path_same_model_temperature_and_contract():
    scenario, foci = fixture()
    svc = service()
    svc._complete_scenario = Mock(return_value={'content': '{"answer":"four"}'})
    plan = build_plan(scenario, foci)
    for arm in plan['variants']:
        result = svc.sample_scenario_completion(scenario, foci, arm['kind'], .7, focus_index=arm['focus_index'])
        assert result['scenario'] == arm['scenario']
        assert svc._complete_scenario.call_args.args == (arm['scenario'], .7)
    assert svc._complete_scenario.call_count == 6
    bound = build_plan(scenario, foci, inputs={'question': 'What is 3 + 3?'})
    assert all(v['scenario']['messages'][-1]['content'] == 'What is 3 + 3?' for v in bound['variants'])


def test_blank_imported_row_and_whitespace_only_ablated_user_are_never_sent():
    scenario, foci = fixture()
    extra = 'CCC.\n\nDDD.'
    scenario['messages'].extend([
        {'id': 'extra-rules', 'role': 'user', 'analysis_mode': 'analyse', 'content': extra},
        {'id': 'unused-row', 'role': 'user', 'analysis_mode': 'retain', 'content': ''},
    ])
    for label, text in [('C', 'CCC.'), ('D', 'DDD.')]:
        start = extra.index(text)
        foci.append({'focus': label, 'spans': [{'message_id': 'extra-rules', 'char_start': start,
                     'char_end': start + len(text), 'text_snapshot': text}]})
    original = deepcopy(scenario)
    svc = service()
    svc.provider.chat_completion.return_value = {'content': '{"answer":"four"}'}
    plan = build_plan(scenario, foci)
    for arm in plan['variants']:
        result = svc.sample_scenario_completion(scenario, foci, arm['kind'], .7, focus_index=arm['focus_index'])
        sent = svc.provider.chat_completion.call_args.kwargs['messages']
        assert all(m['content'].strip() for m in sent)
        assert {'role': 'user', 'content': 'What is 2 + 2?'} in sent
        assert sent == [{'role': m['role'], 'content': m['content']}
                        for m in arm['scenario']['messages'] if m['content'].strip()]
        assert result['scenario'] == arm['scenario']
        assert result['scenario']['messages'][-1] == original['messages'][-1]
        assert result['scenario_metadata']['omitted_blank_message_ids'] == arm['omitted_blank_message_ids']
        assert 'unused-row' in arm['omitted_blank_message_ids']
    empty = next(arm for arm in plan['variants'] if arm['id'] == 'no_focus')
    assert 'extra-rules' in empty['omitted_blank_message_ids']
    assert scenario == original


def test_plan_preflights_all_variants_before_sampling():
    scenario, foci = fixture()
    # A blank retained row used to satisfy the user-role check even when the
    # no-focus condition removed the only real user message.
    scenario['messages'] = [
        {'id': 'only-user', 'role': 'user', 'analysis_mode': 'analyse', 'content': 'AAA.'},
        {'id': 'unused-row', 'role': 'user', 'analysis_mode': 'retain', 'content': ''},
    ]
    foci = [{'focus': 'A', 'spans': [{'message_id': 'only-user', 'char_start': 0,
                                   'char_end': 4, 'text_snapshot': 'AAA.'}]}]
    with pytest.raises(ScenarioValidationError, match='nonblank user message'):
        build_plan(scenario, foci)


def test_three_foci_have_independent_singleton_and_leave_one_out_variants():
    scenario, foci = fixture()
    scenario['messages'][0]['content'] += ' CCC.'
    start = scenario['messages'][0]['content'].index('CCC.')
    foci.append({'focus': 'C', 'spans': [{'message_id': 'rules', 'char_start': start,
                                       'char_end': start + 4, 'text_snapshot': 'CCC.'}]})
    plan = build_plan(scenario, foci)
    assert len(plan['variants']) == len(plan['pools']) == 8
    for arm in plan['variants']:
        if arm['kind'] != 'singleton': continue
        content = arm['scenario']['messages'][0]['content']
        assert [name in content for name in ('AAA.', 'BBB.', 'CCC.')] == [j == arm['focus_index'] for j in range(3)]


def test_influence_sufficiency_negative_values_and_necessity_unchanged():
    scenario, foci = fixture()
    plan = build_plan(scenario, foci, n_baseline=5, n_ablated=5)
    samples = samples_for(plan)
    svc = service()
    result = score_samples(svc, scenario, foci, samples, n_baseline=5, n_ablated=5, n_permutations=100, permutation_seed=4)
    a, b = result['focus_results']
    assert not result['low_behavioral_contrast']
    assert result['full_no_focus_distance'] == pytest.approx(1)
    assert a['influence'] == pytest.approx(1) and a['sufficiency'] == pytest.approx(1)
    assert a['normalized_influence'] == pytest.approx(1)
    assert b['influence'] == pytest.approx(1) and b['singleton_full_distance'] == pytest.approx(2)
    assert b['sufficiency'] == pytest.approx(-1)  # no clamping
    assert a['necessity'] == pytest.approx(2) and b['necessity'] == pytest.approx(0)
    assert a['singleton_outputs'] == ['a'] * 5
    assert result['full_outputs'] == ['full'] * 5 and result['no_focus_outputs'] == ['empty'] * 5
    assert svc.embedding_service.batch_embeddings_with_usage.call_count == 1
    assert result['pairwise_resemblance']['pairs'][0]['views']['full']['row_share'] == 1
    assert set(svc.embedding_service.batch_embeddings_with_usage.call_args.args[0]) == {'full', 'empty', 'a', 'b'}
    prior = svc.score_scenario_from_samples(scenario, foci, result['full_outputs'],
                {i: r['leave_one_out_outputs'] for i, r in enumerate(result['focus_results'])},
                n_permutations=100, permutation_seed=4, temperature=.7)
    for row, old in zip(result['focus_results'], prior['influence_scores']):
        for key in ('t_obs', 'p_value', 'q_value', 'normalized_influence', 'standardized_effect'):
            assert row['necessity_comparison'][key] == old[key]
    json.dumps(sanitize_non_finite(result), allow_nan=False)


@pytest.mark.parametrize('epsilon', [0, 1e-5, 1e-3])
def test_near_zero_contrast_is_explicit_and_ratios_are_null(epsilon):
    scenario, foci = fixture()
    plan = build_plan(scenario, foci, n_baseline=3, n_ablated=3)
    svc = service({'full': [1, epsilon], 'empty': [1, 0], 'a': [0, 1], 'b': [-1, 0]})
    result = score_samples(svc, scenario, foci, samples_for(plan), n_baseline=3, n_ablated=3, n_permutations=20)
    assert result['low_behavioral_contrast'] and result['normalized_metrics_note']
    assert result['full_no_focus_distance'] <= result['contrast_threshold']
    for row in result['focus_results']:
        assert row['sufficiency'] is None and row['normalized_influence'] is None
        assert row['influence'] >= 0 and row['singleton_full_distance'] >= 0


def test_low_contrast_can_be_sampling_noise_even_above_numerical_floor():
    scenario, foci = fixture()
    plan = build_plan(scenario, foci, n_baseline=3, n_ablated=3)
    samples = samples_for(plan)
    full = next(p for p in plan['pools'] if 'full' in p['variants'])
    empty = next(p for p in plan['pools'] if 'no_focus' in p['variants'])
    for sample, name in zip(samples[full['id']], ['full', 'empty', 'a']): sample['content'] = name
    for sample, name in zip(samples[empty['id']], ['full', 'empty', 'b']): sample['content'] = name
    svc = service({'full':[1,0], 'empty':[0,1], 'a':[1,.1], 'b':[1,.2]})
    result = score_samples(svc, scenario, foci, samples, n_baseline=3, n_ablated=3, n_permutations=30)
    assert result['full_no_focus_distance'] > 1e-6
    assert result['low_behavioral_contrast']


@pytest.mark.parametrize('bad', [None, {}, {'pool': []}])
def test_missing_pools_fail_before_embeddings(bad):
    svc = service()
    with pytest.raises(ValueError, match='sample pools'):
        score_samples(svc, *fixture(), bad)
    svc.embedding_service.batch_embeddings_with_usage.assert_not_called()


def test_mismatched_samples_and_invalid_foci_fail_before_inference():
    scenario, foci = fixture()
    svc = service()
    plan = build_plan(scenario, foci)
    samples = samples_for(plan)
    first = next(iter(samples.values()))
    first[0]['scenario'] = {'version': 1, 'messages': []}
    with pytest.raises(ValueError, match='planned scenario'):
        score_samples(svc, scenario, foci, samples)
    svc.embedding_service.batch_embeddings_with_usage.assert_not_called()
    foci[0]['spans'][0]['text_snapshot'] = 'stale'
    with pytest.raises(ValueError, match='snapshot'): build_plan(scenario, foci)


def test_api_fields_checkpoint_and_hosted_guard(monkeypatch, tmp_path):
    scenario, foci = fixture()
    from services.checkpoint_service import CheckpointService
    checkpoints = CheckpointService(str(tmp_path))
    monkeypatch.setattr('routes.singleton_routes.CheckpointService', lambda: checkpoints)
    monkeypatch.setattr('routes.singleton_routes._ablation_service', lambda _: service())
    app = Flask(__name__); app.register_blueprint(singleton_bp); client = app.test_client()
    body = {'scenario': scenario, 'foci': foci, 'n_baseline': 3, 'n_ablated': 3, 'temperature': .7}
    plan_response = client.post('/api/singleton-plan', json=body)
    assert plan_response.status_code == 200
    response = client.post('/api/singleton-score', json={**body, 'samples': samples_for(plan_response.json), 'n_permutations': 50})
    assert response.status_code == 200
    data = response.json
    assert data['protocol'] == 'singleton-focus-v1' and len(data['focus_results']) == 2
    assert {'full_outputs', 'no_focus_outputs', 'low_behavioral_contrast', 'full_no_focus_distance'} <= data.keys()
    assert {'singleton_outputs', 'influence', 'sufficiency', 'necessity', 'normalized_influence', 'singleton_full_distance'} <= data['focus_results'][0].keys()
    assert data['checkpoint']['saved']
    saved = checkpoints.load_checkpoint(data['checkpoint']['session_id'], 'singleton_analysis')
    assert saved['result_data']['focus_results'] == data['focus_results']
    listing = checkpoints.list_checkpoints('singleton_analysis')
    assert listing[0]['num_foci'] == 2 and listing[0]['model'] == 'test-model'
    assert path_requires_live('/api/singleton-score') and not path_requires_live('/api/singleton-plan')
    assert path_requires_live('/api/singleton-pairwise')
    pairwise = client.post('/api/singleton-pairwise', json={**body, 'samples': samples_for(plan_response.json)})
    assert pairwise.status_code == 200
    assert pairwise.json['protocol'] == 'pairwise-singleton-resemblance-v1'
    assert pairwise.json['pairs'][0]['views']['ablations'] is None
    assert client.post('/api/singleton-pairwise', json={**body, 'samples': {}}).status_code == 400
    assert client.post('/api/singleton-score', json={**body, 'samples': {}}).status_code == 400
    assert client.post('/api/singleton-plan', json=['bad']).status_code == 400
