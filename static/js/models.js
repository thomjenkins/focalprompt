// Comprehensive model list for Vercel AI Gateway
// Organized by provider

export const allModels = {
    openai: [
        'gpt-5.2', 'gpt-5.1-instant', 'gpt-5.1-thinking', 'gpt-5.1-codex', 'gpt-5.1-codex-mini', 'gpt-5.1-codex-max',
        'gpt-5.2-pro', 'gpt-5.2-chat', 'gpt-5', 'gpt-5-mini', 'gpt-5-nano', 'gpt-5-pro', 'gpt-5-chat', 'gpt-5-codex',
        'gpt-4.1', 'gpt-4.1-mini', 'gpt-4.1-nano', 'gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo', 'gpt-3.5-turbo-instruct',
        'gpt-oss-120b', 'gpt-oss-20b', 'gpt-oss-safeguard-20b',
        'o3', 'o3-mini', 'o3-pro', 'o3-deep-research', 'o4-mini', 'o1',
        'text-embedding-3-small', 'text-embedding-3-large', 'text-embedding-ada-002',
        'codex-mini'
    ],
    anthropic: [
        'claude-sonnet-4.5', 'claude-haiku-4.5', 'claude-opus-4.5', 'claude-opus-4.1', 'claude-opus-4',
        'claude-3.7-sonnet', 'claude-3.5-sonnet', 'claude-3.5-sonnet-20240620', 'claude-3.5-haiku',
        'claude-3-opus', 'claude-3-sonnet-20240229', 'claude-3-haiku'
    ],
    google: [
        'gemini-3-pro-preview', 'gemini-3-pro-image', 'gemini-3-flash',
        'gemini-2.5-pro', 'gemini-2.5-flash', 'gemini-2.5-flash-lite', 'gemini-2.5-flash-preview-09-2025',
        'gemini-2.5-flash-image', 'gemini-2.5-flash-image-preview', 'gemini-2.5-flash-lite-preview-09-2025',
        'gemini-2.0-flash', 'gemini-2.0-flash-lite',
        'gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-pro',
        'gemini-embedding-001', 'text-multilingual-embedding-002', 'text-embedding-005',
        'imagen-4.0-fast-generate-001', 'imagen-4.0-generate-001', 'imagen-4.0-ultra-generate-001'
    ],
    xai: [
        'grok-4.1-fast-non-reasoning', 'grok-4.1-fast-reasoning', 'grok-4-fast-non-reasoning', 'grok-4-fast-reasoning',
        'grok-4', 'grok-3', 'grok-3-mini', 'grok-3-mini-fast', 'grok-3-fast', 'grok-2', 'grok-2-vision',
        'grok-code-fast-1'
    ],
    minimax: [
        'minimax-m2.1', 'minimax-m2.1-lightning', 'minimax-m2'
    ],
    alibaba: [
        'qwen3-next-80b-a3b-instruct', 'qwen3-next-80b-a3b-thinking', 'qwen3-max', 'qwen3-max-preview',
        'qwen-3-235b', 'qwen3-235b-a22b-thinking', 'qwen-3-30b', 'qwen3-32b', 'qwen3-14b',
        'qwen3-vl-instruct', 'qwen3-vl-thinking', 'qwen3-coder-30b-a3b', 'qwen3-coder-plus', 'qwen3-coder',
        'qwen3-embedding-0.6b', 'qwen3-embedding-8b', 'qwen3-embedding-4b'
    ],
    deepseek: [
        'deepseek-v3.2', 'deepseek-v3.2-thinking', 'deepseek-v3.2-exp', 'deepseek-v3.1', 'deepseek-v3.1-terminus',
        'deepseek-v3', 'deepseek-r1'
    ],
    mistral: [
        'devstral-2', 'devstral-small-2', 'devstral-small', 'ministral-3b', 'ministral-14b', 'ministral-8b',
        'mistral-large-3', 'mistral-medium', 'mistral-small', 'mistral-nemo',
        'pixtral-12b', 'pixtral-large', 'codestral', 'codestral-embed',
        'magistral-medium', 'magistral-small', 'mistral-embed',
        'mixtral-8x22b-instruct'
    ],
    meta: [
        'llama-4-scout', 'llama-4-maverick', 'llama-3.3-70b', 'llama-3.2-90b', 'llama-3.2-11b', 'llama-3.2-3b', 'llama-3.2-1b',
        'llama-3.1-70b', 'llama-3.1-8b'
    ],
    moonshotai: [
        'kimi-k2', 'kimi-k2-0905', 'kimi-k2-thinking', 'kimi-k2-thinking-turbo', 'kimi-k2-turbo'
    ],
    perplexity: [
        'sonar', 'sonar-pro', 'sonar-reasoning', 'sonar-reasoning-pro'
    ],
    amazon: [
        'nova-lite', 'nova-micro', 'nova-pro', 'nova-2-lite', 'titan-embed-text-v2'
    ],
    zai: [
        'glm-4.7', 'glm-4.6', 'glm-4.6v', 'glm-4.6v-flash', 'glm-4.5', 'glm-4.5v', 'glm-4.5-air'
    ],
    voyage: [
        'voyage-3-large', 'voyage-3.5', 'voyage-3.5-lite', 'voyage-code-2', 'voyage-code-3', 'voyage-finance-2', 'voyage-law-2'
    ],
    cohere: [
        'embed-v4.0', 'command-a'
    ],
    morph: [
        'morph-v3-fast', 'morph-v3-large'
    ],
    meituan: [
        'longcat-flash-chat', 'longcat-flash-thinking'
    ],
    nvidia: [
        'nemotron-3-nano-30b-a3b', 'nemotron-nano-9b-v2', 'nemotron-nano-12b-v2-vl'
    ],
    bfl: [
        'flux-2-flex', 'flux-2-pro', 'flux-2-max', 'flux-kontext-pro', 'flux-kontext-max',
        'flux-pro-1.0-fill', 'flux-pro-1.1', 'flux-pro-1.1-ultra'
    ],
    arcee_ai: [
        'trinity-mini'
    ],
    inception: [
        'mercury-coder-small'
    ],
    stealth: [
        'sonoma-sky-alpha', 'sonoma-dusk-alpha'
    ],
    vercel: [
        'v0-1.0-md', 'v0-1.5-md'
    ],
    bytedance: [
        'seed-1.6'
    ],
    prime_intellect: [
        'intellect-3'
    ],
    kwaipilot: [
        'kat-coder-pro-v1'
    ],
    chutes: [
        // Model name not specified in list
    ],
    streamlake: [
        // Model name not specified in list
    ]
};

// Flatten all models into a single searchable list with provider info
export const allModelsFlat = Object.entries(allModels).flatMap(([provider, models]) =>
    models.map(model => ({
        value: model,
        label: `${provider}/${model}`,
        provider: provider,
        searchText: `${provider} ${model} ${provider}/${model}`.toLowerCase()
    }))
).sort((a, b) => a.label.localeCompare(b.label));

