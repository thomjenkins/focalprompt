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

`input_name` is valid only on a retained message. For a batch pair, `pairs[].inputs[input_name]` replaces that message's complete content; every named input must be present and non-blank. CSV columns other than reserved `output` and legacy `prompt` are named inputs. Missing, blank, and unused columns are reported separately.

For a single run, omitting `inputs` uses the contents already stored on retained messages. Passing an explicit `inputs` object switches to named-input binding and requires every configured name.

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

## Interfaces

HTTP requests accept exactly one of `scenario` or `prompt`. Python functions accept a scenario object or path using `scenario=...`. CLI commands accept `--scenario FILE` instead of the positional prompt. MCP tools expose the same optional `scenario` object, and ablation named values are supplied through `options.inputs`.

Legacy prompts remain supported and are normalized to one analysed `user` message with ID `legacy-prompt`, preserving the historical inference role. Version-1 workspace exports are migrated to version 2 using the same conversion.
