from copy import deepcopy
from unittest.mock import Mock

from flask import Flask
import pytest
import requests

from core.gateway_evaluation import EvaluationError, GatewayEvaluation, EVALUATION_URL
from routes.jev_focus_routes import jev_focus_bp
from services.jev_focus_service import compose, order_next, prepare, select
from utils.hosted_mode import path_requires_live


def fixture():
    scenario = {'version': 1, 'messages': [
        {'id': 'rules', 'role': 'developer', 'analysis_mode': 'analyse', 'content': 'Intro. AAA.\nBBB.\nCCC. End.'},
        {'id': 'chat', 'role': 'user', 'analysis_mode': 'retain', 'content': 'How much is 2 + 2?', 'input_name': 'chat'},
        {'id': 'extra', 'role': 'user', 'analysis_mode': 'analyse', 'content': 'DDD.'},
    ], 'output_contract': {'type': 'json_schema', 'name': 'answer', 'strict': True,
                          'schema': {'type': 'object', 'properties': {'answer': {'type': 'string'}},
                                     'required': ['answer'], 'additionalProperties': False}}}
    foci = []
    for word, mid in [('AAA.', 'rules'), ('BBB.', 'rules'), ('CCC.', 'rules'), ('DDD.', 'extra')]:
        content = next(m['content'] for m in scenario['messages'] if m['id'] == mid)
        start = content.index(word)
        foci.append({'focus': word, 'spans': [{'message_id': mid, 'char_start': start,
                                              'char_end': start + len(word), 'text_snapshot': word}]})
    return scenario, foci


def test_exact_composition_reordering_roles_unlabelled_and_contract():
    scenario, foci = fixture()
    original = deepcopy(scenario)
    result = compose(scenario, foci, [0, 2], {'rules': [2, 0]})
    assert result['scenario']['messages'][0]['content'] == 'Intro. CCC.\n\nAAA. End.'
    assert result['scenario']['messages'][1] == scenario['messages'][1]
    assert result['scenario']['output_contract'] == scenario['output_contract']
    assert [m['id'] for m in result['scenario']['messages']] == ['rules', 'chat']
    assert result['deleted_characters'] == 8
    assert scenario == original


def test_no_selection_keeps_unlabelled_content_and_user():
    scenario, foci = fixture()
    result = compose(scenario, foci, [])
    assert result['scenario']['messages'][0]['content'] == 'Intro. \n\n End.'
    assert result['scenario']['messages'][1] == scenario['messages'][1]
    assert compose(scenario, foci, [0, 1, 2, 3])['scenario'] == scenario


def test_overlapping_exclusion_cannot_delete_selected_text_or_move():
    scenario, foci = fixture()
    # Excluding a focus that encompasses two selected foci must not erase either.
    foci.append({'focus': 'envelope', 'spans': [{'message_id': 'rules', 'char_start': 7, 'char_end': 16,
                                               'text_snapshot': 'AAA.\nBBB.'}]})
    result = compose(scenario, foci, [0, 1, 2])
    assert result['scenario']['messages'][0]['content'] == 'Intro. AAA.BBB.\nCCC. End.'
    assert result['shared_text_retained_for_excluded'] == [4]
    assert not result['order_groups']  # only CCC is independent
    with pytest.raises(ValueError, match='movable'):
        compose(scenario, foci, [0, 1, 2], {'rules': [2, 1, 0]})


def test_multispan_keeps_intervening_unlabelled_text_and_is_fixed():
    scenario, foci = fixture()
    foci = [{'focus': 'two parts', 'spans': foci[0]['spans'] + foci[2]['spans']}, foci[1], foci[3]]
    result = compose(scenario, foci, [0])
    assert result['scenario']['messages'][0]['content'] == 'Intro. AAA.\n\nCCC. End.'
    assert not result['order_groups']


@pytest.mark.parametrize('selected,orders', [([0, 0], None), ([True], None), ([99], None),
    ([0, 1], {'rules': [0, 0]}), ([0, 3], {'rules': [3, 0]}), ([0, 1], {'chat': [1, 0]})])
def test_rejects_invalid_or_cross_message_orders(selected, orders):
    with pytest.raises(ValueError):
        compose(*fixture(), selected, orders)


def test_selection_uses_full_context_and_no_outputs_or_budget():
    scenario, foci = fixture()
    foci[1]['focus'] = foci[0]['focus']  # identity is index, never label
    evaluator = Mock()
    evaluator.evaluate.return_value = {'answers': {f'f{i}': {'type': 'boolean', 'probability': p}
                                                  for i, p in enumerate([0.9, 0.1, 0.5, 0])}}
    result = select(evaluator, scenario, foci)
    assert result['selected_indices'] == [0, 2]
    state, questions = evaluator.evaluate.call_args.args
    assert state['scenario'] == scenario
    assert state['retained_user_input'] == [scenario['messages'][1]]
    assert set(questions) == {'f0', 'f1', 'f2', 'f3'}
    assert 'background constraints' in questions['f0']['instructions']
    assert 'no fixed quota' in questions['f0']['instructions']
    assert 'output' not in state


@pytest.mark.parametrize('answers', [{}, {'f0': {'type': 'boolean', 'probability': 1}},
    {f'f{i}': {'type': 'boolean', 'probability': float('nan')} for i in range(4)},
    {f'f{i}': {'type': 'choice', 'probability': 0.5} for i in range(4)}])
def test_missing_malformed_answers_fail_without_fabricated_decisions(answers):
    with pytest.raises(EvaluationError):
        select(Mock(evaluate=Mock(return_value={'answers': answers})), *fixture())


def test_order_choice_sees_selected_catalog_and_prefix():
    evaluator = Mock(evaluate=Mock(return_value={'answers': {'next': {'type': 'choice', 'choice': 'f2',
                                                                    'probabilities': {'f1': .1, 'f2': .9}}}}))
    result = order_next(evaluator, *fixture(), [0, 1, 2, 3], 'rules', [0])
    assert result['focus_index'] == 2
    state, questions = evaluator.evaluate.call_args.args
    assert state['already_ordered'] == ['f0']
    assert set(questions['next']['criteria']) == {'f1', 'f2'}
    evaluator.evaluate.return_value['answers']['next']['choice'] = 'f3'
    with pytest.raises(EvaluationError):
        order_next(evaluator, *fixture(), [0, 1, 2, 3], 'rules', [0])


def test_stale_spans_and_retained_focus_targets_fail_before_inference():
    scenario, foci = fixture()
    foci[0]['spans'][0]['text_snapshot'] = 'changed'
    with pytest.raises(ValueError, match='snapshot'):
        prepare(scenario, foci)
    scenario, foci = fixture()
    foci[0]['spans'][0]['message_id'] = 'chat'
    with pytest.raises(ValueError, match='retained message'):
        prepare(scenario, foci)
    scenario['messages'][1]['analysis_mode'] = 'analyse'
    scenario['messages'][1].pop('input_name')
    with pytest.raises(ValueError, match='retained user'):
        prepare(scenario, foci)


def test_gateway_v4_transport_and_safe_failure(monkeypatch):
    monkeypatch.setenv('AI_GATEWAY_API_KEY', 'test-key')
    post = Mock(return_value=Mock(status_code=200, json=Mock(return_value={'answers': {'q': {'type': 'boolean', 'probability': .7}}, 'headers': {'secret': 'hidden'}})))
    monkeypatch.setattr('core.gateway_evaluation.requests.post', post)
    result = GatewayEvaluation().evaluate({'synthetic': True}, {'q': {'type': 'boolean'}})
    assert 'headers' not in result
    args, kw = post.call_args
    assert args == (EVALUATION_URL,)
    assert kw['headers']['ai-model-id'] == 'typesafe-ai/jev'
    assert kw['headers']['ai-evaluation-model-specification-version'] == '4'
    assert kw['json']['providerOptions']['gateway']['zeroDataRetention'] is True
    assert not {'temperature', 'messages', 'max_tokens'} & kw['json'].keys()
    post.return_value.status_code = 401
    post.return_value.json.return_value = {'error': 'private prompt test-key'}
    with pytest.raises(EvaluationError) as exc:
        GatewayEvaluation().evaluate({}, {})
    assert exc.value.status == 401 and 'private' not in str(exc.value) and 'test-key' not in str(exc.value)
    post.side_effect = requests.Timeout('private prompt')
    with pytest.raises(EvaluationError) as exc:
        GatewayEvaluation().evaluate({}, {})
    assert exc.value.status == 504


def test_routes_validation_guards_and_gateway_error(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(jev_focus_bp)
    client = app.test_client()
    scenario, foci = fixture()
    response = client.post('/api/jev-focus/compose', json={'scenario': scenario, 'foci': foci, 'selected_indices': []})
    assert response.status_code == 200
    monkeypatch.setattr('core.gateway_evaluation.GatewayEvaluation.evaluate', Mock(side_effect=EvaluationError('Rate limited', 429)))
    response = client.post('/api/jev-focus/select', json={'scenario': scenario, 'foci': foci})
    assert response.status_code == 429 and response.json['code'] == 'jev_evaluation_error'
    assert client.post('/api/jev-focus/select', json=['invalid']).status_code == 400
    assert path_requires_live('/api/jev-focus/select')
    assert path_requires_live('/api/jev-focus/order-next')
    assert not path_requires_live('/api/jev-focus/compose')


def test_catalog_keeps_evaluation_models_out_of_chat_picker(monkeypatch):
    from routes.pricing_routes import pricing_bp
    monkeypatch.setenv('AI_GATEWAY_API_KEY', 'test-key')
    monkeypatch.setattr('core.ai_gateway_provider.AIGatewayProvider.list_all_models', lambda _: [
        {'id': 'typesafe-ai/jev', 'type': 'evaluation'}, {'id': 'openai/chat-model', 'type': 'language'}])
    app = Flask(__name__)
    app.register_blueprint(pricing_bp)
    data = app.test_client().get('/api/models').json
    assert set(data['models']) == {'openai'}
    assert data['evaluation_models'][0]['id'] == 'typesafe-ai/jev'
