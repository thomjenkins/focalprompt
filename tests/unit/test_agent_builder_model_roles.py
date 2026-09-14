import json
from unittest.mock import Mock

from flask import Flask

from routes.agent_routes import agent_bp
from services.agent_builder_service import AgentBuilderService


class StubProvider:
    """Replays queued responses in call order and records every request."""

    provider_name = 'openai'

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def chat_completion(self, **kwargs):
        self.calls.append(kwargs)
        if not self.responses:
            raise AssertionError('unexpected extra chat_completion call')
        return self.responses.pop(0)


def _assessment_response(foci_weights, chat_weight=0.2):
    return {
        'content': json.dumps({
            'foci_weights': foci_weights,
            'chat_weight': chat_weight,
            'chat_weight_explanation': 'because',
        }),
        'usage': {'prompt_tokens': 10, 'completion_tokens': 4},
    }


CONTRACT = {
    'type': 'json_schema', 'name': 'answer', 'strict': True,
    'schema': {
        'type': 'object',
        'properties': {'answer': {'type': 'string'}},
        'required': ['answer'],
        'additionalProperties': False,
    },
}


def _scenario(input_name='customer_message'):
    return {
        'version': 1,
        'messages': [
            {
                'id': 'rules', 'role': 'system',
                'content': 'Rule A.\n\nRule B.', 'analysis_mode': 'analyse',
            },
            {
                'id': 'question', 'role': 'user', 'content': 'template',
                'analysis_mode': 'retain', 'input_name': input_name,
            },
        ],
        'output_contract': CONTRACT,
    }


def _span_foci(names=('A', 'B')):
    """Raw scenario foci: exact spans only, no prompt_section."""
    return [
        {
            'focus': names[0],
            'spans': [{'message_id': 'rules', 'char_start': 0, 'char_end': 7}],
        },
        {
            'focus': names[1],
            'spans': [{'message_id': 'rules', 'char_start': 9, 'char_end': 16}],
        },
    ]


def test_agent_builder_generates_with_mut_model_provider():
    analysis_provider = Mock()
    mut_provider = Mock()
    mut_provider.chat_completion.return_value = {'content': 'generated reply'}
    service = AgentBuilderService(
        analysis_provider,
        'gpt-4o',
        provider_name='openai',
        generation_provider=mut_provider,
        generation_model='gpt-3.5-turbo',
        generation_provider_name='openai',
    )

    output = service.generate_agent_response('Prompt', temperature=0.4)

    assert output == 'generated reply'
    analysis_provider.chat_completion.assert_not_called()
    assert mut_provider.chat_completion.call_args.kwargs['model'] == 'gpt-3.5-turbo'
    assert mut_provider.chat_completion.call_args.kwargs['temperature'] == 0.4


def test_scenario_agent_assessment_sees_span_evidence_and_keeps_contract():
    provider = StubProvider([
        _assessment_response([
            {'focus': 'A', 'weight': 0.8, 'explanation': 'needed'},
            {'focus': 'B', 'weight': 0.05, 'explanation': 'unrelated'},
        ], chat_weight=0.15),
        {'content': '{"answer":"ok"}', 'usage': {'prompt_tokens': 2, 'completion_tokens': 1}},
    ])
    service = AgentBuilderService(provider, 'gpt-4o', provider_name='openai')
    scenario = _scenario()

    result = service.process_single_agent_pair(
        {'inputs': {'customer_message': 'My dog is due'}, 'output': 'expected'},
        0,
        _span_foci(),
        scenario,
    )

    assert result['success'] is True
    # The relevance prompt must carry each focus's exact source text, which only
    # the canonical (span-grounded) form supplies.
    assessment_prompt = provider.calls[0]['messages'][1]['content']
    assert 'Content: Rule A.' in assessment_prompt
    assert 'Content: Rule B.' in assessment_prompt
    assert 'My dog is due' in assessment_prompt
    assert [fw['focus_index'] for fw in result['foci_weights']] == [0, 1]

    built = result['constructed_scenario']
    assert built['messages'][0]['content'] == 'Rule A.'
    assert built['messages'][1]['content'] == 'My dog is due'
    assert built['output_contract'] == CONTRACT
    assert result['parsed_output'] == {'answer': 'ok'}
    assert 'constructed_prompt' not in result
    assert provider.calls[1]['messages'] == [
        {'role': 'system', 'content': 'Rule A.'},
        {'role': 'user', 'content': 'My dog is due'},
    ]


def test_scenario_agent_pair_binds_structured_input_value():
    provider = StubProvider([
        _assessment_response([{'focus': 'A', 'weight': 0.9}, {'focus': 'B', 'weight': 0.0}]),
        {'content': '{"answer":"ok"}', 'usage': {'prompt_tokens': 2, 'completion_tokens': 1}},
    ])
    service = AgentBuilderService(provider, 'gpt-4o', provider_name='openai')

    result = service.process_single_agent_pair(
        {'inputs': {'chat_content': {'question': 'Hi'}}, 'output': 'expected'},
        3,
        _span_foci(),
        _scenario(input_name='chat_content'),
    )

    assert result['success'] is True, result.get('error')
    assert provider.calls[1]['messages'][1] == {
        'role': 'user', 'content': '{"question": "Hi"}',
    }
    assert '{"question": "Hi"}' in provider.calls[0]['messages'][1]['content']


def test_repeated_focus_names_are_weighted_by_focus_index():
    scenario = _scenario()
    foci = _span_foci(names=('Policy', 'Policy'))

    built, metadata = AgentBuilderService.build_agent_scenario(
        scenario,
        foci,
        [
            {'focus': 'Policy', 'focus_index': 0, 'weight': 0.9},
            {'focus': 'Policy', 'focus_index': 1, 'weight': 0.0},
        ],
    )

    assert built['messages'][0]['content'] == 'Rule A.'
    assert metadata['selected_focus_indices'] == [0]
    assert metadata['changed_analyse_message_ids'] == ['rules']


def test_legacy_agent_pair_still_builds_prompt_with_chat_content():
    provider = StubProvider([
        _assessment_response([{'focus': 'Greet', 'weight': 0.9}], chat_weight=0.4),
        {'content': 'legacy reply'},
    ])
    service = AgentBuilderService(provider, 'gpt-4o', provider_name='openai')

    result = service.process_single_agent_pair(
        {'inputs': {'chat_content': 'Hello there'}, 'output': 'expected'},
        1,
        [{'focus': 'Greet', 'prompt_section': 'Be friendly.'}],
        None,
    )

    assert result['success'] is True, result.get('error')
    assert '### Greet' in result['constructed_prompt']
    assert 'Be friendly.' in result['constructed_prompt']
    assert 'Hello there' in result['constructed_prompt']
    assert result['generated_output'] == 'legacy reply'
    assert 'constructed_scenario' not in result
    assert provider.calls[1]['messages'] == [
        {'role': 'user', 'content': result['constructed_prompt']},
    ]


def test_build_agent_route_returns_scenario_without_flattening():
    app = Flask(__name__)
    app.register_blueprint(agent_bp)
    client = app.test_client()
    contract = {
        'type': 'json_schema', 'name': 'answer', 'strict': True,
        'schema': {
            'type': 'object',
            'properties': {'answer': {'type': 'string'}},
            'required': ['answer'],
            'additionalProperties': False,
        },
    }
    response = client.post('/api/build-agent-prompt', json={
        'scenario': {
            'version': 1,
            'messages': [
                {
                    'id': 'rules', 'role': 'system', 'content': 'Keep A. Drop B.',
                    'analysis_mode': 'analyse',
                },
                {
                    'id': 'question', 'role': 'user', 'content': 'Current question',
                    'analysis_mode': 'retain', 'input_name': 'question',
                },
            ],
            'output_contract': contract,
        },
        'foci': [
            {
                'focus': 'Keep', 'weight': 0.9,
                'spans': [{
                    'message_id': 'rules', 'char_start': 0, 'char_end': 7,
                    'text_snapshot': 'Keep A.',
                }],
            },
            {
                'focus': 'Drop', 'weight': 0.1,
                'spans': [{
                    'message_id': 'rules', 'char_start': 8, 'char_end': 15,
                    'text_snapshot': 'Drop B.',
                }],
            },
        ],
    })

    assert response.status_code == 200
    payload = response.get_json()
    assert 'constructed_prompt' not in payload
    assert payload['constructed_scenario']['messages'] == [
        {
            'id': 'rules', 'role': 'system', 'content': 'Keep A.',
            'analysis_mode': 'analyse',
        },
        {
            'id': 'question', 'role': 'user', 'content': 'Current question',
            'analysis_mode': 'retain', 'input_name': 'question',
        },
    ]
    assert payload['constructed_scenario']['output_contract'] == contract
