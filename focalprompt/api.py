#!/usr/bin/env python3
"""High-level research API wrapping existing analytical services."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Union

from services.assessor_factory import get_assessor
from services.assessment_service import AssessmentService
from services.ablation_service import AblationService
from services.embedding_service import EmbeddingService
from utils.inference_config import resolve_embedding_config


PathLike = Union[str, Path]


def _load_prompt(prompt: Union[str, PathLike]) -> str:
    p = Path(prompt)
    if p.exists() and p.is_file():
        return p.read_text(encoding='utf-8')
    return str(prompt)


def detect_foci(
    prompt: Union[str, PathLike],
    *,
    model: str = 'gpt-4o-mini',
    provider: str = 'openai',
    backend: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Dict[str, Any]:
    text = _load_prompt(prompt)
    assessor = get_assessor(
        model=model,
        provider=provider,
        backend=backend,
        api_key=api_key,
        base_url=base_url,
    )
    return AssessmentService(assessor).detect_foci(text)


def assess_focus(
    prompt: Union[str, PathLike],
    output: str,
    foci: Optional[List[Dict[str, Any]]] = None,
    *,
    model: str = 'gpt-4o-mini',
    provider: str = 'openai',
    backend: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Dict[str, Any]:
    text = _load_prompt(prompt)
    assessor = get_assessor(
        model=model,
        provider=provider,
        backend=backend,
        api_key=api_key,
        base_url=base_url,
    )
    return AssessmentService(assessor).assess_focus(text, output, user_foci=foci)


def ablate(
    prompt: Union[str, PathLike],
    foci: List[Dict[str, Any]],
    *,
    n_baseline: int = 10,
    n_ablated: int = 5,
    temperature: float = 0.7,
    model: str = 'gpt-4o-mini',
    provider: str = 'openai',
    backend: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    permutation_seed: Optional[int] = None,
) -> Dict[str, Any]:
    text = _load_prompt(prompt)
    assessor = get_assessor(
        model=model,
        provider=provider,
        backend=backend,
        api_key=api_key,
        base_url=base_url,
    )
    emb_cfg = resolve_embedding_config({
        'backend': backend,
        'api_key': api_key,
        'base_url': base_url,
        'provider': provider,
        'model': model,
    })
    embedding = EmbeddingService(
        api_key=emb_cfg['api_key'],
        base_url=emb_cfg['base_url'],
        model=emb_cfg['model'],
    )
    service = AblationService(
        assessor.provider,
        model,
        embedding_service=embedding,
        provider_name=getattr(assessor, 'provider_name', provider),
    )
    return service.run_ablation(
        text,
        foci,
        n_baseline=n_baseline,
        n_ablated=n_ablated,
        temperature=temperature,
        permutation_seed=permutation_seed,
    )


def analyze(
    prompt: Union[str, PathLike],
    *,
    output: Optional[str] = None,
    foci: Optional[List[Dict[str, Any]]] = None,
    n_baseline: int = 10,
    n_ablated: int = 5,
    temperature: float = 0.7,
    model: str = 'gpt-4o-mini',
    provider: str = 'openai',
    backend: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    permutation_seed: Optional[int] = None,
    run_assess: bool = True,
    run_ablation: bool = True,
) -> Dict[str, Any]:
    """
    End-to-end experiment: foci → optional reported focus → perturbation analysis.

    Returns a JSON-serializable dict with keys:
      - foci
      - reported_focus (Experiment A; None if skipped or no output)
      - perturbation (Experiment B; None if skipped)
      - comparison (Experiment C when both present)
      - meta
    """
    text = _load_prompt(prompt)
    meta = {
        'model': model,
        'provider': provider,
        'backend': backend,
        'temperature': temperature,
        'n_baseline': n_baseline,
        'n_ablated': n_ablated,
        'focalprompt_version': __import__('focalprompt').__version__,
    }
    if foci is None:
        detected = detect_foci(
            text, model=model, provider=provider, backend=backend,
            api_key=api_key, base_url=base_url,
        )
        foci = detected.get('foci') or []
    else:
        detected = {'foci': foci}

    reported = None
    if run_assess and output:
        reported = assess_focus(
            text, output, foci,
            model=model, provider=provider, backend=backend,
            api_key=api_key, base_url=base_url,
        )

    perturbation = None
    if run_ablation:
        perturbation = ablate(
            text, foci,
            n_baseline=n_baseline, n_ablated=n_ablated, temperature=temperature,
            model=model, provider=provider, backend=backend,
            api_key=api_key, base_url=base_url, permutation_seed=permutation_seed,
        )

    comparison = None
    if reported and perturbation:
        comparison = _compare_reported_vs_revealed(reported, perturbation)

    return {
        'foci': foci,
        'detect': detected,
        'reported_focus': reported,
        'perturbation': perturbation,
        'comparison': comparison,
        'meta': meta,
    }


def _compare_reported_vs_revealed(
    reported: Mapping[str, Any],
    perturbation: Mapping[str, Any],
) -> Dict[str, Any]:
    """Side-by-side reported scores vs multi-lens revealed sensitivity."""
    from services.behavioral_difference_service import multi_lens_faithfulness_label

    report_by = {
        (f.get('focus') or '').strip(): f
        for f in (reported.get('foci') or [])
    }
    scores = perturbation.get('influence_scores') or []
    if isinstance(scores, dict):
        scores = list(scores.values())
    rows = []
    for item in scores:
        name = (item.get('focus') or '').strip()
        rep = report_by.get(name) or {}
        sem = item.get('semantic_perturbation') or {}
        llm = item.get('llm_behavioral_difference') or {}
        hum = item.get('human_behavioral_difference') or {}

        semantic_sig = sem.get('is_significant', item.get('is_significant'))
        llm_material = None
        if llm.get('status') == 'complete':
            llm_material = bool(llm.get('material_behavioral_difference'))
        human_material = None
        if hum.get('status') == 'complete':
            hm = hum.get('material_behavioral_difference')
            human_material = True if hm is True else (False if hm is False else None)

        faithfulness = multi_lens_faithfulness_label(
            reported_score=rep.get('score'),
            semantic_significant=semantic_sig,
            llm_material=llm_material,
            human_material=human_material,
        )
        rows.append({
            'focus': name,
            'reported_score': rep.get('score'),
            'reported_explanation': rep.get('explanation'),
            't_obs': item.get('t_obs', sem.get('t_obs')),
            'influence': item.get('influence'),
            'normalized_influence': item.get(
                'normalized_influence', sem.get('normalized_influence')
            ),
            'p_value': item.get('p_value', sem.get('p_value')),
            'q_value': item.get('q_value', sem.get('q_value')),
            'is_significant': semantic_sig,
            'semantic_perturbation': sem or {
                't_obs': item.get('t_obs'),
                'normalized_influence': item.get('normalized_influence'),
                'standardized_effect': item.get('standardized_effect'),
                'p_value': item.get('p_value'),
                'q_value': item.get('q_value'),
                'is_significant': item.get('is_significant'),
            },
            'llm_behavioral_difference': llm,
            'human_behavioral_difference': hum,
            'faithfulness': faithfulness,
            'note': (
                'Reported focus is model self-assessment (behavioral), not '
                'transformer attention. Semantic perturbation is leave-one-out '
                'embedding-space shift. LLM/human behavioral-difference lenses '
                'assess observable change only — not quality or preference. '
                'Lenses are independent; disagreement is informative.'
            ),
        })
    return {
        'rows': rows,
        'framing': {
            'experiment_a': 'model-assessed / reported focus distribution',
            'experiment_b': (
                'semantic perturbation sensitivity (cheap first pass); optional '
                'LLM and human behavioral-difference review'
            ),
            'experiment_c': (
                'comparison of reported focus vs revealed sensitivity across '
                'independent evidence lenses (semantic / LLM / human)'
            ),
        },
    }


def save_result(result: Mapping[str, Any], path: PathLike) -> None:
    Path(path).write_text(json.dumps(result, indent=2, default=str), encoding='utf-8')
