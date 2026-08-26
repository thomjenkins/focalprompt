"""
Unit tests for subtractive AblationService.
"""

import numpy as np
import pytest
from unittest.mock import Mock

from services.ablation_service import AblationService
from services.embedding_service import EmbeddingService
from utils.prompt_builder import build_prompt_with_dynamic_foci
from utils.span_alignment import align_quote, delete_span


@pytest.fixture
def mock_provider():
    provider = Mock()
    provider.chat_completion.return_value = {
        'content': 'Test output',
        'usage': {'prompt_tokens': 10, 'completion_tokens': 5},
    }
    return provider


@pytest.fixture
def mock_embedding_service():
    service = Mock(spec=EmbeddingService)

    def _one(_text):
        return np.ones(8), 10

    def _batch(texts):
        return [np.ones(8) for _ in texts], len(texts)

    service.get_embedding_with_usage.side_effect = _one
    service.batch_embeddings_with_usage.side_effect = _batch
    return service


@pytest.fixture
def ablation_service(mock_provider, mock_embedding_service):
    return AblationService(
        mock_provider,
        'gpt-4o-mini',
        'test-key',
        mock_embedding_service,
    )


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr('services.ablation_service.time.sleep', lambda *_a, **_k: None)


PROMPT = (
    "You are a veterinary triage assistant.\n\n"
    "Always cite the source of any medical claim.\n\n"
    "Respond in JSON with keys: urgency, differentials, next_steps."
)


def _static_foci():
    return [
        {'focus': 'Role', 'prompt_section': 'You are a veterinary triage assistant.', 'is_dynamic': False},
        {'focus': 'Cite', 'prompt_section': 'Always cite the source of any medical claim.', 'is_dynamic': False},
        {
            'focus': 'JSON',
            'prompt_section': 'Respond in JSON with keys: urgency, differentials, next_steps.',
            'is_dynamic': False,
        },
    ]


def _user_contents(mock_provider):
    return [
        call.kwargs['messages'][0]['content']
        for call in mock_provider.chat_completion.call_args_list
    ]


def _is_original_or_span_delete(text, original):
    if text == original:
        return True
    # Empty remainder is a valid intervention
    if text == '' or not text.strip():
        # Must be reachable by deleting some verified span (possibly the whole prompt)
        return True
    if set(text) <= set(original) and len(text) < len(original):
        # Exact splice or boundary-collapsed splice for some span
        for focus in _static_foci():
            span = align_quote(original, focus['prompt_section'])
            if not span:
                continue
            start, end = span
            raw = original[:start] + original[end:]
            ablated, _, _ = delete_span(original, start, end)
            if text == raw or text == ablated:
                return True
    return False


def test_run_ablation_scores_verified_static_foci(ablation_service, mock_provider):
    result = ablation_service.run_ablation(
        PROMPT, _static_foci(), n_baseline=2, n_ablated=2, permutation_seed=0
    )
    assert 'baseline_output' in result
    assert len(result['baseline_outputs']) == 2
    assert result['baseline_output'] == result['baseline_outputs'][0]
    assert len(result['influence_scores']) == 3
    assert all(item['attributable'] is True for item in result['influence_scores'])
    assert all('ablated_prompt' in item for item in result['influence_scores'])
    assert all(len(item.get('ablated_outputs') or []) == 2 for item in result['influence_scores'])
    for row in result['ablation_results']:
        assert set(row['ablated_prompt']) <= set(PROMPT)
        start, end = row['char_start'], row['char_end']
        raw = PROMPT[:start] + PROMPT[end:]
        ablated, _, collapsed = delete_span(PROMPT, start, end)
        if collapsed:
            assert row['ablated_prompt'] == ablated
            assert row['ablated_prompt'] != raw
        else:
            assert row['ablated_prompt'] == raw
        assert len(row.get('ablated_outputs') or []) == 2

def test_unverified_focus_excluded_no_score(ablation_service, mock_provider):
    foci = [
        {'focus': 'Role', 'prompt_section': 'You are a veterinary triage assistant.'},
        {'focus': 'Hallucinated', 'prompt_section': 'This quote is not in the prompt at all.'},
    ]
    result = ablation_service.run_ablation(PROMPT, foci, n_baseline=2, n_ablated=2)
    flagged = [r for r in result['ablation_results'] if r['focus'] == 'Hallucinated'][0]
    assert flagged['verified'] is False
    assert flagged['attributable'] is False
    assert flagged['reason'] == 'unverified'
    assert 'ablated_output' not in flagged
    assert 'similarity' not in flagged
    names = [s['focus'] for s in result['influence_scores']]
    assert 'Hallucinated' not in names
    assert 'Role' in names


def test_overlap_refused_flagged_no_score(ablation_service):
    prompt = "The quick brown fox jumps."
    foci = [
        {'focus': 'A', 'prompt_section': 'The quick brown fox'},
        {'focus': 'B', 'prompt_section': 'brown fox jumps.'},
    ]
    result = ablation_service.run_ablation(prompt, foci, n_baseline=2, n_ablated=2)
    assert result['influence_scores'] == []
    for row in result['ablation_results']:
        assert row['attributable'] is False
        assert row['reason'] == 'overlap'
        assert row['overlap_with']
        assert 'ablated_output' not in row


def test_sole_focus_empty_remainder_runs_and_flags(ablation_service, mock_provider):
    prompt = "Only this."
    foci = [{'focus': 'All', 'prompt_section': 'Only this.'}]
    result = ablation_service.run_ablation(prompt, foci, n_baseline=2, n_ablated=2)
    row = result['ablation_results'][0]
    assert row['attributable'] is True
    assert row['prompt_empty'] is True
    assert row['ablated_prompt'] == ''
    assert 'ablated_output' in row
    # Empty ablated prompts must not hit the gateway (real providers reject them).
    contents = _user_contents(mock_provider)
    assert contents.count(prompt) == 2  # baseline samples only
    assert '' not in contents


def test_dynamic_focus_no_llm_call(ablation_service, mock_provider):
    foci = [
        {'focus': 'Role', 'prompt_section': 'You are a veterinary triage assistant.'},
        {
            'focus': 'Chat slot',
            'prompt_section': 'Always cite the source of any medical claim.',
            'is_dynamic': True,
            'dynamic_type': 'chat',
        },
    ]
    result = ablation_service.run_ablation(PROMPT, foci, n_baseline=2, n_ablated=2)
    dyn = [r for r in result['ablation_results'] if r['focus'] == 'Chat slot'][0]
    assert dyn['attributable'] is False
    assert dyn['reason'] == 'dynamic_slot'
    assert 'ablated_output' not in dyn
    names = [s['focus'] for s in result['influence_scores']]
    assert 'Chat slot' not in names

    contents = _user_contents(mock_provider)
    # 2 baseline + 2 ablated for the static focus; none for dynamic
    assert len(contents) == 4
    start, end = align_quote(PROMPT, 'You are a veterinary triage assistant.')
    ablated, _, _ = delete_span(PROMPT, start, end)
    assert contents.count(PROMPT) == 2
    assert contents.count(ablated) == 2


def test_no_builder_constructed_prompts(ablation_service, mock_provider):
    result = ablation_service.run_ablation(
        PROMPT, _static_foci(), n_baseline=2, n_ablated=2
    )
    builder_full = build_prompt_with_dynamic_foci(
        [{'focus': f['focus'], 'weight': 1.0, 'prompt_section': f['prompt_section']} for f in _static_foci()],
        _static_foci(),
        {},
        0.5,
    )
    for content in _user_contents(mock_provider):
        assert '## Primary Instructions' not in content
        assert content != builder_full
        assert _is_original_or_span_delete(content, PROMPT)
    for row in result['ablation_results']:
        assert '## Primary Instructions' not in row['ablated_prompt']


def test_temperature_zero_raises(ablation_service):
    with pytest.raises(ValueError, match='temperature must be > 0'):
        ablation_service.run_ablation(
            PROMPT, _static_foci(), n_baseline=1, n_ablated=1, temperature=0
        )


def test_bh_denominator_excludes_non_attributable(ablation_service, monkeypatch):
    seen = []

    def capture(ps, alpha=0.05):
        seen.append(list(ps))
        from utils.permutation_test import benjamini_hochberg as real_bh
        return real_bh(ps, alpha)

    monkeypatch.setattr('services.ablation_service.benjamini_hochberg', capture)
    foci = [
        {'focus': 'Role', 'prompt_section': 'You are a veterinary triage assistant.'},
        {'focus': 'Hallucinated', 'prompt_section': 'not in prompt'},
        {
            'focus': 'Chat',
            'prompt_section': 'Always cite the source of any medical claim.',
            'is_dynamic': True,
            'dynamic_type': 'chat',
        },
        {
            'focus': 'JSON',
            'prompt_section': 'Respond in JSON with keys: urgency, differentials, next_steps.',
        },
    ]
    ablation_service.run_ablation(PROMPT, foci, n_baseline=2, n_ablated=2)
    assert len(seen) == 1
    assert len(seen[0]) == 2


def test_no_generation_or_embedding_inside_permutation(
    ablation_service, mock_provider, mock_embedding_service
):
    ablation_service.run_ablation(PROMPT, _static_foci(), n_baseline=2, n_ablated=2)
    assert mock_provider.chat_completion.call_count == 2 + 2 * 3
    assert mock_embedding_service.batch_embeddings_with_usage.call_count == 1 + 3
    for item in ablation_service.run_ablation(
        PROMPT, _static_foci(), n_baseline=2, n_ablated=2
    )['influence_scores']:
        assert 'p_value' in item
        assert 'q_value' in item
        assert 'is_significant' in item
        assert 'null_deciles' in item


def test_sample_completion_baseline_and_ablated(ablation_service, mock_provider):
    base = ablation_service.sample_completion(PROMPT, _static_foci(), 'baseline', 0.7)
    assert base['content'] == 'Test output'
    ablated = ablation_service.sample_completion(
        PROMPT, _static_foci(), 'ablated', 0.7, focus_index=0
    )
    assert ablated['content'] == 'Test output'
    assert 'You are a veterinary triage assistant.' not in ablated['ablated_prompt']
    with pytest.raises(ValueError, match='cannot be ablated'):
        ablation_service.sample_completion(
            PROMPT,
            [
                {
                    'focus': 'Chat slot',
                    'prompt_section': 'Always cite the source of any medical claim.',
                    'is_dynamic': True,
                    'dynamic_type': 'chat',
                }
            ],
            'ablated',
            0.7,
            focus_index=0,
        )

