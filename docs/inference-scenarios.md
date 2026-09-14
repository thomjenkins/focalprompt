# Ordered inference scenarios

Inference scenario version 1 is the canonical model-under-test request used by the web UI, HTTP and Python APIs, CLI, MCP, batch experiments, rewrites, optimization, and agent generation.

```json
{
  "version": 1,
  "messages": [
    {
      "id": "clinic-rules",
      "role": "system",
      "content": "You help veterinary teams.",
      "analysis_mode": "analyse"
    },
    {
      "id": "customer-message",
      "role": "user",
      "content": "",
      "analysis_mode": "retain",
      "input_name": "customer_message"
    }
  ]
}
```

Messages keep their order and role. Supported text roles are `system`, `developer`, `user`, and `assistant`; tool calls are not supported in version 1. All system and developer blocks must precede conversational messages, IDs must be unique, and generation requires at least one user message. System and developer messages default to Analyse; user and assistant messages default to Retain.

Analyse messages are eligible for focus detection and ablation. Retain messages are copied unchanged into every arm. A focus can cover several exact message-relative spans:

```json
{
  "focus": "Safety and escalation",
  "spans": [
    {"message_id":"clinic-rules","char_start":0,"char_end":26,"text_snapshot":"You help veterinary teams."}
  ]
}
```

## Named batch inputs

`input_name` is valid only on a retained message. For a batch pair, `pairs[].inputs[input_name]` replaces that message's complete content; every named input must be present and non-blank. CSV columns other than reserved `output` and legacy `prompt` are named inputs. Missing, blank, and unused columns are reported separately.

For a single run, omitting `inputs` uses the contents already stored on retained messages. Passing an explicit `inputs` object switches to named-input binding and requires every configured name.

In the web editor, **Input name** means “batch input column (optional).” Leave it blank for messages whose content should stay fixed across rows, or when only doing single runs. Naming an input does not itself replace the editor text; replacement happens when an input mapping is supplied.

The Batch Analysis page lists the configured input names and required CSV columns. **Configure inputs in Prompt Analysis** takes you to the scenario editor. If no inputs are named, the page explicitly shows an output-only batch: message content stays fixed across rows.

For the `customer_message` input above, upload a CSV such as:

```csv
customer_message,output
"My pup needs a booster.","When was their last vaccination?"
"Can I book a check-up?","What day works for you?"
```

Each row's `customer_message` replaces the entire retained message, while `output` is the recorded response for that example. Analyse messages and the output contract remain shared across rows. Multiple varying messages need distinct input names, each with a matching column and a non-blank value in every row. Manual batch entry uses the same names.

This is **not placeholder interpolation**: setting `input_name` to `clientName` does not substitute `{{clientName}}` inside a message. Message `id` is a separate reference key used by focus spans and rewrites, not a batch column.

## Strict structured output

Add `output_contract` to require JSON Schema output:

```json
{
  "type": "json_schema",
  "name": "answer",
  "strict": true,
  "schema": {
    "type": "object",
    "properties": {"answer":{"type":"string"}},
    "required": ["answer"],
    "additionalProperties": false
  }
}
```

The contract is request configuration, not a message. FocalPrompt passes it through each supported provider adapter and validates every response locally. Malformed JSON, schema mismatches, refusals, incomplete output, and unsupported adapters stop the experiment; the contract is never silently removed.

For OpenAI GPT-3.5 Turbo (`gpt-3.5-turbo`, `gpt-3.5-turbo-0125`, and `gpt-3.5-turbo-1106`), the direct OpenAI and Vercel Gateway adapters express the contract as a forced function call with `strict: true`, the unchanged schema as its parameters, and parallel calls disabled. These models do not support the newer `json_schema` response format. The function is an output container: no function is executed, and its arguments become the generated JSON response. The adapter leaves message content, roles, order, model and temperature intact. It chooses this representation before sampling and uses it consistently for baseline and ablated arms; it does not repair or resample malformed output.

Sample `scenario_metadata` records `structured_output: "strict_function_call"` and `structured_output_function` for this translation. This API representation is part of the experimental conditions and should be retained when interpreting or reproducing results. Models using native schema responses continue to receive `response_format.json_schema`. GPT-3.5 assessment calls using JSON mode are unaffected. See the official [structured-output guide](https://developers.openai.com/api/docs/guides/structured-outputs) and [strict function-calling documentation](https://developers.openai.com/api/docs/guides/function-calling#strict-mode).

With **Output contract** enabled, the web editor validates the schema's JSON syntax as you type and requires a JSON object. Invalid input shows an inline error and blocks submission; correcting it clears the error. This editor check does not replace server-side JSON Schema validation.

## Target focus mix and rewriting

The focus sliders express one global target mix across all Analyse messages, not separate percentages within each message. Positive `rewrite_weight` values are normalized together to 100% and guide relative instructional emphasis. There are no absolute minimize/retain/emphasize thresholds: 20% can be the largest target in a distribution. These are desired reported-focus shares in generated output, not text-length quotas or guaranteed shares of model attention.

A weight of exactly 0 requests omission of that focus's instructions. Omitting instructions may change correctness or behavior; it is an experimental transformation, not an optimization recommendation.

Rewriting uses one coordinated model request containing the ordered scenario, retained context, output contract, focus definitions, and global targets. Replacement text is keyed by the targeted Analyse message IDs. Message roles, IDs, order, retained content, and the output contract remain unchanged; untargeted Analyse messages are also preserved. A focus spanning several messages has one shared target, not a separate allocation in each message. If every focus mapped to a targeted message is omitted, its content may become empty while its message boundary remains.

The web preview displays separate role- and ID-labelled messages, including unchanged retained context. **Generate Output with Adjusted Focus** generates from the rewritten scenario and reassesses that output against the same focus definitions, including zero-target foci. **Compare Target vs Reported** displays the requested mix and reported results with differences in percentage points. Reassessment does not replace the chosen targets. The original editor scenario is not overwritten.

The comparison describes one sampled output using the existing reported-focus assessment method. It does not establish causal importance, output quality, or that a rewrite will reliably achieve its target mix.

## Interfaces

HTTP requests accept exactly one of `scenario` or `prompt`. Python functions accept a scenario object or path using `scenario=...`. CLI commands accept `--scenario FILE` instead of the positional prompt. MCP tools expose the same optional `scenario` object, and ablation named values are supplied through `options.inputs`.

Legacy prompts remain supported and are normalized to one analysed `user` message with ID `legacy-prompt`, preserving the historical inference role. Version-1 workspace exports are migrated to version 2 using the same conversion.
