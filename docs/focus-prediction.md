# Focus self-assessment

Prediction uses the selected baseline model in separate assessment calls. It receives the complete ordered scenario, including retained chat, the output contract and the grounded focus definitions. It does not receive a generated output or a previous experiment's assessment. Retained input conditions the allocation; the 100% budget is distributed only among the supplied foci.

The `joint-budget-v3` method separates two tasks:

- A short interpretation of the current request, supported by exact quotes from scenario messages. When retained user input exists, at least one quote must come from it.
- A classification for every focus: `direct` contribution to content or action, `background` constraint on the response, or `inactive` for this case.
- A case-specific justification for each focus, without numeric scores.

After applicability and explanations cover the whole catalog, a separate call receives that assessment and the complete original scenario and focus definitions. It allocates one budget across **all** foci, returning a compact mapping from original focus indices to percentages and a short rationale for the allocation. Inactive foci receive zero. Equal weights are permitted; the application does not impose a preferred ranking.

Retrospective calls use the same method and additionally receive one actual output. Justifications must describe what that output contains, including departures from the instructions, rather than what an ideal response should contain. The prospective assessment is withheld.

Prediction and retrospective assessment run at temperature **0.2**. Baseline generation uses the independently configured temperature, initially **0.7**. The UI labels these separately and shows the request interpretation, evidence and applicability alongside the allocation.

Validation checks exact quotes, complete focus coverage, applicability and finite nonnegative scores. A positive score total is rescaled proportionally to 100%, preserving the model’s relative weights and zero scores. The raw scores and total are saved; the UI discloses rescaling when the total differs from 100 by more than 0.5. Validation does not judge semantic correctness or retry merely because a distribution looks unexpected. These are model self-reports with unknown error; matching a quote does not establish that the allocation is faithful to internal processing.

Missing or invalid applicability entries and justifications are repaired in groups of up to eight original indices. Duplicate indices are ambiguous and must be reassessed. Every recovery call receives the full scenario and focus catalog. Scores are neither requested nor retained in this stage, even if the model emits them. Request evidence can be repaired independently.

Numeric allocations are always requested for the entire catalog. An incomplete or invalid numeric response is discarded in full and retried, at most twice. Numeric responses from different calls are never merged or used as anchors. This corrects the v2 recovery failure where the model could give each batch a separate budget, or copy identical raw weights into missing rows, producing misleading normalized percentages such as 5.9% for each of seventeen foci.

Applicability recovery is bounded to twice the number of eight-focus batches. Persistent failure names unresolved indices. `allocation_recovery` records applicability follow-up `calls`, recovered `focus_indices`, and `budget_retries`; all calls contribute to token usage. Normal execution uses two calls per assessment, increasing latency and usage relative to a successful v2 single-call assessment.

Uniform allocations remain visible and receive an explicit limitation notice: they do not distinguish contributions among foci. This is diagnostic, not proof that the model is wrong. The app does not retry solely to force unequal scores. The notice also applies to older saved uniform results, and the UI displays the model's overall allocation rationale. A different baseline model requires a new experimental run so prospective and retrospective assessments stay comparable.

Saved results include `assessment_protocol`. Earlier completed runs remain viewable and comparable within their original method. Continuing sampling or retrospective assessment with an earlier prediction requires a new prediction so a comparison does not silently mix methods. Export a run before starting over to keep its results.

## Evaluation

The regression probe uses a synthetic clothing-store scenario with seventeen foci. It varies only the retained chat between returns, delivery and damage requests, and reverses focus order. The relevant conditional focus must outrank the two unrelated conditional foci; complete but uniform allocations fail this probe. It also checks a retrospective assessment and deliberately removes five applicability entries to verify recovery followed by a new joint allocation:

```sh
.venv/bin/python scripts/evaluate_focus_recovery.py --live \
  --model gpt-3.5-turbo --output /tmp/focus-recovery-evaluation.json
```

This probe also requires inference credentials and makes billed calls. Its simulated omissions test recovery; they are not an estimate of the model's natural omission rate.

The final `joint-budget-v3` probe on 2026-09-14 produced:

| Model | Natural cases (six prospective, one retrospective) | Forced applicability recovery | Total |
| --- | ---: | ---: | ---: |
| GPT-3.5 Turbo | 7/7 | 0/1 | 7/8 |
| GPT-4o mini | 7/7 | 1/1 | 8/8 |

GPT-3.5's recovered result was structurally complete but assigned an unrelated delivery focus the same weight as returns. The app does not override that model judgement. GPT-4o mini performed better on this small fixture; this is not a general model ranking or a reliability guarantee. Both models retained the same scenario and model within each prospective/retrospective experiment. The selected baseline model is never changed automatically.

The opt-in evaluation uses synthetic booking, medication-refill and injury chats with the same twelve foci. It reverses the focus list while preserving the scenario and matches results by focus name. Its relevance check asks whether the conditional focus for the current request outranks the two unrelated conditional foci; no exact percentage is ground truth.

```sh
.venv/bin/python scripts/evaluate_focus_prediction.py --live \
  --model gpt-3.5-turbo --compare-ref 259e35b \
  --output /tmp/focus-prediction-evaluation.json
```

This requires configured inference credentials and makes billed calls. Add `--repeats` for repeated measurements. Inspect the saved allocations and justifications as well as the relevance checks. This small fixture is a regression probe, not a general reliability benchmark or a validation of introspection.

For historical context, a `context-grounded-v2` GPT-3.5 Turbo probe on 2026-09-14 passed six relevance checks on the smaller twelve-focus fixture (one run per request and focus-list order):

| Request | Relevant focus | Original list | Reversed list |
| --- | --- | ---: | ---: |
| Booster appointment | Appointment booking | 33.3% | 33.3% |
| Medication refill | Med requests | 50.0% | 66.7% |
| Paw injury | First aid | 25.0% | 20.0% |

The other two conditional foci received zero in each case. Later seventeen-focus tests exposed flat and batch-distorted v2 allocations despite passing coverage checks. The percentages also vary with list order; passing these small relevance probes does not establish order invariance or precise focus measurement.

The explicit instructions, separated context and evaluation approach follow the [OpenAI prompt engineering guidance](https://developers.openai.com/api/docs/guides/prompt-engineering).
