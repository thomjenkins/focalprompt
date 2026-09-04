from utils.request_inference import request_inference_fields


def test_request_inference_fields_prefers_analysis_model_for_analysis_role():
    fields = request_inference_fields(
        {
            'provider': 'openai',
            'model': 'gpt-3.5-turbo',
            'analysis_provider': 'openai',
            'analysis_model': 'gpt-4o',
            'mut_provider': 'openai',
            'mut_model': 'gpt-3.5-turbo',
        },
        model_role='analysis',
    )

    assert fields['provider'] == 'openai'
    assert fields['model'] == 'gpt-4o'
    assert fields['model_role'] == 'analysis'


def test_request_inference_fields_prefers_mut_model_for_mut_role():
    fields = request_inference_fields(
        {
            'provider': 'openai',
            'model': 'gpt-4o',
            'analysis_provider': 'openai',
            'analysis_model': 'gpt-4o',
            'mut_provider': 'openai',
            'mut_model': 'gpt-3.5-turbo',
        },
        model_role='mut',
    )

    assert fields['provider'] == 'openai'
    assert fields['model'] == 'gpt-3.5-turbo'
    assert fields['model_role'] == 'mut'


def test_request_inference_fields_keeps_legacy_model_without_role():
    fields = request_inference_fields(
        {
            'provider': 'openai',
            'model': 'gpt-4o-mini',
            'analysis_provider': 'openai',
            'analysis_model': 'gpt-4o',
            'mut_provider': 'openai',
            'mut_model': 'gpt-3.5-turbo',
        }
    )

    assert fields['provider'] == 'openai'
    assert fields['model'] == 'gpt-4o-mini'
    assert 'model_role' not in fields
