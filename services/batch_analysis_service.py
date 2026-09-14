#!/usr/bin/env python3
"""
Batch analysis service.

Per-pair subtractive ablation with a permutation test.
"""

import json
import threading
import time
from typing import Any, Callable, List, Dict, Mapping, Optional, Generator
from datetime import datetime
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from services.embedding_service import EmbeddingService
from services.cost_calculator import CostCalculator
from services.checkpoint_service import CheckpointService
from utils.span_alignment import classify_foci_for_ablation, delete_span
from utils.data_processing import (
    calculate_statistics_from_results,
    calculate_focus_distribution_statistics,
)
from services.assessment_service import AssessmentService
from utils.gateway_chat import chat_completion as gateway_chat_completion
from services.ablation_service import AblationService, SAMPLE_GAP_SECONDS
from utils.permutation_test import (
    DEFAULT_ALPHA,
    DEFAULT_N_PERMUTATIONS,
    require_stochastic_temperature,
)
from utils.inference_scenario import (
    ProviderCapabilityError,
    StructuredOutputError,
    ablate_scenario,
    bind_scenario_inputs,
    normalize_scenario_foci,
    scenario_analysis_document,
    validate_scenario,
)


class BatchRunCancelled(Exception):
    """Raised inside a worker row when its own run has been cancelled."""


def _sse_safe_pair_result(result: Dict) -> Dict:
    """Drop bulky sample texts from SSE payloads so browsers can render mid-stream."""
    if not isinstance(result, dict):
        return result
    slim = dict(result)
    for key in (
        'baseline_outputs',
        'ablated_outputs',
        'baseline_embeddings',
        'ablated_embeddings',
        'pair_data',
    ):
        slim.pop(key, None)
    baseline = slim.get('baseline_output')
    if isinstance(baseline, str) and len(baseline) > 500:
        slim['baseline_output'] = baseline[:500] + '…'
    return slim


class BatchAnalysisService:
    """Service for batch ablation analysis."""
    
    def __init__(
        self,
        provider,
        model: str,
        api_key: str,
        embedding_service: Optional[EmbeddingService] = None,
        cost_calculator: Optional[CostCalculator] = None,
        checkpoint_service: Optional[CheckpointService] = None,
        assessment_service: Optional[AssessmentService] = None,
        provider_name: Optional[str] = None,
        max_workers: int = 10
    ):
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.embedding_service = embedding_service or EmbeddingService()
        self.cost_calculator = cost_calculator or CostCalculator()
        self.checkpoint_service = checkpoint_service or CheckpointService()
        self.assessment_service = assessment_service
        self.provider_name = provider_name or 'openai'
        self.max_workers = max(1, int(max_workers))
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
    
    def _complete(self, prompt: str, temperature: float) -> Dict:
        if not (prompt or '').strip():
            raise ValueError(
                'Cannot call the model with an empty prompt. '
                'Enter the shared batch prompt (or a per-row prompt), and ensure '
                'ablated prompts are non-empty before sampling.'
            )
        return gateway_chat_completion(
            self.provider,
            self.model,
            self.provider_name,
            [{"role": "user", "content": prompt}],
            temperature=temperature,
        )
    
    def _sample_outputs(
        self,
        prompt: str,
        n: int,
        temperature: float,
        *,
        before_sample: Optional[Callable[[int], None]] = None,
    ):
        # Whole-prompt ablation yields an empty string; do not hit the gateway.
        if not (prompt or '').strip():
            return [''] * n, 0, 0
        outputs = []
        in_tok = 0
        out_tok = 0
        for i in range(n):
            if i > 0:
                time.sleep(SAMPLE_GAP_SECONDS)
            if before_sample is not None:
                before_sample(i)
            response = self._complete(prompt, temperature)
            outputs.append(response['content'])
            if 'usage' in response:
                in_tok += response['usage']['prompt_tokens']
                out_tok += response['usage']['completion_tokens']
        return outputs, in_tok, out_tok
    
    def process_single_pair(
        self,
        pair_data: Dict,
        pair_idx: int,
        foci_list: List[Dict],
        n_baseline: int = 10,
        n_ablated: int = 5,
        n_permutations: int = DEFAULT_N_PERMUTATIONS,
        alpha: float = DEFAULT_ALPHA,
        permutation_seed: Optional[int] = None,
        temperature: float = 0.7,
        scenario: Optional[Mapping[str, Any]] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> Dict:
        """
        Process one pair.

        Orchestration only: sample baseline/ablated outputs, optional reported-focus
        assessment, then delegate statistical scoring to
        ``AblationService.score_from_samples`` (canonical single-run scorer).
        """
        def before_sample(_index: int = 0) -> None:
            """Abort before paying for another sample once this run is cancelled."""
            if cancel_event is not None and cancel_event.is_set():
                raise BatchRunCancelled(f'Batch run cancelled before pair {pair_idx}')

        try:
            before_sample()
            require_stochastic_temperature(temperature)
            prompt = pair_data.get('prompt', '')
            if scenario is None and not (prompt or '').strip():
                return {
                    'success': False,
                    'pair_index': pair_idx,
                    'error': (
                        'Pair prompt is empty. Set the shared prompt in Batch Analysis, '
                        'include a per-row prompt in the CSV, or ensure foci cover the source text.'
                    ),
                }
            scorer = AblationService(
                self.provider,
                self.model,
                api_key=self.api_key,
                embedding_service=self.embedding_service,
                cost_calculator=self.cost_calculator,
                provider_name=self.provider_name,
            )
            bound_scenario = None
            binding = None
            if scenario is not None:
                bound_scenario, binding = bind_scenario_inputs(
                    scenario, pair_data.get('inputs') or {}
                )
                classified = normalize_scenario_foci(bound_scenario, foci_list)
                baseline_outputs, input_tokens, output_tokens, baseline_metadata = (
                    scorer._sample_scenario_outputs(
                        bound_scenario,
                        n_baseline,
                        temperature,
                        before_sample=before_sample,
                    )
                )
            else:
                classified = classify_foci_for_ablation(prompt, foci_list)
                baseline_outputs, input_tokens, output_tokens = self._sample_outputs(
                    prompt, n_baseline, temperature, before_sample=before_sample
                )
                baseline_metadata = []
            baseline_output = baseline_outputs[0]

            focus_distribution_assessment = None
            assessment_error = None
            if self.assessment_service:
                provided_out = (pair_data.get('output') or '').strip()
                output_for_assessment = provided_out if provided_out else baseline_output
                assessment_source = 'provided_output' if provided_out else 'generated_baseline'
                # Reported-focus evidence must come from the grounded foci so the
                # assessor sees the same spans ablation deletes.
                user_foci_for_assess = [
                    {'focus': f.get('focus', ''), 'prompt_section': f.get('prompt_section', '')}
                    for f in classified
                ]
                before_sample()
                try:
                    fd = self.assessment_service.assess_focus(
                        scenario_analysis_document(bound_scenario) if bound_scenario else prompt,
                        output_for_assessment,
                        user_foci=user_foci_for_assess,
                    )
                    usage_fd = fd.pop('usage', None)
                    focus_distribution_assessment = {
                        'foci': fd.get('foci', []),
                        'overall_summary': fd.get('overall_summary', ''),
                        'assessment_source': assessment_source,
                    }
                    if usage_fd:
                        input_tokens += usage_fd.get('prompt_tokens', 0) or usage_fd.get('input_tokens', 0)
                        output_tokens += usage_fd.get('completion_tokens', 0) or usage_fd.get('output_tokens', 0)
                except BatchRunCancelled:
                    raise
                except Exception as ex:
                    assessment_error = str(ex)

            ablated_by_index: Dict[int, List[str]] = {}
            ablated_metadata: Dict[str, Any] = {}
            for i, focus in enumerate(classified):
                if not focus.get('attributable'):
                    continue
                before_sample()
                if bound_scenario is not None:
                    ablated, deletion = ablate_scenario(bound_scenario, focus)
                    texts, tin, tout, metadata = scorer._sample_scenario_outputs(
                        ablated,
                        n_ablated,
                        temperature,
                        before_sample=before_sample,
                    )
                    ablated_metadata[str(i)] = {
                        'scenario_metadata': metadata,
                        **deletion,
                    }
                else:
                    ablated_prompt, _prompt_empty, _collapsed = delete_span(
                        prompt, focus['char_start'], focus['char_end']
                    )
                    texts, tin, tout = self._sample_outputs(
                        ablated_prompt,
                        n_ablated,
                        temperature,
                        before_sample=before_sample,
                    )
                input_tokens += tin
                output_tokens += tout
                ablated_by_index[i] = texts

            pair_seed = (
                None if permutation_seed is None else int(permutation_seed) + int(pair_idx)
            )
            score_kwargs = {
                'n_permutations': n_permutations,
                'alpha': alpha,
                'permutation_seed': pair_seed,
                'temperature': temperature,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
            }
            if bound_scenario is not None:
                scored = scorer.score_scenario_from_samples(
                    bound_scenario,
                    classified,
                    baseline_outputs,
                    ablated_by_index,
                    **score_kwargs,
                )
            else:
                scored = scorer.score_from_samples(
                    prompt,
                    foci_list,
                    baseline_outputs,
                    ablated_by_index,
                    **score_kwargs,
                )

            # Batch aggregate helpers expect a focus-name -> metrics dict.
            influence_scores = {}
            for item in scored.get('influence_scores') or []:
                name = item.get('focus')
                if not name:
                    continue
                influence_scores[name] = dict(item)

            out = {
                'success': True,
                'pair_index': pair_idx,
                'pair_data': pair_data,
                'influence_scores': influence_scores,
                'ablation_results': scored.get('ablation_results', []),
                'foci_list': scored.get('foci_list', classified),
                'baseline_outputs': baseline_outputs,
                'n_baseline': scored.get('n_baseline', n_baseline),
                'n_ablated': scored.get('n_ablated', n_ablated),
                'n_permutations': scored.get('n_permutations', n_permutations),
                'alpha': scored.get('alpha', alpha),
                'temperature': scored.get('temperature', temperature),
                'test_type': scored.get('test_type'),
                'power_warning': scored.get('power_warning'),
                'significance_method': scored.get('significance_method', 'permutation_bh'),
                'summary': scored.get('summary', {}),
                'model': self.model,
                'provider': self.provider_name,
                'tokens': {
                    'input': input_tokens,
                    'output': output_tokens,
                    'embedding': int(scored.get('embedding_tokens') or 0),
                },
            }
            if focus_distribution_assessment is not None:
                out['focus_distribution_assessment'] = focus_distribution_assessment
            if assessment_error is not None:
                out['focus_distribution_assessment_error'] = assessment_error
            if bound_scenario is not None:
                out['scenario'] = bound_scenario
                out['scenario_metadata'] = {
                    'input_binding': binding,
                    'baseline': baseline_metadata,
                    'ablated_arms': ablated_metadata,
                }
                out['reproducibility'] = scored.get('reproducibility')
            return out
        except BatchRunCancelled as cancelled:
            return {
                'success': False,
                'pair_index': pair_idx,
                'cancelled': True,
                'error': str(cancelled),
            }
        except (StructuredOutputError, ProviderCapabilityError):
            # A required contract failure invalidates the experiment. Cancel this
            # run at the source — before the future resolves — so a row the
            # executor starts next sees the cancellation and pays for nothing.
            if cancel_event is not None:
                cancel_event.set()
            raise
        except Exception as e:
            return {
                'success': False,
                'pair_index': pair_idx,
                'error': str(e),
            }

    def stream_batch_analysis(
        self,
        pairs: List[Dict],
        foci_list: List[Dict],
        num_samples: Optional[int] = None,
        session_id: Optional[str] = None,
        resume: bool = False,
        n_baseline: int = 10,
        n_ablated: int = 5,
        n_permutations: int = DEFAULT_N_PERMUTATIONS,
        alpha: float = DEFAULT_ALPHA,
        permutation_seed: Optional[int] = None,
        temperature: float = 0.7,
        scenario: Optional[Mapping[str, Any]] = None,
    ) -> Generator[str, None, None]:
        """Stream batch analysis. Each pair is its own permutation experiment."""
        require_stochastic_temperature(temperature)
        normalized_scenario = validate_scenario(scenario) if scenario is not None else None
        if num_samples is not None:
            n_baseline = int(num_samples)
        if not session_id:
            session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        total_input_tokens = 0
        total_output_tokens = 0
        total_embedding_tokens = 0
        
        pair_results = []
        total_pairs = len(pairs)
        completed_count = 0
        
        completed_pairs = {}
        if resume:
            checkpoint = self.checkpoint_service.load_checkpoint(session_id, 'batch_analysis')
            if checkpoint:
                completed_pairs = {r['pair_index']: r for r in checkpoint.get('pair_results', [])}
                pair_results = list(completed_pairs.values())
                yield f"data: {json.dumps({'type': 'resume', 'completed': len(completed_pairs), 'total': len(pairs)})}\n\n"
        
        yield f"data: {json.dumps({'type': 'progress', 'stage': 'processing', 'message': f'Processing {total_pairs} pairs...'})}\n\n"
        
        # Bounded scheduling: only as many rows as the executor can run are
        # queued, so a fatal contract failure stops the run before any further
        # row pays for samples. Cancellation is scoped to this stream's event,
        # so unrelated runs sharing the executor keep going.
        cancel_event = threading.Event()
        window = max(1, self.max_workers)
        pending = [
            (pair_idx, pair)
            for pair_idx, pair in enumerate(pairs)
            if pair_idx not in completed_pairs
        ]
        next_pending = 0
        inflight: Dict[Future, int] = {}

        def submit_pending() -> None:
            nonlocal next_pending
            while (
                not cancel_event.is_set()
                and next_pending < len(pending)
                and len(inflight) < window
            ):
                idx, pair = pending[next_pending]
                next_pending += 1
                future = self.executor.submit(
                    self.process_single_pair,
                    pair,
                    idx,
                    foci_list,
                    n_baseline,
                    n_ablated,
                    n_permutations,
                    alpha,
                    permutation_seed,
                    temperature,
                    normalized_scenario,
                    cancel_event,
                )
                inflight[future] = idx

        def abandon_run() -> None:
            cancel_event.set()
            for queued in list(inflight):
                queued.cancel()
            inflight.clear()

        submit_pending()
        try:
            while inflight:
                done, _not_done = wait(list(inflight), return_when=FIRST_COMPLETED)
                for future in done:
                    pair_idx = inflight.pop(future)
                    try:
                        result = future.result()
                    except (StructuredOutputError, ProviderCapabilityError):
                        # A required contract failure invalidates the experiment:
                        # drop queued rows and stop active rows before more samples.
                        abandon_run()
                        raise
                    pair_results.append(result)
                    completed_count += 1
                    if result.get('success') and result.get('tokens'):
                        total_input_tokens += result['tokens'].get('input', 0)
                        total_output_tokens += result['tokens'].get('output', 0)
                        total_embedding_tokens += result['tokens'].get('embedding', 0)

                    checkpoint_data = {
                        'session_id': session_id,
                        'timestamp': datetime.now().isoformat(),
                        'type': 'batch_analysis',
                        'completed': completed_count,
                        'total_pairs': total_pairs,
                        'pair_results': pair_results,
                        'complete': completed_count >= total_pairs
                    }
                    if normalized_scenario is not None:
                        checkpoint_data['scenario'] = normalized_scenario
                        checkpoint_data['workspace_version'] = 2
                    self.checkpoint_service.save_checkpoint(session_id, checkpoint_data, 'batch_analysis')

                    progress_event = {
                        'type': 'progress',
                        'stage': 'processing',
                        'message': 'Processing pairs',
                        'completed': completed_count,
                        'total': total_pairs,
                        'pair_index': pair_idx,
                    }
                    yield f"data: {json.dumps(progress_event)}\n\n"

                    if result.get('success'):
                        # Stream a UI-sized payload (drop raw sample texts) so the
                        # browser can render even if the final complete event is cut.
                        pair_event = {
                            'type': 'pair_result',
                            'pair_index': pair_idx,
                            'completed': completed_count,
                            'total': total_pairs,
                            'result': _sse_safe_pair_result(result),
                        }
                        yield f"data: {json.dumps(pair_event)}\n\n"
                    else:
                        err = result.get('error', 'Unknown error')
                        err_event = {
                            'type': 'error',
                            'pair_index': pair_idx,
                            'error': err,
                            'message': err,
                        }
                        yield f"data: {json.dumps(err_event)}\n\n"
                submit_pending()
        finally:
            # Client disconnect or abort must not leave rows paying for samples.
            abandon_run()

        yield f"data: {json.dumps({'type': 'progress', 'stage': 'calculating_statistics', 'message': 'Calculating statistics...'})}\n\n"
        
        statistics = calculate_statistics_from_results(pair_results)
        focus_distribution_statistics = calculate_focus_distribution_statistics(pair_results)
        
        cost_breakdown = self.cost_calculator.calculate_cost(
            total_input_tokens,
            total_output_tokens,
            total_embedding_tokens,
            self.model,
            self.provider_name,
        )
        
        checkpoint_data = {
            'session_id': session_id,
            'timestamp': datetime.now().isoformat(),
            'type': 'batch_analysis',
            'completed': completed_count,
            'total_pairs': total_pairs,
            'pair_results': pair_results,
            'statistics': statistics,
            'focus_distribution_statistics': focus_distribution_statistics,
            'cost_breakdown': cost_breakdown,
            'complete': True
        }
        if normalized_scenario is not None:
            checkpoint_data['scenario'] = normalized_scenario
            checkpoint_data['workspace_version'] = 2
        self.checkpoint_service.save_checkpoint(session_id, checkpoint_data, 'batch_analysis')
        
        safe_pairs = [_sse_safe_pair_result(r) for r in pair_results]
        final_result = {
            'type': 'complete',
            'session_id': session_id,
            'completed': completed_count,
            'total_pairs': total_pairs,
            'pair_results': safe_pairs,
            'results': safe_pairs,
            'statistics': statistics,
            'focus_distribution_statistics': focus_distribution_statistics,
            'cost_breakdown': cost_breakdown,
            'significance_method': 'permutation_bh',
            'n_baseline': n_baseline,
            'n_ablated': n_ablated,
            'alpha': alpha,
        }
        if normalized_scenario is not None:
            final_result['scenario'] = normalized_scenario
            final_result['workspace_version'] = 2

        yield f"data: {json.dumps(final_result)}\n\n"
