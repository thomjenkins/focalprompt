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
from utils.inference_scenario import (
    normalize_scenario_input,
    scenario_analysis_document,
    validate_scenario,
)


PathLike = Union[str, Path]


def _load_prompt(prompt: Union[str, PathLike]) -> str:
    p = Path(prompt)
    if p.exists() and p.is_file():
        return p.read_text(encoding='utf-8')
    return str(prompt)


def _load_scenario(value: Union[Mapping[str, Any], PathLike]) -> Dict[str, Any]:
    if isinstance(value, Mapping):
        return validate_scenario(value)
    path = Path(value)
    if not path.exists() or not path.is_file():
        raise ValueError(f'Scenario file not found: {value}')
    return validate_scenario(json.loads(path.read_text(encoding='utf-8')))


def detect_foci(
    prompt: Optional[Union[str, PathLike]] = None,
    *,
    scenario: Optional[Union[Mapping[str, Any], PathLike]] = None,
    model: str = 'gpt-4o-mini',
    provider: str = 'openai',
    backend: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Dict[str, Any]:
    loaded = _load_scenario(scenario) if scenario is not None else None
    text = _load_prompt(prompt) if prompt is not None else None
    resolved, is_legacy = normalize_scenario_input(scenario=loaded, prompt=text)
    assessor = get_assessor(
        model=model,
        provider=provider,
        backend=backend,
        api_key=api_key,
        base_url=base_url,
    )
    service = AssessmentService(assessor)
    if is_legacy:
        # Legacy prompts keep the flat report: coverage.uncovered_spans and the
        # span-size / overlap quality keys have no per-message equivalent.
        return service.detect_foci(str(text))
    return service.detect_foci_scenario(resolved)


def assess_focus(
    prompt: Optional[Union[str, PathLike]] = None,
    output: str = '',
    foci: Optional[List[Dict[str, Any]]] = None,
    *,
    scenario: Optional[Union[Mapping[str, Any], PathLike]] = None,
    model: str = 'gpt-4o-mini',
    provider: str = 'openai',
    backend: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Dict[str, Any]:
    if not output:
        raise ValueError('Output is required')
    loaded = _load_scenario(scenario) if scenario is not None else None
    text = _load_prompt(prompt) if prompt is not None else None
    resolved, is_legacy = normalize_scenario_input(scenario=loaded, prompt=text)
    analysis_text = str(text) if is_legacy else scenario_analysis_document(resolved)
    assessor = get_assessor(
        model=model,
        provider=provider,
        backend=backend,
        api_key=api_key,
        base_url=base_url,
    )
    return AssessmentService(assessor).assess_focus(
        analysis_text,
        output,
        user_foci=foci,
        scenario=None if is_legacy else resolved,
    )


def generate_output(
    prompt: Optional[Union[str, PathLike]] = None,
    *,
    scenario: Optional[Union[Mapping[str, Any], PathLike]] = None,
    inputs: Optional[Mapping[str, Any]] = None,
    temperature: float = 0.7,
    model: str = 'gpt-4o-mini',
    provider: str = 'openai',
    backend: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate one model-under-test response from one canonical source."""
    loaded = _load_scenario(scenario) if scenario is not None else None
    text = _load_prompt(prompt) if prompt is not None else None
    resolved, is_legacy = normalize_scenario_input(scenario=loaded, prompt=text)
    assessor = get_assessor(
        model=model,
        provider=provider,
        backend=backend,
        api_key=api_key,
        base_url=base_url,
    )
    response = assessor.generate_output_response(
        str(text) if is_legacy else None,
        scenario=None if is_legacy else resolved,
        inputs=inputs,
        temperature=temperature,
    )
    result = {
        'output': response['content'],
        'scenario': response.get('scenario', resolved),
        'scenario_metadata': response.get('scenario_metadata'),
    }
    if 'parsed_output' in response:
        result['parsed_output'] = response['parsed_output']
    return result


def ablate(
    prompt: Optional[Union[str, PathLike]] = None,
    foci: Optional[List[Dict[str, Any]]] = None,
    *,
    scenario: Optional[Union[Mapping[str, Any], PathLike]] = None,
    inputs: Optional[Mapping[str, Any]] = None,
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
    if not foci:
        raise ValueError('Foci are required')
    loaded = _load_scenario(scenario) if scenario is not None else None
    text = _load_prompt(prompt) if prompt is not None else None
    resolved, is_legacy = normalize_scenario_input(scenario=loaded, prompt=text)
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
    if is_legacy:
        return service.run_ablation(
            str(text), foci, n_baseline=n_baseline, n_ablated=n_ablated,
            temperature=temperature, permutation_seed=permutation_seed,
        )
    return service.run_scenario_ablation(
        resolved, foci, inputs=inputs, n_baseline=n_baseline,
        n_ablated=n_ablated, temperature=temperature,
        permutation_seed=permutation_seed,
    )


def analyze(
    prompt: Optional[Union[str, PathLike]] = None,
    *,
    scenario: Optional[Union[Mapping[str, Any], PathLike]] = None,
    inputs: Optional[Mapping[str, Any]] = None,
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
    loaded = _load_scenario(scenario) if scenario is not None else None
    text = _load_prompt(prompt) if prompt is not None else None
    resolved, is_legacy = normalize_scenario_input(scenario=loaded, prompt=text)
    meta = {
        'model': model,
        'provider': provider,
        'backend': backend,
        'temperature': temperature,
        'n_baseline': n_baseline,
        'n_ablated': n_ablated,
        'focalprompt_version': __import__('focalprompt').__version__,
        'scenario_version': resolved['version'],
        'legacy_prompt': is_legacy,
    }
    if foci is None:
        if is_legacy:
            detected = detect_foci(
                text, model=model, provider=provider, backend=backend,
                api_key=api_key, base_url=base_url,
            )
        else:
            detected = detect_foci(
                scenario=resolved, model=model, provider=provider, backend=backend,
                api_key=api_key, base_url=base_url,
            )
        foci = detected.get('foci') or []
    else:
        detected = {'foci': foci}

    reported = None
    if run_assess and output:
        if is_legacy:
            reported = assess_focus(
                text, output, foci, model=model, provider=provider, backend=backend,
                api_key=api_key, base_url=base_url,
            )
        else:
            reported = assess_focus(
                None, output, foci, scenario=resolved, model=model,
                provider=provider, backend=backend, api_key=api_key,
                base_url=base_url,
            )

    perturbation = None
    if run_ablation:
        perturbation = ablate(
            text if is_legacy else None, foci,
            scenario=None if is_legacy else resolved,
            inputs=inputs,
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
        'scenario': resolved,
    }


def _compare_reported_vs_revealed(
    reported: Mapping[str, Any],
    perturbation: Mapping[str, Any],
) -> Dict[str, Any]:
    """Side-by-side reported scores vs multi-lens revealed sensitivity."""
    from services.behavioral_difference_service import compare_reported_vs_revealed

    return compare_reported_vs_revealed(reported, perturbation)


def save_result(result: Mapping[str, Any], path: PathLike) -> None:
    Path(path).write_text(json.dumps(result, indent=2, default=str), encoding='utf-8')
