"""Scenario-preserving optimization behavior."""

import json
from unittest.mock import Mock

from services.optimization_service import OptimizationService


def test_optimizer_rewrites_each_analyse_message_and_preserves_retained_contract():
    provider = Mock()
    provider.chat_completion.return_value = {
        'content': json.dumps({
            'summary': 'ok',
            'recommendations': [],
            'suggested_prompt_structure': {},
            'key_insights': [],
            'data_quality_assessment': {},
            'optimized_prompt': 'legacy projection',
            'optimized_messages': {
                'system-rules': 'Optimized system rules',
                'developer-rules': 'Optimized developer rules',
            },
        }),
        'usage': {'prompt_tokens': 10, 'completion_tokens': 5},
    }
    scenario = {
        'version': 1,
        'messages': [
            {
                'id': 'system-rules', 'role': 'system', 'content': 'System rules',
                'analysis_mode': 'analyse',
            },
            {
                'id': 'developer-rules', 'role': 'developer', 'content': 'Developer rules',
                'analysis_mode': 'analyse',
            },
            {
                'id': 'question', 'role': 'user', 'content': 'template',
                'analysis_mode': 'retain', 'input_name': 'question',
            },
        ],
        'output_contract': {
            'type': 'json_schema', 'name': 'answer', 'strict': True,
            'schema': {'type': 'string'},
        },
    }

    result = OptimizationService(provider, 'analysis-model').analyze_scenario_optimization(
        [], {}, {}, [], [], scenario
    )

    optimized = result['optimized_scenario']
    assert [message['content'] for message in optimized['messages']] == [
        'Optimized system rules', 'Optimized developer rules', 'template'
    ]
    assert optimized['messages'][2] == scenario['messages'][2]
    assert optimized['output_contract'] == scenario['output_contract']
    request_text = provider.chat_completion.call_args.kwargs['messages'][1]['content']
    assert '"system-rules"' in request_text
    assert '"developer-rules"' in request_text
