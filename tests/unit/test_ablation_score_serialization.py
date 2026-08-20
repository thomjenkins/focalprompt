"""Ablation sample/score path serialization (no live LLM)."""

import numpy as np
import pytest
from unittest.mock import Mock

from services.ablation_service import AblationService
from services.embedding_service import EmbeddingService


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
def service():
    provider = Mock()
    provider.chat_completion.return_value = {
        'content': 'out',
        'usage': {'prompt_tokens': 1, 'completion_tokens': 1},
    }
    emb = Mock(spec=EmbeddingService)
    emb.batch_embeddings_with_usage.side_effect = lambda texts: (
        [np.ones(4) for _ in texts],
        len(texts),
    )
    return AblationService(provider, 'gpt-4o-mini', embedding_service=emb, provider_name='openai')


def test_score_from_samples_roundtrip(service):
    baseline = ['a', 'b']
    ablated = {0: ['x', 'y'], 1: ['p', 'q']}
    result = service.score_from_samples(
        PROMPT, _foci(), baseline, ablated, n_permutations=50, permutation_seed=0, temperature=0.7
    )
    assert result['n_baseline'] == 2
    assert result['n_ablated'] == 2
    assert result['significance_method'] == 'permutation_bh'
    assert len(result['influence_scores']) == 2
    for item in result['influence_scores']:
        assert 'q_value' in item
        assert 'is_significant' in item
        assert 't_obs' in item
