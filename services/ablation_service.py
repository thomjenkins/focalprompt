#!/usr/bin/env python3
"""
Ablation analysis service.

Strict subtractive ablation: delete a verified focus span from the original prompt.
Significance: permutation test of centroid cosine distance.
"""

import numpy as np
import time
import random
from typing import List, Dict, Optional
from services.embedding_service import EmbeddingService
from services.cost_calculator import CostCalculator
from utils.span_alignment import classify_foci_for_ablation, delete_span, build_shuffled_remaining_prompt
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
from utils.baseline_stability import compute_baseline_stability, attach_signal_to_noise
from utils.ablation_stability import (
    build_stability_scatter_points,
    build_stability_summary,
    compare_behavioral_outcomes,
    compute_ablation_stability,
)
from utils.reported_focus_dynamics import build_reported_focus_dynamics
from services.behavioral_difference_service import enrich_influence_item_for_review

# Space sequential completions so a 429 on sample 1 does not become a burst.
SAMPLE_GAP_SECONDS = 1.5


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
        # Gateway already retries 429s. Do not stack another loop here.
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
    
    def _sample_outputs(self, prompt: str, n: int, temperature: float):
        # Whole-prompt ablation can leave an empty string; do not call the gateway.
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

    def sample_completion(
        self,
        prompt: str,
        foci_list: List[Dict],
        kind: str,
        temperature: float,
        focus_index: Optional[int] = None,
        shuffle_remaining: bool = False,
        shuffle_seed: Optional[int] = None,
        inputs: Optional[Dict] = None,
    ) -> Dict:
        """One model completion for client-paced ablation (survives gateway RPM limits)."""
        require_stochastic_temperature(temperature)
        kind = (kind or 'baseline').lower()
        if kind == 'baseline':
            return self._complete(prompt, temperature)
        if kind != 'ablated':
            raise ValueError("kind must be 'baseline' or 'ablated'")
        if focus_index is None:
            raise ValueError('focus_index is required for ablated samples')
        classified = classify_foci_for_ablation(prompt, foci_list)
        idx = int(focus_index)
        if idx < 0 or idx >= len(classified):
            raise ValueError('focus_index out of range')
        focus = classified[idx]
        if not focus.get('attributable'):
            raise ValueError(
                f"Focus '{focus.get('focus')}' cannot be ablated ({focus.get('reason')})"
            )
        if shuffle_remaining:
            seed = shuffle_seed if shuffle_seed is not None else random.randint(0, 2**31 - 1)
            ablated_prompt, prompt_empty, doc_order, shuffled_order = build_shuffled_remaining_prompt(
                prompt,
                classified,
                idx,
                shuffle_seed=seed,
                inputs=inputs,
            )
            shuffle_meta = {
                'ablation_mode': 'shuffled_remaining',
                'shuffle_seed': seed,
                'remaining_foci_document_order': doc_order,
                'remaining_foci_shuffled_order': shuffled_order,
            }
        else:
            ablated_prompt, prompt_empty, _collapsed = delete_span(
                prompt, focus['char_start'], focus['char_end']
            )
            shuffle_meta = {'ablation_mode': 'subtractive'}
        result = dict(self._complete(ablated_prompt, temperature))
        result['ablated_prompt'] = ablated_prompt
        result['prompt_empty'] = prompt_empty
        result['focus'] = focus.get('focus')
        result['focus_index'] = idx
        result.update(shuffle_meta)
        return result

    def run_shuffle_robustness(
        self,
        prompt: str,
        foci_list: List[Dict],
        focus_index: int,
        baseline_outputs: List[str],
        *,
        n_ablated: int = 5,
        shuffle_seed: Optional[int] = None,
        n_permutations: int = DEFAULT_N_PERMUTATIONS,
        alpha: float = DEFAULT_ALPHA,
        permutation_seed: Optional[int] = None,
        temperature: float = 0.7,
        inputs: Optional[Dict] = None,
    ) -> Dict:
        """
        Re-test one focus after shuffling the order of remaining focus spans.

        Reuses the original baseline samples. Reports an uncorrected p-value —
        a sensitivity check, not part of the main BH family across foci.
        Preserves non-attributable residual text (including dynamic chat already
        in the prompt) and appends ``inputs`` chat/RAG/tools when provided.
        """
        require_stochastic_temperature(temperature)
        baseline_outputs = [
            str(t) for t in (baseline_outputs or []) if t is not None and str(t).strip()
        ]
        if len(baseline_outputs) < 1:
            raise ValueError('baseline_outputs must contain at least one sample')

        classified = classify_foci_for_ablation(prompt, foci_list)
        idx = int(focus_index)
        if idx < 0 or idx >= len(classified):
            raise ValueError('focus_index out of range')
        focus = classified[idx]
        if not focus.get('attributable'):
            raise ValueError(
                f"Focus '{focus.get('focus')}' cannot be ablated ({focus.get('reason')})"
            )

        seed = shuffle_seed if shuffle_seed is not None else random.randint(0, 2**31 - 1)
        ablated_prompt, prompt_empty, doc_order, shuffled_order = build_shuffled_remaining_prompt(
            prompt,
            classified,
            idx,
            shuffle_seed=seed,
            inputs=inputs,
        )

        n_ablated = int(n_ablated)
        if n_ablated < 1:
            raise ValueError('n_ablated must be at least 1')

        texts, input_tokens, output_tokens = self._sample_outputs(
            ablated_prompt, n_ablated, temperature
        )

        baseline_embeddings, emb_in = self.embedding_service.batch_embeddings_with_usage(
            baseline_outputs
        )
        ablated_embeddings, emb_out = self.embedding_service.batch_embeddings_with_usage(texts)
        total_embedding_tokens = emb_in + emb_out
        baseline_embeddings = np.asarray(baseline_embeddings, dtype=float)
        ablated_embeddings = np.asarray(ablated_embeddings, dtype=float)

        rng = np.random.default_rng(permutation_seed)
        perm = permutation_test(
            baseline_embeddings,
            ablated_embeddings,
            n_permutations=n_permutations,
            rng=rng,
        )
        p_value = float(perm['p_value'])
        cost_breakdown = self.cost_calculator.calculate_cost(
            int(input_tokens),
            int(output_tokens),
            int(total_embedding_tokens),
            self.model,
            self.provider_name,
        )

        order_changed = doc_order != shuffled_order
        return {
            'ablation_mode': 'shuffled_remaining',
            'focus': focus.get('focus'),
            'focus_index': idx,
            'shuffle_seed': seed,
            'remaining_foci_document_order': doc_order,
            'remaining_foci_shuffled_order': shuffled_order,
            'order_changed': order_changed,
            'ablated_prompt': ablated_prompt,
            'prompt_empty': prompt_empty,
            'ablated_outputs': texts,
            'n_ablated': n_ablated,
            'n_baseline': len(baseline_outputs),
            't_obs': float(perm['t_obs']),
            'p_value': p_value,
            'is_significant_uncorrected': p_value < float(alpha),
            'q_value': None,
            'alpha': float(alpha),
            'standardized_effect': perm['standardized_effect'],
            'null_mean': perm['null_mean'],
            'null_p95': perm['null_p95'],
            'null_deciles': perm['null_deciles'],
            'n_permutations': perm['n_permutations'],
            'exact': perm['exact'],
            'test_type': design_test_type(len(baseline_outputs), n_ablated, n_permutations),
            'cost_breakdown': cost_breakdown,
            'note': (
                'Sensitivity check: remaining focus spans were reordered before sampling. '
                'p-value is uncorrected (not part of the main BH correction across foci). '
                'Non-attributable residual text (glue, dynamic chat already in the prompt) '
                'is preserved; optional inputs append chat/RAG/tools when missing.'
            ),
        }

    def score_from_samples(
        self,
        prompt: str,
        foci_list: List[Dict],
        baseline_outputs: List[str],
        ablated_outputs: Dict,
        n_permutations: int = DEFAULT_N_PERMUTATIONS,
        alpha: float = DEFAULT_ALPHA,
        permutation_seed: Optional[int] = None,
        temperature: float = 0.7,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> Dict:
        """Permutation + BH on already-collected sample texts. Does not call the chat model.

        ``normalized_influence`` is in percentage points on [0, 100]: attributable
        foci share the observed influence mass so their values sum to 100 (equal
        shares of 100/n when all raw influences are zero).
        """
        require_stochastic_temperature(temperature)
        baseline_outputs = [str(t) for t in baseline_outputs if t is not None and str(t).strip()]
        if len(baseline_outputs) < 1:
            raise ValueError('baseline_outputs must contain at least one sample')
        n_baseline = len(baseline_outputs)
        ablated_map: Dict[int, List[str]] = {}
        for key, vals in (ablated_outputs or {}).items():
            ablated_map[int(key)] = [str(t) for t in vals]

        classified = classify_foci_for_ablation(prompt, foci_list)
        n_ablated = 0
        for i, focus in enumerate(classified):
            if not focus.get('attributable'):
                continue
            texts = ablated_map.get(i) or []
            if len(texts) < 1:
                raise ValueError(
                    f"Missing ablated samples for focus '{focus.get('focus')}'"
                )
            if n_ablated == 0:
                n_ablated = len(texts)
            elif len(texts) != n_ablated:
                raise ValueError('All attributable foci must have the same number of ablated samples')

        total_embedding_tokens = 0
        baseline_embeddings, tokens = self.embedding_service.batch_embeddings_with_usage(
            baseline_outputs
        )
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
            texts = ablated_map[i]
            row['ablated_prompt'] = ablated_prompt
            row['prompt_empty'] = prompt_empty
            row['ablated_output'] = texts[0]
            row['ablated_outputs'] = texts

            ablated_embeddings, emb_tokens = self.embedding_service.batch_embeddings_with_usage(
                texts
            )
            total_embedding_tokens += emb_tokens
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
                'focus_index': ablation.get('focus_index'),
                'prompt_section': ablation['prompt_section'],
                'verified': True,
                'attributable': True,
                'char_start': ablation['char_start'],
                'char_end': ablation['char_end'],
                'ablated_prompt': ablation['ablated_prompt'],
                'prompt_empty': ablation.get('prompt_empty', False),
                'ablated_output': ablation.get('ablated_output'),
                'ablated_outputs': list(ablation.get('ablated_outputs') or []),
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

        # Baseline-only stability / noise (does not alter the permutation test).
        baseline_stability = compute_baseline_stability(baseline_embeddings)
        influence_scores = attach_signal_to_noise(influence_scores, baseline_stability)

        # Attach independent evidence lenses (semantic + empty LLM/human slots).
        # Qualitative difference review is selective and never auto-run here.
        influence_scores = [
            enrich_influence_item_for_review(item) for item in influence_scores
        ]

        # Per-focus ablation-condition stability (dispersion after removal vs baseline).
        influence_by_idx = {
            int(item['focus_index']): item for item in influence_scores
            if item.get('focus_index') is not None
        }
        for ablation, _perm, ablated_embeddings in scored_payloads:
            idx = int(ablation['focus_index'])
            inf = influence_by_idx.get(idx)
            if inf is None:
                continue
            stab = compute_ablation_stability(
                ablated_embeddings,
                baseline_stability,
                n_ablated_configured=n_ablated,
                t_obs=inf.get('t_obs'),
                standardized_effect=inf.get('standardized_effect'),
                behavioral_outcome=inf.get('behavioral_outcome'),
            )
            ablation['ablation_stability'] = stab
            inf['ablation_stability'] = stab

        n_attr = len(influence_scores)
        if n_ablated < 1:
            n_ablated = 1
        power_warning = power_guardrail_message(
            n_baseline, n_ablated, n_attr, alpha=alpha, n_permutations=n_permutations
        )
        # normalized_influence is percentage points: attributable foci sum to 100.
        cost_breakdown = self.cost_calculator.calculate_cost(
            int(input_tokens),
            int(output_tokens),
            total_embedding_tokens,
            self.model,
            self.provider_name,
        )
        summary = {item['focus']: item['normalized_influence'] for item in influence_scores}
        stability_summary = build_stability_summary(influence_scores)
        stability_scatter = build_stability_scatter_points(influence_scores)
        return {
            'baseline_output': baseline_outputs[0],
            'baseline_outputs': baseline_outputs,
            'ablation_results': ablation_results,
            'influence_scores': influence_scores,
            'baseline_stability': baseline_stability,
            'stability_summary': stability_summary,
            'stability_scatter': stability_scatter,
            'interpretation_axes': {
                'baseline_stability': (
                    'How much does the model vary when nothing changes?'
                ),
                'semantic_perturbation': (
                    'How far does behaviour move when this focus is removed?'
                ),
                'ablation_stability': (
                    'How variable is behaviour after this focus is removed?'
                ),
                'behavioral_outcome': (
                    'How does removal change the probability of the behaviour the user cares about?'
                ),
                'scatter': {
                    'x': 'Semantic perturbation (centroid distance / standardized effect)',
                    'y': 'Ablation-to-baseline mean pairwise dispersion ratio',
                    'y_reference': 1.0,
                },
            },
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
            'embedding_tokens': int(total_embedding_tokens),
            'prompt': prompt,
            'foci_list': classified,
            'model': self.model,
            'provider': self.provider_name,
            'power_warning': power_warning,
            'significance_method': 'permutation_bh',
        }

    def run_reported_focus_dynamics(
        self,
        prompt: str,
        foci_list: List[Dict],
        baseline_outputs: List[str],
        ablated_outputs: Dict,
        *,
        assessment_service=None,
        behavior_labels: Optional[Dict] = None,
        association_focus: Optional[str] = None,
    ) -> Dict:
        """
        Optional diagnostic: assess reported focus weights on every sample.

        Requires an AssessmentService-like object with ``assess_focus``.
        Does not modify permutation significance.
        """
        if assessment_service is None:
            raise ValueError('assessment_service is required for reported-focus dynamics')

        def assess_fn(p: str, output: str, foci: List[Dict]) -> Dict:
            return assessment_service.assess_focus(p, output, user_foci=foci)

        return build_reported_focus_dynamics(
            prompt=prompt,
            foci=foci_list,
            baseline_outputs=baseline_outputs,
            ablated_outputs=ablated_outputs,
            assess_fn=assess_fn,
            behavior_labels=behavior_labels,
            association_focus=association_focus,
        )
    
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
        
        classified = classify_foci_for_ablation(prompt, foci_list)
        
        try:
            baseline_outputs, tin, tout = self._sample_outputs(prompt, n_baseline, temperature)
        except Exception as e:
            raise Exception(f"Failed to generate baseline output: {e}") from e
        total_input_tokens += tin
        total_output_tokens += tout

        ablated_by_index: Dict[int, List[str]] = {}
        for i, focus in enumerate(classified):
            if not focus.get('attributable'):
                continue
            focus_name = focus.get('focus', f'Focus {i + 1}')
            ablated_prompt, _prompt_empty, _collapsed = delete_span(
                prompt, focus['char_start'], focus['char_end']
            )
            time.sleep(0.5)
            try:
                texts, tin, tout = self._sample_outputs(
                    ablated_prompt, n_ablated, temperature
                )
            except Exception as e:
                raise Exception(
                    f"Failed to generate ablated output for focus '{focus_name}': {e}"
                ) from e
            total_input_tokens += tin
            total_output_tokens += tout
            ablated_by_index[i] = texts

        return self.score_from_samples(
            prompt,
            foci_list,
            baseline_outputs,
            ablated_by_index,
            n_permutations=n_permutations,
            alpha=alpha,
            permutation_seed=permutation_seed,
            temperature=temperature,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
        )

    def refine_focus_stability_samples(
        self,
        prompt: str,
        foci_list: List[Dict],
        focus_index: int,
        baseline_outputs: List[str],
        existing_ablated_outputs: List[str],
        n_additional: int,
        *,
        n_permutations: int = DEFAULT_N_PERMUTATIONS,
        alpha: float = DEFAULT_ALPHA,
        permutation_seed: Optional[int] = None,
        temperature: float = 0.7,
        behavioral_criterion: Optional[str] = None,
        task_context: str = '',
        run_behavioral_judge: bool = False,
    ) -> Dict:
        """
        Generate extra ablated samples for one focus and refresh stability + permutation.

        Does not re-sample baseline or other foci.
        """
        require_stochastic_temperature(temperature)
        n_additional = int(n_additional)
        if n_additional < 1:
            raise ValueError('n_additional must be at least 1')
        idx = int(focus_index)
        classified = classify_foci_for_ablation(prompt, foci_list)
        if idx < 0 or idx >= len(classified):
            raise ValueError('focus_index out of range')
        focus = classified[idx]
        if not focus.get('attributable'):
            raise ValueError(
                f"Focus '{focus.get('focus')}' is not attributable ({focus.get('reason')})"
            )

        ablated_prompt, prompt_empty, _collapsed = delete_span(
            prompt, focus['char_start'], focus['char_end']
        )
        new_texts, tin, tout = self._sample_outputs(
            ablated_prompt, n_additional, temperature
        )
        merged = list(existing_ablated_outputs or []) + list(new_texts)
        merged = [str(t) for t in merged if str(t).strip()]
        if len(merged) < 2:
            raise ValueError('Need at least 2 ablated samples after merge for stability metrics')

        baseline_outputs = [str(t) for t in baseline_outputs if str(t).strip()]
        baseline_embeddings, base_tokens = (
            self.embedding_service.batch_embeddings_with_usage(baseline_outputs)
        )
        baseline_embeddings = np.asarray(baseline_embeddings, dtype=float)
        baseline_stability = compute_baseline_stability(baseline_embeddings)

        ablated_embeddings, abl_tokens = (
            self.embedding_service.batch_embeddings_with_usage(merged)
        )
        ablated_embeddings = np.asarray(ablated_embeddings, dtype=float)

        rng = np.random.default_rng(permutation_seed)
        perm = permutation_test(
            baseline_embeddings,
            ablated_embeddings,
            n_permutations=n_permutations,
            rng=rng,
        )
        t_obs = perm['t_obs']
        bh = benjamini_hochberg([perm['p_value']], alpha=alpha)[0]

        behavioral_outcome = None
        if run_behavioral_judge and (behavioral_criterion or '').strip():
            from services.behavioral_criterion_judge import BehavioralCriterionJudge

            judge = BehavioralCriterionJudge(
                self.provider, self.model, self.provider_name
            )
            base_j = judge.judge_many(
                criterion=behavioral_criterion,
                outputs=baseline_outputs,
                task_context=task_context,
                temperature=0.2,
            )
            abl_j = judge.judge_many(
                criterion=behavioral_criterion,
                outputs=merged,
                task_context=task_context,
                temperature=0.2,
            )
            behavioral_outcome = compare_behavioral_outcomes(base_j, abl_j)

        stab = compute_ablation_stability(
            ablated_embeddings,
            baseline_stability,
            n_ablated_configured=len(merged),
            t_obs=t_obs,
            standardized_effect=perm.get('standardized_effect'),
            behavioral_outcome=behavioral_outcome,
        )

        influence_row = enrich_influence_item_for_review({
            'focus': focus.get('focus'),
            'focus_index': idx,
            't_obs': float(t_obs),
            'influence': float(t_obs),
            'p_value': bh['p_value'],
            'q_value': bh['q_value'],
            'is_significant': bh['significant'],
            'standardized_effect': perm.get('standardized_effect'),
            'ablation_stability': stab,
            'behavioral_outcome': behavioral_outcome,
        })

        cost_breakdown = self.cost_calculator.calculate_cost(
            tin, tout, base_tokens + abl_tokens, self.model, self.provider_name
        )

        return {
            'focus_index': idx,
            'focus': focus.get('focus'),
            'ablated_outputs': merged,
            'n_ablated_samples': len(merged),
            'n_additional_generated': n_additional,
            'ablation_stability': stab,
            'semantic_perturbation': influence_row.get('semantic_perturbation'),
            'permutation': {
                't_obs': t_obs,
                'p_value': bh['p_value'],
                'q_value': bh['q_value'],
                'is_significant': bh['significant'],
                'standardized_effect': perm.get('standardized_effect'),
                'n_permutations': perm.get('n_permutations'),
            },
            'behavioral_outcome': behavioral_outcome,
            'cost_breakdown': cost_breakdown,
            'note': (
                'Refined ablation stability for this focus only. Other foci unchanged. '
                'BH q-value here is single-focus (not re-corrected across all foci).'
            ),
        }

    def attach_behavioral_outcome_dispersion(
        self,
        *,
        baseline_outputs: List[str],
        ablated_outputs: Dict,
        behavioral_criterion: str,
        task_context: str = '',
        temperature: float = 0.2,
    ) -> Dict[int, Dict]:
        """Judge baseline + each focus's ablated outputs against a user criterion."""
        if not (behavioral_criterion or '').strip():
            raise ValueError('behavioral_criterion is required')
        from services.behavioral_criterion_judge import BehavioralCriterionJudge

        judge = BehavioralCriterionJudge(
            self.provider, self.model, self.provider_name
        )
        baseline_j = judge.judge_many(
            criterion=behavioral_criterion,
            outputs=baseline_outputs,
            task_context=task_context,
            temperature=temperature,
        )
        out: Dict[int, Dict] = {}
        for key, texts in (ablated_outputs or {}).items():
            idx = int(key)
            abl_j = judge.judge_many(
                criterion=behavioral_criterion,
                outputs=list(texts or []),
                task_context=task_context,
                temperature=temperature,
            )
            comparison = compare_behavioral_outcomes(baseline_j, abl_j)
            out[idx] = comparison
        return out
