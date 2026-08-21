"""SSE orchestration for batch analysis with mocked inference."""

from __future__ import annotations

import json
from unittest.mock import Mock

import numpy as np
import pytest

from services.batch_analysis_service import BatchAnalysisService
from services.checkpoint_service import CheckpointService
from services.embedding_service import EmbeddingService
from utils.data_processing import calculate_statistics_from_results


PROMPT = (
    "You are a veterinary triage assistant.\n\n"
    "Always cite the source of any medical claim."
)
FOCI = [
    {'focus': 'Role', 'prompt_section': 'You are a veterinary triage assistant.'},
    {'focus': 'Cite', 'prompt_section': 'Always cite the source of any medical claim.'},
]


@pytest.fixture
def mock_provider():
    provider = Mock()
    provider.chat_completion.return_value = {
        'content': 'ok',
        'usage': {'prompt_tokens': 5, 'completion_tokens': 3},
    }
    return provider


@pytest.fixture
def mock_embeddings():
    service = Mock(spec=EmbeddingService)

    def _batch(texts):
        return [np.ones(8) for _ in texts], len(texts)

    service.batch_embeddings_with_usage.side_effect = _batch
    return service


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr('services.batch_analysis_service.time.sleep', lambda *_a, **_k: None)
    monkeypatch.setattr('services.ablation_service.time.sleep', lambda *_a, **_k: None)


def _parse_events(chunks):
    events = []
    for chunk in chunks:
        for block in chunk.strip().split('\n\n'):
            line = block.strip()
            if line.startswith('data: '):
                events.append(json.loads(line[6:]))
    return events


def test_stream_progress_pair_complete_and_aggregates(mock_provider, mock_embeddings, tmp_path, monkeypatch):
    monkeypatch.setenv('CHECKPOINT_DIR', str(tmp_path))
    # CheckpointService may use a fixed dir — inject instance
    checkpoints = CheckpointService()
    if hasattr(checkpoints, 'checkpoint_dir'):
        checkpoints.checkpoint_dir = str(tmp_path)
    elif hasattr(checkpoints, 'base_dir'):
        checkpoints.base_dir = str(tmp_path)

    svc = BatchAnalysisService(
        mock_provider, 'gpt-4o-mini', 'k',
        embedding_service=mock_embeddings,
        checkpoint_service=checkpoints,
        provider_name='openai',
        max_workers=1,
    )
    pairs = [
        {'prompt': PROMPT, 'output': 'o1'},
        {'prompt': PROMPT + '\n\nExtra.', 'output': 'o2'},
    ]
    events = _parse_events(list(
        svc.stream_batch_analysis(
            pairs, FOCI, n_baseline=2, n_ablated=2, session_id='sse-test-1'
        )
    ))
    types = [e.get('type') for e in events]
    assert 'progress' in types
    assert types.count('pair_result') == 2
    assert 'complete' in types
    complete = next(e for e in events if e['type'] == 'complete')
    assert complete['completed'] == 2
    assert complete['total_pairs'] == 2
    assert len(complete['pair_results']) == 2
    direct = calculate_statistics_from_results(complete['pair_results'])
    assert complete['statistics'] == direct
    # checkpoint written
    loaded = checkpoints.load_checkpoint('sse-test-1', 'batch_analysis')
    assert loaded is not None
    assert loaded.get('complete') is True


def test_stream_resume_skips_completed(mock_provider, mock_embeddings, tmp_path, monkeypatch):
    monkeypatch.setenv('CHECKPOINT_DIR', str(tmp_path))
    checkpoints = CheckpointService()
    if hasattr(checkpoints, 'checkpoint_dir'):
        checkpoints.checkpoint_dir = str(tmp_path)
    elif hasattr(checkpoints, 'base_dir'):
        checkpoints.base_dir = str(tmp_path)

    svc = BatchAnalysisService(
        mock_provider, 'gpt-4o-mini', 'k',
        embedding_service=mock_embeddings,
        checkpoint_service=checkpoints,
        max_workers=1,
    )
    pairs = [
        {'prompt': PROMPT, 'output': 'o1'},
        {'prompt': PROMPT + '\n\nExtra.', 'output': 'o2'},
    ]
    list(svc.stream_batch_analysis(pairs[:1], FOCI, n_baseline=1, n_ablated=1, session_id='resume-1'))
    mock_provider.chat_completion.reset_mock()
    events = _parse_events(list(
        svc.stream_batch_analysis(
            pairs, FOCI, n_baseline=1, n_ablated=1,
            session_id='resume-1', resume=True,
        )
    ))
    assert any(e.get('type') == 'resume' for e in events)
    # Second pair only should generate new LLM calls (baseline + 2 foci)
    # With resume, pair 0 skipped.
    assert mock_provider.chat_completion.call_count > 0
    complete = next(e for e in events if e['type'] == 'complete')
    assert complete['total_pairs'] == 2
    successes = [r for r in complete['pair_results'] if r.get('success')]
    assert len(successes) == 2


def test_stream_pair_failure_does_not_corrupt_stats(mock_provider, mock_embeddings, monkeypatch):
    svc = BatchAnalysisService(
        mock_provider, 'gpt-4o-mini', 'k',
        embedding_service=mock_embeddings,
        max_workers=1,
    )

    real = svc.process_single_pair

    def flaky(pair_data, pair_idx, *args, **kwargs):
        if pair_idx == 1:
            return {'success': False, 'pair_index': 1, 'error': 'boom'}
        return real(pair_data, pair_idx, *args, **kwargs)

    monkeypatch.setattr(svc, 'process_single_pair', flaky)
    pairs = [
        {'prompt': PROMPT, 'output': 'o1'},
        {'prompt': PROMPT, 'output': 'o2'},
        {'prompt': PROMPT + '\n\nZ', 'output': 'o3'},
    ]
    events = _parse_events(list(
        svc.stream_batch_analysis(pairs, FOCI, n_baseline=1, n_ablated=1)
    ))
    assert any(e.get('type') == 'error' and e.get('pair_index') == 1 for e in events)
    complete = next(e for e in events if e['type'] == 'complete')
    ok = [r for r in complete['pair_results'] if r.get('success')]
    assert len(ok) == 2
    stats = complete['statistics']
    assert stats  # aggregates only successful pairs
    assert calculate_statistics_from_results(complete['pair_results']) == stats
