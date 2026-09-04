from unittest.mock import Mock

from flask import Flask

from routes.agent_routes import agent_bp
from services.agent_builder_service import AgentBuilderService


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


def test_scenario_agent_builder_changes_only_analyse_messages_and_keeps_contract():
    provider = Mock()
    provider.chat_completion.return_value = {
        'content': '{"answer":"ok"}',
        'usage': {'prompt_tokens': 2, 'completion_tokens': 1},
    }
    service = AgentBuilderService(provider, 'model', provider_name='openai')
    service.assess_chat_foci = Mock(return_value={
        'foci_weights': [
            {'focus': 'A', 'weight': 0.8},
            {'focus': 'B', 'weight': 0.05},
        ],
        'chat_weight': 0.15,
    })
    scenario = {
        'version': 1,
        'messages': [
            {
                'id': 'rules', 'role': 'system',
                'content': 'Rule A.\n\nRule B.', 'analysis_mode': 'analyse',
            },
            {
                'id': 'question', 'role': 'user', 'content': 'template',
                'analysis_mode': 'retain', 'input_name': 'customer_message',
            },
        ],
        'output_contract': {
            'type': 'json_schema', 'name': 'answer', 'strict': True,
            'schema': {
                'type': 'object',
                'properties': {'answer': {'type': 'string'}},
                'required': ['answer'],
                'additionalProperties': False,
            },
        },
    }
    foci = [
        {
            'focus': 'A',
            'spans': [{
                'message_id': 'rules', 'char_start': 0, 'char_end': 7,
                'text_snapshot': 'Rule A.',
            }],
        },
        {
            'focus': 'B',
            'spans': [{
                'message_id': 'rules', 'char_start': 9, 'char_end': 16,
                'text_snapshot': 'Rule B.',
            }],
        },
    ]

    result = service.process_single_agent_pair(
        {'inputs': {'customer_message': 'My dog is due'}, 'output': 'expected'},
        0,
        foci,
        scenario,
    )

    assert result['success'] is True
    built = result['constructed_scenario']
    assert built['messages'][0]['content'] == 'Rule A.'
    assert built['messages'][1]['content'] == 'My dog is due'
    assert built['output_contract'] == scenario['output_contract']
    assert result['parsed_output'] == {'answer': 'ok'}
    assert provider.chat_completion.call_args.kwargs['messages'] == [
        {'role': 'system', 'content': 'Rule A.'},
        {'role': 'user', 'content': 'My dog is due'},
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
