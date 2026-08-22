# Behavioral difference assessment

FocalPrompt’s Experiment B has three independent evidence lenses. They answer
different questions and must not be collapsed into one score.

## The three questions

1. **Semantic perturbation** — Did removing this focus shift outputs in embedding
   space? (cheap first-pass screen: centroid cosine distance + permutation + BH)
2. **Behavioral difference** — Did baseline vs ablated output *sets* change in
   observable ways (structure, compliance, content, tools, safety posture, …)?
3. **Quality / preference** — Was one output better? (existing batch agent eval /
   thumbs — **unchanged** and **not** used as a difference rubric)

Canonical distinction:

> Semantic perturbation asks whether outputs move in embedding space.
> Behavioral-difference review asks whether the outputs differ materially in
> observable behavior. Quality evaluation asks whether one output is better.
> These are separate questions.

## Why multiple lenses

Embeddings are a useful broad screen, but they are blind to some behavioral
changes that matter in practice.

### Semantic and qualitative agree

Content changes substantially (topic, decision, or facts). Both embedding shift
and human/LLM difference review light up.

### Semantic weak / qualitative strong

Example: JSON schema / formatting instructions. Ablated outputs remain
semantically similar (same facts) but violate required structure. Embeddings
often miss this; a difference judge scores `structure_format` and
`instruction_compliance` highly.

### Semantic strong / qualitative weak

Outputs are phrased differently but accomplish essentially the same task with
the same structure and compliance. Embedding distance can be large while a
difference judge reports little *material* behavioral change.

### Quality changes independently

Ablated outputs may be very different without being better or worse, or similar
while quality changes. Quality evaluation remains a separate product path and
must not be silently repurposed as difference assessment.

## Progressive evidence funnel

1. Run semantic LOO for every attributable focus (default).
2. Optionally escalate selected foci to the LLM behavioral-difference judge.
3. Optionally escalate selected foci to human-observed difference review.

Escalation may be manual or advisory (structural focus keywords; high reported
focus with weak semantic evidence; large effect but non-significant; etc.).
Recommendations are advisory only — they do not claim the embedding result is
wrong.

## LLM judge (difference only)

The judge compares **Group A vs Group B** as sets (optionally blinded), with a
bounded sample of baseline and ablated outputs. Metadata records how many
outputs were shown and the sampling method.

It must **not** ask which group is better, preferred, more correct, or whether
the prompt should change. Schema fields are difference-oriented
(`material_behavioral_difference`, `overall_difference_score` 0–5, dimensions,
`summary`).

A single LLM judgment is **not** “statistically significant.” Results store
enough metadata for future multi-judge aggregation.

## Human review

Separate rubric from thumbs-up/down preference. Reviewers see the focus, removed
span, and baseline/ablated sets, then record material difference
(yes/no/uncertain), overall score, dimensions, and notes.

## Experiment C

Reported focus vs revealed sensitivity is shown under **separate faithfulness
lenses** (semantic / LLM / human). Labels such as `semantic_blind_spot` or
`metric_disagreement` describe agreement across lenses; they do not override
raw results or invent ground truth.

## Batch

Batch analysis keeps semantic screening as the default. LLM/human difference
review is selective (queue + caps + cost estimate). Aggregates report the three
lenses separately, with agreement rates and false-positive/negative
**candidates** relative to another lens — never as ground truth.
