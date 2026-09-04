from unittest.mock import Mock

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
