"""Workflow isolation, strict budgets, provenance and exploratory clustering."""

import copy
import json
from unittest.mock import Mock

import numpy as np
import pytest
from flask import Flask

from core.focal_assessor import FocalAssessor
from services.focus_workflow_service import (
    FocusWorkflowService, attach_focus_workflow, compare_assessments, validate_allocation,
)
from utils.output_distribution import describe_output_distribution


@pytest.fixture
def scenario():
    return {'version': 1, 'messages': [
        {'id': 'instructions', 'role': 'system', 'analysis_mode': 'analyse',
         'content': 'Be concise. Cite sources.'},
        {'id': 'history', 'role': 'assistant', 'analysis_mode': 'retain', 'content': 'Previous response'},
        {'id': 'chat', 'role': 'user', 'analysis_mode': 'retain',
         'input_name': 'chat_content', 'content': 'Retained question'},
    ]}


@pytest.fixture
def foci():
    # Duplicate labels must still get separate, correctly aligned allocations.
    return [{'focus': 'Rule', 'message_id': 'instructions', 'prompt_section': 'Be concise.'},
            {'focus': 'Rule', 'message_id': 'instructions', 'prompt_section': 'Cite sources.'}]


def allocation(first=60):
    return {'foci': [
        {'focus_index': 1, 'score': 100 - first, 'explanation': 'Sources support the response.'},
        {'focus_index': 0, 'score': first, 'explanation': 'A brief answer is appropriate.'},
    ]}


def test_assessment_isolation_and_retained_input(scenario, foci):
    provider = Mock()
    provider.chat_completion.return_value = {'content': json.dumps(allocation())}
    assessor = FocalAssessor(model='same-model', provider_instance=provider)
    service = FocusWorkflowService(assessor)
    foci[0]['explanation'] = 'OLD_ASSESSMENT_DO_NOT_INCLUDE'
    before = copy.deepcopy(scenario)
    forecast = service.assess(scenario, foci, phase='prospective', output='LEAKED_OUTPUT',
                              inputs={'chat_content': 'Actual retained question'})
    request = provider.chat_completion.call_args.kwargs
    source = json.loads(request['messages'][1]['content'])
    assert source['scenario']['messages'][-1]['content'] == 'Actual retained question'
    assert source['scenario']['messages'][1]['role'] == 'assistant'
    assert 'output' not in source
    assert 'LEAKED_OUTPUT' not in json.dumps(request)
    assert 'OLD_ASSESSMENT' not in json.dumps(request)
    assert request['model'] == forecast['model'] == 'same-model'
    assert scenario == before
    assert [f['score'] for f in forecast['foci']] == [60, 40]
    service.assess(scenario, foci, phase='retrospective', output='Only this output')
    source = json.loads(provider.chat_completion.call_args.kwargs['messages'][1]['content'])
    assert source['output'] == 'Only this output'
    assert 'prospective' not in source
    assert 'retrospective' not in source


@pytest.mark.parametrize('bad_scores', [[-1, 101], [0, 0], [float('nan'), 100], [True, 99], [50, 49]])
def test_rejects_invalid_budgets(foci, bad_scores):
    payload = allocation()
    for row, value in zip(payload['foci'], bad_scores):
        row['score'] = value
    with pytest.raises(ValueError):
        validate_allocation(payload, foci)


def test_missing_duplicate_and_unknown_foci_rejected(foci):
    for payload in ({'foci': allocation()['foci'][:1]}, {'foci': allocation()['foci'] * 2}):
        with pytest.raises(ValueError):
            validate_allocation(payload, foci)
    for index in (0, 10, '1'):
        payload = allocation()
        payload['foci'][0]['focus_index'] = index
        with pytest.raises(ValueError):
            validate_allocation(payload, foci)


def test_invalid_model_allocation_retried_once(scenario, foci):
    provider = Mock()
    provider.chat_completion.side_effect = [
        {'content': '{"foci":[]}', 'usage': {'total_tokens': 10}},
        {'content': json.dumps(allocation()), 'usage': {'total_tokens': 20}},
    ]
    result = FocusWorkflowService(FocalAssessor(provider_instance=provider)).assess(scenario, foci, phase='prospective')
    assert result['usage']['total_tokens'] == 30
    assert provider.chat_completion.call_count == 2
    provider.chat_completion.side_effect = None
    provider.chat_completion.return_value = {'content': '{"foci":[]}'}
    with pytest.raises(ValueError, match='after retry'):
        FocusWorkflowService(FocalAssessor(provider_instance=provider)).assess(scenario, foci, phase='prospective')


def test_average_deltas_and_ablation_shares(foci):
    result = compare_assessments(foci, allocation(60), [allocation(80), allocation(40)], [
        {'focus_index': 0, 't_obs': 0.3, 'q_value': 0.02},
        {'focus_index': 1, 't_obs': 0.1, 'q_value': 0.5},
    ])
    row = result['comparison'][0]
    assert row['retrospective_mean'] == 60
    assert row['retrospective_stddev'] == pytest.approx(np.std([80, 40], ddof=1))
    assert row['retrospective_minus_prospective_pp'] == 0
    assert row['ablation_shift_share'] == pytest.approx(75)
    assert row['ablation_minus_prospective_pp'] == pytest.approx(15)
    assert sum(f['score'] for f in result['average']['foci']) == pytest.approx(100)
    zero = compare_assessments(foci, allocation(), [allocation()], [{'focus_index': 0, 't_obs': 0}])
    assert zero['comparison'][0]['ablation_shift_share'] is None
    assert zero['comparison'][1]['ablation_shift_share'] is None


@pytest.mark.parametrize('modes', [2, 3, 4])
def test_detects_separated_modes_and_membership(modes):
    vectors = np.repeat(np.eye(modes), 3, axis=0)
    d = describe_output_distribution(vectors)['output_distribution']
    assert d['candidate_mode_count'] == modes
    assert [g['size'] for g in d['clusters']] == [3] * modes
    assert d['membership'] == np.repeat(np.arange(modes), 3).tolist()
    assert np.array(d['pairwise_cosine_distances']).shape == (3 * modes, 3 * modes)
    assert len(d['projection']['coordinates']) == 3 * modes


def test_tight_cluster_small_sample_and_outlier_are_not_declared_modes():
    rng = np.random.default_rng(10)
    for vectors in (np.ones((10, 4)), np.ones((10, 4)) + rng.normal(0, .001, (10, 4)),
                    [[1., 0.]], [[1., 0.]] * 9 + [[0., 1.]]):
        d = describe_output_distribution(vectors)['output_distribution']
        assert d['candidate_mode_count'] is None
    assert describe_output_distribution([[1, 0]])['baseline_stability']['mean_pairwise_cosine_distance'] is None


def test_invalid_embeddings_rejected():
    for vectors in ([[0., 0.]], [[1., float('nan')]], [], [[1.], [float('inf')]]):
        with pytest.raises(ValueError):
            describe_output_distribution(vectors)


def workflow(scenario, foci):
    return {'context': {'scenario': scenario, 'foci': foci,
                        'model': {'model': 'test-model', 'provider': 'openai'},
                        'temperature': .7, 'n_baseline': 2},
            'prospective': allocation(), 'samples': [{'content': 'first'}, {'content': 'second'}],
            'retrospective': [allocation(40), allocation(80)]}


def test_comparison_provenance_checked_before_checkpoint(scenario, foci):
    result = {'baseline_outputs': ['first', 'second'], 'influence_scores': []}
    fields = {'model': 'test-model', 'provider': 'openai'}
    valid = workflow(scenario, foci)
    attach_focus_workflow(result, valid, scenario, foci, fields, .7)
    assert result['baseline_reused']
    assert result['focus_comparison']['n_outputs'] == 2
    for mutation in ('samples', 'temperature', 'model', 'scenario', 'retrospective'):
        bad = copy.deepcopy(valid)
        if mutation == 'samples': bad['samples'].reverse()
        if mutation == 'temperature': bad['context']['temperature'] = .9
        if mutation == 'model': bad['context']['model']['model'] = 'other'
        if mutation == 'scenario': bad['context']['scenario']['messages'][-1]['content'] = 'Other question'
        if mutation == 'retrospective': bad['retrospective'].pop()
        with pytest.raises(ValueError):
            attach_focus_workflow(result, bad, scenario, foci, fields, .7)


def test_routes_refuse_forecast_leakage_and_use_mut(scenario, foci, monkeypatch):
    import routes.assessment_routes as routes
    app = Flask(__name__)
    app.register_blueprint(routes.assessment_bp)
    client = app.test_client()
    assessor = Mock(model='model-under-test', provider_name='openai')
    factory = Mock(return_value=assessor)
    monkeypatch.setattr(routes, 'get_assessor', factory)
    monkeypatch.setattr(FocusWorkflowService, 'assess', Mock(return_value=allocation()))
    data = {'scenario': scenario, 'foci': foci, 'phase': 'prospective',
            'mut_model': 'model-under-test', 'analysis_model': 'different-judge'}
    assert client.post('/api/focus-self-assessment', json={**data, 'output': 'future'}).status_code == 400
    factory.assert_not_called()
    assert client.post('/api/focus-self-assessment', json=data).status_code == 200
    assert factory.call_args.kwargs['data']['model'] == 'model-under-test'
    response = client.post('/api/focus-comparison', json={
        'foci': foci, 'prospective': allocation(), 'retrospective': [allocation(40), allocation(80)]})
    assert response.status_code == 200
    assert response.json['average']['foci'][0]['score'] == 60
