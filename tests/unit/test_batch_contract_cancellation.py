"""Fatal inference-contract failures must cancel the rest of their own batch run.

A StructuredOutputError/ProviderCapabilityError invalidates the experiment, so no
queued row may start and an active row must stop before its next paid sample.
Cancellation is scoped to one stream: other runs sharing the executor continue.
"""

from __future__ import annotations

import json
import threading
from unittest.mock import Mock

import numpy as np
import pytest

from services.ablation_service import AblationService
from services.batch_analysis_service import BatchAnalysisService, BatchRunCancelled
from services.embedding_service import EmbeddingService
from utils.inference_scenario import StructuredOutputError


PROMPT = (
    "You are a veterinary triage assistant.\n\n"
    "Always cite the source of any medical claim."
)
FOCI = [
    {'focus': 'Role', 'prompt_section': 'You are a veterinary triage assistant.'},
    {'focus': 'Cite', 'prompt_section': 'Always cite the source of any medical claim.'},
]


def _pair(tag: str) -> dict:
    return {'prompt': f'{PROMPT}\n\n{tag}', 'output': 'answer'}


@pytest.fixture
def mock_embeddings():
    service = Mock(spec=EmbeddingService)

    def _batch(texts):
        return [np.ones(8) for _ in texts], len(texts)

    service.batch_embeddings_with_usage.side_effect = _batch
    return service


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch, tmp_path):
    monkeypatch.setenv('CHECKPOINT_DIR', str(tmp_path))
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


class RecordingProvider:
    """Records every prompt and fails fatally on the nth call."""

    def __init__(self, fail_on_call: int):
        self.fail_on_call = fail_on_call
        self.prompts: list = []
        self._lock = threading.Lock()

    def chat_completion(self, model=None, messages=None, temperature=None, **_kw):
        with self._lock:
            self.prompts.append(messages[0]['content'])
            index = len(self.prompts)
        if index == self.fail_on_call:
            raise StructuredOutputError('provider cannot honour the structured output contract')
        return {'content': f'out-{index}', 'usage': {'prompt_tokens': 5, 'completion_tokens': 3}}


def test_fatal_failure_stops_queued_rows_and_active_sampling(mock_embeddings):
    provider = RecordingProvider(fail_on_call=2)
    svc = BatchAnalysisService(
        provider,
        'gpt-4o-mini',
        'test-key',
        embedding_service=mock_embeddings,
        max_workers=1,
    )
    pairs = [_pair('ROW-0'), _pair('ROW-1'), _pair('ROW-2')]

    stream = svc.stream_batch_analysis(
        pairs, FOCI, n_baseline=4, n_ablated=2, n_permutations=10, session_id='fatal'
    )
    with pytest.raises(StructuredOutputError):
        list(stream)

    # Only the failing row ever reached the gateway, and it stopped at the failure.
    assert len(provider.prompts) == 2
    assert all('ROW-0' in prompt for prompt in provider.prompts)


def test_cancelled_run_stops_active_row_before_next_sample(mock_embeddings):
    """An in-flight row aborts at the next sample boundary once its run is cancelled."""
    cancel_event = threading.Event()
    calls = []

    class CancellingProvider:
        def chat_completion(self, model=None, messages=None, temperature=None, **_kw):
            calls.append(messages[0]['content'])
            # A sibling row's fatal failure cancels the run mid-baseline.
            cancel_event.set()
            return {'content': 'ok', 'usage': {'prompt_tokens': 5, 'completion_tokens': 3}}

    svc = BatchAnalysisService(
        CancellingProvider(),
        'gpt-4o-mini',
        'test-key',
        embedding_service=mock_embeddings,
        max_workers=1,
    )
    result = svc.process_single_pair(
        _pair('ROW-9'),
        9,
        FOCI,
        n_baseline=5,
        n_ablated=3,
        n_permutations=10,
        cancel_event=cancel_event,
    )

    assert result['success'] is False
    assert result['cancelled'] is True
    assert len(calls) == 1


@pytest.mark.parametrize('sampler', ['batch', 'ablation', 'scenario'])
def test_cancellation_during_sample_pacing_prevents_next_call(sampler, monkeypatch, mock_embeddings):
    cancel_event = threading.Event()
    provider = Mock()
    provider.chat_completion.return_value = {
        'content': 'ok', 'usage': {'prompt_tokens': 1, 'completion_tokens': 1},
    }
    if sampler == 'batch':
        service = BatchAnalysisService(
            provider, 'gpt-4o-mini', 'test-key', embedding_service=mock_embeddings,
        )
    else:
        service = AblationService(provider, 'gpt-4o-mini', embedding_service=mock_embeddings)

    def check_cancelled(_index):
        if cancel_event.is_set():
            raise BatchRunCancelled('cancelled')

    monkeypatch.setattr('services.ablation_service.time.sleep', lambda _seconds: cancel_event.set())
    try:
        with pytest.raises(BatchRunCancelled):
            if sampler == 'scenario':
                service._sample_scenario_outputs(
                    {'version': 1, 'messages': [{
                        'id': 'user', 'role': 'user', 'content': 'Hello', 'analysis_mode': 'retain',
                    }]},
                    3, 0.7, before_sample=check_cancelled,
                )
            else:
                service._sample_outputs('Hello', 3, 0.7, before_sample=check_cancelled)
    finally:
        if sampler == 'batch':
            service.executor.shutdown()
    assert provider.chat_completion.call_count == 1


def test_cancellation_does_not_touch_a_concurrent_run(mock_embeddings):
    """Two streams share one executor; only the failing stream is cancelled."""
    b_started = threading.Event()
    b_release = threading.Event()
    lock = threading.Lock()
    a_prompts: list = []
    b_prompts: list = []

    class SharedProvider:
        def chat_completion(self, model=None, messages=None, temperature=None, **_kw):
            content = messages[0]['content']
            if 'RUN-B' in content:
                with lock:
                    b_prompts.append(content)
                    first = len(b_prompts) == 1
                if first:
                    b_started.set()
                    # Hold run B inside a sample until run A has failed.
                    assert b_release.wait(10)
                return {'content': 'b-ok', 'usage': {'prompt_tokens': 5, 'completion_tokens': 3}}
            with lock:
                a_prompts.append(content)
                index = len(a_prompts)
            if index == 2:
                raise StructuredOutputError('provider cannot honour the structured output contract')
            return {'content': 'a-ok', 'usage': {'prompt_tokens': 5, 'completion_tokens': 3}}

    svc = BatchAnalysisService(
        SharedProvider(),
        'gpt-4o-mini',
        'test-key',
        embedding_service=mock_embeddings,
        max_workers=2,
    )

    b_chunks: list = []

    def run_b():
        b_chunks.extend(
            svc.stream_batch_analysis(
                [_pair('RUN-B')],
                FOCI,
                n_baseline=3,
                n_ablated=2,
                n_permutations=10,
                session_id='run-b',
            )
        )

    worker = threading.Thread(target=run_b)
    worker.start()
    try:
        assert b_started.wait(10)
        with pytest.raises(StructuredOutputError):
            list(
                svc.stream_batch_analysis(
                    [_pair('RUN-A0'), _pair('RUN-A1')],
                    FOCI,
                    n_baseline=4,
                    n_ablated=2,
                    n_permutations=10,
                    session_id='run-a',
                )
            )
        assert not any('RUN-A1' in prompt for prompt in a_prompts)
    finally:
        b_release.set()
        worker.join(30)

    assert not worker.is_alive()
    events = _parse_events(b_chunks)
    complete = [e for e in events if e.get('type') == 'complete']
    assert len(complete) == 1
    assert complete[0]['completed'] == 1
    assert all(r['success'] for r in complete[0]['pair_results'])
    # Run B kept sampling after run A was cancelled: baseline + two ablated arms.
    assert len(b_prompts) == 3 + 2 + 2
