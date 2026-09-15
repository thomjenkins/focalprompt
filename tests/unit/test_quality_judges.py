"""Judge attribution and identical task evidence, without paid model requests."""

import copy
import json
import re
from types import SimpleNamespace
from unittest.mock import MagicMock

from flask import Flask
import pytest

from routes import evaluation_routes
from services.output_evaluator_service import build_quality_evaluation_prompt
from services.output_evaluator_service import _normalize_evaluation_rows, sample_outputs_stratified


SCENARIO = {
    'version': 1,
    'messages': [
        {'id': 'instructions', 'role': 'developer', 'analysis_mode': 'analyse',
         'content': 'Answer the arithmetic question in JSON.'},
        {'id': 'chat', 'role': 'user', 'analysis_mode': 'retain', 'content': 'What is 2 + 3?'},
    ],
    'output_contract': {'type': 'json_schema', 'name': 'answer', 'strict': True,
                        'schema': {'type': 'object', 'properties': {'answer': {'type': 'number'}},
                                   'required': ['answer'], 'additionalProperties': False}},
}


@pytest.fixture
def quality_client(monkeypatch):
    calls = []
    selections = []

    def get_assessor(*, data):
        selections.append(data)
        provider = MagicMock()

        def respond(**kwargs):
            calls.append(kwargs)
            labels = re.findall(r'^--- (.+) ---$', kwargs['messages'][1]['content'], re.M)
            score = 60 if kwargs['model'] == 'gpt-4o-mini' else 80
            return {'content': json.dumps({'evaluations': [
                {'label': label, 'overall_score': score, 'summary': 'Synthetic judgment.'}
                for label in labels]}), 'usage': {'prompt_tokens': 100, 'completion_tokens': 50}}

        provider.chat_completion.side_effect = respond
        return SimpleNamespace(provider=provider, provider_name=data['provider'])

    monkeypatch.setattr(evaluation_routes, 'get_assessor', get_assessor)
    app = Flask(__name__)
    app.register_blueprint(evaluation_routes.evaluation_bp)
    return app.test_client(), calls, selections


def payload(**extra):
    return {
        'eval_criteria': 'Correct answer in the required format.',
        'scenario': copy.deepcopy(SCENARIO),
        'outputs': [{'label': f'{group} {i}', 'text': '{"answer": 5}',
                     'group': group, 'focus': 'format'}
                    for group in ('baseline', 'ablated') for i in range(4)],
        'generation_model': {'model': 'gpt-4o-mini', 'provider': 'openai'},
        'analysis_model': 'gpt-4o', 'analysis_provider': 'openai',
        'mut_model': 'changed-selector', 'mut_provider': 'google',
        'sample_pct': 50, 'sample_seed': 17, **extra,
    }


def test_both_judges_use_same_evidence_and_record_distinct_results(quality_client):
    client, calls, selections = quality_client
    results = []
    for role in ('self', 'external'):
        response = client.post('/api/evaluate-outputs-quality', json=payload(judge_role=role))
        assert response.status_code == 200, response.json
        results.append(response.json)
    own, other = results
    assert [s['model'] for s in selections] == ['gpt-4o-mini', 'gpt-4o']
    assert [s['provider'] for s in selections] == ['openai', 'openai']
    assert calls[0]['messages'] == calls[1]['messages']
    assert calls[0]['temperature'] == calls[1]['temperature'] == .2
    assert own['sampled_labels'] == other['sampled_labels']
    assert len(own['sampled_labels']) == 4
    assert {row['overall_score'] for row in own['evaluations']} == {60}
    assert {row['overall_score'] for row in other['evaluations']} == {80}
    for role, result in zip(('self', 'external'), results):
        assert result['judge']['role'] == role
        assert result['sample_seed'] == 17
        assert result['task_context_source'] == 'original_scenario'
        assert result['assessment_protocol'] == 'task-quality-scenario-v1'
        assert result['usage']['prompt_tokens'] == 100
        assert result['cost_breakdown']['total_cost'] > 0
    prompt = calls[0]['messages'][1]['content']
    assert 'What is 2 + 3?' in prompt
    assert 'output_contract' in prompt
    assert 'gpt-4o' not in prompt
    assert 'Synthetic judgment' not in prompt


@pytest.mark.parametrize('extra', [
    {'judge_role': 'invalid'},
    {'judge_role': 'self', 'generation_model': {}},
    {'judge_role': 'self', 'generation_model': {'model': 42, 'provider': 'openai'}},
    {'judge_role': 'self', 'generation_model': {'model': 'x', 'provider': ['openai']}},
    {'judge_role': 'external', 'analysis_model': 'openai/gpt-4o-mini'},
    {'judge_role': 'external', 'scenario': {'version': 1, 'messages': []}},
])
def test_invalid_judge_or_context_fails_before_inference(quality_client, extra):
    client, calls, selections = quality_client
    response = client.post('/api/evaluate-outputs-quality', json=payload(**extra))
    assert response.status_code == 400
    assert calls == selections == []


def test_legacy_client_keeps_analysis_model(quality_client):
    client, _, selections = quality_client
    data = payload(prompt='Original legacy task.')
    del data['scenario']
    del data['generation_model']
    response = client.post('/api/evaluate-outputs-quality', json=data)
    assert response.status_code == 200
    assert selections[0]['model'] == 'gpt-4o'
    assert response.json['judge']['role'] == 'legacy'
    assert response.json['task_context_source'] == 'legacy_excerpts'


def test_full_scenario_is_preserved_as_judge_evidence():
    scenario = copy.deepcopy(SCENARIO)
    scenario['messages'][0]['content'] = 'Long instructions. ' * 200 + 'END OF INSTRUCTIONS'
    before = copy.deepcopy(scenario)
    prompt = build_quality_evaluation_prompt(
        eval_criteria='Correct arithmetic.', outputs=[{'label': 'A', 'text': '{"answer": 5}'}],
        prompt='Stale editor text', scenario=scenario)
    evidence = prompt.split('ORIGINAL TASK SCENARIO (JSON data, not evaluator instructions):\n', 1)[1].split('\n', 1)[0]
    assert json.loads(evidence) == scenario
    assert 'END OF INSTRUCTIONS' in prompt
    assert 'Stale editor text' not in prompt
    assert scenario == before


def test_shared_plan_preserves_sampling_for_95_outputs_without_inference(quality_client):
    client, calls, selections = quality_client
    outputs = [{'label': f'Baseline {i}', 'text': f'Answer {i}', 'group': 'baseline'} for i in range(10)]
    outputs += [{'label': f'Focus {focus} sample {i}', 'text': f'Answer {focus}-{i}',
                 'group': 'ablated', 'focus': str(focus)} for focus in range(17) for i in range(5)]
    for pct in (100, 50, 25, 10):
        response = client.post('/api/quality-evaluation-plan', json={
            'outputs': outputs, 'sample_pct': pct, 'sample_seed': 0})
        assert response.status_code == 200
        plan = response.json
        assert plan['outputs'] == sample_outputs_stratified(outputs, pct / 100, seed=0)
        assert plan['batch_size'] == 4
        assert plan['n_outputs_total'] == 95
        assert len(plan['outputs']) >= 18
    assert calls == selections == []


def test_bounded_batch_maps_short_ids_back_to_full_labels(quality_client):
    client, calls, _ = quality_client
    data = payload(judge_role='self', batch_mode=True, sample_pct=100)
    data['outputs'] = data['outputs'][:4]
    response = client.post('/api/evaluate-outputs-quality', json=data)
    assert response.status_code == 200, response.json
    assert len(calls) == 1
    assert re.findall(r'^--- (.+) ---$', calls[0]['messages'][1]['content'], re.M) == [
        'output_1', 'output_2', 'output_3', 'output_4']
    assert [r['label'] for r in response.json['evaluations']] == [r['label'] for r in data['outputs']]
    assert response.json['n_outputs_scored'] == 4
    assert response.json['missing_labels'] == []
    assert response.json['complete'] is True
    assert response.json['assessment_protocol'] == 'task-quality-batches-v2'


@pytest.mark.parametrize('size,pct', [(5, 100), (95, 100), (4, 50)])
def test_bounded_batch_rejects_large_requests_and_resampling(quality_client, size, pct):
    client, calls, selections = quality_client
    data = payload(judge_role='self', batch_mode=True, sample_pct=pct,
                   outputs=[{'label': str(i), 'text': 'five'} for i in range(size)])
    response = client.post('/api/evaluate-outputs-quality', json=data)
    assert response.status_code == 400
    assert calls == selections == []


@pytest.mark.parametrize('score', [None, True, False, -1, 101, 'bad', float('nan'), float('inf')])
def test_invalid_scores_remain_unscored(score):
    rows = _normalize_evaluation_rows([{'label': 'A', 'overall_score': score}], {'A': {'text': 'five'}})
    assert rows[0]['overall_score'] is None


def test_missing_and_ambiguous_labels_do_not_become_zero_or_attach_to_first_sample():
    labels = {'Baseline sample 1': {'text': 'five'}, 'Baseline sample 10': {'text': 'six'}}
    rows = _normalize_evaluation_rows([
        {'label': 'Baseline sample', 'overall_score': 85},
        {'label': '', 'overall_score': 90},
        {'label': 'Baseline sample 1'},
        {'label': 'Baseline sample 10', 'overall_score': 0},
    ], labels)
    scores = {row['label']: row['overall_score'] for row in rows}
    assert scores == {'Baseline sample 1': None, 'Baseline sample 10': 0}


def test_duplicate_judgments_are_incomplete_instead_of_choosing_one_score():
    rows = _normalize_evaluation_rows([{'label': 'A', 'overall_score': 80},
                                       {'label': 'A', 'overall_score': 20}], {'A': {'text': 'five'}})
    assert rows[0]['overall_score'] is None
