#!/usr/bin/env python3
"""
Ablation analysis service.

Strict subtractive ablation: delete a verified focus span from the original prompt.
Significance: permutation test of centroid cosine distance.
"""

import numpy as np
import time
from typing import List, Dict, Optional
from services.embedding_service import EmbeddingService
from services.cost_calculator import CostCalculator
from utils.span_alignment import classify_foci_for_ablation, delete_span
from utils.gateway_chat import chat_completion as gateway_chat_completion
from utils.permutation_test import (
    DEFAULT_ALPHA,
    DEFAULT_N_PERMUTATIONS,
    benjamini_hochberg,
    permutation_test,
    power_guardrail_message,
    require_stochastic_temperature,
    design_test_type,
)


class AblationService:
    """Service for running ablation analysis."""
    
    def __init__(
        self,
        provider,
        model: str,
        api_key: Optional[str] = None,
        embedding_service: Optional[EmbeddingService] = None,
        cost_calculator: Optional[CostCalculator] = None,
        provider_name: Optional[str] = None,
    ):
        self.provider = provider
        self.model = model
        self.provider_name = provider_name or 'openai'
        self.api_key = api_key
        self.embedding_service = embedding_service or EmbeddingService()
        self.cost_calculator = cost_calculator or CostCalculator()
    
    def _complete(self, user_content: str, temperature: float) -> Dict:
        max_retries = 3
        retry_delay = 2
        last_error = None
        for attempt in range(max_retries):
            try:
                response = gateway_chat_completion(
                    self.provider,
                    self.model,
                    self.provider_name,
                    [{"role": "user", "content": user_content}],
                    temperature=temperature,
                )
                if not response or not response.get('content'):
                    raise Exception(
                        "Model returned an empty response. "
                        "Check model/provider selection and try again."
                    )
                return response
            except Exception as e:
                last_error = e
                error_msg = str(e).lower()
                if 'rate limit' in error_msg or '429' in error_msg or 'too many requests' in error_msg:
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** attempt)
                        time.sleep(wait_time)
                        continue
                    raise Exception(
                        f"Rate limit exceeded after {max_retries} retries. "
                        "Please wait a few minutes and try again with fewer samples."
                    ) from e
                raise
        raise Exception(
            "Failed to generate output after retries. "
            "Check model/provider selection, rate limits, and Vercel function timeouts."
        ) from last_error
    
    def _sample_outputs(self, prompt: str, n: int, temperature: float):
        outputs = []
        in_tok = 0
        out_tok = 0
        for i in range(n):
            if i > 0:
                time.sleep(0.5)
            response = self._complete(prompt, temperature)
            outputs.append(response['content'])
            if 'usage' in response:
                in_tok += response['usage']['prompt_tokens']
                out_tok += response['usage']['completion_tokens']
        return outputs, in_tok, out_tok
    
    def run_ablation(
        self,
        prompt: str,
        foci_list: List[Dict],
        num_samples: Optional[int] = None,
        inputs: Optional[Dict] = None,
        n_baseline: int = 10,
        n_ablated: int = 5,
        n_permutations: int = DEFAULT_N_PERMUTATIONS,
        alpha: float = DEFAULT_ALPHA,
        permutation_seed: Optional[int] = None,
        temperature: float = 0.7,
    ) -> Dict:
        """
        Run subtractive ablation with a permutation test per attributable focus.

        `num_samples` is an alias for `n_baseline` (legacy). `inputs` is ignored.
        """
        del inputs
        require_stochastic_temperature(temperature)
        if num_samples is not None:
            n_baseline = int(num_samples)
        n_baseline = int(n_baseline)
        n_ablated = int(n_ablated)
        if n_baseline < 1 or n_ablated < 1:
            raise ValueError('n_baseline and n_ablated must be at least 1.')
        
        total_input_tokens = 0
        total_output_tokens = 0
        total_embedding_tokens = 0
        
        classified = classify_foci_for_ablation(prompt, foci_list)
        
        try:
            baseline_outputs, tin, tout = self._sample_outputs(prompt, n_baseline, temperature)
        except Exception as e:
            raise Exception(f"Failed to generate baseline output: {e}") from e
        total_input_tokens += tin
        total_output_tokens += tout
        baseline_output = baseline_outputs[0]
        
        baseline_embeddings, tokens = self.embedding_service.batch_embeddings_with_usage(baseline_outputs)
        total_embedding_tokens += tokens
        baseline_embeddings = np.asarray(baseline_embeddings, dtype=float)
        
        ablation_results = []
        scored_payloads = []
        rng = np.random.default_rng(permutation_seed)
        
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
            
            time.sleep(0.5)
            try:
                ablated_outputs, tin, tout = self._sample_outputs(
                    ablated_prompt, n_ablated, temperature
                )
            except Exception as e:
                raise Exception(
                    f"Failed to generate ablated output for focus '{focus_name}': {e}"
                ) from e
            total_input_tokens += tin
            total_output_tokens += tout
            row['ablated_output'] = ablated_outputs[0]
            row['ablated_outputs'] = ablated_outputs
            
            ablated_embeddings, tokens = self.embedding_service.batch_embeddings_with_usage(
                ablated_outputs
            )
            total_embedding_tokens += tokens
            ablated_embeddings = np.asarray(ablated_embeddings, dtype=float)
            
            perm = permutation_test(
                baseline_embeddings,
                ablated_embeddings,
                n_permutations=n_permutations,
                rng=rng,
            )
            row['t_obs'] = perm['t_obs']
            ablation_results.append(row)
            scored_payloads.append((row, perm, ablated_embeddings))
        
        influence_scores = []
        raw_p = [p['p_value'] for _, p, _ in scored_payloads]
        bh = benjamini_hochberg(raw_p, alpha=alpha)
        for (ablation, perm, _emb), adj in zip(scored_payloads, bh):
            t_obs = perm['t_obs']
            influence_scores.append({
                'focus': ablation['focus'],
                'focus_name': ablation['focus'],
                'prompt_section': ablation['prompt_section'],
                'verified': True,
                'attributable': True,
                'char_start': ablation['char_start'],
                'char_end': ablation['char_end'],
                'ablated_prompt': ablation['ablated_prompt'],
                'prompt_empty': ablation.get('prompt_empty', False),
                'similarity': float(1.0 - t_obs),
                'influence': float(t_obs),
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
            })
        
        if influence_scores:
            total_influence = sum(item['influence'] for item in influence_scores)
            if total_influence > 0:
                for item in influence_scores:
                    item['normalized_influence'] = (item['influence'] / total_influence) * 100
            else:
                equal_share = 100.0 / len(influence_scores)
                for item in influence_scores:
                    item['normalized_influence'] = equal_share
        
        n_attr = len(influence_scores)
        power_warning = power_guardrail_message(
            n_baseline, n_ablated, n_attr, alpha=alpha, n_permutations=n_permutations
        )
        
        cost_breakdown = self.cost_calculator.calculate_cost(
            total_input_tokens,
            total_output_tokens,
            total_embedding_tokens,
            self.model,
            'openai'
        )
        
        summary = {item['focus']: item['normalized_influence'] for item in influence_scores}
        
        return {
            'baseline_output': baseline_output,
            'baseline_outputs': baseline_outputs,
            'ablation_results': ablation_results,
            'influence_scores': influence_scores,
            'n_baseline': n_baseline,
            'n_ablated': n_ablated,
            'n_permutations': n_permutations,
            'alpha': alpha,
            'temperature': temperature,
            'permutation_seed': permutation_seed,
            'num_baseline_samples': n_baseline,
            'test_type': design_test_type(n_baseline, n_ablated, n_permutations),
            'summary': summary,
            'cost_breakdown': cost_breakdown,
            'prompt': prompt,
            'foci_list': classified,
            'model': self.model,
            'power_warning': power_warning,
            'significance_method': 'permutation_bh',
        }
