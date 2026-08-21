"""Parity: batch pair scoring must match AblationService.score_from_samples."""

from __future__ import annotations

import numpy as np
import pytest
from unittest.mock import Mock

from services.ablation_service import AblationService
from services.batch_analysis_service import BatchAnalysisService
from services.embedding_service import EmbeddingService


PROMPT = (
    "You are a veterinary triage assistant.\n\n"
    "Always cite the source of any medical claim.\n\n"
    "Respond in JSON with keys: urgency, differentials, next_steps."
)

FOCI = [
    {'focus': 'Role', 'prompt_section': 'You are a veterinary triage assistant.', 'is_dynamic': False},
    {'focus': 'Cite', 'prompt_section': 'Always cite the source of any medical claim.', 'is_dynamic': False},
    {
        'focus': 'JSON',
        'prompt_section': 'Respond in JSON with keys: urgency, differentials, next_steps.',
        'is_dynamic': False,
    },
]

COMPARE_KEYS = (
    't_obs',
    'influence',
    'similarity',
    'p_value',
    'q_value',
    'is_significant',
    'exact',
    'n_permutations',
    'null_mean',
    'null_p95',
    'standardized_effect',
    'null_deciles',
    'normalized_influence',
    'char_start',
    'char_end',
    'attributable',
)


@pytest.fixture
def mock_provider():
    provider = Mock()
    provider.chat_completion.return_value = {
        'content': 'shared completion',
        'usage': {'prompt_tokens': 3, 'completion_tokens': 2},
    }
    return provider


@pytest.fixture
def deterministic_embeddings():
    service = Mock(spec=EmbeddingService)

    def _vec(text: str) -> np.ndarray:
        rng = np.random.default_rng(abs(hash(text)) % (2**32))
        v = rng.normal(size=16)
        return v / (np.linalg.norm(v) + 1e-12)

    def _batch(texts):
        return [_vec(t) for t in texts], len(texts)

    service.batch_embeddings_with_usage.side_effect = _batch
    service.get_embedding_with_usage.side_effect = lambda t: (_vec(t), 1)
    return service


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr('services.ablation_service.time.sleep', lambda *_a, **_k: None)
    monkeypatch.setattr('services.batch_analysis_service.time.sleep', lambda *_a, **_k: None)


def _fixed_samples():
    baseline = ['baseline-a', 'baseline-b']
    ablated = {
        0: ['role-a', 'role-b'],
        1: ['cite-a', 'cite-b'],
        2: ['json-a', 'json-b'],
    }
    return baseline, ablated


def test_score_from_samples_normalized_sums_to_100(mock_provider, deterministic_embeddings):
    baseline, ablated = _fixed_samples()
    svc = AblationService(
        mock_provider, 'gpt-4o-mini', 'k', deterministic_embeddings, provider_name='openai'
    )
    scored = svc.score_from_samples(
        PROMPT, FOCI, baseline, ablated,
        n_permutations=64, permutation_seed=7, temperature=0.7,
    )
    norms = [item['normalized_influence'] for item in scored['influence_scores']]
    assert norms
    assert abs(sum(norms) - 100.0) < 1e-6


def test_batch_pair_matches_score_from_samples(mock_provider, deterministic_embeddings, monkeypatch):
    baseline, ablated = _fixed_samples()
    seed = 11
    n_perm = 128

    ablation = AblationService(
        mock_provider, 'gpt-4o-mini', 'k', deterministic_embeddings, provider_name='anthropic'
    )
    standalone = ablation.score_from_samples(
        PROMPT, FOCI, baseline, ablated,
        n_permutations=n_perm, alpha=0.05, permutation_seed=seed, temperature=0.7,
    )

    batch = BatchAnalysisService(
        mock_provider, 'gpt-4o-mini', 'k',
        embedding_service=deterministic_embeddings,
        provider_name='anthropic',
        max_workers=1,
    )

    calls = {'n': 0}

    def fake_sample(prompt, n, temperature):
        calls['n'] += 1
        if calls['n'] == 1:
            return list(baseline), 1, 1
        focus_idx = calls['n'] - 2
        return list(ablated[focus_idx]), 1, 1

    monkeypatch.setattr(batch, '_sample_outputs', fake_sample)

    pair = batch.process_single_pair(
        {'prompt': PROMPT, 'output': 'x'},
        pair_idx=0,
        foci_list=FOCI,
        n_baseline=2,
        n_ablated=2,
        n_permutations=n_perm,
        alpha=0.05,
        permutation_seed=seed,
        temperature=0.7,
    )
    assert pair['success'] is True

    standalone_by = {item['focus']: item for item in standalone['influence_scores']}
    batch_by = pair['influence_scores']
    assert set(standalone_by) == set(batch_by)

    for name in standalone_by:
        left, right = standalone_by[name], batch_by[name]
        for key in COMPARE_KEYS:
            lv, rv = left[key], right[key]
            if isinstance(lv, (float, np.floating)):
                assert rv == pytest.approx(float(lv), rel=0, abs=1e-12), (name, key, lv, rv)
            else:
                assert rv == lv, (name, key, lv, rv)

    assert abs(sum(v['normalized_influence'] for v in batch_by.values()) - 100.0) < 1e-6


def test_exclusion_parity_dynamic_unverified(mock_provider, deterministic_embeddings):
    prompt = "Alpha instructions here. Beta instructions here."
    foci = [
        {'focus': 'Alpha', 'prompt_section': 'Alpha instructions here.', 'is_dynamic': False},
        {
            'focus': 'Dyn',
            'prompt_section': 'Beta instructions here.',
            'is_dynamic': True,
            'dynamic_type': 'chat',
        },
        {'focus': 'Ghost', 'prompt_section': 'not in the prompt', 'is_dynamic': False},
    ]
    ablation = AblationService(mock_provider, 'gpt-4o-mini', 'k', deterministic_embeddings)
    scored = ablation.score_from_samples(
        prompt, foci, ['b1', 'b2'], {0: ['a1', 'a2']},
        n_permutations=32, permutation_seed=1, temperature=0.5,
    )
    assert [x['focus'] for x in scored['influence_scores']] == ['Alpha']
    reasons = {r['focus']: r['reason'] for r in scored['ablation_results']}
    assert reasons['Dyn'] == 'dynamic_slot'
    assert reasons['Ghost'] == 'unverified'

    batch = BatchAnalysisService(
        mock_provider, 'gpt-4o-mini', 'k',
        embedding_service=deterministic_embeddings, max_workers=1,
    )
    pair = batch.process_single_pair(
        {'prompt': prompt}, 0, foci, n_baseline=2, n_ablated=2,
        n_permutations=32, permutation_seed=1, temperature=0.5,
    )
    assert set(pair['influence_scores']) == {'Alpha'}
    reasons_b = {r['focus']: r['reason'] for r in pair['ablation_results']}
    assert reasons_b['Dyn'] == 'dynamic_slot'
    assert reasons_b['Ghost'] == 'unverified'


def test_whole_prompt_deletion_parity(mock_provider, deterministic_embeddings):
    prompt = "Only one focus span covering everything here."
    foci = [{'focus': 'All', 'prompt_section': prompt, 'is_dynamic': False}]
    ablation = AblationService(mock_provider, 'gpt-4o-mini', 'k', deterministic_embeddings)
    scored = ablation.score_from_samples(
        prompt, foci, ['b1', 'b2'], {0: ['empty-a', 'empty-b']},
        n_permutations=16, permutation_seed=3, temperature=0.4,
    )
    assert scored['influence_scores'][0]['prompt_empty'] is True
    assert scored['influence_scores'][0]['normalized_influence'] == pytest.approx(100.0)

    batch = BatchAnalysisService(
        mock_provider, 'gpt-4o-mini', 'k',
        embedding_service=deterministic_embeddings, max_workers=1,
    )
    pair = batch.process_single_pair(
        {'prompt': prompt}, 0, foci, n_baseline=2, n_ablated=2,
        n_permutations=16, permutation_seed=3, temperature=0.4,
    )
    assert pair['influence_scores']['All']['prompt_empty'] is True
    assert pair['influence_scores']['All']['normalized_influence'] == pytest.approx(100.0)
