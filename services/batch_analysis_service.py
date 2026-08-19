#!/usr/bin/env python3
"""
Batch analysis service.

Per-pair subtractive ablation with a permutation test.
"""

import json
import time
import numpy as np
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
from services.ablation_service import SAMPLE_GAP_SECONDS
from utils.permutation_test import (
    DEFAULT_ALPHA,
    DEFAULT_N_PERMUTATIONS,
    benjamini_hochberg,
    permutation_test,
    power_guardrail_message,
    require_stochastic_temperature,
    design_test_type,
)


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
        return gateway_chat_completion(
            self.provider,
            self.model,
            self.provider_name,
            [{"role": "user", "content": prompt}],
            temperature=temperature,
        )
    
    def _sample_outputs(self, prompt: str, n: int, temperature: float):
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
        """Process one pair: shared baseline samples, per-focus ablated samples, permutation + BH."""
        try:
            require_stochastic_temperature(temperature)
            prompt = pair_data.get('prompt', '')
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
            
            baseline_embeddings, embedding_tokens = self.embedding_service.batch_embeddings_with_usage(
                baseline_outputs
            )
            baseline_embeddings = np.asarray(baseline_embeddings, dtype=float)
            
            ablation_results = []
            scored_payloads = []
            rng = np.random.default_rng(
                None if permutation_seed is None else permutation_seed + pair_idx
            )
            
            for i, focus in enumerate(classified):
                focus_name = focus.get('focus', f'Focus {i + 1}')
                row = {
                    'focus_index': i,
                    'focus': focus_name,
                    'prompt_section': focus.get('prompt_section', ''),
                    'verified': bool(focus.get('verified')),
                    'char_start': focus.get('char_start'),
                    'char_end': focus.get('char_end'),
                    'attributable': bool(focus.get('attributable')),
                    'reason': focus.get('reason'),
                    'overlap_with': list(focus.get('overlap_with') or []),
                    'is_dynamic': bool(focus.get('is_dynamic')),
                }
                if not focus.get('attributable'):
                    ablation_results.append(row)
                    continue
                
                ablated_prompt, prompt_empty, _collapsed = delete_span(
                    prompt, focus['char_start'], focus['char_end']
                )
                row['ablated_prompt'] = ablated_prompt
                row['prompt_empty'] = prompt_empty
                
                ablated_outputs, tin, tout = self._sample_outputs(
                    ablated_prompt, n_ablated, temperature
                )
                input_tokens += tin
                output_tokens += tout
                row['ablated_output'] = ablated_outputs[0]
                row['ablated_outputs'] = ablated_outputs
                
                ablated_embeddings, tokens = self.embedding_service.batch_embeddings_with_usage(
                    ablated_outputs
                )
                embedding_tokens += tokens
                ablated_embeddings = np.asarray(ablated_embeddings, dtype=float)
                
                perm = permutation_test(
                    baseline_embeddings,
                    ablated_embeddings,
                    n_permutations=n_permutations,
                    rng=rng,
                )
                row['t_obs'] = perm['t_obs']
                ablation_results.append(row)
                scored_payloads.append((focus_name, row, perm))
            
            raw_p = [p['p_value'] for _, _, p in scored_payloads]
            bh = benjamini_hochberg(raw_p, alpha=alpha)
            focus_influences = {}
            for (focus_name, row, perm), adj in zip(scored_payloads, bh):
                t_obs = perm['t_obs']
                focus_influences[focus_name] = {
                    'influence': float(t_obs),
                    'similarity': float(1.0 - t_obs),
                    't_obs': float(t_obs),
                    'p_value': adj['p_value'],
                    'q_value': adj['q_value'],
                    'is_significant': adj['significant'],
                    'exact': perm['exact'],
                    'n_permutations': perm['n_permutations'],
                    'null_mean': perm['null_mean'],
                    'null_p95': perm['null_p95'],
                    'standardized_effect': perm['standardized_effect'],
                    'null_deciles': perm['null_deciles'],
                    'ablated_prompt': row['ablated_prompt'],
                    'prompt_empty': row.get('prompt_empty', False),
                    'verified': True,
                    'attributable': True,
                    'char_start': row['char_start'],
                    'char_end': row['char_end'],
                }
            
            total_raw = sum(d['influence'] for d in focus_influences.values())
            if total_raw > 0:
                for d in focus_influences.values():
                    d['normalized_influence'] = d['influence'] / total_raw
            elif focus_influences:
                share = 1.0 / len(focus_influences)
                for d in focus_influences.values():
                    d['normalized_influence'] = share
            
            n_attr = len(focus_influences)
            power_warning = power_guardrail_message(
                n_baseline, n_ablated, n_attr, alpha=alpha, n_permutations=n_permutations
            )
            
            out = {
                'success': True,
                'pair_index': pair_idx,
                'pair_data': pair_data,
                'influence_scores': focus_influences,
                'ablation_results': ablation_results,
                'foci_list': classified,
                'baseline_outputs': baseline_outputs,
                'n_baseline': n_baseline,
                'n_ablated': n_ablated,
                'n_permutations': n_permutations,
                'alpha': alpha,
                'temperature': temperature,
                'test_type': design_test_type(n_baseline, n_ablated, n_permutations),
                'power_warning': power_warning,
                'significance_method': 'permutation_bh',
                'tokens': {
                    'input': input_tokens,
                    'output': output_tokens,
                    'embedding': embedding_tokens
                }
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
                'error': str(e)
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
            
            yield f"data: {json.dumps({'type': 'progress', 'stage': 'processing', 'completed': completed_count, 'total': total_pairs, 'pair_index': pair_idx})}\n\n"
            
            if result.get('success'):
                yield f"data: {json.dumps({'type': 'pair_result', 'pair_index': pair_idx, 'result': result})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'error', 'pair_index': pair_idx, 'error': result.get('error', 'Unknown error')})}\n\n"
        
        yield f"data: {json.dumps({'type': 'progress', 'stage': 'calculating_statistics', 'message': 'Calculating statistics...'})}\n\n"
        
        statistics = calculate_statistics_from_results(pair_results)
        focus_distribution_statistics = calculate_focus_distribution_statistics(pair_results)
        
        cost_breakdown = self.cost_calculator.calculate_cost(
            total_input_tokens,
            total_output_tokens,
            total_embedding_tokens,
            self.model,
            'openai'
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
        
        final_result = {
            'type': 'complete',
            'session_id': session_id,
            'completed': completed_count,
            'total_pairs': total_pairs,
            'pair_results': pair_results,
            'results': pair_results,
            'statistics': statistics,
            'focus_distribution_statistics': focus_distribution_statistics,
            'cost_breakdown': cost_breakdown,
            'significance_method': 'permutation_bh',
            'n_baseline': n_baseline,
            'n_ablated': n_ablated,
            'alpha': alpha,
        }
        
        yield f"data: {json.dumps(final_result)}\n\n"
