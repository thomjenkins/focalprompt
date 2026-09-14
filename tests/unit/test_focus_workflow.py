"""Workflow isolation, strict budgets, provenance and exploratory clustering."""

import copy
import json
from unittest.mock import Mock

import numpy as np
import pytest
from flask import Flask

from core.focal_assessor import FocalAssessor
from services.focus_workflow_service import (
    ASSESSMENT_PROTOCOL, FocusWorkflowService, attach_focus_workflow, compare_assessments, validate_allocation,
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
    return {'request_summary': 'Answer the retained question briefly with sources.',
            'request_evidence': [{'message_id': 'chat', 'quote': 'question'}], 'foci': [
        {'focus_index': 1, 'applicability': 'direct', 'score': 100 - first, 'explanation': 'Sources support the response.'},
        {'focus_index': 0, 'applicability': 'background', 'score': first, 'explanation': 'A brief answer is appropriate.'},
    ]}


def test_assessment_isolation_and_retained_input(scenario, foci):
    provider = Mock()
    provider.chat_completion.side_effect = lambda **kw: {'content': json.dumps(
        {'scores': {'0': 60, '1': 40}} if 'applicability_assessment' in json.loads(kw['messages'][1]['content']) else allocation())}
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
    assert forecast['request_evidence'] == [{'message_id': 'chat', 'quote': 'question'}]
    assert forecast['assessment_protocol'] == ASSESSMENT_PROTOCOL
    assert forecast['assessment_temperature'] == request['temperature'] == 0.2
    assert all('score' not in row for row in source['applicability_assessment']['foci'])
    service.assess(scenario, foci, phase='retrospective', output='Only this output')
    source = json.loads(provider.chat_completion.call_args.kwargs['messages'][1]['content'])
    assert source['output'] == 'Only this output'
    assert 'prospective' not in source
    assert 'retrospective' not in source


@pytest.mark.parametrize('mutation', ['missing_summary', 'missing_evidence', 'fabricated_quote',
                                     'unknown_message', 'instructions_only', 'missing_applicability',
                                     'invalid_applicability', 'inactive_with_budget'])
def test_live_assessment_requires_grounding(scenario, foci, mutation):
    payload = allocation()
    if mutation == 'missing_summary': payload.pop('request_summary')
    if mutation == 'missing_evidence': payload.pop('request_evidence')
    if mutation == 'fabricated_quote': payload['request_evidence'][0]['quote'] = 'Invented request'
    if mutation == 'unknown_message': payload['request_evidence'][0]['message_id'] = 'missing'
    if mutation == 'instructions_only': payload['request_evidence'] = [{'message_id': 'instructions', 'quote': 'Be concise.'}]
    if mutation == 'missing_applicability': payload['foci'][0].pop('applicability')
    if mutation == 'invalid_applicability': payload['foci'][0]['applicability'] = []
    if mutation == 'inactive_with_budget': payload['foci'][0]['applicability'] = 'inactive'
    with pytest.raises(ValueError):
        validate_allocation(payload, foci, scenario=scenario)


def test_grounding_can_use_analysed_user_request_and_preserves_zero_and_equal_scores(scenario, foci):
    scenario['messages'][-1]['analysis_mode'] = 'analyse'
    payload = allocation(50)
    result = validate_allocation(payload, foci, scenario=scenario)
    assert [f['score'] for f in result['foci']] == [50, 50]
    payload = allocation(100)
    payload['foci'][0]['applicability'] = 'inactive'
    result = validate_allocation(payload, foci, scenario=scenario)
    assert result['foci'][1]['score'] == 0
    assert result['foci'][1]['applicability'] == 'inactive'


def test_rescaling_preserves_model_ratios_raw_scores_and_zeros(scenario, foci):
    payload = allocation()
    payload['foci'][0]['score'] = 10
    payload['foci'][1]['score'] = 20
    result = validate_allocation(payload, foci, scenario=scenario, normalize_budget=True)
    assert result['budget_normalized'] is True
    assert result['raw_score_total'] == 30
    assert [f['raw_score'] for f in result['foci']] == [20, 10]
    assert result['foci'][0]['score'] / result['foci'][1]['score'] == 2
    assert sum(f['score'] for f in result['foci']) == pytest.approx(100)
    payload['foci'][0].update(score=0, applicability='inactive')
    result = validate_allocation(payload, foci, scenario=scenario, normalize_budget=True)
    assert [f['score'] for f in result['foci']] == [100, 0]
    payload['foci'][1]['score'] = 0
    with pytest.raises(ValueError, match='sum to 100'):
        validate_allocation(payload, foci, scenario=scenario, normalize_budget=True)


def test_comparison_preserves_legacy_runs_but_refuses_mixed_methods(foci):
    legacy = allocation()
    legacy.pop('request_summary')
    legacy.pop('request_evidence')
    for row in legacy['foci']: row.pop('applicability')
    assert compare_assessments(foci, legacy, [legacy])['n_outputs'] == 1
    new = {**allocation(), 'assessment_protocol': ASSESSMENT_PROTOCOL}
    assert compare_assessments(foci, new, [new])['n_outputs'] == 1
    for before, after in ((legacy, new), (new, legacy)):
        with pytest.raises(ValueError, match='same assessment method'):
            compare_assessments(foci, before, [after])


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


def test_invalid_model_allocation_recovery_is_bounded(scenario, foci):
    provider = Mock()
    provider.chat_completion.side_effect = [
        {'content': '{"foci":[]}', 'usage': {'total_tokens': 10}},
        {'content': json.dumps(allocation()), 'usage': {'total_tokens': 20}},
        {'content': json.dumps({'scores': {'0': 60, '1': 40}}), 'usage': {'total_tokens': 30}},
    ]
    result = FocusWorkflowService(FocalAssessor(provider_instance=provider)).assess(scenario, foci, phase='prospective')
    assert result['usage']['total_tokens'] == 60
    assert provider.chat_completion.call_count == 3
    provider.chat_completion.side_effect = None
    provider.chat_completion.return_value = {'content': '{"foci":[]}'}
    provider.chat_completion.reset_mock()
    with pytest.raises(ValueError, match='after 2 recovery calls.*1. Rule, 2. Rule'):
        FocusWorkflowService(FocalAssessor(provider_instance=provider)).assess(scenario, foci, phase='prospective')
    assert provider.chat_completion.call_count == 3


@pytest.mark.parametrize('phase', ['prospective', 'retrospective'])
def test_missing_focus_repair_keeps_explanations_but_never_scores(scenario, foci, phase):
    initial = allocation()
    initial['foci'] = initial['foci'][:1]  # Only index 1: the first catalog row is missing.
    repaired = allocation(20)
    repaired['request_evidence'][0]['quote'] = 'Invented repair evidence'
    provider = Mock()
    provider.chat_completion.side_effect = [
        {'content': json.dumps(initial), 'usage': {'total_tokens': 10}},
        {'content': json.dumps(repaired), 'usage': {'total_tokens': 20}},
        {'content': json.dumps({'scores': {'0': 20, '1': 80}}), 'usage': {'total_tokens': 30}},
    ]
    result = FocusWorkflowService(FocalAssessor(provider_instance=provider)).assess(
        scenario, foci, phase=phase, output='Actual response')
    source = json.loads(provider.chat_completion.call_args_list[1].kwargs['messages'][1]['content'])
    assert source['recovery']['requested_focus_indices'] == [0]
    assert [row['focus_index'] for row in source['recovery']['requested_foci']] == [0]
    assert source['recovery']['accepted_reasoning']['foci'] == [
        {k: v for k, v in row.items() if k != 'score'} for row in initial['foci']]
    assert len(source['foci']) == 2
    assert (source.get('output') == 'Actual response') == (phase == 'retrospective')
    assert [f['raw_score'] for f in result['foci']] == [20, 80]  # Every score comes from the joint call.
    assert result['request_evidence'] == initial['request_evidence']
    assert result['allocation_recovery'] == {'calls': 1, 'focus_indices': [0], 'budget_retries': 0}
    assert result['usage']['total_tokens'] == 60


@pytest.mark.parametrize('defect', ['duplicate', 'unknown', 'no_explanation', 'invalid_applicability'])
def test_repair_reassesses_invalid_rows_without_inventing_scores(scenario, foci, defect):
    initial = allocation()
    row = initial['foci'][1]
    if defect == 'duplicate': initial['foci'].append(copy.deepcopy(row))
    if defect == 'unknown': row['focus_index'] = 99
    if defect == 'no_explanation': row['explanation'] = ''
    if defect == 'invalid_applicability': row['applicability'] = 'unknown'
    provider = Mock()
    provider.chat_completion.side_effect = [
        {'content': json.dumps(initial)}, {'content': json.dumps(allocation())},
        {'content': json.dumps({'scores': {'0': 60, '1': 40}})},
    ]
    result = FocusWorkflowService(FocalAssessor(provider_instance=provider)).assess(scenario, foci, phase='prospective')
    source = json.loads(provider.chat_completion.call_args_list[1].kwargs['messages'][1]['content'])
    assert source['recovery']['requested_focus_indices'] == [0]
    assert [f['raw_score'] for f in result['foci']] == [60, 40]
    assert len(result['foci']) == 2


def test_truncated_explanations_can_recover_in_batches_but_budget_is_always_joint(scenario, foci):
    catalog = foci * 9  # 18 foci, with deliberately repeated labels.
    provider = Mock()
    requested_batches = []

    def reply(**kwargs):
        source = json.loads(kwargs['messages'][1]['content'])
        assert len(source['foci']) == 18
        if 'applicability_assessment' in source:
            assert len(source['applicability_assessment']['foci']) == 18
            assert all('score' not in row for row in source['applicability_assessment']['foci'])
            return {'content': json.dumps({'scores': {str(i): i + 1 for i in range(18)}})}
        if 'recovery' not in source:
            return {'content': '{"request_summary": "Cut off', 'finish_reason': 'length'}
        requested = source['recovery']['requested_focus_indices']
        requested_batches.append(requested)
        assert 'Do not assign any scores' in kwargs['messages'][0]['content']
        return {'content': json.dumps({**allocation(), 'foci': [
            {'focus_index': i, 'score': 100 / len(requested), 'applicability': 'background',
             'explanation': f'Constraint {i} shapes this answer.'} for i in reversed(requested)]})}

    provider.chat_completion.side_effect = reply
    result = FocusWorkflowService(FocalAssessor(provider_instance=provider)).assess(scenario, catalog, phase='prospective')
    assert requested_batches == [list(range(8)), list(range(8, 16)), [16, 17]]
    assert [f['focus_index'] for f in result['foci']] == list(range(18))
    assert [f['raw_score'] for f in result['foci']] == list(range(1, 19))
    assert result['raw_score_total'] == sum(range(1, 19))
    assert sum(f['score'] for f in result['foci']) == pytest.approx(100)
    assert result['foci'][-1]['score'] / result['foci'][0]['score'] == pytest.approx(18)
    assert result['allocation_recovery'] == {'calls': 3, 'focus_indices': list(range(18)), 'budget_retries': 0}


def test_repair_retries_only_still_missing_entries(scenario, foci):
    catalog = foci * 2
    payload = allocation()
    provider = Mock()
    provider.chat_completion.side_effect = [
        {'content': json.dumps(payload)},
        {'content': json.dumps({'foci': [{**payload['foci'][0], 'focus_index': 3}]})},
        {'content': json.dumps({'foci': [{**payload['foci'][0], 'focus_index': 2,
                                        'score': 0, 'applicability': 'inactive'}]})},
        {'content': json.dumps({'scores': {'0': 10, '1': 20, '2': 0, '3': 70}})},
    ]
    result = FocusWorkflowService(FocalAssessor(provider_instance=provider)).assess(scenario, catalog, phase='prospective')
    sources = [json.loads(call.kwargs['messages'][1]['content']) for call in provider.chat_completion.call_args_list]
    assert sources[1]['recovery']['requested_focus_indices'] == [2, 3]
    assert sources[2]['recovery']['requested_focus_indices'] == [2]
    assert [f['raw_score'] for f in result['foci']] == [10, 20, 0, 70]


def test_grounding_only_repair_retains_explanations_before_joint_budget(scenario, foci):
    payload = allocation()
    payload['request_evidence'][0]['quote'] = 'Not a real quote'
    repaired = allocation()
    repaired['foci'] = []
    provider = Mock()
    provider.chat_completion.side_effect = [
        {'content': json.dumps(payload)}, {'content': json.dumps(repaired)},
        {'content': json.dumps({'scores': {'0': 60, '1': 40}})},
    ]
    result = FocusWorkflowService(FocalAssessor(provider_instance=provider)).assess(scenario, foci, phase='prospective')
    source = json.loads(provider.chat_completion.call_args_list[1].kwargs['messages'][1]['content'])
    assert source['recovery']['requested_focus_indices'] == []
    assert [f['score'] for f in result['foci']] == [60, 40]
    assert result['request_evidence'] == repaired['request_evidence']


def test_all_zero_budget_requires_new_model_scores(scenario, foci):
    provider = Mock()
    provider.chat_completion.side_effect = [
        {'content': json.dumps(allocation())}, {'content': json.dumps({'scores': {'0': 0, '1': 0}})},
        {'content': json.dumps({'scores': {'0': 60, '1': 40}})},
    ]
    result = FocusWorkflowService(FocalAssessor(provider_instance=provider)).assess(scenario, foci, phase='prospective')
    source = json.loads(provider.chat_completion.call_args.kwargs['messages'][1]['content'])
    assert 'recovery' not in source
    assert all('score' not in row for row in source['applicability_assessment']['foci'])
    assert [f['score'] for f in result['foci']] == [60, 40]
    assert result['allocation_recovery']['budget_retries'] == 1


@pytest.mark.parametrize('invalid', [[10], [10, 10, 10], [-10, 110], [True, 99], [float('nan'), 50]])
def test_numeric_retries_replace_the_entire_budget_without_partial_anchors(scenario, foci, invalid):
    provider = Mock()
    provider.chat_completion.side_effect = [
        {'content': json.dumps(allocation())}, {'content': json.dumps({'scores': {str(i): v for i, v in enumerate(invalid)}})},
        {'content': json.dumps({'scores': {'0': 80, '1': 20}})},
    ]
    result = FocusWorkflowService(FocalAssessor(provider_instance=provider)).assess(scenario, foci, phase='prospective')
    first, retry = provider.chat_completion.call_args_list[1:]
    assert first.kwargs['messages'][1] == retry.kwargs['messages'][1]
    assert [row['score'] for row in result['foci']] == [80, 20]
    assert result['allocation_recovery']['budget_retries'] == 1


def test_uniform_17_focus_budget_is_flagged_without_forcing_unequal_scores(scenario, foci):
    catalog = (foci * 9)[:17]
    reasoning = {**allocation(), 'foci': [{**allocation()['foci'][1], 'focus_index': i} for i in range(17)]}
    provider = Mock()
    provider.chat_completion.side_effect = [
        {'content': json.dumps(reasoning)}, {'content': json.dumps({'scores': {str(i): 10 for i in range(17)}})},
    ]
    result = FocusWorkflowService(FocalAssessor(provider_instance=provider)).assess(scenario, catalog, phase='prospective')
    assert [round(row['score'], 1) for row in result['foci']] == [5.9] * 17
    assert result['uniform_allocation']
    assert 'identical weights' in result['assessment_warnings'][0]
    assert provider.chat_completion.call_count == 2


def test_joint_budget_never_assigns_positive_scores_to_inactive_foci(scenario, foci):
    reasoning = allocation()
    reasoning['foci'][0]['applicability'] = 'inactive'
    provider = Mock()
    provider.chat_completion.side_effect = [
        {'content': json.dumps(reasoning)}, {'content': json.dumps({'scores': {'0': 50, '1': 50}})},
        {'content': json.dumps({'scores': {'0': 100, '1': 0}})},
    ]
    result = FocusWorkflowService(FocalAssessor(provider_instance=provider)).assess(scenario, foci, phase='prospective')
    assert [row['score'] for row in result['foci']] == [100, 0]


def test_joint_budget_retries_are_bounded(scenario, foci):
    provider = Mock()
    provider.chat_completion.side_effect = [{'content': json.dumps(allocation())}] + [{'content': '{"scores": []}'}] * 3
    with pytest.raises(ValueError, match='complete joint focus budget'):
        FocusWorkflowService(FocalAssessor(provider_instance=provider)).assess(scenario, foci, phase='prospective')
    assert provider.chat_completion.call_count == 4


def test_joint_budget_aligns_by_id_and_rejects_wrong_ids(scenario, foci):
    provider = Mock()
    provider.chat_completion.side_effect = [
        {'content': json.dumps(allocation())},
        {'content': '{"scores": {"1": 20, "2": 80}}'},
        {'content': '{"scores": {"1": 80, "0": 20}}'},
    ]
    result = FocusWorkflowService(FocalAssessor(provider_instance=provider)).assess(scenario, foci, phase='prospective')
    assert [row['score'] for row in result['foci']] == [20, 80]


def test_joint_budget_accepts_complete_index_mapping_without_wrapper(scenario, foci):
    provider = Mock()
    provider.chat_completion.side_effect = [
        {'content': json.dumps(allocation())},
        {'content': '{"1": 80, "0": 20, "overall_summary": "Sources matter most here."}'},
    ]
    result = FocusWorkflowService(FocalAssessor(provider_instance=provider)).assess(scenario, foci, phase='prospective')
    assert [row['score'] for row in result['foci']] == [20, 80]
    assert result['overall_summary'] == 'Sources matter most here.'


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
