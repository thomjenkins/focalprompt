"""No-focus → singleton → full → leave-one-out experiments using existing scoring."""
from copy import deepcopy
import hashlib
import json
import math

import numpy as np

from services.ablation_service import AblationService
from utils.focus_variants import compose_scenario_foci, prepare_focus_variants
from utils.inference_scenario import ablate_scenario, bind_scenario_inputs, compile_scenario
from utils.permutation_test import (
    benjamini_hochberg, cosine_distance_centroids, permutation_test,
    require_stochastic_temperature,
)
from utils.ablation_stability import NEAR_ZERO_BASELINE_DISPERSION
from utils.pairwise_resemblance import pairwise_resemblance

PROTOCOL = 'singleton-focus-v1'


def integer(value, name, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f'{name} must be an integer from {minimum} to {maximum}.')
    return value


def build_plan(scenario, foci, *, n_baseline=10, n_ablated=5, temperature=0.7, inputs=None):
    require_stochastic_temperature(temperature)
    if not math.isfinite(float(temperature)) or float(temperature) > 2:
        raise ValueError('Temperature must be greater than zero and at most 2.')
    integer(n_baseline, 'n_baseline', 1, 50)
    integer(n_ablated, 'n_ablated', 1, 25)
    scenario, binding = bind_scenario_inputs(scenario, inputs)
    scenario, grounded = prepare_focus_variants(scenario, foci)
    if len(grounded) > 60:
        raise ValueError('This experiment supports up to 60 foci.')
    variants, pools = [], {}

    def add(variant_id, kind, arm, count, index=None, **metadata):
        # Preflight every condition before scheduling paid requests. A retained
        # blank row must not conceal removal of the only usable user message.
        compiled = compile_scenario(arm)
        # All pools belong to this one model/temperature context. Only exact
        # requests share samples; no global cache suppresses stochastic draws.
        key = hashlib.sha256(json.dumps(arm, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        variant = {'id': variant_id, 'kind': kind, 'focus_index': index,
                   'pool_id': key, 'n_samples': count, 'scenario': arm,
                   'omitted_blank_message_ids': compiled['metadata']['omitted_blank_message_ids'], **metadata}
        variants.append(variant)
        pool = pools.setdefault(key, {'id': key, 'scenario': arm, 'n_samples': count,
                                    'kind': kind, 'focus_index': index, 'variants': []})
        pool['n_samples'] = max(pool['n_samples'], count)
        pool['variants'].append(variant_id)

    add('full', 'baseline', scenario, n_baseline)
    empty = compose_scenario_foci(scenario, grounded, [], preserve_whitespace=True)
    add('no_focus', 'no_focus', empty['scenario'], n_baseline)
    for i, focus in enumerate(grounded):
        one = compose_scenario_foci(scenario, grounded, [i], preserve_whitespace=True)
        add(f'singleton_{i}', 'singleton', one['scenario'], n_ablated, i,
            shared_text_retained_for_excluded=one['shared_text_retained_for_excluded'])
        arm, deletion = ablate_scenario(scenario, focus)
        add(f'leave_one_out_{i}', 'ablated', arm, n_ablated, i, **deletion)
    return {'protocol': PROTOCOL, 'scenario': scenario, 'foci': grounded, 'input_binding': binding,
            'variants': variants, 'pools': list(pools.values()),
            'n_baseline': n_baseline, 'n_ablated': n_ablated, 'temperature': temperature,
            'planned_calls': sum(p['n_samples'] for p in pools.values()),
            'calls_without_reuse': sum(v['n_samples'] for v in variants)}


class CachedEmbeddings:
    """One scoring request reuses embeddings across existing and new comparisons."""
    def __init__(self, service, texts):
        self.vectors, self.tokens = {}, 0
        unique = list(dict.fromkeys(texts))
        for start in range(0, len(unique), 64):
            batch = unique[start:start + 64]
            vectors, tokens = service.batch_embeddings_with_usage(batch)
            arr = np.asarray(vectors, dtype=float)
            if (arr.ndim != 2 or arr.shape[0] != len(batch) or arr.shape[1] < 1
                    or not np.isfinite(arr).all() or np.any(np.linalg.norm(arr, axis=1) == 0)):
                raise ValueError('The embedding evaluator returned invalid or zero-length vectors.')
            self.vectors.update(zip(batch, arr))
            self.tokens += int(tokens)
        if len({v.shape for v in self.vectors.values()}) != 1:
            raise ValueError('The embedding evaluator returned inconsistent dimensions.')

    def batch_embeddings_with_usage(self, texts):
        return [self.vectors[text] for text in texts], 0

    def array(self, texts):
        return np.asarray([self.vectors[text] for text in texts], dtype=float)


def _validated_samples(plan, samples):
    if not isinstance(samples, dict) or set(samples) != {p['id'] for p in plan['pools']}:
        raise ValueError('Supply exactly the sample pools returned by the experiment plan.')
    all_texts, input_tokens, output_tokens, reused = [], 0, 0, 0
    for pool in plan['pools']:
        entries = samples[pool['id']]
        if not isinstance(entries, list) or len(entries) != pool['n_samples']:
            raise ValueError('Finish every sample pool before scoring.')
        for sample in entries:
            if not isinstance(sample, dict) or not isinstance(sample.get('content'), str) or not sample['content'].strip():
                raise ValueError('Every sample must contain a nonempty output.')
            if sample.get('scenario') is not None and sample['scenario'] != pool['scenario']:
                raise ValueError('A saved sample does not match its planned scenario.')
            all_texts.append(sample['content'])
            if sample.get('reused_from'):
                reused += 1
            else:
                usage = sample.get('usage') or {}
                input_tokens += max(0, int(usage.get('prompt_tokens') or 0))
                output_tokens += max(0, int(usage.get('completion_tokens') or 0))
    return all_texts, input_tokens, output_tokens, reused


def _sample_arms(plan, samples):
    return {v['id']: {**v, 'outputs': [s['content'] for s in samples[v['pool_id']]][:v['n_samples']]}
            for v in plan['variants']}


def score_pairwise(service, scenario, foci, samples, *, n_baseline=10, n_ablated=5, temperature=0.7):
    """Upgrade completed saved runs using embeddings only, without resampling."""
    plan = build_plan(scenario, foci, n_baseline=n_baseline, n_ablated=n_ablated, temperature=temperature)
    texts, _, _, _ = _validated_samples(plan, samples)
    cache = CachedEmbeddings(service.embedding_service, texts)
    result = pairwise_resemblance(plan, _sample_arms(plan, samples), cache)
    result.update(embedding_tokens=cache.tokens,
                  evaluator_model=getattr(service.embedding_service, 'model', None),
                  cost_breakdown=service.cost_calculator.calculate_cost(0, 0, cache.tokens, service.model, service.provider_name))
    return result


def score_samples(service, scenario, foci, samples, *, n_baseline=10, n_ablated=5,
                  temperature=0.7, n_permutations=10000, alpha=0.05, permutation_seed=None):
    plan = build_plan(scenario, foci, n_baseline=n_baseline, n_ablated=n_ablated, temperature=temperature)
    integer(n_permutations, 'n_permutations', 1, 10000)
    if type(alpha) not in (int, float) or not math.isfinite(alpha) or not 0 < alpha < 1:
        raise ValueError('alpha must be between 0 and 1.')
    if permutation_seed is not None:
        integer(permutation_seed, 'permutation_seed', 0, 2**32 - 1)
    all_texts, input_tokens, output_tokens, reused = _validated_samples(plan, samples)
    cache = CachedEmbeddings(service.embedding_service, all_texts)
    arms = _sample_arms(plan, samples)
    full, empty = arms['full']['outputs'], arms['no_focus']['outputs']
    # The original necessity engine, including its BH family and diagnostics,
    # sees exactly the same full/LOO samples and random seed as before.
    scorer = AblationService(service.provider, service.model, provider_name=service.provider_name,
                             embedding_service=cache, cost_calculator=service.cost_calculator)
    necessity = scorer.score_scenario_from_samples(
        plan['scenario'], foci, full, {i: arms[f'leave_one_out_{i}']['outputs'] for i in range(len(foci))},
        n_permutations=n_permutations, alpha=alpha, permutation_seed=permutation_seed, temperature=temperature)
    rng = np.random.default_rng(permutation_seed)
    contrast = permutation_test(cache.array(empty), cache.array(full), n_permutations=n_permutations, rng=rng)
    distance = contrast['t_obs']
    # Null p95 gives a descriptive sampling-noise floor. At n=1 there is no
    # useful noise estimate, so only the existing numerical tolerance applies.
    tolerance = max(NEAR_ZERO_BASELINE_DISPERSION, contrast['null_p95'] if min(len(full), len(empty)) >= 2 else 0)
    low = distance <= tolerance
    reason = ('Full vs no-focus centroid distance is at or below the numerical/sampling-noise threshold. '
              'Normalized scores are unavailable; raw comparisons remain valid descriptive distances.' if low else None)
    necessity_by_index = {r['focus_index']: r for r in necessity['influence_scores']}
    rows = []
    for i, focus in enumerate(plan['foci']):
        single = arms[f'singleton_{i}']['outputs']
        influence = permutation_test(cache.array(empty), cache.array(single), n_permutations=n_permutations, rng=rng)
        to_full = cosine_distance_centroids(cache.array(single), cache.array(full))
        rows.append({'focus_index': i, 'focus_id': focus.get('id'), 'focus': focus['focus'],
                     'spans': focus['spans'], 'singleton_output': single[0], 'singleton_outputs': single,
                     'influence': influence['t_obs'], 'influence_comparison': influence,
                     'normalized_influence': None if low else influence['t_obs'] / distance,
                     'sufficiency': None if low else (distance - to_full) / distance,
                     'singleton_full_distance': to_full,
                     'necessity': necessity_by_index[i]['t_obs'], 'necessity_comparison': necessity_by_index[i],
                     'leave_one_out_outputs': arms[f'leave_one_out_{i}']['outputs'],
                     'shared_text_retained_for_excluded': arms[f'singleton_{i}']['shared_text_retained_for_excluded']})
    for row, adjusted in zip(rows, benjamini_hochberg([r['influence_comparison']['p_value'] for r in rows], alpha=alpha)):
        row['influence_comparison'].update(adjusted)
    return {'protocol': PROTOCOL, 'model': service.model, 'provider': service.provider_name,
            'context': {'scenario': plan['scenario'], 'foci': deepcopy(foci),
                'model': {'model': service.model, 'provider': service.provider_name},
                'temperature': temperature, 'n_baseline': n_baseline, 'n_ablated': n_ablated},
            'plan': plan, 'samples': deepcopy(samples), 'arms': arms, 'focus_results': rows,
            'pairwise_resemblance': pairwise_resemblance(plan, arms, cache) | {
                'evaluator_model': getattr(service.embedding_service, 'model', None)},
            'full_output': full[0], 'full_outputs': full, 'no_focus_output': empty[0], 'no_focus_outputs': empty,
            'full_no_focus_distance': distance, 'full_no_focus_comparison': contrast,
            'low_behavioral_contrast': low, 'contrast_threshold': tolerance,
            'contrast_threshold_method': 'max(1e-6, full_vs_no_focus_permutation_null_p95) when both n>=2; otherwise 1e-6',
            'normalized_metrics_note': reason, 'necessity_analysis': necessity,
            'evaluator': {'method': 'cosine_distance_between_embedding_centroids',
                          'model': getattr(service.embedding_service, 'model', None)},
            'n_permutations': n_permutations, 'alpha': alpha, 'permutation_seed': permutation_seed,
            'reused_samples': reused, 'new_samples': len(all_texts) - reused,
            'embedding_tokens': cache.tokens,
            'cost_breakdown': service.cost_calculator.calculate_cost(input_tokens, output_tokens, cache.tokens,
                                                                     service.model, service.provider_name),
            'notes': [
                'Influence compares singleton vs no-focus; necessity retains the existing leave-one-out statistic.',
                'Normalized influence is a ratio to the full/no-focus shift, not a percentage allocation. It may exceed 1.',
                'Sufficiency may be negative. A shared pool reuses the same sample prefix for equivalent prompts.',
                'Centroid comparisons are descriptive, can miss output modes, and do not measure task quality or internal attention.',
                'High sufficiency with low necessity can suggest redundancy; the reverse can suggest context dependence. '
                'These conditions do not uniquely identify interactions; pairwise/factorial interventions are needed.',
                'Singletons preserve shared selected text; leave-one-out deletes the target spans even where other foci overlap.',
            ]}
