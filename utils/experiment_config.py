#!/usr/bin/env python3
"""
Experiment configuration: copy, cost, sample-size suggestions, and live preview.

Preview math calls the same `power_guardrail` / permutation-regime helpers as
the API. No change to the permutation test itself.
"""

from __future__ import annotations

from math import comb
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from utils.permutation_test import (
    DEFAULT_ALPHA,
    DEFAULT_N_PERMUTATIONS,
    min_achievable_pvalue,
    monte_carlo_pvalue_se,
    power_guardrail,
    stochastic_temperature_message,
    design_test_type,
    uses_exact_enumeration,
)

STOCHASTIC_TEMPERATURE_TEMPLATE = (
    "Permutation test requires output stochasticity: temperature must be > 0 "
    "(got {temperature}). Repeated samples of the same prompt must be allowed "
    "to vary; set temperature above 0."
)

DEFAULT_TEMPERATURE = 0.7
TEMPERATURE_MIN = 0.1
TEMPERATURE_MAX = 2.0
TEMPERATURE_STEP = 0.1
DEFAULT_N_BASELINE = 10
DEFAULT_N_ABLATED = 5
N_BASELINE_MIN = 5
N_BASELINE_MAX = 50
N_ABLATED_MIN = 3
N_ABLATED_MAX = 25

TEMPERATURE_HELP = (
    "Use the temperature your prompt runs at in production. Results describe "
    "the model's behaviour at this temperature only."
)

TEMPERATURE_HIGH = (
    "High temperature widens normal output variation, so subtle effects need "
    "more samples to detect."
)

SUGGESTION_LABEL = "suggested for this temperature"

SUGGESTION_TOOLTIP = (
    "A heuristic starting point. If results warn about power or sit near the "
    "threshold, increase ablated samples."
)

COST_LINE_COUNTED = "This experiment will make {n_calls} model calls."

COST_LINE_FORMULA = (
    "This experiment will make {n_baseline} + {n_ablated} × n_foci model calls."
)

POWER_OK = "This design can detect effects at your significance level"

POWER_FAIL = (
    "With {n_foci} foci, this design cannot reach significance after correction. "
    "Increase samples."
)

EXACT_DISCLOSURE_TEMPLATE = (
    "Significance: exact test ({n_assignments} enumerated group assignments)"
)

SAMPLED_DISCLOSURE_TEMPLATE = (
    "Significance: 10,000 sampled permutations (p-value margin ~±{se})"
)

RUN_HEADER_TEMPLATE = (
    "Run at temperature {t}, {n_baseline}+{n_ablated} samples per focus, "
    "{test_type} test."
)

EXPERIMENT_COPY = {
    'TEMPERATURE_HELP': TEMPERATURE_HELP,
    'TEMPERATURE_HIGH': TEMPERATURE_HIGH,
    'SUGGESTION_LABEL': SUGGESTION_LABEL,
    'SUGGESTION_TOOLTIP': SUGGESTION_TOOLTIP,
    'COST_LINE_COUNTED': COST_LINE_COUNTED,
    'COST_LINE_FORMULA': COST_LINE_FORMULA,
    'POWER_OK': POWER_OK,
    'POWER_FAIL': POWER_FAIL,
    'EXACT_DISCLOSURE_TEMPLATE': EXACT_DISCLOSURE_TEMPLATE,
    'SAMPLED_DISCLOSURE_TEMPLATE': SAMPLED_DISCLOSURE_TEMPLATE,
    'RUN_HEADER_TEMPLATE': RUN_HEADER_TEMPLATE,
    'STOCHASTIC_TEMPERATURE_TEMPLATE': STOCHASTIC_TEMPERATURE_TEMPLATE,
}


def format_temperature(temperature: float) -> str:
    return f'{float(temperature):.1f}'


def temperature_rejection(temperature: Any) -> Optional[str]:
    """Client- and server-side: None if ok, else the stochasticity explanation."""
    if temperature is None:
        return stochastic_temperature_message(temperature)
    try:
        t = float(temperature)
    except (TypeError, ValueError):
        return stochastic_temperature_message(temperature)
    if t <= 0:
        return stochastic_temperature_message(temperature)
    return None


def suggested_sample_sizes(temperature: float) -> Tuple[int, int]:
    """Heuristic starting point. t < 0.5 and 0.5–1.0 → 10/5; t > 1.0 → 15/8."""
    t = float(temperature)
    if t > 1.0:
        return (15, 8)
    return (10, 5)


def clamp_n_baseline(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = DEFAULT_N_BASELINE
    return max(N_BASELINE_MIN, min(N_BASELINE_MAX, n))


def clamp_n_ablated(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = DEFAULT_N_ABLATED
    return max(N_ABLATED_MIN, min(N_ABLATED_MAX, n))


def model_call_count(n_baseline: int, n_ablated: int, n_attributable_foci: int) -> int:
    return int(n_baseline) + int(n_ablated) * int(n_attributable_foci)


def count_preview_attributable(foci: Optional[Sequence[Mapping[str, Any]]]) -> int:
    """Client preview: tagged foci that are not runtime slots."""
    if not foci:
        return 0
    n = 0
    for focus in foci:
        if not focus.get('is_dynamic'):
            n += 1
    return n


def format_cost_line(
    n_baseline: int,
    n_ablated: int,
    n_attributable_foci: Optional[int] = None,
    foci_tagged: bool = False,
) -> str:
    if not foci_tagged:
        return COST_LINE_FORMULA.format(
            n_baseline=int(n_baseline),
            n_ablated=int(n_ablated),
        )
    n_calls = model_call_count(n_baseline, n_ablated, int(n_attributable_foci or 0))
    return COST_LINE_COUNTED.format(n_calls=n_calls)


def format_permutation_disclosure(
    n_baseline: int,
    n_ablated: int,
    n_permutations: int = DEFAULT_N_PERMUTATIONS,
) -> str:
    if uses_exact_enumeration(n_baseline, n_ablated, n_permutations):
        n_assignments = comb(int(n_baseline) + int(n_ablated), int(n_ablated))
        return EXACT_DISCLOSURE_TEMPLATE.format(
            n_assignments=f'{n_assignments:,}'
        )
    se = monte_carlo_pvalue_se(0.05, n_permutations)
    return SAMPLED_DISCLOSURE_TEMPLATE.format(se=f'{se:.3f}')


def format_power_preview_line(
    n_baseline: int,
    n_ablated: int,
    n_foci: int,
    alpha: float = DEFAULT_ALPHA,
    n_permutations: int = DEFAULT_N_PERMUTATIONS,
) -> Optional[str]:
    """Green/amber line, or None when focus count is unknown."""
    info = power_guardrail(
        n_baseline, n_ablated, n_foci, alpha=alpha, n_permutations=n_permutations
    )
    if info['can_reach_significance'] is None:
        return None
    if info['can_reach_significance']:
        return POWER_OK
    return POWER_FAIL.format(n_foci=int(n_foci))


def format_run_header(
    temperature: float,
    n_baseline: int,
    n_ablated: int,
    test_type: str,
) -> str:
    kind = 'exact' if test_type == 'exact' else 'sampled'
    return RUN_HEADER_TEMPLATE.format(
        t=format_temperature(temperature),
        n_baseline=int(n_baseline),
        n_ablated=int(n_ablated),
        test_type=kind,
    )


def experiment_preview(
    temperature: float,
    n_baseline: int,
    n_ablated: int,
    foci: Optional[Sequence[Mapping[str, Any]]] = None,
    alpha: float = DEFAULT_ALPHA,
    n_permutations: int = DEFAULT_N_PERMUTATIONS,
) -> Dict[str, Any]:
    """Single payload for tests and any server-side preview."""
    foci_tagged = bool(foci)
    n_attr = count_preview_attributable(foci)
    n_foci_for_bh = n_attr
    guard = power_guardrail(
        n_baseline, n_ablated, n_foci_for_bh, alpha=alpha, n_permutations=n_permutations
    )
    suggested = suggested_sample_sizes(temperature)
    return {
        'temperature': float(temperature),
        'n_baseline': int(n_baseline),
        'n_ablated': int(n_ablated),
        'n_attributable_foci': n_attr,
        'foci_tagged': foci_tagged,
        'cost_line': format_cost_line(
            n_baseline, n_ablated, n_attr, foci_tagged=foci_tagged
        ),
        'model_calls': (
            model_call_count(n_baseline, n_ablated, n_attr) if foci_tagged else None
        ),
        'suggested_n_baseline': suggested[0],
        'suggested_n_ablated': suggested[1],
        'high_temperature': float(temperature) >= 1.0,
        'temperature_error': temperature_rejection(temperature),
        'permutation_disclosure': format_permutation_disclosure(
            n_baseline, n_ablated, n_permutations
        ),
        'test_type': design_test_type(n_baseline, n_ablated, n_permutations),
        'power_line': format_power_preview_line(
            n_baseline, n_ablated, n_foci_for_bh, alpha=alpha, n_permutations=n_permutations
        ),
        'power_ok': guard['can_reach_significance'],
        'min_p': guard['min_p'],
        'run_header': format_run_header(
            temperature,
            n_baseline,
            n_ablated,
            design_test_type(n_baseline, n_ablated, n_permutations),
        ),
        'min_achievable_p': min_achievable_pvalue(n_baseline, n_ablated, n_permutations),
    }
