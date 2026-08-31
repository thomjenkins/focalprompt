"""Subtractive ablation in BatchAnalysisService."""

import json
import numpy as np
import pytest
from unittest.mock import Mock

from services.batch_analysis_service import BatchAnalysisService
from services.embedding_service import EmbeddingService
from utils.prompt_builder import build_prompt_with_dynamic_foci
from utils.span_alignment import align_quote, delete_span


PROMPT = (
    "You are a veterinary triage assistant.\n\n"
    "Always cite the source of any medical claim."
)


def _foci():
    return [
        {'focus': 'Role', 'prompt_section': 'You are a veterinary triage assistant.', 'is_dynamic': False},
        {'focus': 'Cite', 'prompt_section': 'Always cite the source of any medical claim.', 'is_dynamic': False},
    ]


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
def batch_service(mock_provider, mock_embedding_service):
    return BatchAnalysisService(
        mock_provider,
        'gpt-4o-mini',
        'test-key',
        embedding_service=mock_embedding_service,
        max_workers=1,
    )


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr('services.batch_analysis_service.time.sleep', lambda *_a, **_k: None)


def _user_contents(mock_provider):
    return [
        call.kwargs['messages'][0]['content']
        for call in mock_provider.chat_completion.call_args_list
    ]


def test_process_single_pair_strict_subset(batch_service, mock_provider):
    pair = {'prompt': PROMPT, 'output': 'out'}
    result = batch_service.process_single_pair(
        pair, 0, _foci(), n_baseline=2, n_ablated=2
    )
    assert result['success'] is True
    assert 'chat_content_influence' not in result
    assert len(result['influence_scores']) == 2
    for row in result['ablation_results']:
        start, end = row['char_start'], row['char_end']
        raw = PROMPT[:start] + PROMPT[end:]
        ablated, _, collapsed = delete_span(PROMPT, start, end)
        assert set(row['ablated_prompt']) <= set(PROMPT)
        if collapsed:
            assert row['ablated_prompt'] == ablated
        else:
            assert row['ablated_prompt'] == raw
            assert row['ablated_prompt'] == PROMPT[:start] + PROMPT[end:]

    builder = build_prompt_with_dynamic_foci(
        [{'focus': f['focus'], 'weight': 1.0, 'prompt_section': f['prompt_section']} for f in _foci()],
        _foci(),
        {'chat_content': 'should not appear'},
        0.5,
    )
    for content in _user_contents(mock_provider):
        assert content != builder
        assert '## Primary Instructions' not in content
        assert '## Current Chat Context' not in content


def test_process_single_pair_dynamic_no_llm(batch_service, mock_provider):
    foci = [
        {'focus': 'Role', 'prompt_section': 'You are a veterinary triage assistant.'},
        {
            'focus': 'Chat',
            'prompt_section': 'Always cite the source of any medical claim.',
            'is_dynamic': True,
            'dynamic_type': 'chat',
        },
    ]
    pair = {'prompt': PROMPT, 'output': 'out'}
    result = batch_service.process_single_pair(pair, 0, foci, n_baseline=2, n_ablated=2)
    assert 'Chat' not in result['influence_scores']
    dyn = [r for r in result['ablation_results'] if r['focus'] == 'Chat'][0]
    assert dyn['reason'] == 'dynamic_slot'
    contents = _user_contents(mock_provider)
    # 2 baseline + 2 role ablation
    assert len(contents) == 4
    assert contents.count(PROMPT) == 2
    start, end = align_quote(PROMPT, 'You are a veterinary triage assistant.')
    ablated, _, _ = delete_span(PROMPT, start, end)
    assert contents.count(ablated) == 2


def test_process_single_pair_unverified_and_overlap(batch_service):
    prompt = "The quick brown fox jumps."
    pair = {'prompt': prompt, 'output': 'o'}
    foci = [
        {'focus': 'A', 'prompt_section': 'The quick brown fox'},
        {'focus': 'B', 'prompt_section': 'brown fox jumps.'},
        {'focus': 'Nope', 'prompt_section': 'not present'},
    ]
    result = batch_service.process_single_pair(pair, 0, foci, n_baseline=2, n_ablated=2)
    reasons = {r['focus']: r.get('reason') for r in result['ablation_results']}
    assert reasons['Nope'] == 'unverified'
    # Overlapping A/B remain attributable and contribute scores
    assert 'A' in result['influence_scores'] or any(
        r.get('focus') == 'A' and r.get('attributable') for r in result['ablation_results']
    )
    assert reasons.get('A') in (None, 'overlap')  # reason should be None when attributable
    a_row = next(r for r in result['ablation_results'] if r['focus'] == 'A')
    assert a_row['attributable'] is True
    assert a_row.get('has_overlap') is True


def test_stream_uses_same_pair_prompt(batch_service, mock_provider):
    chat = "My dog is coughing."
    pair_prompt = PROMPT + "\n\n" + chat
    pairs = [{'prompt': pair_prompt, 'output': 'o', 'inputs': {'chat_content': chat}}]
    events = list(
        batch_service.stream_batch_analysis(
            pairs, _foci(), n_baseline=2, n_ablated=2
        )
    )
    assert any('"type": "complete"' in e or "'type': 'complete'" in e or '"complete"' in e for e in events)
    contents = _user_contents(mock_provider)
    # Noise samples + pair baseline must use pair_prompt, never chat-stripped / blank-stripped
    stripped = pair_prompt.replace(chat, '').strip()
    stripped = '\n'.join([line for line in stripped.split('\n') if line.strip()])
    assert stripped not in contents or stripped == pair_prompt
    assert pair_prompt in contents
    for c in contents:
        assert c == pair_prompt or set(c) <= set(pair_prompt)
        assert '## Primary Instructions' not in c
        # Must not be the chat-stripped system-only string if that differs
        if stripped != pair_prompt:
            assert c != stripped


def test_batch_temperature_zero_rejected(batch_service):
    out = batch_service.process_single_pair(
        {'prompt': PROMPT}, 0, _foci(), n_baseline=1, n_ablated=1, temperature=0
    )
    assert out['success'] is False
    assert 'temperature' in out['error'].lower()


def test_batch_bh_denominator_excludes_non_attributable(batch_service, monkeypatch):
    captured = {}

    def capture(p_values, alpha=0.05):
        from utils.permutation_test import benjamini_hochberg as real_bh
        captured['n'] = len(p_values)
        return real_bh(p_values, alpha=alpha)

    monkeypatch.setattr('services.ablation_service.benjamini_hochberg', capture)
    foci = [
        {'focus': 'Role', 'prompt_section': 'You are a veterinary triage assistant.'},
        {
            'focus': 'Chat',
            'prompt_section': 'Always cite the source of any medical claim.',
            'is_dynamic': True,
            'dynamic_type': 'chat',
        },
    ]
    result = batch_service.process_single_pair(
        {'prompt': PROMPT}, 0, foci, n_baseline=2, n_ablated=2
    )
    assert result['success'] is True
    assert captured['n'] == 1


def test_batch_no_embedding_inside_permutation(batch_service, mock_embedding_service, monkeypatch):
    embed_calls = {'n': 0}

    def counting_batch(texts):
        embed_calls['n'] += 1
        import numpy as np
        return [np.ones(8) for _ in texts], len(texts)

    mock_embedding_service.batch_embeddings_with_usage.side_effect = counting_batch

    from utils.permutation_test import permutation_test as real_perm

    def wrapped_perm(*args, **kwargs):
        before = embed_calls['n']
        out = real_perm(*args, **kwargs)
        assert embed_calls['n'] == before
        return out

    monkeypatch.setattr('services.ablation_service.permutation_test', wrapped_perm)
    result = batch_service.process_single_pair(
        {'prompt': PROMPT}, 0, _foci(), n_baseline=2, n_ablated=2, n_permutations=32
    )
    assert result['success'] is True, result.get('error')
    # baseline once + one embedding batch per attributable focus
    assert embed_calls['n'] == 1 + 2


def test_batch_normalized_influence_sums_to_100(batch_service):
    result = batch_service.process_single_pair(
        {'prompt': PROMPT}, 0, _foci(), n_baseline=2, n_ablated=2
    )
    assert result['success'] is True
    total = sum(d['normalized_influence'] for d in result['influence_scores'].values())
    assert abs(total - 100.0) < 1e-6


def test_batch_provider_passed_to_cost(batch_service, monkeypatch):
    seen = {}

    class FakeCost:
        def calculate_cost(self, *args, **kwargs):
            # signature: input, output, embedding, model, provider
            seen['provider'] = args[4] if len(args) >= 5 else kwargs.get('provider')
            return {'total_cost': 0.0}

    batch_service.cost_calculator = FakeCost()
    batch_service.provider_name = 'anthropic'
    events = list(
        batch_service.stream_batch_analysis(
            [{'prompt': PROMPT, 'output': 'o'}], _foci(), n_baseline=1, n_ablated=1
        )
    )
    assert any('"type": "complete"' in e for e in events)
    assert seen.get('provider') == 'anthropic'
