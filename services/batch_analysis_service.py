#!/usr/bin/env python3
"""
Batch analysis service.

Per-pair subtractive ablation with a permutation test.
"""

import json
import time
from typing import List, Dict, Optional, Generator
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
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
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
    
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
    
    def _sample_outputs(self, prompt: str, n: int, temperature: float):
        # Whole-prompt ablation yields an empty string; do not hit the gateway.
        if not (prompt or '').strip():
            return [''] * n, 0, 0
        outputs = []
        in_tok = 0
        out_tok = 0
        for i in range(n):
            if i > 0:
                time.sleep(SAMPLE_GAP_SECONDS)
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
    ) -> Dict:
        """
        Process one pair.

        Orchestration only: sample baseline/ablated outputs, optional reported-focus
        assessment, then delegate statistical scoring to
        ``AblationService.score_from_samples`` (canonical single-run scorer).
        """
        try:
            require_stochastic_temperature(temperature)
            prompt = pair_data.get('prompt', '')
            if not (prompt or '').strip():
                return {
                    'success': False,
                    'pair_index': pair_idx,
                    'error': (
                        'Pair prompt is empty. Set the shared prompt in Batch Analysis, '
                        'include a per-row prompt in the CSV, or ensure foci cover the source text.'
                    ),
                }
            classified = classify_foci_for_ablation(prompt, foci_list)

            baseline_outputs, input_tokens, output_tokens = self._sample_outputs(
                prompt, n_baseline, temperature
            )
            baseline_output = baseline_outputs[0]

            focus_distribution_assessment = None
            assessment_error = None
            if self.assessment_service:
                provided_out = (pair_data.get('output') or '').strip()
                output_for_assessment = provided_out if provided_out else baseline_output
                assessment_source = 'provided_output' if provided_out else 'generated_baseline'
                user_foci_for_assess = [
                    {'focus': f.get('focus', ''), 'prompt_section': f.get('prompt_section', '')}
                    for f in foci_list
                ]
                try:
                    fd = self.assessment_service.assess_focus(
                        prompt, output_for_assessment, user_foci=user_foci_for_assess
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
                except Exception as ex:
                    assessment_error = str(ex)

            ablated_by_index: Dict[int, List[str]] = {}
            for i, focus in enumerate(classified):
                if not focus.get('attributable'):
                    continue
                ablated_prompt, _prompt_empty, _collapsed = delete_span(
                    prompt, focus['char_start'], focus['char_end']
                )
                texts, tin, tout = self._sample_outputs(
                    ablated_prompt, n_ablated, temperature
                )
                input_tokens += tin
                output_tokens += tout
                ablated_by_index[i] = texts

            pair_seed = (
                None if permutation_seed is None else int(permutation_seed) + int(pair_idx)
            )
            scorer = AblationService(
                self.provider,
                self.model,
                api_key=self.api_key,
                embedding_service=self.embedding_service,
                cost_calculator=self.cost_calculator,
                provider_name=self.provider_name,
            )
            scored = scorer.score_from_samples(
                prompt,
                foci_list,
                baseline_outputs,
                ablated_by_index,
                n_permutations=n_permutations,
                alpha=alpha,
                permutation_seed=pair_seed,
                temperature=temperature,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
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
            return out
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
    ) -> Generator[str, None, None]:
        """Stream batch analysis. Each pair is its own permutation experiment."""
        require_stochastic_temperature(temperature)
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
        
        futures = {}
        for pair_idx, pair in enumerate(pairs):
            if pair_idx in completed_pairs:
                continue
            
            future = self.executor.submit(
                self.process_single_pair,
                pair,
                pair_idx,
                foci_list,
                n_baseline,
                n_ablated,
                n_permutations,
                alpha,
                permutation_seed,
                temperature,
            )
            futures[future] = pair_idx
        
        for future in as_completed(futures):
            pair_idx = futures[future]
            result = future.result()
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

        yield f"data: {json.dumps(final_result)}\n\n"
