# Focus self-assessment

Prediction uses the selected baseline model in a separate assessment call. It receives the complete ordered scenario, including retained chat, the output contract and the grounded focus definitions. It does not receive a generated output or previous assessment. Retained input conditions the allocation; the 100% budget is distributed only among the supplied foci.

The `context-grounded-v2` assessment asks for:

- A short interpretation of the current request, supported by exact quotes from scenario messages. When retained user input exists, at least one quote must come from it.
- A classification for every focus: `direct` contribution to content or action, `background` constraint on the response, or `inactive` for this case.
- A case-specific justification and a percentage for each focus. Inactive foci receive zero. Equal weights are permitted when justified; the application does not impose a preferred ranking.

Retrospective calls use the same method and additionally receive one actual output. Justifications must describe what that output contains, including departures from the instructions, rather than what an ideal response should contain. The prospective assessment is withheld.

Prediction and retrospective assessment run at temperature **0.2**. Baseline generation uses the independently configured temperature, initially **0.7**. The UI labels these separately and shows the request interpretation, evidence and applicability alongside the allocation.

Validation checks exact quotes, complete focus coverage, applicability and finite nonnegative scores. A positive score total is rescaled proportionally to 100%, preserving the model’s relative weights and zero scores. The raw scores and total are saved; the UI discloses rescaling when the total differs from 100 by more than 0.5. Validation does not judge semantic correctness or retry merely because a distribution looks unexpected. These are model self-reports with unknown error; matching a quote does not establish that the allocation is faithful to internal processing.

If the model omits foci or returns invalid entries, valid rows are retained and the model is asked to complete only the missing or invalid original indices, at most eight per recovery call. Duplicate indices are ambiguous and must be reassessed. Every recovery call still receives the complete scenario and focus catalog, along with accepted raw allocations from this same assessment as a shared scale. A batch is not allocated its own 100% budget. Scores are normalized once, only after every focus has a valid model-supplied score and justification. Missing rows are never filled with assumed zeros. Malformed JSON falls back to these smaller requests; a complete all-zero allocation must be reassessed because it has no usable relative scale. Invalid request evidence can be repaired without changing accepted scores.

Recovery is bounded to twice the number of eight-focus batches. Persistent failure names the remaining missing or invalid foci. Successful results save `allocation_recovery` (follow-up call count and recovered indices), include all calls in token usage, and disclose recovery in the UI. Completing an allocation over multiple calls can affect the model's estimates; the metadata allows these cases to be distinguished from allocations completed in one call. This uses the same assessment protocol and does not feed a prospective result into a retrospective call.

Saved results include `assessment_protocol`. Earlier completed runs remain viewable and comparable within their original method. Continuing sampling or retrospective assessment with an earlier prediction requires a new prediction so a comparison does not silently mix methods. Export a run before starting over to keep its results.

## Evaluation

The coverage regression probe uses a synthetic clothing-store scenario with seventeen foci. It checks prospective and retrospective coverage, deliberately removes five model-produced entries, and verifies that live recovery restores every original index while preserving the other raw scores:

```sh
.venv/bin/python scripts/evaluate_focus_recovery.py --live \
  --model gpt-3.5-turbo --output /tmp/focus-recovery-evaluation.json
```

This probe also requires inference credentials and makes billed calls. Its simulated omissions test recovery; they are not an estimate of the model's natural omission rate.

The opt-in evaluation uses synthetic booking, medication-refill and injury chats with the same twelve foci. It reverses the focus list while preserving the scenario and matches results by focus name. Its relevance check asks whether the conditional focus for the current request outranks the two unrelated conditional foci; no exact percentage is ground truth.

```sh
.venv/bin/python scripts/evaluate_focus_prediction.py --live \
  --model gpt-3.5-turbo --compare-ref 259e35b \
  --output /tmp/focus-prediction-evaluation.json
```

This requires configured inference credentials and makes billed calls. Add `--repeats` for repeated measurements. Inspect the saved allocations and justifications as well as the relevance checks. This small fixture is a regression probe, not a general reliability benchmark or a validation of introspection.

The final GPT-3.5 Turbo probe on 2026-09-14 passed all six relevance checks (one run per request and focus-list order):

| Request | Relevant focus | Original list | Reversed list |
| --- | --- | ---: | ---: |
| Booster appointment | Appointment booking | 33.3% | 33.3% |
| Medication refill | Med requests | 50.0% | 66.7% |
| Paw injury | First aid | 25.0% | 20.0% |

The other two conditional foci received zero in each case. The percentages still vary with list order; passing these relevance checks does not establish order invariance or precise focus measurement.

The explicit instructions, separated context and evaluation approach follow the [OpenAI prompt engineering guidance](https://developers.openai.com/api/docs/guides/prompt-engineering).
