#!/usr/bin/env python3
"""
Focus order / position sensitivity experiment service.

Measures behavioural sensitivity to focus ordering while preserving prompt
semantic completeness. Complements LOO ablation (content removal).
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Mapping, Optional, Sequence

import numpy as np

from services.behavioral_criterion_judge import BehavioralCriterionJudge
from services.cost_calculator import CostCalculator
from services.embedding_service import EmbeddingService
from utils.baseline_stability import compute_baseline_stability
from utils.gateway_chat import chat_completion as gateway_chat_completion
from utils.order_sensitivity_stats import (
    compare_behavioral_distributions,
    compare_condition_to_baseline,
    focus_positions_from_assignment,
    position_association_analysis,
    summarize_global_order_experiment,
    summarize_position_sweep,
)
from utils.permutation_test import DEFAULT_N_PERMUTATIONS, require_stochastic_temperature
from utils.prompt_order import (
    assignment_for_focus_at_slot,
    build_reordered_prompt,
    position_sweep_slot_indices,
    prepare_order_experiment,
    sample_random_assignments,
)

SAMPLE_GAP_SECONDS = 1.5
DEFAULT_K_PERMUTATIONS = 5
DEFAULT_M_SAMPLES = 3


class OrderSensitivityService:
    """Run global order sensitivity and single-focus position sweeps."""

    def __init__(
        self,
        provider,
        model: str,
        api_key: Optional[str] = None,
        embedding_service: Optional[EmbeddingService] = None,
        cost_calculator: Optional[CostCalculator] = None,
        provider_name: Optional[str] = None,
        judge_provider=None,
        judge_model: Optional[str] = None,
        judge_provider_name: Optional[str] = None,
    ):
        self.provider = provider
        self.model = model
        self.provider_name = provider_name or 'openai'
        self.judge_provider = judge_provider or provider
        self.judge_model = judge_model or model
        self.judge_provider_name = judge_provider_name or self.provider_name
        self.api_key = api_key
        # Planning and single-output requests do not need embedding credentials.
        self.embedding_service = embedding_service
        self.cost_calculator = cost_calculator or CostCalculator()

    def estimate_cost(
        self,
        *,
        k_permutations: int = DEFAULT_K_PERMUTATIONS,
        m_samples: int = DEFAULT_M_SAMPLES,
        n_position_slots: int = 5,
        run_position_sweep: bool = False,
        run_behavioral_judge: bool = False,
        n_baseline: int = 10,
    ) -> Dict[str, Any]:
        """Rough model-call estimate before running."""
        global_calls = int(k_permutations) * int(m_samples)
        sweep_calls = int(n_position_slots) * int(m_samples) if run_position_sweep else 0
        judge_calls = 0
        if run_behavioral_judge:
            judge_calls = n_baseline + global_calls + sweep_calls
        return {
            'global_order_model_calls': global_calls,
            'position_sweep_model_calls': sweep_calls,
            'behavioral_judge_calls': judge_calls,
            'total_model_calls': global_calls + sweep_calls + judge_calls,
            'note': 'Baseline outputs are reused from Experiment B; not re-generated.',
        }

    def _complete(self, user_content: str, temperature: float) -> Dict[str, Any]:
        response = gateway_chat_completion(
            self.provider,
            self.model,
            self.provider_name,
            [{'role': 'user', 'content': user_content}],
            temperature=temperature,
        )
        if not response or not response.get('content'):
            raise Exception('Model returned an empty response.')
        return response

    def _sample_outputs(self, prompt: str, n: int, temperature: float):
        if not (prompt or '').strip():
            return [''] * n, 0, 0
        outputs: List[str] = []
        in_tok = 0
        out_tok = 0
        for i in range(n):
            if i > 0:
                time.sleep(SAMPLE_GAP_SECONDS)
            response = self._complete(prompt, temperature)
            outputs.append(response['content'])
            usage = response.get('usage') or {}
            in_tok += int(usage.get('prompt_tokens') or 0)
            out_tok += int(usage.get('completion_tokens') or 0)
        return outputs, in_tok, out_tok

    def _embed(self, texts: Sequence[str]) -> tuple[np.ndarray, int]:
        if self.embedding_service is None:
            self.embedding_service = EmbeddingService()
        embeddings, tokens = self.embedding_service.batch_embeddings_with_usage(list(texts))
        return np.asarray(embeddings, dtype=float), int(tokens)

    def _maybe_judge(
        self,
        judge: Optional[BehavioralCriterionJudge],
        criterion: Optional[str],
        outputs: Sequence[str],
        task_context: str,
        temperature: float,
    ) -> Optional[List[Dict[str, Any]]]:
        if judge is None or not (criterion or '').strip():
            return None
        return judge.judge_many(
            criterion=criterion,
            outputs=outputs,
            task_context=task_context,
            temperature=temperature,
        )

    def run_focus_order_experiment(
        self,
        *,
        prompt: str,
        foci: Sequence[Mapping[str, Any]],
        baseline_outputs: Sequence[str],
        baseline_embeddings: Optional[Sequence[Sequence[float]]] = None,
        k_permutations: int = DEFAULT_K_PERMUTATIONS,
        m_samples: int = DEFAULT_M_SAMPLES,
        permutation_seed: int = 42,
        order_seed: int = 7,
        n_permutations: int = DEFAULT_N_PERMUTATIONS,
        statistical_seed: Optional[int] = None,
        temperature: float = 0.7,
        inputs: Optional[Dict[str, Any]] = None,
        user_policies: Optional[Mapping[Any, str]] = None,
        behavioral_criterion: Optional[str] = None,
        task_context: str = '',
        focus_index_for_sweep: Optional[int] = None,
        run_position_sweep: bool = False,
        run_behavioral_judge: bool = False,
        assessment_service=None,
        run_reported_focus: bool = False,
        plan_only: bool = False,
        recorded_samples: Optional[Mapping[str, Any]] = None,
        recorded_judgments: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Full focus order sensitivity payload for export.

        Reuses baseline_outputs from Experiment B. Optionally runs global order
        sampling, single-focus position sweep, behavioural judge, reported focus.
        """
        require_stochastic_temperature(temperature)
        if not 1 <= int(k_permutations) <= 20 or not 1 <= int(m_samples) <= 10:
            raise ValueError('Use 1–20 permutations and 1–10 samples per permutation.')
        baseline_outputs = [str(t) for t in baseline_outputs if str(t).strip()]
        if len(baseline_outputs) < 2:
            raise ValueError('Need at least 2 baseline outputs from Experiment B')

        prep = prepare_order_experiment(prompt, foci, user_policies=user_policies)
        if not prep.get('ok'):
            return {
                'ok': False,
                'error': prep.get('reason'),
                'ordering_policy': prep.get('ordering_policy'),
                'n_movable_slots': prep.get('n_movable_slots'),
            }

        classified = prep['classified']
        template = prep['template']
        policies = prep['ordering_policy']
        n_slots = int(prep['n_movable_slots'])

        assignments = sample_random_assignments(
            n_slots, int(k_permutations), seed=order_seed, include_identity=True,
        )
        conditions = []
        for perm_id, assignment in assignments:
            text, _ = build_reordered_prompt(prompt, classified, assignment, inputs=inputs, policies=policies)
            conditions.append({'id': f'permutation_{perm_id}', 'kind': 'permutation',
                               'permutation_id': perm_id, 'assignment': assignment,
                               'reordered_prompt': text, 'n_samples': int(m_samples)})
        if run_position_sweep:
            movable = list(template.get('movable_focus_indices') or [])
            if focus_index_for_sweep is None or int(focus_index_for_sweep) not in movable:
                raise ValueError('Select a movable attributable focus for the position sweep.')
            for slot in position_sweep_slot_indices(n_slots):
                assignment = assignment_for_focus_at_slot(n_slots, movable.index(int(focus_index_for_sweep)), slot)
                text, _ = build_reordered_prompt(prompt, classified, assignment, inputs=inputs, policies=policies)
                conditions.append({'id': f'position_{slot}', 'kind': 'position', 'slot_index': slot,
                                   'assignment': assignment, 'reordered_prompt': text, 'n_samples': int(m_samples)})
        if run_behavioral_judge and not (behavioral_criterion or '').strip():
            raise ValueError('Enter a behavioural criterion for the judge.')
        if plan_only:
            return {'ok': True, 'protocol': 'focus-order-v1', 'conditions': conditions,
                    'planned_samples': sum(c['n_samples'] for c in conditions),
                    'n_movable_slots': n_slots, 'baseline_outputs': baseline_outputs}

        # The resumable API scores already received samples. It must never launch
        # generation or judging again, even if imported work is incomplete.
        saved_embeddings = None
        if recorded_samples is not None:
            expected = {c['id']: c['n_samples'] for c in conditions}
            if set(recorded_samples) != set(expected):
                raise ValueError('Saved sample conditions do not match the order experiment.')
            for key, count in expected.items():
                rows = recorded_samples[key]
                if not isinstance(rows, list) or len(rows) != count or any(
                    not isinstance(s, dict) or not isinstance(s.get('content'), str) or not s['content'].strip() for s in rows
                ):
                    raise ValueError(f'Complete every sample for {key} before scoring.')
            if run_reported_focus:
                raise ValueError('Reported-focus assessment is not part of resumable order scoring.')
            if run_behavioral_judge:
                counts = {'baseline': len(baseline_outputs), **expected}
                if not isinstance(recorded_judgments, dict) or set(recorded_judgments) != set(counts):
                    raise ValueError('Complete all behavioural judgments before scoring.')
                for key, count in counts.items():
                    rows = recorded_judgments[key]
                    if not isinstance(rows, list) or len(rows) != count or any(
                        not isinstance(j, dict) or j.get('sample_index') != i
                        or j.get('classification') not in ('COMPLIES', 'AMBIGUOUS', 'VIOLATES')
                        or not isinstance(j.get('score'), (int, float)) or not 0 <= j['score'] <= 100
                        for i, j in enumerate(rows)
                    ):
                        raise ValueError(f'Invalid or incomplete behavioural judgments for {key}.')
            all_texts = baseline_outputs + [s['content'] for c in conditions for s in recorded_samples[c['id']]]
            all_embeddings, saved_embedding_tokens = self._embed(all_texts)
            baseline_embeddings = all_embeddings[:len(baseline_outputs)]
            saved_embeddings, offset = {}, len(baseline_outputs)
            for c in conditions:
                saved_embeddings[c['id']] = all_embeddings[offset:offset+c['n_samples']]
                offset += c['n_samples']

        def sample_condition(key, text):
            if recorded_samples is None:
                return self._sample_outputs(text, int(m_samples), temperature)
            rows = recorded_samples[key]
            return ([s['content'] for s in rows],
                    sum(int((s.get('usage') or {}).get('prompt_tokens') or 0) for s in rows),
                    sum(int((s.get('usage') or {}).get('completion_tokens') or 0) for s in rows))

        def judge_condition(key, texts):
            if recorded_samples is not None:
                return recorded_judgments[key] if run_behavioral_judge else None
            return self._maybe_judge(judge, behavioral_criterion, texts, task_context, temperature)

        def embed_condition(key, texts):
            return (saved_embeddings[key], 0) if saved_embeddings is not None else self._embed(texts)

        if baseline_embeddings is not None:
            base_emb = np.asarray(baseline_embeddings, dtype=float)
            emb_tokens = 0
        else:
            base_emb, emb_tokens = self._embed(baseline_outputs)
        if saved_embeddings is not None:
            emb_tokens = saved_embedding_tokens

        baseline_stability = compute_baseline_stability(base_emb)
        total_in = 0
        total_out = 0

        judge = None
        if recorded_samples is None and run_behavioral_judge and behavioral_criterion:
            judge = BehavioralCriterionJudge(
                self.judge_provider, self.judge_model, self.judge_provider_name
            )

        baseline_judgments = judge_condition('baseline', baseline_outputs)
        permutations: List[Dict[str, Any]] = []
        position_rows_for_assoc: List[Dict[str, Any]] = []

        for perm_id, assignment in assignments:
            reordered_prompt, recon_meta = build_reordered_prompt(
                prompt,
                classified,
                assignment,
                inputs=inputs,
                policies=policies,
            )
            condition_id = f'permutation_{perm_id}'
            texts, tin, tout = sample_condition(condition_id, reordered_prompt)
            total_in += tin
            total_out += tout
            cond_emb, et = embed_condition(condition_id, texts)
            emb_tokens += et
            stats = compare_condition_to_baseline(
                base_emb,
                cond_emb,
                baseline_stability,
                n_permutations=n_permutations,
                permutation_seed=statistical_seed,
            )
            positions = focus_positions_from_assignment(template, assignment)
            row: Dict[str, Any] = {
                'permutation_id': perm_id,
                'order_seed': order_seed,
                'assignment': list(assignment),
                'ordered_focus_names': recon_meta.get('ordered_focus_names'),
                'focus_positions': positions,
                'reordered_prompt': reordered_prompt,
                'reconstruction': recon_meta,
                'outputs': texts,
                'model': self.model,
                'provider': self.provider_name,
                'temperature': temperature,
                **stats,
            }
            judgments = judge_condition(condition_id, texts)
            if judgments is not None:
                row['behavioral_judgments'] = judgments
                if baseline_judgments is not None:
                    row['behavioral_comparison'] = compare_behavioral_distributions(
                        baseline_judgments, judgments
                    )
            permutations.append(row)
            position_rows_for_assoc.append(row)

        global_summary = summarize_global_order_experiment(permutations, baseline_stability)

        position_sweeps: List[Dict[str, Any]] = []
        if run_position_sweep and focus_index_for_sweep is not None:
            movable_indices_list = list(template.get('movable_focus_indices') or [])
            fi = int(focus_index_for_sweep)
            if fi not in movable_indices_list:
                raise ValueError(
                    f'focus_index_for_sweep {fi} is not a movable attributable focus'
                )
            movable_i = movable_indices_list.index(fi)
            focus_name = (classified[fi].get('focus') or f'Focus {fi}').strip()
            sweep_results: List[Dict[str, Any]] = []
            for slot in position_sweep_slot_indices(n_slots):
                assignment = assignment_for_focus_at_slot(n_slots, movable_i, slot)
                reordered_prompt, recon_meta = build_reordered_prompt(
                    prompt,
                    classified,
                    assignment,
                    inputs=inputs,
                    policies=policies,
                )
                condition_id = f'position_{slot}'
                texts, tin, tout = sample_condition(condition_id, reordered_prompt)
                total_in += tin
                total_out += tout
                cond_emb, et = embed_condition(condition_id, texts)
                emb_tokens += et
                stats = compare_condition_to_baseline(
                    base_emb,
                    cond_emb,
                    baseline_stability,
                    n_permutations=n_permutations,
                    permutation_seed=statistical_seed,
                )
                sweep_row = {
                    'focus_index': int(focus_index_for_sweep),
                    'focus': focus_name,
                    'slot_index': slot,
                    'assignment': assignment,
                    'ordered_focus_names': recon_meta.get('ordered_focus_names'),
                    'reordered_prompt': reordered_prompt,
                    'outputs': texts,
                    **stats,
                }
                judgments = judge_condition(condition_id, texts)
                if judgments is not None:
                    sweep_row['behavioral_judgments'] = judgments
                sweep_results.append(sweep_row)
            position_sweeps.append({
                'focus_index': int(focus_index_for_sweep),
                'focus': focus_name,
                'summary': summarize_position_sweep(
                    sweep_results, baseline_stability, focus_name
                ),
                'positions': sweep_results,
            })

        position_associations = [
            position_association_analysis(position_rows_for_assoc, name)
            for name in (template.get('movable_focus_names') or [])
        ]

        reported_focus_dynamics = None
        if run_reported_focus and assessment_service is not None:
            from utils.reported_focus_dynamics import build_reported_focus_dynamics

            def assess_fn(p, output, fl):
                return assessment_service.assess_focus(p, output, user_foci=fl)

            extra: Dict[int, List[str]] = {}
            for i, perm in enumerate(permutations):
                extra[1000 + i] = list(perm.get('outputs') or [])
            reported_focus_dynamics = build_reported_focus_dynamics(
                prompt=prompt,
                foci=foci,
                baseline_outputs=baseline_outputs,
                ablated_outputs=extra,
                assess_fn=assess_fn,
            )

        cost_breakdown = self.cost_calculator.calculate_cost(
            total_in, total_out, emb_tokens, self.model, self.provider_name
        )

        warnings: List[str] = list(baseline_stability.get('warnings') or [])
        if global_summary.get('advisory_ui'):
            warnings.append(str(global_summary['advisory_ui']))

        return {
            'ok': True,
            'experiment_type': 'focus_order_sensitivity',
            'ordering_policy': {str(k): v for k, v in policies.items()},
            'baseline_stability': baseline_stability,
            'baseline_outputs': baseline_outputs,
            'global_order_experiment': {
                'k_permutations': len(permutations),
                'm_samples_per_permutation': int(m_samples),
                'order_seed': order_seed,
                'summary': global_summary,
                'permutations': permutations,
                'position_associations_exploratory': position_associations,
            },
            'position_sweeps': position_sweeps,
            'behavioral_criterion': behavioral_criterion,
            'baseline_behavioral_judgments': baseline_judgments,
            'reported_focus_dynamics': reported_focus_dynamics,
            'n_baseline': len(baseline_outputs),
            'n_movable_slots': n_slots,
            'movable_focus_names': template.get('movable_focus_names'),
            'template_metadata': {
                'n_slots': n_slots,
                'movable_focus_indices': template.get('movable_focus_indices'),
            },
            'model': self.model,
            'provider': self.provider_name,
            'temperature': temperature,
            'embedding_model': getattr(self.embedding_service, 'model', None),
            'statistical_method': 'permutation_test_centroid_cosine_distance',
            'cost_breakdown': cost_breakdown,
            'warnings': warnings,
            'limitations': [
                'Order sensitivity is behavioural embedding-space testing — not mechanistic attention.',
                'Global permutation position associations are exploratory, not causal.',
                'Behavioural criterion judgments are LLM rubric scores, not ground truth.',
                'Self-reported focus weights describe model-stated emphasis, not internal activations.',
            ],
        }

    def run_scenario_order_experiment(
        self,
        *,
        scenario: Mapping[str, Any],
        foci: Sequence[Mapping[str, Any]],
        baseline_outputs: Sequence[str],
        inputs: Optional[Mapping[str, Any]] = None,
        focus_index_for_sweep: Optional[int] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Run an order experiment inside one message/role boundary.

        The established statistical engine operates on one text document. A
        proxy maps each reordered document back onto the selected scenario
        message before generation, so retained history and output contracts
        remain unchanged.
        """
        from copy import deepcopy

        from utils.inference_scenario import (
            bind_scenario_inputs,
            complete_scenario,
            normalize_scenario_foci,
            scenario_order_groups,
        )

        bound, binding = bind_scenario_inputs(scenario, inputs)
        classified = normalize_scenario_foci(bound, foci)
        groups = scenario_order_groups(bound, classified)
        if not groups:
            return {
                'ok': False,
                'error': 'No foci are reorderable within the same message and role.',
                'ordering_groups': [],
            }
        selected_group = None
        if focus_index_for_sweep is not None:
            index = int(focus_index_for_sweep)
            selected_group = next(
                (group for group in groups if index in group['focus_indices']), None
            )
        if selected_group is None:
            selected_group = groups[0]
        message_id = selected_group['message_id']
        target = next(message for message in bound['messages'] if message['id'] == message_id)
        global_indices = list(selected_group['focus_indices'])
        local_foci: List[Dict[str, Any]] = []
        for global_index in global_indices:
            item = deepcopy(classified[global_index])
            item['spans'] = [
                {
                    'char_start': span['char_start'],
                    'char_end': span['char_end'],
                    'text_snapshot': span['text_snapshot'],
                }
                for span in item['spans']
            ]
            item.pop('message_id', None)
            item.pop('message_ids', None)
            local_foci.append(item)

        translations: List[Dict[str, Any]] = []
        outer = self

        class ScenarioProxy:
            def chat_completion(
                self,
                messages,
                model,
                temperature=0.7,
                response_format=None,
                provider=None,
                max_tokens=None,
            ):
                reordered_text = messages[-1]['content']
                arm = deepcopy(bound)
                for message in arm['messages']:
                    if message['id'] == message_id:
                        message['content'] = reordered_text
                        break
                response = complete_scenario(
                    outer.provider,
                    outer.model,
                    outer.provider_name,
                    arm,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                translations.append(dict(response.get('scenario_metadata') or {}))
                return response

        proxy_service = OrderSensitivityService(
            ScenarioProxy(),
            self.model,
            api_key=self.api_key,
            embedding_service=self.embedding_service,
            cost_calculator=self.cost_calculator,
            provider_name=self.provider_name,
            judge_provider=self.judge_provider,
            judge_model=self.judge_model,
            judge_provider_name=self.judge_provider_name,
        )
        local_sweep = None
        if focus_index_for_sweep is not None and int(focus_index_for_sweep) in global_indices:
            local_sweep = global_indices.index(int(focus_index_for_sweep))
        result = proxy_service.run_focus_order_experiment(
            prompt=target['content'],
            foci=local_foci,
            baseline_outputs=baseline_outputs,
            focus_index_for_sweep=local_sweep,
            **kwargs,
        )
        if kwargs.get('recorded_samples') is not None:
            translations = [dict(sample.get('scenario_metadata') or {})
                            for samples in kwargs['recorded_samples'].values() for sample in samples]
        result['scenario'] = bound
        result['scenario_metadata'] = {
            'input_binding': binding,
            'ordering_message_id': message_id,
            'ordering_role': selected_group['role'],
            'focus_index_map': {
                str(local): global_index
                for local, global_index in enumerate(global_indices)
            },
            'provider_translations': translations,
        }
        result['ordering_groups'] = groups
        result['cross_message_foci_fixed'] = [
            index for index in range(len(classified)) if index not in global_indices
        ]
        if kwargs.get('plan_only'):
            for condition in result.get('conditions', []):
                arm = deepcopy(bound)
                next(m for m in arm['messages'] if m['id'] == message_id)['content'] = condition['reordered_prompt']
                condition['scenario'] = arm
        return result
