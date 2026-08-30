// FocalPrompt Web Application JavaScript

let foci = [];
let agentFoci = []; // Separate foci for agent builder
let batchFoci = []; // Separate foci for batch analysis
let batchPairs = []; // Store input-output pairs for batch analysis
let currentTab = 'documentation'; // Track current tab (defaults to documentation)

window.getAblationFoci = function () { return foci; };
window.getBatchFoci = function () { return batchFoci; };

// Settings management
let userProvider = localStorage.getItem('focalprompt_provider') || 'openai';
let userApiKey = localStorage.getItem('focalprompt_api_key') || '';
let userModel = localStorage.getItem('focalprompt_model') || 'gpt-4o-mini';

// Dynamic model list - will be populated from API
let allModelsData = {
    openai: ['gpt-5.2', 'gpt-5.1-instant', 'gpt-5.1-thinking', 'gpt-5.1-codex', 'gpt-5.1-codex-mini', 'gpt-5.1-codex-max', 'gpt-5.2-pro', 'gpt-5.2-chat', 'gpt-5', 'gpt-5-mini', 'gpt-5-nano', 'gpt-5-pro', 'gpt-5-chat', 'gpt-5-codex', 'gpt-4.1', 'gpt-4.1-mini', 'gpt-4.1-nano', 'gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo', 'gpt-3.5-turbo-instruct', 'gpt-oss-120b', 'gpt-oss-20b', 'gpt-oss-safeguard-20b', 'o3', 'o3-mini', 'o3-pro', 'o3-deep-research', 'o4-mini', 'o1', 'text-embedding-3-small', 'text-embedding-3-large', 'text-embedding-ada-002', 'codex-mini'],
    anthropic: ['claude-sonnet-4.5', 'claude-haiku-4.5', 'claude-opus-4.5', 'claude-opus-4.1', 'claude-opus-4', 'claude-3.7-sonnet', 'claude-3.5-sonnet', 'claude-3.5-sonnet-20240620', 'claude-3.5-haiku', 'claude-3-opus', 'claude-3-sonnet-20240229', 'claude-3-haiku'],
    google: ['gemini-3-pro-preview', 'gemini-3-pro-image', 'gemini-3-flash', 'gemini-2.5-pro', 'gemini-2.5-flash', 'gemini-2.5-flash-lite', 'gemini-2.5-flash-preview-09-2025', 'gemini-2.5-flash-image', 'gemini-2.5-flash-image-preview', 'gemini-2.5-flash-lite-preview-09-2025', 'gemini-2.0-flash', 'gemini-2.0-flash-lite', 'gemini-1.5-flash', 'gemini-embedding-001', 'text-multilingual-embedding-002', 'text-embedding-005', 'imagen-4.0-fast-generate-001', 'imagen-4.0-generate-001', 'imagen-4.0-ultra-generate-001'],
    xai: ['grok-4.1-fast-non-reasoning', 'grok-4.1-fast-reasoning', 'grok-4-fast-non-reasoning', 'grok-4-fast-reasoning', 'grok-4', 'grok-3', 'grok-3-mini', 'grok-3-mini-fast', 'grok-3-fast', 'grok-2', 'grok-2-vision', 'grok-code-fast-1'],
    minimax: ['minimax-m2.1', 'minimax-m2.1-lightning', 'minimax-m2'],
    alibaba: ['qwen3-next-80b-a3b-instruct', 'qwen3-next-80b-a3b-thinking', 'qwen3-max', 'qwen3-max-preview', 'qwen-3-235b', 'qwen3-235b-a22b-thinking', 'qwen-3-30b', 'qwen3-32b', 'qwen3-14b', 'qwen3-vl-instruct', 'qwen3-vl-thinking', 'qwen3-coder-30b-a3b', 'qwen3-coder-plus', 'qwen3-coder', 'qwen3-embedding-0.6b', 'qwen3-embedding-8b', 'qwen3-embedding-4b'],
    deepseek: ['deepseek-v3.2', 'deepseek-v3.2-thinking', 'deepseek-v3.2-exp', 'deepseek-v3.1', 'deepseek-v3.1-terminus', 'deepseek-v3', 'deepseek-r1'],
    mistral: ['devstral-2', 'devstral-small-2', 'devstral-small', 'ministral-3b', 'ministral-14b', 'ministral-8b', 'mistral-large-3', 'mistral-medium', 'mistral-small', 'mistral-nemo', 'pixtral-12b', 'pixtral-large', 'codestral', 'codestral-embed', 'magistral-medium', 'magistral-small', 'mistral-embed', 'mixtral-8x22b-instruct'],
    meta: ['llama-4-scout', 'llama-4-maverick', 'llama-3.3-70b', 'llama-3.2-90b', 'llama-3.2-11b', 'llama-3.2-3b', 'llama-3.2-1b', 'llama-3.1-70b', 'llama-3.1-8b'],
    moonshotai: ['kimi-k2', 'kimi-k2-0905', 'kimi-k2-thinking', 'kimi-k2-thinking-turbo', 'kimi-k2-turbo'],
    perplexity: ['sonar', 'sonar-pro', 'sonar-reasoning', 'sonar-reasoning-pro'],
    amazon: ['nova-lite', 'nova-micro', 'nova-pro', 'nova-2-lite', 'titan-embed-text-v2'],
    zai: ['glm-4.7', 'glm-4.6', 'glm-4.6v', 'glm-4.6v-flash', 'glm-4.5', 'glm-4.5v', 'glm-4.5-air'],
    voyage: ['voyage-3-large', 'voyage-3.5', 'voyage-3.5-lite', 'voyage-code-2', 'voyage-code-3', 'voyage-finance-2', 'voyage-law-2'],
    cohere: ['embed-v4.0', 'command-a'],
    morph: ['morph-v3-fast', 'morph-v3-large'],
    meituan: ['longcat-flash-chat', 'longcat-flash-thinking'],
    nvidia: ['nemotron-3-nano-30b-a3b', 'nemotron-nano-9b-v2', 'nemotron-nano-12b-v2-vl'],
    bfl: ['flux-2-flex', 'flux-2-pro', 'flux-2-max', 'flux-kontext-pro', 'flux-kontext-max', 'flux-pro-1.0-fill', 'flux-pro-1.1', 'flux-pro-1.1-ultra'],
    arcee_ai: ['trinity-mini'],
    inception: ['mercury-coder-small'],
    stealth: ['sonoma-sky-alpha', 'sonoma-dusk-alpha'],
    vercel: ['v0-1.0-md', 'v0-1.5-md'],
    bytedance: ['seed-1.6'],
    prime_intellect: ['intellect-3'],
    kwaipilot: ['kat-coder-pro-v1']
};

// Flatten all models into searchable format (will be updated dynamically)
let allModelsFlat = Object.entries(allModelsData).flatMap(([provider, models]) =>
    models.map(model => ({
        value: model,
        label: `${provider}/${model}`,
        provider: provider,
        searchText: `${provider} ${model} ${provider}/${model}`.toLowerCase()
    }))
).sort((a, b) => a.label.localeCompare(b.label));

// Load models dynamically from AI Gateway
async function loadModelsFromGateway() {
    try {
        const response = await fetch('/api/models');
        if (!response.ok) {
            console.warn('Failed to fetch models from gateway, using fallback');
            return false;
        }
        
        const data = await response.json();
        if (data.source === 'gateway' && data.models) {
            // Update allModelsData with fetched models
            allModelsData = {};
            for (const [provider, models] of Object.entries(data.models)) {
                allModelsData[provider] = models.map(m => m.value);
            }
            
            // Rebuild allModelsFlat
            allModelsFlat = Object.entries(allModelsData).flatMap(([provider, models]) =>
                models.map(model => ({
                    value: model,
                    label: `${provider}/${model}`,
                    provider: provider,
                    searchText: `${provider} ${model} ${provider}/${model}`.toLowerCase()
                }))
            ).sort((a, b) => a.label.localeCompare(b.label));
            
            // Update legacy providerModels for backward compatibility
            providerModels.openai = allModelsData.openai?.map(m => ({ value: m, label: `openai/${m}` })) || providerModels.openai;
            providerModels.anthropic = allModelsData.anthropic?.map(m => ({ value: m, label: `anthropic/${m}` })) || providerModels.anthropic;
            providerModels.google = allModelsData.google?.map(m => ({ value: m, label: `google/${m}` })) || providerModels.google;
            providerModels.xai = allModelsData.xai?.map(m => ({ value: m, label: `xai/${m}` })) || providerModels.xai;
            providerModels.grok = providerModels.xai;
            
            console.log(`✅ Loaded ${data.total} models from AI Gateway`);
            return true;
        }
        console.warn('Models API returned fallback data');
        return false;
    } catch (error) {
        console.warn('Error loading models from gateway:', error);
        return false;
    }
}

// Legacy provider models for backward compatibility (will be updated dynamically)
let providerModels = {
    openai: allModelsData.openai?.map(m => ({ value: m, label: `openai/${m}` })) || [],
    anthropic: allModelsData.anthropic?.map(m => ({ value: m, label: `anthropic/${m}` })) || [],
    google: allModelsData.google?.map(m => ({ value: m, label: `google/${m}` })) || [],
    grok: allModelsData.xai?.map(m => ({ value: m, label: `xai/${m}` })) || [],
    xai: allModelsData.xai?.map(m => ({ value: m, label: `xai/${m}` })) || []
};

// Default models for each provider
const defaultModels = {
    openai: 'gpt-4o-mini',
    anthropic: 'claude-3-5-sonnet',
    google: 'gemini-2.5-flash', // More commonly available than gemini-1.5-pro
    grok: 'grok-2',
    xai: 'grok-2',
    mistral: 'mistral-small',
    meta: 'llama-3.1-70b',
    deepseek: 'deepseek-v3.2',
    alibaba: 'qwen3-max',
    minimax: 'minimax-m2.1',
    moonshotai: 'kimi-k2',
    perplexity: 'sonar',
    amazon: 'nova-lite',
    zai: 'glm-4.7',
    voyage: 'voyage-3-large',
    cohere: 'command-a',
    morph: 'morph-v3-fast',
    nvidia: 'nemotron-nano-9b-v2',
    bfl: 'flux-2-pro',
    vercel: 'v0-1.5-md'
};

// Searchable model selector
let modelSearchInput, modelDropdown, modelSelectHidden;
let filteredModels = [];
let selectedModelIndex = -1;

function initModelSearch() {
    modelSearchInput = document.getElementById('model-search');
    modelDropdown = document.getElementById('model-dropdown');
    modelSelectHidden = document.getElementById('model-select');
    
    if (!modelSearchInput || !modelDropdown || !modelSelectHidden) return;
    
    // Set initial value
    updateModelSearchValue();
    
    // Filter models based on provider
    modelSearchInput.addEventListener('input', handleModelSearch);
    modelSearchInput.addEventListener('focus', () => {
        if (modelSearchInput.value) {
            handleModelSearch();
        } else {
            showModelDropdown();
        }
    });
    modelSearchInput.addEventListener('blur', (e) => {
        // Delay to allow click on dropdown item
        setTimeout(() => {
            if (!modelDropdown.contains(document.activeElement)) {
                hideModelDropdown();
            }
        }, 200);
    });
    modelSearchInput.addEventListener('keydown', handleModelSearchKeydown);
    
    // Update when provider changes
    const providerSelect = document.getElementById('provider-select');
    if (providerSelect) {
        providerSelect.addEventListener('change', function () {
            updateModelSearchValue();
        });
    }
}

function handleModelSearch() {
    const query = modelSearchInput.value.toLowerCase().trim();
    
    // Filter models - show all models that match, but prioritize current provider
    const currentProvider = userProvider;
    filteredModels = allModelsFlat.filter(model => {
        const matches = model.searchText.includes(query);
        return matches;
    });
    
    // Sort: current provider first, then alphabetically
    filteredModels.sort((a, b) => {
        const aIsCurrent = a.provider === currentProvider;
        const bIsCurrent = b.provider === currentProvider;
        if (aIsCurrent && !bIsCurrent) return -1;
        if (!aIsCurrent && bIsCurrent) return 1;
        return a.label.localeCompare(b.label);
    });
    
    // Limit to 50 results for performance
    filteredModels = filteredModels.slice(0, 50);
    
    renderModelDropdown();
    showModelDropdown();
}

function renderModelDropdown() {
    if (!modelDropdown) return;
    
    if (filteredModels.length === 0) {
        modelDropdown.innerHTML = '<div style="padding: 12px; color: #999; text-align: center;">No models found</div>';
        return;
    }
    
    const currentProvider = userProvider;
    let html = '';
    let currentProviderGroup = '';
    
    filteredModels.forEach((model, index) => {
        // Group by provider
        if (model.provider !== currentProviderGroup) {
            if (currentProviderGroup) html += '</div>';
            currentProviderGroup = model.provider;
            const providerName = model.provider.charAt(0).toUpperCase() + model.provider.slice(1).replace('_', ' ');
            html += `<div style="padding: 8px 12px; background: #f5f5f5; font-weight: 600; font-size: 0.85em; color: #666; border-bottom: 1px solid #e5e7eb;">${providerName}</div>`;
        }
        
        const isSelected = model.value === userModel && model.provider === userProvider;
        html += `
            <div class="model-option" data-index="${index}" data-value="${model.value}" data-provider="${model.provider}" 
                 style="padding: 10px 12px; cursor: pointer; border-bottom: 1px solid #f0f0f0; ${isSelected ? 'background: #e8f4f8;' : ''}"
                 onmouseover="this.style.background='#f8f9fa'" 
                 onmouseout="this.style.background='${isSelected ? '#e8f4f8' : 'white'}'"
                 onclick="selectModel('${model.value}', '${model.provider}')">
                <div style="font-weight: ${isSelected ? '600' : '500'}; color: var(--text-primary);">${escapeHtml(model.label)}</div>
            </div>
        `;
    });
    
    if (currentProviderGroup) html += '</div>';
    modelDropdown.innerHTML = html;
}

function showModelDropdown() {
    if (modelDropdown) {
        modelDropdown.style.display = 'block';
    }
}

function hideModelDropdown() {
    if (modelDropdown) {
        modelDropdown.style.display = 'none';
    }
    selectedModelIndex = -1;
}

function resolveModelFromSearchText(text) {
    const q = (text || '').trim();
    if (!q) return null;
    const exact = allModelsFlat.find(function (m) {
        return m.label.toLowerCase() === q.toLowerCase();
    });
    if (exact) {
        return { provider: exact.provider, model: exact.value };
    }
    const slash = q.match(/^([^/]+)\/(.+)$/);
    if (slash) {
        const p = slash[1].trim().toLowerCase();
        const m = slash[2].trim();
        const hit = allModelsFlat.find(function (x) {
            return x.provider === p && x.value === m;
        });
        if (hit) {
            return { provider: hit.provider, model: hit.value };
        }
    }
    return null;
}

function getCurrentModelSelection() {
    const fromSearch = modelSearchInput
        ? resolveModelFromSearchText(modelSearchInput.value)
        : null;
    if (fromSearch) {
        return fromSearch;
    }
    return { provider: userProvider, model: userModel };
}

function persistModelSelection(provider, model) {
    userProvider = provider;
    userModel = model;
    localStorage.setItem('focalprompt_provider', provider);
    localStorage.setItem('focalprompt_model', model);
    const providerSelect = document.getElementById('provider-select');
    if (providerSelect && providerSelect.value !== provider) {
        providerSelect.value = provider;
    }
    if (modelSelectHidden) {
        modelSelectHidden.value = model;
    }
    updateModelSearchValue();
    if (typeof updateModelChipLabel === 'function') {
        updateModelChipLabel();
    }
}

function selectModel(modelValue, modelProvider) {
    persistModelSelection(modelProvider, modelValue);
    
    // Update model select dropdown (if it exists)
    const modelSelect = document.getElementById('model-select');
    if (modelSelect) {
        modelSelect.value = modelValue;
    }
    
    hideModelDropdown();
    updateCostEstimate();
}

// Make selectModel available globally for onclick handlers
window.selectModel = selectModel;

function updateModelSearchValue() {
    if (!modelSearchInput) return;
    
    const selectedModel = allModelsFlat.find(m => m.value === userModel && m.provider === userProvider);
    if (selectedModel) {
        modelSearchInput.value = selectedModel.label;
    } else {
        // Try to find any model with this value
        const anyModel = allModelsFlat.find(m => m.value === userModel);
        if (anyModel) {
            modelSearchInput.value = anyModel.label;
            userProvider = anyModel.provider;
        } else {
            modelSearchInput.value = `${userProvider}/${userModel}`;
        }
    }
    
    if (modelSelectHidden) {
        modelSelectHidden.value = userModel;
    }
}

function handleModelSearchKeydown(e) {
    if (!modelDropdown || modelDropdown.style.display === 'none') return;
    
    const options = modelDropdown.querySelectorAll('.model-option');
    if (options.length === 0) return;
    
    if (e.key === 'ArrowDown') {
        e.preventDefault();
        selectedModelIndex = Math.min(selectedModelIndex + 1, options.length - 1);
        options[selectedModelIndex].scrollIntoView({ block: 'nearest' });
        options[selectedModelIndex].style.background = '#e8f4f8';
        if (selectedModelIndex > 0) {
            options[selectedModelIndex - 1].style.background = '';
        }
    } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        selectedModelIndex = Math.max(selectedModelIndex - 1, 0);
        options[selectedModelIndex].scrollIntoView({ block: 'nearest' });
        options[selectedModelIndex].style.background = '#e8f4f8';
        if (selectedModelIndex < options.length - 1) {
            options[selectedModelIndex + 1].style.background = '';
        }
    } else if (e.key === 'Enter') {
        e.preventDefault();
        if (selectedModelIndex >= 0 && selectedModelIndex < options.length) {
            const option = options[selectedModelIndex];
            const value = option.dataset.value;
            const provider = option.dataset.provider;
            selectModel(value, provider);
        }
    } else if (e.key === 'Escape') {
        hideModelDropdown();
        modelSearchInput.blur();
    }
}

// Legacy function for backward compatibility
function updateModelSelector(provider) {
    // This is now handled by the searchable input
    updateModelSearchValue();
}

// Helper function to get API request headers
function getApiHeaders() {
    return {
        'Content-Type': 'application/json',
    };
}

// Helper: request body with selected model/provider (BYO credentials live server-side via env)
function getApiBody(additionalData = {}) {
    const body = { ...additionalData };
    const sel = getCurrentModelSelection();
    body.model = sel.model;
    body.provider = sel.provider;
    return body;
}

// DOM Elements
const promptInput = document.getElementById('prompt-input');
const outputInput = document.getElementById('output-input');
const detectFociBtn = document.getElementById('detect-foci-btn');
const addFocusBtn = document.getElementById('add-focus-btn');
const clearFociBtn = document.getElementById('clear-foci-btn');
const mergeFociBtn = document.getElementById('merge-foci-btn');
const generateOutputBtn = document.getElementById('generate-output-btn');
const assessBtn = document.getElementById('assess-btn');
const loadAssessmentCheckpointBtn = document.getElementById('load-assessment-checkpoint-btn');
const fociContainer = document.getElementById('foci-container');
const assessmentResults = document.getElementById('assessment-results');
const loadingOverlay = document.getElementById('loading-overlay');
const loadingText = document.getElementById('loading-text');
const promptVisualization = document.getElementById('prompt-visualization');
const promptHighlighted = document.getElementById('prompt-highlighted');
const coverageIndicator = document.getElementById('coverage-indicator');
const coveragePercent = document.getElementById('coverage-percent');
const coverageWarning = document.getElementById('coverage-warning');
const toggleVisualization = document.getElementById('toggle-visualization');
const legendItems = document.getElementById('legend-items');
const slidersContainer = document.getElementById('sliders-container');
const rewritePromptBtn = document.getElementById('rewrite-prompt-btn');
const generateFocusedOutputBtn = document.getElementById('generate-focused-output-btn');
const resetSlidersBtn = document.getElementById('reset-sliders-btn');
const rewrittenPromptContainer = document.getElementById('rewritten-prompt-container');
const rewrittenPrompt = document.getElementById('rewritten-prompt');
const adjustedOutputContainer = document.getElementById('adjusted-output-container');
const adjustedOutput = document.getElementById('adjusted-output');
const compareIntentBtn = document.getElementById('compare-intent-btn');
const focusControlSection = document.getElementById('focus-control-section');
const totalBudget = document.getElementById('total-budget');
const totalBudgetValue = document.getElementById('total-budget-value');
const selectionToolbar = document.getElementById('selection-toolbar');
const tagSelectionBtn = document.getElementById('tag-selection-btn');
const cancelSelectionBtn = document.getElementById('cancel-selection-btn');
const selectionText = document.getElementById('selection-text');
const runAblationBtn = document.getElementById('run-ablation-btn');
const loadAblationCheckpointBtn = document.getElementById('load-ablation-checkpoint-btn');
const ablationResults = document.getElementById('ablation-results');

(function fillDocsMethodsPanel() {
    const el = document.getElementById('docs-methods-panel');
    if (!el || !window.FOCALPROMPT_COPY) return;
    const escape = window.FocalPromptResults
        ? window.FocalPromptResults.escapeHtml
        : function (t) { return String(t == null ? '' : t); };
    el.innerHTML = window.FOCALPROMPT_COPY.METHODS_PANEL.split(/\n\n/).filter(function (p) {
        return p.trim();
    }).map(function (p) {
        return '<p>' + escape(p.trim()) + '</p>';
    }).join('');
})();

if (window.FocalPromptExperiment) {
    window.FocalPromptExperiment.bind();
}
document.querySelectorAll('.experiment-config').forEach(function (root) {
    root.addEventListener('input', function () {
        if (typeof updateCostEstimate === 'function') updateCostEstimate();
    });
});

// Agent Builder elements
const chatInput = document.getElementById('chat-input');
const agentFociContainer = document.getElementById('agent-foci-container');
const agentDetectFociBtn = document.getElementById('agent-detect-foci-btn');
const agentClearFociBtn = document.getElementById('agent-clear-foci-btn');
const importFociBtn = document.getElementById('import-foci-btn');
const assessChatBtn = document.getElementById('assess-chat-btn');
const fociWeightsResults = document.getElementById('foci-weights-results');
const generateAgentResponseBtn = document.getElementById('generate-agent-response-btn');
const agentResponseResults = document.getElementById('agent-response-results');

// Batch Analysis elements
const csvUpload = document.getElementById('csv-upload');
const clearPairsBtn = document.getElementById('clear-pairs-btn');
const manualInputFields = document.getElementById('manual-input-fields');
const manualPairInput = document.getElementById('manual-pair-input');
const manualOutput = document.getElementById('manual-output');
const batchPromptInput = document.getElementById('batch-prompt-input');
const addPairBtn = document.getElementById('add-pair-btn');
const pairsContainer = document.getElementById('pairs-container');
const batchFociContainer = document.getElementById('batch-foci-container');
const batchDetectFociBtn = document.getElementById('batch-detect-foci-btn');
const batchDetectDynamicFociBtn = document.getElementById('batch-detect-dynamic-foci-btn');
const batchImportFociBtn = document.getElementById('batch-import-foci-btn');
const batchClearFociBtn = document.getElementById('batch-clear-foci-btn');
const runBatchAnalysisBtn = document.getElementById('run-batch-analysis-btn');
const batchProgress = document.getElementById('batch-progress');
const batchProgressText = document.getElementById('batch-progress-text');
const batchResults = document.getElementById('batch-results');
const exportResultsBtn = document.getElementById('export-results-btn');
const exportResultsJsonBtn = document.getElementById('export-results-json-btn');
const batchCostEstimate = document.getElementById('batch-cost-estimate');
const batchCostEstimateContent = document.getElementById('batch-cost-estimate-content');
const loadCheckpointBtn = document.getElementById('load-checkpoint-btn');
const checkpointList = document.getElementById('checkpoint-list');
const checkpointListContent = document.getElementById('checkpoint-list-content');

// Batch Agent Building elements
const importBatchResultsBtn = document.getElementById('import-batch-results-btn');
const loadAgentCheckpointBtn = document.getElementById('load-agent-checkpoint-btn');
const runBatchAgentBtn = document.getElementById('run-batch-agent-btn');
const runLLMEvalBtn = document.getElementById('run-llm-eval-btn');
const batchAgentStatus = document.getElementById('batch-agent-status');
const batchAgentResults = document.getElementById('batch-agent-results');
const batchAgentReportingSection = document.getElementById('batch-agent-reporting-section');
const batchAgentReporting = document.getElementById('batch-agent-reporting');
const exportBatchAgentResultsBtn = document.getElementById('export-batch-agent-results-btn');
const promptOptimizationSection = document.getElementById('prompt-optimization-section');
const analyzeOptimizationBtn = document.getElementById('analyze-optimization-btn');
const optimizationResults = document.getElementById('optimization-results');

let batchAgentData = null; // Store imported batch analysis data
let batchAgentResultsData = []; // Store generated agent results

let focusWeights = {}; // Store slider values for each focus
let rewrittenPromptText = '';
let intendedDistribution = {}; // Store intended distribution for comparison
let assessmentFoci = []; // Store assessment results
let singleAblationResults = null; // Store single ablation analysis results
let selectedText = ''; // Currently selected text
let selectedStart = 0; // Start position of selection
let selectedEnd = 0; // End position of selection

// Tab Navigation
function switchTab(tabName) {
    currentTab = tabName;
    
    const buttons = document.querySelectorAll('.tab-btn');
    const contents = document.querySelectorAll('.tab-content');
    
    // Update tab buttons
    buttons.forEach(btn => {
        if (btn.getAttribute('data-tab') === tabName) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
    
    // Re-attach batch analysis handler when switching to batch tab
    if (tabName === 'batch-analysis') {
        setTimeout(() => {
            attachBatchAnalysisHandler();
            updateBatchAnalysisButton();
            console.log('Re-attached batch analysis handler after tab switch');
        }, 100);
    }
    
    // Update tab contents
    contents.forEach(content => {
        if (content.id === `${tabName}-tab`) {
            content.classList.add('active');
        } else {
            content.classList.remove('active');
        }
    });
}

// Initialize tab navigation - use event delegation for reliability
document.addEventListener('click', (e) => {
    // Check if clicked element or its parent is a tab button
    const tabBtn = e.target.closest('.tab-btn');
    if (tabBtn) {
        e.preventDefault();
        e.stopPropagation();
        const tabName = tabBtn.getAttribute('data-tab');
        console.log('Tab clicked via delegation:', tabName, tabBtn);
        if (tabName) {
            switchTab(tabName);
        }
    }
});

// Save/Load Prompt and Foci
function savePromptAndFoci() {
    const prompt = promptInput ? promptInput.value.trim() : '';
    const data = {
        prompt: prompt,
        foci: foci,
        timestamp: new Date().toISOString()
    };
    localStorage.setItem('focalprompt_saved_prompt', JSON.stringify(data));
    alert('✓ Prompt and foci saved! They will be restored when you refresh the page.');
}

function loadPromptAndFoci() {
    const saved = localStorage.getItem('focalprompt_saved_prompt');
    if (!saved) {
        alert('No saved prompt found.');
        return;
    }
    
    if (!confirm('Load saved prompt and foci? This will replace your current prompt and foci.')) {
        return;
    }
    
    try {
        const data = JSON.parse(saved);
        if (promptInput && data.prompt) {
            promptInput.value = data.prompt;
        }
        if (data.foci && Array.isArray(data.foci)) {
            foci = data.foci;
            renderFoci();
        }
        alert('✓ Prompt and foci loaded!');
    } catch (error) {
        alert('Error loading saved data: ' + error.message);
    }
}

// Save/Load Batch Analysis data
function saveBatchAnalysis() {
    const prompt = batchPromptInput ? batchPromptInput.value.trim() : '';
    const data = {
        prompt: prompt,
        foci: batchFoci,
        pairs: batchPairs,
        timestamp: new Date().toISOString()
    };
    localStorage.setItem('focalprompt_saved_batch', JSON.stringify(data));
    alert('✓ Batch analysis data saved!');
}

function loadBatchAnalysis() {
    const saved = localStorage.getItem('focalprompt_saved_batch');
    if (!saved) {
        alert('No saved batch analysis found.');
        return;
    }
    
    if (!confirm('Load saved batch analysis? This will replace your current data.')) {
        return;
    }
    
    try {
        const data = JSON.parse(saved);
        if (batchPromptInput && data.prompt) {
            batchPromptInput.value = data.prompt;
        }
        if (data.foci && Array.isArray(data.foci)) {
            batchFoci = data.foci.map(f => ({
                ...f,
                is_dynamic: f.is_dynamic || false,
                dynamic_type: f.dynamic_type || null
            }));
            renderBatchFoci();
        }
        if (data.pairs && Array.isArray(data.pairs)) {
            // Migrate old structure to new structure
            batchPairs = data.pairs.map(pair => {
                if (pair.inputs) {
                    // Already in new format
                    return pair;
                } else if (pair.chat_content) {
                    // Old format - migrate
                    return {
                        inputs: {
                            chat_content: pair.chat_content || '',
                            rag_context: pair.rag_context || '',
                            tool_results: pair.tool_results || ''
                        },
                        output: pair.output || ''
                    };
                } else {
                    // Fallback
                    return {
                        inputs: {
                            chat_content: pair.input || '',
                            rag_context: '',
                            tool_results: ''
                        },
                        output: pair.output || ''
                    };
                }
            });
            renderPairs();
        }
        updateBatchAnalysisButton();
        updateCostEstimate();
        alert('✓ Batch analysis data loaded!');
    } catch (error) {
        alert('Error loading saved data: ' + error.message);
    }
}

// Model pricing cache
let modelPricingCache = null;

// Load model pricing on page load
async function loadModelPricing() {
    try {
        const response = await fetch('/api/pricing/models');
        if (response.ok) {
            modelPricingCache = await response.json();
            updateCostDisplay();
        }
    } catch (error) {
        console.error('Error loading model pricing:', error);
    }
}

// Update cost display based on selected model
function updateCostDisplay() {
    const costEstimate = document.getElementById('cost-estimate');
    if (!costEstimate || !modelPricingCache) return;

    const sel = getCurrentModelSelection();
    const provider = sel.provider;
    const model = sel.model;

    const providerData = modelPricingCache[provider];
    if (!providerData) {
        costEstimate.textContent = '-';
        return;
    }

    const modelData = providerData.models.find(function (m) { return m.id === model; });
    if (!modelData || !modelData.pricing) {
        costEstimate.textContent = '-';
        return;
    }
    
    const pricing = modelData.pricing;
    
    // Estimate for a typical request (1000 input, 500 output tokens)
    const typicalInput = 1000;
    const typicalOutput = 500;
    const estimatedCost = (typicalInput * pricing.input_per_1k / 1000) + (typicalOutput * pricing.output_per_1k / 1000);
    
    // Show total cost (already includes markup)
    costEstimate.textContent = `$${estimatedCost.toFixed(4)}`;
    costEstimate.title = `Estimated cost for a typical request (${typicalInput} input + ${typicalOutput} output tokens)`;
}

// Check health on page load
window.addEventListener('DOMContentLoaded', async () => {
    // Initialize model search with fallback models first (for immediate UI)
    initModelSearch();
    
    // Then load models dynamically from AI Gateway and update
    const modelsLoaded = await loadModelsFromGateway();
    if (modelsLoaded) {
        // Update the model search input with current selection
        updateModelSearchValue();
        console.log('Model selector updated with gateway models');
    }
    
    // Load model pricing
    await loadModelPricing();
    
    // Also add direct listeners as backup
    const buttons = document.querySelectorAll('.tab-btn');
    console.log('Found', buttons.length, 'tab buttons on load');
    buttons.forEach((btn, index) => {
        console.log(`Button ${index}:`, btn, 'data-tab:', btn.getAttribute('data-tab'));
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            const tabName = btn.getAttribute('data-tab');
            console.log('Tab clicked directly:', tabName);
            if (tabName) {
                switchTab(tabName);
            }
        });
    });
    
    // Auto-load saved prompt and foci
    const savedPrompt = localStorage.getItem('focalprompt_saved_prompt');
    if (savedPrompt) {
        try {
            const data = JSON.parse(savedPrompt);
            if (promptInput && data.prompt) {
                promptInput.value = data.prompt;
            }
            if (data.foci && Array.isArray(data.foci) && data.foci.length > 0) {
                foci = data.foci;
                renderFoci();
                console.log('Auto-loaded saved prompt and', data.foci.length, 'foci');
            }
        } catch (error) {
            console.error('Error auto-loading saved prompt:', error);
        }
    }
    
    // Auto-load saved batch analysis
    const savedBatch = localStorage.getItem('focalprompt_saved_batch');
    if (savedBatch) {
        try {
            const data = JSON.parse(savedBatch);
            if (batchPromptInput && data.prompt) {
                batchPromptInput.value = data.prompt;
            }
            if (data.foci && Array.isArray(data.foci) && data.foci.length > 0) {
                batchFoci = data.foci;
                renderBatchFoci();
            }
            if (data.pairs && Array.isArray(data.pairs) && data.pairs.length > 0) {
                batchPairs = data.pairs;
                renderPairs();
            }
            updateBatchAnalysisButton();
            updateCostEstimate();
            console.log('Auto-loaded saved batch analysis');
        } catch (error) {
            console.error('Error auto-loading saved batch:', error);
        }
    }
    
    updateManualInputFields();
    refreshQualityEvalPreview();
    refreshFocusOrderControls(window.singleAblationResults);
    
    // Initialize settings UI
    const providerSelect = document.getElementById('provider-select');
    const apiKeyInput = document.getElementById('api-key-input');
    const modelSelect = document.getElementById('model-select');
    const saveSettingsBtn = document.getElementById('save-settings-btn');
    const testApiKeyBtn = document.getElementById('test-api-key-btn');
    const toggleSettingsBtn = document.getElementById('toggle-settings-btn');
    const settingsContent = document.getElementById('settings-content');
    const apiKeyStatus = document.getElementById('api-key-status');
    
    if (providerSelect) {
        providerSelect.value = userProvider;
        updateModelSelector(userProvider);
        
        // Update model list when provider changes
        providerSelect.addEventListener('change', () => {
            const newProvider = providerSelect.value;
            const oldProvider = userProvider;
            userProvider = newProvider;
            
            // Only reset model if provider actually changed
            if (oldProvider !== newProvider) {
                // Check if current model is valid for new provider
                const currentModelValid = allModelsFlat.some(m => m.value === userModel && m.provider === newProvider);
                
                if (!currentModelValid) {
                    const defaultModel = defaultModels[newProvider] || (allModelsData[newProvider] && allModelsData[newProvider][0]) || 'gpt-4o-mini';
                    persistModelSelection(newProvider, defaultModel);
                } else {
                    persistModelSelection(newProvider, userModel);
                }
            }
            
            updateModelSelector(newProvider);
        });
    }
    
    if (apiKeyInput) {
        apiKeyInput.value = userApiKey;
    }
    if (modelSelect) {
        modelSelect.value = userModel;
    }
    
    // Toggle settings visibility (preserve model-chip markup)
    if (toggleSettingsBtn && settingsContent) {
        const chipAction = toggleSettingsBtn.querySelector('.chip-action');
        const setExpanded = (expanded) => {
            settingsContent.style.display = expanded ? 'block' : 'none';
            if (chipAction) {
                chipAction.textContent = expanded ? 'Close' : 'Change';
            } else if (!toggleSettingsBtn.querySelector('#model-chip-label')) {
                // Legacy plain button fallback
                toggleSettingsBtn.textContent = expanded ? 'Hide' : 'Show';
            }
            localStorage.setItem('focalprompt_settings_expanded', expanded.toString());
        };

        let isExpanded = localStorage.getItem('focalprompt_settings_expanded') === 'true';
        setExpanded(isExpanded);

        toggleSettingsBtn.addEventListener('click', () => {
            isExpanded = !isExpanded;
            setExpanded(isExpanded);
        });
    }

    const updateModelChipLabel = () => {
        const label = document.getElementById('model-chip-label');
        if (!label) return;
        const provider = (userProvider || 'openai');
        const model = (userModel || '').trim();
        label.textContent = model ? `${provider} · ${model}` : 'Model';
    };
    updateModelChipLabel();
    
    // Save settings — use searchable picker state, not stale hidden <select>
    if (saveSettingsBtn) {
        saveSettingsBtn.addEventListener('click', () => {
            const sel = getCurrentModelSelection();
            const valid = allModelsFlat.some(function (m) {
                return m.provider === sel.provider && m.value === sel.model;
            });
            if (!valid) {
                apiKeyStatus.textContent = '⚠ Pick a model from the search list';
                apiKeyStatus.style.color = '#ffc107';
                return;
            }
            persistModelSelection(sel.provider, sel.model);
            
            apiKeyStatus.textContent = '✓ Model selection saved';
            apiKeyStatus.style.color = '#28a745';
            setTimeout(() => {
                apiKeyStatus.textContent = '';
            }, 3000);
            
            updateCostDisplay();
        });
    }
    
    // Update cost when provider or model changes
    if (providerSelect) {
        providerSelect.addEventListener('change', async () => {
            await updateModelSelector(providerSelect.value);
            updateModelChipLabel();
        });
    }
    
    if (modelSelect) {
        modelSelect.addEventListener('change', () => {
            updateCostDisplay();
            updateModelChipLabel();
        });
    }
    
    // Test API key
    if (testApiKeyBtn) {
        testApiKeyBtn.addEventListener('click', async () => {
            const apiKey = apiKeyInput.value.trim();
            if (!apiKey) {
                apiKeyStatus.textContent = '⚠ Please enter an API key';
                apiKeyStatus.style.color = '#ffc107';
                return;
            }
            
            apiKeyStatus.textContent = 'Testing...';
            apiKeyStatus.style.color = '#666';
            
            try {
                const provider = providerSelect.value;
                const response = await fetch('/api/test-api-key', {
                    method: 'POST',
                    headers: getApiHeaders(),
                    body: JSON.stringify({ 
                        api_key: apiKey,
                        provider: provider
                    })
                });
                
                const data = await response.json();
                if (data.valid) {
                    apiKeyStatus.textContent = '✓ API key is valid';
                    apiKeyStatus.style.color = '#28a745';
                } else {
                    apiKeyStatus.textContent = '✗ API key is invalid: ' + (data.error || 'Unknown error');
                    apiKeyStatus.style.color = '#dc3545';
                }
            } catch (error) {
                apiKeyStatus.textContent = '✗ Error testing API key: ' + error.message;
                apiKeyStatus.style.color = '#dc3545';
            }
        });
    }
    
    // Attach save/load button handlers
    const savePromptBtn = document.getElementById('save-prompt-btn');
    const loadPromptBtn = document.getElementById('load-prompt-btn');
    const saveBatchBtn = document.getElementById('save-batch-btn');
    const loadBatchBtn = document.getElementById('load-batch-btn');
    
    if (savePromptBtn) {
        savePromptBtn.addEventListener('click', savePromptAndFoci);
    }
    if (loadPromptBtn) {
        loadPromptBtn.addEventListener('click', loadPromptAndFoci);
    }
    if (saveBatchBtn) {
        saveBatchBtn.addEventListener('click', saveBatchAnalysis);
    }
    if (loadBatchBtn) {
        loadBatchBtn.addEventListener('click', loadBatchAnalysis);
        
        // Load Checkpoint button
        if (loadCheckpointBtn) {
            loadCheckpointBtn.addEventListener('click', displayCheckpointList);
        }
    }

    const exportWorkspaceBtn = document.getElementById('export-workspace-btn');
    const importWorkspaceBtn = document.getElementById('import-workspace-btn');
    const importWorkspaceInput = document.getElementById('import-workspace-input');
    if (exportWorkspaceBtn) {
        exportWorkspaceBtn.addEventListener('click', exportWorkspaceSessionFile);
    }
    if (importWorkspaceBtn && importWorkspaceInput) {
        importWorkspaceBtn.addEventListener('click', function () {
            importWorkspaceInput.click();
        });
        importWorkspaceInput.addEventListener('change', function () {
            const file = importWorkspaceInput.files && importWorkspaceInput.files[0];
            if (file) {
                importWorkspaceSessionFile(file);
            }
            importWorkspaceInput.value = '';
        });
    }
    
    // Error Modal Event Listeners
    const errorModal = document.getElementById('error-modal');
    const errorModalClose = document.getElementById('error-modal-close');
    const errorModalOk = document.getElementById('error-modal-ok');

    if (errorModalClose) {
        errorModalClose.addEventListener('click', hideErrorModal);
    }

    if (errorModalOk) {
        errorModalOk.addEventListener('click', hideErrorModal);
    }

    // Close modal when clicking overlay
    if (errorModal) {
        const overlay = errorModal.querySelector('.modal-overlay');
        if (overlay) {
            overlay.addEventListener('click', hideErrorModal);
        }
        
        // Close on Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && errorModal.style.display !== 'none') {
                hideErrorModal();
            }
        });
    }
    
    // Health check removed - users no longer need to set API keys
    // The service uses AI Gateway which is configured server-side
});

// Utility Functions
function showLoading(message = 'Processing...') {
    loadingText.textContent = message;
    loadingOverlay.classList.remove('hidden');
}

function hideLoading() {
    loadingOverlay.classList.add('hidden');
}

// Error Modal Functions
function showErrorModal(message) {
    const modal = document.getElementById('error-modal');
    const messageEl = document.getElementById('error-modal-message');
    
    if (!modal || !messageEl) {
        // Fallback to old method if modal doesn't exist
        console.error('Error modal not found, using fallback');
        showError(message);
        return;
    }
    
    messageEl.textContent = message;
    modal.style.display = 'flex';
    
    // Prevent body scroll when modal is open
    document.body.style.overflow = 'hidden';
}

function hideErrorModal() {
    const modal = document.getElementById('error-modal');
    if (modal) {
        modal.style.display = 'none';
        document.body.style.overflow = '';
    }
}

// Updated showError function - uses modal
function showError(message) {
    // Try modal first
    const modal = document.getElementById('error-modal');
    if (modal) {
        showErrorModal(message);
        return;
    }
    
    // Fallback to old method if modal doesn't exist
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.textContent = message;
    if (assessmentResults) {
        assessmentResults.innerHTML = '';
        assessmentResults.appendChild(errorDiv);
    } else {
        console.error('Error:', message);
    }
}

// Auto-Detect Foci
detectFociBtn.addEventListener('click', async () => {
    const prompt = promptInput.value.trim();
    
    if (!prompt) {
        showErrorModal('Please enter a prompt first.');
        return;
    }
    
    // Estimate cost before making the request
    try {
        const estimateResponse = await fetch('/api/pricing/estimate', {
            method: 'POST',
            headers: getApiHeaders(),
            body: JSON.stringify({
                estimated_input_tokens: Math.ceil(prompt.length / 4) + 500, // Rough estimate: prompt + system message
                estimated_output_tokens: 1000, // Estimate for foci detection response
                model: userModel,
                provider: userProvider
            })
        });
        
        if (estimateResponse.ok) {
            const estimate = await estimateResponse.json();
            const cost = estimate.total_cost || 0;
            
            if (cost > 0) {
                
                // Show action-specific cost estimate
                const confirmMsg = `Auto-Detect Foci\n\nEstimated Cost: $${cost.toFixed(4)}\n\nYour configured provider will be billed for these tokens.\n\nProceed?`;
                if (!confirm(confirmMsg)) {
                    return;
                }
            }
        } else {
            // If estimate fails, log but continue (don't block the request)
            const errorText = await estimateResponse.text();
            console.warn('Could not get cost estimate:', estimateResponse.status, errorText);
        }
    } catch (error) {
        console.warn('Could not estimate cost:', error);
        // Continue anyway - don't block the request
    }
    
    showLoading('Detecting foci from prompt...');
    
    try {
        const response = await fetch('/api/detect-foci', {
            method: 'POST',
            headers: getApiHeaders(),
            body: JSON.stringify(getApiBody({ prompt })),
        });
        
        // Check content-type before parsing JSON
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            const text = await response.text();
            throw new Error(`Server returned ${response.status}: ${text.substring(0, 200)}`);
        }
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to detect foci');
        }
        
        if (!data.foci || data.foci.length === 0) {
            throw new Error('No foci detected. Please check your prompt.');
        }
        
        foci = (data.foci || []).map(f => ({
            ...f,
            is_dynamic: f.is_dynamic || false,
            dynamic_type: f.dynamic_type || null
        }));
        window.fociCoverage = data.coverage || null;
        // Automatic proposals without source provenance are omitted from foci;
        // keep them for debug/advanced inspection only.
        window.rejectedFocusProposals = data.rejected_proposals || [];
        if (window.rejectedFocusProposals.length) {
            console.info(
                'Omitted',
                window.rejectedFocusProposals.length,
                'auto-detected proposal(s) lacking source provenance',
                window.rejectedFocusProposals
            );
        }
        renderFoci();
        
    } catch (error) {
        // Log full error details for debugging
        console.error('Detect foci error:', error);
        console.error('Error details:', {
            message: error.message,
            stack: error.stack,
            response: error.response
        });
        
        // Show user-friendly error message
        let errorMessage = 'Error detecting foci: ' + error.message;
        if (error.message.includes('404') || error.message.includes('deployment')) {
            errorMessage = 'Service temporarily unavailable. Please try again in a moment. If the problem persists, please contact support.';
        }
        showErrorModal(errorMessage);
    } finally {
        hideLoading();
    }
});

// Handle text selection in prompt
if (promptInput) {
    promptInput.addEventListener('mouseup', handleTextSelection);
    promptInput.addEventListener('keyup', handleTextSelection);
}

function handleTextSelection() {
    const textarea = promptInput;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selected = textarea.value.substring(start, end).trim();
    
    if (selected.length > 0 && start !== end) {
        selectedText = selected;
        selectedStart = start;
        selectedEnd = end;
        selectionText.textContent = `"${selected.substring(0, 50)}${selected.length > 50 ? '...' : ''}"`;
        selectionToolbar.classList.remove('hidden');
    } else {
        selectionToolbar.classList.add('hidden');
        selectedText = '';
    }
}

// Tag selected text as focus
if (tagSelectionBtn) {
    tagSelectionBtn.addEventListener('click', () => {
        if (!selectedText) {
            showErrorModal('Please select some text first.');
            return;
        }
        
        const focusName = prompt('Enter a name for this focus point:', selectedText.substring(0, 50));
        if (!focusName) {
            selectionToolbar.classList.add('hidden');
            promptInput.setSelectionRange(0, 0);
            return;
        }
        
        // Check if this text is already tagged
        const alreadyTagged = foci.some(f => f.prompt_section === selectedText);
        if (alreadyTagged) {
            if (!confirm('This text is already tagged as a focus. Add it anyway?')) {
                selectionToolbar.classList.add('hidden');
                promptInput.setSelectionRange(0, 0);
                return;
            }
        }
        
        foci.push({
            focus: focusName.trim(),
            prompt_section: selectedText,
            description: '',
            is_dynamic: false,
            dynamic_type: null,
            verified: true,
            char_start: selectedStart,
            char_end: selectedEnd,
            grounding_method: 'manual_selection',
            grounding_confidence: 1.0,
        });
        
        renderFoci();
        selectionToolbar.classList.add('hidden');
        promptInput.setSelectionRange(0, 0);
    });
}

// Cancel selection
if (cancelSelectionBtn) {
    cancelSelectionBtn.addEventListener('click', () => {
        selectionToolbar.classList.add('hidden');
        promptInput.setSelectionRange(0, 0);
        selectedText = '';
    });
}

// Clear All Foci
clearFociBtn.addEventListener('click', () => {
    if (confirm('Are you sure you want to clear all foci?')) {
        foci = [];
        renderFoci();
    }
});

// Merge foci button
if (mergeFociBtn) {
    mergeFociBtn.addEventListener('click', mergeSelectedFoci);
}

// Color palette for foci
const focusColors = [
    '#dbeafe', '#d1fae5', '#fef3c7', '#fce7f3', '#e0e7ff',
    '#fef2f2', '#ecfdf5', '#f0fdfa', '#fefce8', '#fef2f2',
    '#f3e8ff', '#ede9fe', '#e0f2fe', '#f0f9ff', '#f5f3ff'
];


// Repair an unverified focus by binding the current prompt selection as its exact span.
function repairFocusSpan(index) {
    const prompt = promptInput.value;
    const start = promptInput.selectionStart;
    const end = promptInput.selectionEnd;
    if (start === end || start == null || end == null) {
        showErrorModal('Select the exact source span in the prompt first, then click Use selection as span.');
        return;
    }
    if (start < 0 || end > prompt.length || start >= end) {
        showErrorModal('Invalid selection for focus span.');
        return;
    }
    const exact = prompt.substring(start, end);
    const focus = foci[index];
    if (!focus) return;
    if (!focus.original_proposal && focus.prompt_section) {
        focus.original_proposal = focus.prompt_section;
    }
    focus.char_start = start;
    focus.char_end = end;
    focus.prompt_section = exact;
    focus.verified = true;
    focus.grounding_method = 'manual_selection';
    focus.grounding_confidence = 1.0;
    focus.grounding_failure = null;
    focus.attributable = focus.is_dynamic ? false : true;
    if (focus.is_dynamic) {
        focus.reason = 'dynamic_slot';
    } else {
        focus.reason = null;
    }
    renderFoci();
}

// Render Foci
function renderFoci() {
    if (foci.length === 0) {
        fociContainer.innerHTML = '<p class="empty-state">No foci defined yet. Click "Auto-Detect Foci" or "Add Focus Manually" to get started.</p>';
        promptVisualization.classList.add('hidden');
        coverageIndicator.classList.add('hidden');
        coverageWarning.classList.add('hidden');
        if (mergeFociBtn) mergeFociBtn.style.display = 'none';
        if (window.FocalPromptExperiment) window.FocalPromptExperiment.refreshAll();
        return;
    }
    
    // Assign colors to foci
    foci.forEach((focus, index) => {
        focus.color = focusColors[index % focusColors.length];
        focus.colorDark = getDarkColor(focus.color);
    });
    
    fociContainer.innerHTML = foci.map((focus, index) => {
        const isDynamic = focus.is_dynamic || false;
        const dynamicType = focus.dynamic_type || '';
        const dynamicTypeOptions = ['chat', 'rag', 'tools', 'other'];
        
        return `
        <div class="focus-item" data-focus-index="${index}" draggable="true" style="border-left: 4px solid ${focus.colorDark}; cursor: move;">
            <div class="focus-item-header">
                <div class="focus-item-title" style="display: flex; align-items: center; gap: 8px;">
                    <span style="cursor: move; user-select: none;">☰</span>
                    <input type="checkbox" class="focus-select-checkbox" data-focus-index="${index}" onchange="updateMergeButton()" style="cursor: pointer;">
                    <span>${index + 1}. ${escapeHtml(focus.focus)}</span>
                    ${isDynamic ? `<span style="margin-left: 8px; padding: 2px 6px; background: #fef3c7; border-radius: 4px; font-size: 0.75em; color: #92400e;">Dynamic: ${dynamicType}</span>` : ''}
                </div>
                <button class="focus-item-remove" onclick="removeFocus(${index})">×</button>
            </div>
            <div class="focus-item-section">
                ${focus.verified === false ? `
                <div style="margin-bottom:8px;padding:8px;background:#fef3c7;border:1px solid #f59e0b;border-radius:6px;font-size:0.9em;">
                    <strong>Not grounded for ablation</strong>
                    <div style="margin-top:4px;">Could not uniquely map this focus to an exact span of the original prompt${focus.grounding_failure ? ` (${escapeHtml(focus.grounding_failure)})` : ''}.</div>
                    ${focus.original_proposal || focus.prompt_section ? `<div style="margin-top:6px;"><em>Proposed:</em> ${escapeHtml(focus.original_proposal || focus.prompt_section)}</div>` : ''}
                    ${focus.evidence_quote ? `<div style="margin-top:4px;"><em>Evidence quote:</em> ${escapeHtml(focus.evidence_quote)}</div>` : ''}
                    <div style="margin-top:8px;">Select the exact source span in the prompt, then
                      <button type="button" onclick="repairFocusSpan(${index})" style="margin-left:4px;padding:2px 8px;font-size:0.85em;">Use selection as span</button>
                    </div>
                </div>` : `
                <div style="margin-bottom:6px;">
                  <span style="display:inline-block;padding:2px 6px;border-radius:4px;font-size:0.75em;background:#dcfce7;color:#166534;">Verified span</span>
                  ${focus.grounding_method ? `<span style="margin-left:6px;font-size:0.75em;color:#64748b;">${escapeHtml(focus.grounding_method)}</span>` : ''}
                </div>
                <strong>Exact source span under test:</strong> ${escapeHtml(focus.prompt_section)}
                `}
            </div>
            <div class="focus-item-controls" style="margin-top: 8px; padding-top: 8px; border-top: 1px solid #e5e7eb; display: flex; align-items: center; gap: 12px;">
                <label style="display: flex; align-items: center; gap: 6px; cursor: pointer;">
                    <input type="checkbox" ${isDynamic ? 'checked' : ''} onchange="toggleFocusDynamic(${index}, this.checked)" style="cursor: pointer;">
                    <span style="font-size: 0.9em;">Mark as Dynamic</span>
                </label>
                ${isDynamic ? `
                <select onchange="setFocusDynamicType(${index}, this.value)" style="padding: 4px 8px; border: 1px solid #d1d5db; border-radius: 4px; font-size: 0.9em;" value="${dynamicType}">
                    <option value="">Select type...</option>
                    ${dynamicTypeOptions.map(opt => `<option value="${opt}" ${dynamicType === opt ? 'selected' : ''}>${opt.charAt(0).toUpperCase() + opt.slice(1)}</option>`).join('')}
                </select>
                ` : ''}
            </div>
        </div>
        `;
    }).join('');
    
    // Setup drag and drop
    setupDragAndDrop();
    
    // Update merge button visibility
    updateMergeButton();
    
    // Update visualization
    updateCoverageVisualization();
    updateCoverageStats();
    
    // Enable ablation analysis if we have foci
    if (foci.length > 0) {
        runAblationBtn.disabled = false;
    } else {
        runAblationBtn.disabled = true;
    }
    if (window.FocalPromptExperiment) window.FocalPromptExperiment.refreshAll();
}

// Setup drag and drop for foci reordering
function setupDragAndDrop() {
    const focusItems = fociContainer.querySelectorAll('.focus-item');
    
    focusItems.forEach(item => {
        item.addEventListener('dragstart', handleDragStart);
        item.addEventListener('dragover', handleDragOver);
        item.addEventListener('drop', handleDrop);
        item.addEventListener('dragend', handleDragEnd);
    });
}

let draggedIndex = null;
let dragOverIndex = null;

function handleDragStart(e) {
    draggedIndex = parseInt(e.target.closest('.focus-item').dataset.focusIndex);
    e.target.closest('.focus-item').style.opacity = '0.5';
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/html', e.target.outerHTML);
}

function handleDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    
    const targetItem = e.target.closest('.focus-item');
    if (!targetItem) return;
    
    const targetIndex = parseInt(targetItem.dataset.focusIndex);
    if (targetIndex !== draggedIndex && targetIndex !== dragOverIndex) {
        // Remove previous drop indicator
        if (dragOverIndex !== null) {
            const prevItem = fociContainer.querySelector(`[data-focus-index="${dragOverIndex}"]`);
            if (prevItem) prevItem.style.borderTop = '';
        }
        
        // Add drop indicator
        targetItem.style.borderTop = '3px solid var(--primary-color)';
        dragOverIndex = targetIndex;
    }
}

function handleDrop(e) {
    e.preventDefault();
    
    const targetItem = e.target.closest('.focus-item');
    if (!targetItem || draggedIndex === null) return;
    
    const targetIndex = parseInt(targetItem.dataset.focusIndex);
    
    if (draggedIndex !== targetIndex) {
        // Reorder foci array
        const [draggedFocus] = foci.splice(draggedIndex, 1);
        foci.splice(targetIndex, 0, draggedFocus);
        
        // Re-render to update indices
        renderFoci();
    }
    
    // Clean up
    handleDragEnd(e);
}

function handleDragEnd(e) {
    e.target.closest('.focus-item').style.opacity = '1';
    
    // Remove drop indicators
    const focusItems = fociContainer.querySelectorAll('.focus-item');
    focusItems.forEach(item => {
        item.style.borderTop = '';
    });
    
    draggedIndex = null;
    dragOverIndex = null;
}

// Update merge button visibility based on selected foci
function updateMergeButton() {
    if (!mergeFociBtn) return;
    
    const selectedCheckboxes = fociContainer.querySelectorAll('.focus-select-checkbox:checked');
    const selectedCount = selectedCheckboxes.length;
    
    if (selectedCount >= 2) {
        mergeFociBtn.style.display = 'inline-block';
        mergeFociBtn.textContent = `🔗 Merge Selected (${selectedCount})`;
    } else {
        mergeFociBtn.style.display = 'none';
    }
}

// Merge selected foci
function mergeSelectedFoci() {
    const selectedCheckboxes = Array.from(fociContainer.querySelectorAll('.focus-select-checkbox:checked'));
    
    if (selectedCheckboxes.length < 2) {
        showErrorModal('Please select at least 2 foci to merge.');
        return;
    }
    
    const selectedIndices = selectedCheckboxes
        .map(cb => parseInt(cb.dataset.focusIndex))
        .sort((a, b) => a - b); // Sort ascending
    
    // Merge foci: combine focus names and prompt sections
    const mergedFocus = {
        focus: foci[selectedIndices[0]].focus, // Use first focus name as base
        prompt_section: foci[selectedIndices[0]].prompt_section, // Use first prompt section as base
        is_dynamic: foci[selectedIndices[0]].is_dynamic || false,
        dynamic_type: foci[selectedIndices[0]].dynamic_type || ''
    };
    
    // Combine all selected foci
    const allFocusNames = selectedIndices.map(i => foci[i].focus);
    const allPromptSections = selectedIndices.map(i => foci[i].prompt_section);
    
    // Merge focus names (if different)
    const uniqueNames = [...new Set(allFocusNames)];
    if (uniqueNames.length > 1) {
        mergedFocus.focus = uniqueNames.join(' + ');
    }
    
    // Merge prompt sections (if different)
    const uniqueSections = [...new Set(allPromptSections)];
    if (uniqueSections.length > 1) {
        mergedFocus.prompt_section = uniqueSections.join(' | ');
    }
    
    // If any selected focus is dynamic, mark merged as dynamic
    const hasDynamic = selectedIndices.some(i => foci[i].is_dynamic);
    if (hasDynamic) {
        mergedFocus.is_dynamic = true;
        // Use the first dynamic type found
        const dynamicType = selectedIndices.find(i => foci[i].is_dynamic && foci[i].dynamic_type);
        if (dynamicType !== undefined) {
            mergedFocus.dynamic_type = foci[dynamicType].dynamic_type;
        }
    }
    
    // Remove selected foci (in reverse order to maintain indices)
    for (let i = selectedIndices.length - 1; i >= 0; i--) {
        foci.splice(selectedIndices[i], 1);
    }
    
    // Insert merged focus at the position of the first selected focus
    foci.splice(selectedIndices[0], 0, mergedFocus);
    
    // Re-render
    renderFoci();
    
    showSuccessMessage(`Merged ${selectedIndices.length} foci into one.`);
}

// Helper function to show success message
function showSuccessMessage(message) {
    // Create a temporary success message
    const successDiv = document.createElement('div');
    successDiv.style.cssText = 'position: fixed; top: 20px; right: 20px; background: #10b981; color: white; padding: 12px 20px; border-radius: 6px; z-index: 10000; box-shadow: 0 4px 6px rgba(0,0,0,0.1);';
    successDiv.textContent = '✓ ' + message;
    document.body.appendChild(successDiv);
    
    setTimeout(() => {
        successDiv.style.opacity = '0';
        successDiv.style.transition = 'opacity 0.3s';
        setTimeout(() => successDiv.remove(), 300);
    }, 2000);
}

// Toggle focus dynamic status
function toggleFocusDynamic(index, isDynamic) {
    if (foci[index]) {
        foci[index].is_dynamic = isDynamic;
        if (!isDynamic) {
            foci[index].dynamic_type = null;
        } else if (!foci[index].dynamic_type) {
            // Default to 'chat' if no type set
            foci[index].dynamic_type = 'chat';
        }
        renderFoci();
    }
}

// Set focus dynamic type
function setFocusDynamicType(index, dynamicType) {
    if (foci[index]) {
        foci[index].dynamic_type = dynamicType || null;
        if (dynamicType) {
            foci[index].is_dynamic = true;
        }
        renderFoci();
    }
}

// Get darker shade of a color
function getDarkColor(lightColor) {
    const colorMap = {
        '#dbeafe': '#3b82f6', // blue
        '#d1fae5': '#10b981', // green
        '#fef3c7': '#f59e0b', // yellow
        '#fce7f3': '#ec4899', // pink
        '#e0e7ff': '#6366f1', // indigo
        '#fef2f2': '#ef4444', // red
        '#ecfdf5': '#059669', // emerald
        '#f0fdfa': '#14b8a6', // teal
        '#fefce8': '#eab308', // yellow
        '#f3e8ff': '#a855f7', // purple
        '#ede9fe': '#8b5cf6', // violet
        '#e0f2fe': '#06b6d4', // cyan
        '#f0f9ff': '#0ea5e9', // sky
        '#f5f3ff': '#9333ea'  // purple
    };
    return colorMap[lightColor] || '#64748b';
}

// Update coverage visualization
function updateCoverageVisualization() {
    const prompt = promptInput.value.trim();
    
    if (!prompt || foci.length === 0) {
        promptVisualization.classList.add('hidden');
        if (toggleVisualization) toggleVisualization.textContent = 'Show';
        return;
    }
    
    promptVisualization.classList.remove('hidden');
    if (toggleVisualization) toggleVisualization.textContent = 'Hide';
    
    // Find all covered sections
    const coveredRanges = [];
    foci.forEach((focus, index) => {
        if (focus.verified === false || focus.is_dynamic) {
            return;
        }
        let startIndex = null;
        let endIndex = null;
        if (Number.isInteger(focus.char_start) && Number.isInteger(focus.char_end)
            && focus.char_start >= 0 && focus.char_end <= prompt.length
            && focus.char_start < focus.char_end) {
            startIndex = focus.char_start;
            endIndex = focus.char_end;
        } else if (focus.prompt_section) {
            const idx = prompt.indexOf(focus.prompt_section);
            if (idx !== -1) {
                startIndex = idx;
                endIndex = idx + focus.prompt_section.length;
            }
        }
        if (startIndex !== null) {
            coveredRanges.push({
                start: startIndex,
                end: endIndex,
                focusIndex: index,
                focus: focus
            });
        }
    });
    
    // Sort by start position
    coveredRanges.sort((a, b) => a.start - b.start);
    
    // Merge overlapping ranges
    const mergedRanges = [];
    for (const range of coveredRanges) {
        if (mergedRanges.length === 0) {
            mergedRanges.push({...range, focusIndices: [range.focusIndex]});
        } else {
            const last = mergedRanges[mergedRanges.length - 1];
            if (range.start <= last.end) {
                last.end = Math.max(last.end, range.end);
                if (!last.focusIndices.includes(range.focusIndex)) {
                    last.focusIndices.push(range.focusIndex);
                }
            } else {
                mergedRanges.push({...range, focusIndices: [range.focusIndex]});
            }
        }
    }
    
    // Build highlighted HTML
    let html = '';
    let lastIndex = 0;
    let totalCovered = 0;
    
    for (const range of mergedRanges) {
        // Add uncovered text before this range
        if (range.start > lastIndex) {
            const uncovered = prompt.substring(lastIndex, range.start);
            html += `<span class="uncovered" title="Not covered by any focus">${escapeHtml(uncovered)}</span>`;
        }
        
        // Add covered text
        const covered = prompt.substring(range.start, range.end);
        const focusNames = range.focusIndices.map(i => foci[i].focus).join(', ');
        const colors = range.focusIndices.map(i => foci[i].color).join(', ');
        html += `<span class="highlight" style="background: ${foci[range.focusIndices[0]].color};" title="Focus: ${escapeHtml(focusNames)}">${escapeHtml(covered)}</span>`;
        
        totalCovered += (range.end - range.start);
        lastIndex = range.end;
    }
    
    // Add remaining uncovered text
    if (lastIndex < prompt.length) {
        const uncovered = prompt.substring(lastIndex);
        html += `<span class="uncovered" title="Not covered by any focus">${escapeHtml(uncovered)}</span>`;
    }
    
    promptHighlighted.innerHTML = html;
    
    // Update legend
    updateLegend();
}

// Update legend
function updateLegend() {
    if (foci.length === 0) {
        legendItems.innerHTML = '';
        return;
    }
    
    legendItems.innerHTML = foci.map((focus, index) => `
        <div class="legend-item">
            <div class="legend-color" style="background: ${focus.color}; border-color: ${focus.colorDark};"></div>
            <span class="legend-item-name">${index + 1}. ${escapeHtml(focus.focus.substring(0, 30))}${focus.focus.length > 30 ? '...' : ''}</span>
        </div>
    `).join('');
}

// Update coverage statistics
function updateCoverageStats() {
    const prompt = promptInput.value.trim();
    
    if (!prompt || foci.length === 0) {
        coverageIndicator.classList.add('hidden');
        coverageWarning.classList.add('hidden');
        return;
    }
    
    // Calculate coverage
    let totalCovered = 0;
    const coveredPositions = new Set();
    
    foci.forEach(focus => {
        const section = focus.prompt_section;
        if (section) {
            const startIndex = prompt.toLowerCase().indexOf(section.toLowerCase());
            if (startIndex !== -1) {
                for (let i = startIndex; i < startIndex + section.length; i++) {
                    coveredPositions.add(i);
                }
            }
        }
    });
    
    totalCovered = coveredPositions.size;
    const coverage = (totalCovered / prompt.length) * 100;
    
    coverageIndicator.classList.remove('hidden');
    coveragePercent.textContent = `${coverage.toFixed(1)}%`;
    
    // Update warning
    if (coverage < 100) {
        coverageWarning.classList.remove('hidden');
    } else {
        coverageWarning.classList.add('hidden');
    }
    
    // Update color based on coverage
    if (coverage === 100) {
        coverageIndicator.style.background = '#d1fae5';
        coveragePercent.style.color = '#059669';
    } else if (coverage >= 80) {
        coverageIndicator.style.background = '#fef3c7';
        coveragePercent.style.color = '#d97706';
    } else {
        coverageIndicator.style.background = '#fee2e2';
        coveragePercent.style.color = '#dc2626';
    }
}

// Remove Focus
function removeFocus(index) {
    foci.splice(index, 1);
    renderFoci();
}

// Generate Output
generateOutputBtn.addEventListener('click', async () => {
    const prompt = promptInput.value.trim();
    
    if (!prompt) {
        showErrorModal('Please enter a prompt first.');
        return;
    }
    
    // Estimate cost before making the request
    try {
        const estimateResponse = await fetch('/api/pricing/estimate', {
            method: 'POST',
            headers: getApiHeaders(),
            body: JSON.stringify({
                estimated_input_tokens: Math.ceil(prompt.length / 4) + 500, // Rough estimate: prompt + system message
                estimated_output_tokens: 500, // Estimate for generated output
                model: userModel,
                provider: userProvider
            })
        });
        
        if (estimateResponse.ok) {
            const estimateData = await estimateResponse.json();
            const estimatedCost = estimateData.total_cost || 0;
            
            if (estimatedCost > 0) {
                const confirmMessage = `Estimated cost: $${estimatedCost.toFixed(4)}\n\nProceed with generating output?`;
                if (!confirm(confirmMessage)) {
                    return;
                }
            }
        }
    } catch (error) {
        console.warn('Could not fetch cost estimate:', error);
        // Continue anyway - cost estimate is optional
    }
    
    showLoading('Generating output...');
    
    try {
        const response = await fetch('/api/generate-output', {
            method: 'POST',
            headers: getApiHeaders(),
            body: JSON.stringify(getApiBody({ prompt })),
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to generate output');
        }
        
        if (!data.output) {
            throw new Error('No output generated. Please try again.');
        }
        
        outputInput.value = data.output;
        
        // Reset flag - this is not from adjusted prompt
        window.generatedFromAdjustedPrompt = false;
        compareIntentBtn.classList.add('hidden');
        
    } catch (error) {
        showError('Error generating output: ' + error.message);
        console.error('Generate output error:', error);
    } finally {
        hideLoading();
    }
});

// Load Assessment Checkpoint
if (loadAssessmentCheckpointBtn) {
    loadAssessmentCheckpointBtn.addEventListener('click', async () => {
        try {
            const checkpoints = await listCheckpoints('single_assessment');
            if (checkpoints.length === 0) {
                showErrorModal('No assessment checkpoints found. Previous runs before checkpoint saving was implemented were not saved. Future runs will be automatically saved.');
                return;
            }
            await displayCheckpointList('single_assessment');
        } catch (error) {
            showError('Error loading checkpoints: ' + error.message);
            console.error('Checkpoint loading error:', error);
        }
    });
}

// Assess Focus
assessBtn.addEventListener('click', async () => {
    const prompt = promptInput.value.trim();
    const output = outputInput.value.trim();
    
    if (!prompt) {
        alert('Please enter a prompt.');
        return;
    }
    
    if (!output) {
        showErrorModal('Please enter or generate an output.');
        return;
    }
    
    // Estimate cost before making the request
    try {
        // Estimate tokens: prompt + output + foci descriptions + system message
        const promptTokens = Math.ceil(prompt.length / 4);
        const outputTokens = Math.ceil(output.length / 4);
        const fociTokens = foci.length > 0 ? foci.reduce((sum, f) => sum + Math.ceil((f.name?.length || 0) / 4) + Math.ceil((f.description?.length || 0) / 4), 0) : 0;
        const systemTokens = 1000; // System message + instructions
        const estimatedInputTokens = promptTokens + outputTokens + fociTokens + systemTokens;
        const estimatedOutputTokens = Math.max(500, foci.length * 200); // Assessment response scales with number of foci
        
        const estimateResponse = await fetch('/api/pricing/estimate', {
            method: 'POST',
            headers: getApiHeaders(),
            body: JSON.stringify({
                estimated_input_tokens: estimatedInputTokens,
                estimated_output_tokens: estimatedOutputTokens,
                model: userModel,
                provider: userProvider
            })
        });
        
        if (estimateResponse.ok) {
            const estimate = await estimateResponse.json();
            const cost = estimate.total_cost || 0;
            
            if (cost > 0) {
            }
        }
    } catch (error) {
        console.warn('Could not estimate cost:', error);
        // Continue anyway - don't block the request
    }
    
    showLoading('Assessing focus distribution...');
    
    try {
        const response = await fetch('/api/assess', {
            method: 'POST',
            headers: getApiHeaders(),
            body: JSON.stringify(getApiBody({ 
                prompt, 
                output,
                foci: foci.length > 0 ? foci : undefined
            })),
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to assess focus');
        }
        
        renderAssessment(data);
        
    } catch (error) {
        showError('Error assessing focus: ' + error.message);
    } finally {
        hideLoading();
    }
});

// Helper function to match assessed foci to original foci
function matchFocus(originalFocus, assessedFoci) {
    // Try exact name match first
    let match = assessedFoci.find(af => 
        af.focus.toLowerCase().trim() === originalFocus.focus.toLowerCase().trim()
    );
    if (match) return match;
    
    // Try matching by prompt_section (exact or substring)
    const originalSection = originalFocus.prompt_section.toLowerCase().trim();
    match = assessedFoci.find(af => {
        const assessedSection = (af.prompt_section || '').toLowerCase().trim();
        return assessedSection.includes(originalSection) || 
               originalSection.includes(assessedSection) ||
               assessedSection === originalSection;
    });
    if (match) return match;
    
    // Try fuzzy name matching (contains check)
    match = assessedFoci.find(af => {
        const originalName = originalFocus.focus.toLowerCase();
        const assessedName = af.focus.toLowerCase();
        return originalName.includes(assessedName) || 
               assessedName.includes(originalName);
    });
    if (match) return match;
    
    return null;
}

// Render Assessment Results
function renderAssessment(data) {
    const totalPoints = data.foci.reduce((sum, f) => sum + f.score, 0);
    
    // Merge assessment results with all original foci
    // This ensures all foci are shown, even if they got 0 points
    const allFoci = [];
    
    // For each original focus, try to find a matching assessed focus
    foci.forEach(originalFocus => {
        const matched = matchFocus(originalFocus, data.foci);
        
        if (matched) {
            // Use the matched assessment result, but keep original focus name and section
            allFoci.push({
                focus: originalFocus.focus,
                prompt_section: originalFocus.prompt_section,
                score: matched.score || 0,
                explanation: matched.explanation || 'Not addressed in the output'
            });
        } else {
            // No match found - this focus wasn't assessed (got 0 points)
            allFoci.push({
                focus: originalFocus.focus,
                prompt_section: originalFocus.prompt_section,
                score: 0,
                explanation: 'Not addressed in the output - this focus was not found in the assessment results'
            });
        }
    });
    
    // Also include any assessed foci that don't match original foci (in case assessment found new ones)
    data.foci.forEach(assessedFocus => {
        const alreadyIncluded = allFoci.some(f => 
            matchFocus({focus: f.focus, prompt_section: f.prompt_section}, [assessedFocus])
        );
        if (!alreadyIncluded) {
            allFoci.push(assessedFocus);
        }
    });
    
    // Store for sliders and workspace export
    assessmentFoci = allFoci;
    window.assessmentFoci = allFoci;
    window.lastAssessmentApiPayload = data;
    if (window.FocalPromptReport && typeof window.FocalPromptReport.refresh === 'function') {
        window.FocalPromptReport.refresh();
    }
    
    let html = `
        <div class="assessment-summary">
            <h3>Overall Summary</h3>
            <p>${escapeHtml(data.overall_summary || 'No summary available.')}</p>
            <p style="margin-top: 12px; font-weight: 600;">Total Points: ${totalPoints.toFixed(1)}/100</p>
        </div>
        <div class="assessment-foci">
    `;
    
    allFoci.forEach((focus, index) => {
        const score = focus.score || 0;
        html += `
            <div class="assessment-focus">
                <div class="assessment-focus-header">
                    <div class="assessment-focus-title">${index + 1}. ${escapeHtml(focus.focus)}</div>
                    <div class="assessment-focus-score">${score.toFixed(1)}</div>
                </div>
                <div class="score-bar">
                    <div class="score-bar-fill" style="width: ${score}%"></div>
                </div>
                <div class="assessment-focus-section">
                    <strong>Prompt Section:</strong> ${escapeHtml(focus.prompt_section)}
                </div>
                <div class="assessment-focus-explanation">
                    ${escapeHtml(focus.explanation)}
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    assessmentResults.innerHTML = html;
    
    // Show focus control section and initialize sliders with all foci
    focusControlSection.classList.remove('hidden');
    initializeSlidersFromAssessment(allFoci);
    
    // Show compare button only if we've generated output from adjusted prompt
    if (window.generatedFromAdjustedPrompt && Object.keys(intendedDistribution).length > 0) {
        compareIntentBtn.classList.remove('hidden');
    } else {
        compareIntentBtn.classList.add('hidden');
    }

    refreshExperimentCComparison();
}

// Utility: Escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Toggle visualization
if (toggleVisualization) {
    toggleVisualization.addEventListener('click', () => {
        if (promptVisualization.classList.contains('hidden')) {
            promptVisualization.classList.remove('hidden');
            toggleVisualization.textContent = 'Hide';
        } else {
            promptVisualization.classList.add('hidden');
            toggleVisualization.textContent = 'Show';
        }
    });
}

// Update visualization when prompt changes
if (promptInput) {
    promptInput.addEventListener('input', () => {
        if (foci.length > 0) {
            updateCoverageVisualization();
            updateCoverageStats();
        }
        // Hide selection toolbar if prompt changes
        selectionToolbar.classList.add('hidden');
    });
    
    // Hide selection toolbar when clicking outside
    promptInput.addEventListener('blur', () => {
        // Small delay to allow button clicks
        setTimeout(() => {
            if (document.activeElement !== tagSelectionBtn && 
                document.activeElement !== cancelSelectionBtn) {
                selectionToolbar.classList.add('hidden');
            }
        }, 200);
    });
}


function rewriteWeightBand(weight) {
    const w = Number(weight) || 0;
    if (w <= 0) return 'omit';
    if (w <= 29) return 'minimize';
    if (w <= 69) return 'retain';
    return 'emphasize';
}

// Initialize sliders from assessment results
function initializeSlidersFromAssessment(assessmentFoci) {
    if (!assessmentFoci || assessmentFoci.length === 0) {
        slidersContainer.innerHTML = '<p class="empty-state">No assessment data available.</p>';
        return;
    }
    
    // Initialize rewrite weights from reported-focus scores (including 0).
    // reported_focus_score stays on the focus; focusWeights holds editable rewrite_weight.
    focusWeights = {};
    assessmentFoci.forEach((focus, index) => {
        const reported = (typeof focus.score === 'number') ? focus.score : (parseFloat(focus.score) || 0);
        focus.reported_focus_score = reported;
        // Do not treat a reported 0 as "missing" — keep exact 0 as rewrite intent seed.
        focusWeights[index] = reported;
        focus.rewrite_weight = reported;
    });
    
    // Normalize to 100 if total is not 100
    const total = Object.values(focusWeights).reduce((sum, val) => sum + val, 0);
    if (total > 0 && Math.abs(total - 100) > 0.1) {
        // Redistribute proportionally to make total 100
        Object.keys(focusWeights).forEach(key => {
            focusWeights[key] = (focusWeights[key] / total) * 100;
        });
    }
    
    renderSliders();
    updateTotalBudget();
}

// Render sliders
function renderSliders() {
    if (assessmentFoci.length === 0) {
        slidersContainer.innerHTML = '<p class="empty-state">No assessment data available.</p>';
        rewritePromptBtn.disabled = true;
        generateFocusedOutputBtn.disabled = true;
        return;
    }
    
    slidersContainer.innerHTML = assessmentFoci.map((focus, index) => {
        const weight = focusWeights[index] || 0;
        // Find color for this focus
        const focusColor = foci.find(f => f.focus === focus.focus);
        const colorDark = focusColor ? focusColor.colorDark : '#64748b';
        
        return `
            <div class="slider-item" style="border-left: 4px solid ${colorDark};">
                <div class="slider-item-header">
                    <div class="slider-item-title">${index + 1}. ${escapeHtml(focus.focus)}</div>
                    <div class="slider-value" id="slider-value-${index}">${weight.toFixed(1)}%</div>
                </div>
                <div style="font-size: 0.8em; color: #64748b; margin-bottom: 6px;">
                    Rewrite weight (editable)
                    · reported focus: ${(typeof focus.reported_focus_score === 'number' ? focus.reported_focus_score : (focus.score || 0)).toFixed(1)}%
                    · band: <span id="slider-band-${index}">${rewriteWeightBand(weight)}</span>
                </div>
                <div class="slider-wrapper">
                    <input 
                        type="range" 
                        class="slider" 
                        id="slider-${index}" 
                        min="0" 
                        max="100" 
                        step="0.1"
                        value="${weight}"
                        data-focus-index="${index}"
                    >
                    <div class="slider-labels">
                        <span>0%</span>
                        <span>50%</span>
                        <span>100%</span>
                    </div>
                </div>
            </div>
        `;
    }).join('');
    
    // Add event listeners to sliders with constraint logic
    assessmentFoci.forEach((focus, index) => {
        const slider = document.getElementById(`slider-${index}`);
        const valueDisplay = document.getElementById(`slider-value-${index}`);
        
        slider.addEventListener('input', (e) => {
            const newValue = parseFloat(e.target.value);
            const oldValue = focusWeights[index] || 0;
            const delta = newValue - oldValue;
            
            // Calculate total of other sliders
            let otherTotal = 0;
            assessmentFoci.forEach((f, i) => {
                if (i !== index) {
                    otherTotal += focusWeights[i] || 0;
                }
            });
            
            // Adjust other sliders proportionally to maintain 100% total
            if (delta !== 0 && otherTotal > 0) {
                const remainingBudget = 100 - newValue;
                
                if (remainingBudget < 0) {
                    // Can't go above 100%, revert
                    e.target.value = oldValue;
                    return;
                }
                
                // Distribute remaining budget proportionally
                assessmentFoci.forEach((f, i) => {
                    if (i !== index) {
                        const oldOtherValue = focusWeights[i] || 0;
                        if (otherTotal > 0) {
                            focusWeights[i] = (oldOtherValue / otherTotal) * remainingBudget;
                        } else {
                            focusWeights[i] = remainingBudget / (assessmentFoci.length - 1);
                        }
                        
                        // Update slider and display
                        const otherSlider = document.getElementById(`slider-${i}`);
                        const otherDisplay = document.getElementById(`slider-value-${i}`);
                        if (assessmentFoci[i]) {
                            assessmentFoci[i].rewrite_weight = focusWeights[i];
                        }
                        if (otherSlider && otherDisplay) {
                            otherSlider.value = focusWeights[i];
                            otherDisplay.textContent = `${focusWeights[i].toFixed(1)}%`;
                        }
                        const otherBand = document.getElementById(`slider-band-${i}`);
                        if (otherBand) otherBand.textContent = rewriteWeightBand(focusWeights[i]);
                    }
                });
            }
            
            focusWeights[index] = newValue;
            if (assessmentFoci[index]) {
                assessmentFoci[index].rewrite_weight = newValue;
            }
            valueDisplay.textContent = `${newValue.toFixed(1)}%`;
            const bandEl = document.getElementById(`slider-band-${index}`);
            if (bandEl) bandEl.textContent = rewriteWeightBand(newValue);
            
            updateTotalBudget();
        });
    });
    
    rewritePromptBtn.disabled = false;
    generateFocusedOutputBtn.disabled = false;
}

// Update total budget display
function updateTotalBudget() {
    const total = Object.values(focusWeights).reduce((sum, val) => sum + (val || 0), 0);
    totalBudgetValue.textContent = `${total.toFixed(1)}%`;
    
    if (Math.abs(total - 100) < 0.1) {
        totalBudget.classList.remove('invalid');
        totalBudget.classList.add('valid');
    } else {
        totalBudget.classList.remove('valid');
        totalBudget.classList.add('invalid');
    }
}

// Reset sliders to current assessment values
if (resetSlidersBtn) {
    resetSlidersBtn.addEventListener('click', () => {
        if (assessmentFoci.length === 0) return;
        
        assessmentFoci.forEach((focus, index) => {
            const reported = (typeof focus.reported_focus_score === 'number')
                ? focus.reported_focus_score
                : ((typeof focus.score === 'number') ? focus.score : (parseFloat(focus.score) || 0));
            focus.reported_focus_score = reported;
            focusWeights[index] = reported;
            focus.rewrite_weight = reported;
        });
        
        // Normalize to 100
        const total = Object.values(focusWeights).reduce((sum, val) => sum + val, 0);
        if (total > 0 && Math.abs(total - 100) > 0.1) {
            Object.keys(focusWeights).forEach(key => {
                focusWeights[key] = (focusWeights[key] / total) * 100;
            });
        }
        
        renderSliders();
        updateTotalBudget();
    });
}

// Rewrite prompt with emphasis
if (rewritePromptBtn) {
    rewritePromptBtn.addEventListener('click', async () => {
        const prompt = promptInput.value.trim();
        
        if (!prompt || foci.length === 0) {
            showErrorModal('Please enter a prompt and define foci first.');
            return;
        }
        
        // Send current slider values as rewrite_weight (not stale assessment-only scores).
        const weights = assessmentFoci.map((focus, index) => {
            // Use Number() so an explicit 0 is preserved (|| would also keep 0, but be explicit).
            const rewriteWeight = Number(focusWeights[index]);
            const weight = Number.isFinite(rewriteWeight) ? rewriteWeight : 0;
            return {
                focus: focus.focus,
                prompt_section: focus.prompt_section,
                reported_focus_score: (typeof focus.reported_focus_score === 'number')
                    ? focus.reported_focus_score
                    : (focus.score || 0),
                rewrite_weight: weight,
                // Legacy alias still accepted by the service:
                weight: weight,
            };
        });

        if (weights.some(w => w.rewrite_weight <= 0)) {
            const proceed = confirm(
                'One or more foci are set to 0% (omit). Removing a focus may change correctness or behavior. ' +
                'Reported focus is not the same as causal importance. Continue rewrite?'
            );
            if (!proceed) {
                return;
            }
        }
        
        // Estimate cost before making the request
        try {
            // Estimate tokens: prompt + foci descriptions + system message + output
            const promptTokens = Math.ceil(prompt.length / 4);
            const fociTokens = weights.reduce((sum, f) => {
                const focusDesc = f.prompt_section?.length || 0;
                const focusName = f.focus?.length || 0;
                return sum + Math.ceil((focusDesc + focusName) / 4);
            }, 0);
            const systemTokens = 1000; // System message + rewrite instructions
            const estimatedInputTokens = promptTokens + fociTokens + systemTokens;
            const estimatedOutputTokens = Math.ceil(prompt.length / 4) + 500; // Rewritten prompt is typically similar length to original
            
            const estimateResponse = await fetch('/api/pricing/estimate', {
                method: 'POST',
                headers: getApiHeaders(),
                body: JSON.stringify({
                    estimated_input_tokens: estimatedInputTokens,
                    estimated_output_tokens: estimatedOutputTokens,
                    model: userModel,
                    provider: userProvider
                })
            });
            
            if (estimateResponse.ok) {
                const estimate = await estimateResponse.json();
                const cost = estimate.total_cost || 0;
                
                if (cost > 0) {
                }
            }
        } catch (error) {
            console.warn('Could not estimate cost:', error);
            // Continue anyway - don't block the request
        }
        
        showLoading('Rewriting prompt with focus emphasis...');
        
        try {
            const response = await fetch('/api/rewrite-prompt', {
                method: 'POST',
                headers: getApiHeaders(),
                body: JSON.stringify(getApiBody({ 
                    prompt,
                    foci: weights
                })),
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to rewrite prompt');
            }
            
            const nextRewritten = (data.rewritten_prompt || '').trim();
            if (!nextRewritten) {
                throw new Error(
                    'Rewrite returned an empty prompt. Try again or adjust focus weights.'
                );
            }
            // Never overwrite the original prompt field — only the rewritten panel.
            rewrittenPromptText = nextRewritten;
            rewrittenPrompt.textContent = rewrittenPromptText;
            rewrittenPromptContainer.classList.remove('hidden');
            if (adjustedOutputContainer) {
                adjustedOutputContainer.classList.add('hidden');
            }
            if (adjustedOutput) {
                adjustedOutput.textContent = '';
            }
            if (generateFocusedOutputBtn) {
                generateFocusedOutputBtn.disabled = false;
            }
            rewrittenPromptContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            
            // Store intended distribution for comparison (normalize to 100)
            const totalWeight = weights.reduce((sum, w) => sum + (w.rewrite_weight || 0), 0);
            weights.forEach(w => {
                // Omit (0) stays 0 in the intended mix; do not redistribute zeros upward.
                intendedDistribution[w.focus] = totalWeight > 0 ? (w.rewrite_weight / totalWeight) * 100 : 0;
            });
            
            // Don't show compare button yet - wait until after new output is generated and assessed
            compareIntentBtn.classList.add('hidden');
            
        } catch (error) {
            showError('Error rewriting prompt: ' + error.message);
            console.error('Rewrite prompt error:', error);
        } finally {
            hideLoading();
        }
    });
}

// Generate output with focused prompt
if (generateFocusedOutputBtn) {
    generateFocusedOutputBtn.addEventListener('click', async () => {
        if (!rewrittenPromptText) {
            showErrorModal('Please rewrite the prompt first.');
            return;
        }
        
        // Estimate cost before making the request
        try {
            // Estimate tokens: rewritten prompt + system message + output
            const promptTokens = Math.ceil(rewrittenPromptText.length / 4);
            const systemTokens = 200; // System message overhead
            const estimatedInputTokens = promptTokens + systemTokens;
            const estimatedOutputTokens = Math.ceil(promptTokens * 1.5); // Output is typically 1.5x input length
            
            const estimateResponse = await fetch('/api/pricing/estimate', {
                method: 'POST',
                headers: getApiHeaders(),
                body: JSON.stringify({
                    estimated_input_tokens: estimatedInputTokens,
                    estimated_output_tokens: estimatedOutputTokens,
                    model: userModel,
                    provider: userProvider
                })
            });
            
            if (estimateResponse.ok) {
                const estimate = await estimateResponse.json();
                const cost = estimate.total_cost || 0;
                
                if (cost > 0) {
                }
            }
        } catch (error) {
            console.warn('Could not estimate cost:', error);
            // Continue anyway - don't block the request
        }
        
        showLoading('Generating output with focused prompt...');
        
        try {
            const response = await fetch('/api/generate-output', {
                method: 'POST',
                headers: getApiHeaders(),
                body: JSON.stringify(getApiBody({ prompt: rewrittenPromptText })),
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to generate output');
            }
            
            const generated = data.output || '';
            // Keep section 3 in sync for assess/compare flows, but show result
            // next to the rewritten prompt so it is obvious what was produced.
            if (outputInput) {
                outputInput.value = generated;
            }
            if (adjustedOutput) {
                adjustedOutput.textContent = generated;
            }
            if (adjustedOutputContainer) {
                adjustedOutputContainer.classList.remove('hidden');
                adjustedOutputContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
            
            // Show success message
            const successMsg = document.createElement('div');
            successMsg.className = 'success-message';
            successMsg.style.cssText = 'position: fixed; top: 20px; right: 20px; background: #10b981; color: white; padding: 12px 20px; border-radius: 6px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); z-index: 10000; font-size: 14px;';
            successMsg.textContent = '✓ Output generated from rewritten prompt (shown below)';
            document.body.appendChild(successMsg);
            
            setTimeout(() => {
                successMsg.style.opacity = '0';
                successMsg.style.transition = 'opacity 0.3s ease';
                setTimeout(() => {
                    document.body.removeChild(successMsg);
                }, 300);
            }, 3000);
            
            // Store that we've generated from adjusted prompt
            window.generatedFromAdjustedPrompt = true;
            
            // Auto-assess after generation
            setTimeout(() => {
                assessBtn.click();
            }, 500);
            
        } catch (error) {
            showError('Error generating output: ' + error.message);
            console.error('Generate focused output error:', error);
        } finally {
            hideLoading();
        }
    });
}

// Compare intended vs actual focus
if (compareIntentBtn) {
    compareIntentBtn.addEventListener('click', () => {
        if (Object.keys(intendedDistribution).length === 0) {
            showErrorModal('Please rewrite the prompt and generate output first.');
            return;
        }
        
        // Get the last assessment results
        const assessmentDiv = assessmentResults.querySelector('.assessment-foci');
        if (!assessmentDiv) {
            showErrorModal('Please assess the output first.');
            return;
        }
        
        const actualFoci = Array.from(assessmentDiv.querySelectorAll('.assessment-focus')).map(focusEl => {
            const title = focusEl.querySelector('.assessment-focus-title').textContent.replace(/^\d+\.\s*/, '');
            const score = parseFloat(focusEl.querySelector('.assessment-focus-score').textContent);
            return { focus: title, score };
        });
        
        // Build comparison
        let html = '<div class="comparison-results">';
        html += '<h3>Intended vs Actual Focus Distribution</h3>';
        html += '<table class="comparison-table">';
        html += '<thead><tr><th>Focus</th><th>Intended</th><th>Actual</th><th>Difference</th></tr></thead>';
        html += '<tbody>';
        
        let totalDiff = 0;
        actualFoci.forEach(actual => {
            const intended = intendedDistribution[actual.focus] || 0;
            const diff = actual.score - intended;
            totalDiff += Math.abs(diff);
            
            const diffClass = diff >= 0 ? 'positive' : 'negative';
            const diffSign = diff >= 0 ? '+' : '';
            
            html += `
                <tr>
                    <td class="focus-name">${escapeHtml(actual.focus)}</td>
                    <td class="intended-value">${intended.toFixed(1)}%</td>
                    <td class="actual-value">${actual.score.toFixed(1)}%</td>
                    <td class="difference ${diffClass}">${diffSign}${diff.toFixed(1)}%</td>
                </tr>
            `;
        });
        
        html += '</tbody></table>';
        
        const avgDiff = totalDiff / actualFoci.length;
        html += `<div class="comparison-summary">`;
        html += `<strong>Average Absolute Difference:</strong> ${avgDiff.toFixed(1)}%<br>`;
        if (avgDiff < 10) {
            html += `<span style="color: var(--success-color);">✓ Excellent match! The output closely follows the intended focus distribution.</span>`;
        } else if (avgDiff < 20) {
            html += `<span style="color: var(--primary-color);">○ Good match. The output generally follows the intended distribution.</span>`;
        } else {
            html += `<span style="color: var(--danger-color);">⚠ Significant difference. Consider adjusting the prompt emphasis or weights.</span>`;
        }
        html += `</div>`;
        html += '</div>';
        
        assessmentResults.insertAdjacentHTML('beforeend', html);
    });
}

// Load Ablation Checkpoint
if (loadAblationCheckpointBtn) {
    loadAblationCheckpointBtn.addEventListener('click', async () => {
        try {
            const checkpoints = await listCheckpoints('single_ablation');
            if (checkpoints.length === 0) {
                showErrorModal('No ablation analysis checkpoints found. Previous runs before checkpoint saving was implemented were not saved. Future runs will be automatically saved.');
                return;
            }
            // Show checkpoint list - we'll need to create a temporary display
            await displayCheckpointList('single_ablation');
        } catch (error) {
            showError('Error loading checkpoints: ' + error.message);
            console.error('Checkpoint loading error:', error);
        }
    });
}

// Run Ablation Analysis
function sleepMs(ms) {
    return new Promise(function (resolve) { setTimeout(resolve, ms); });
}

async function fetchAblationSample(prompt, fociList, kind, focusIndex, temperature, controller) {
    const maxAttempts = 8;
    for (let attempt = 0; attempt < maxAttempts; attempt++) {
        const response = await fetch('/api/ablation-sample', {
            method: 'POST',
            headers: getApiHeaders(),
            body: JSON.stringify(getApiBody({
                prompt: prompt,
                foci: fociList,
                kind: kind,
                focus_index: focusIndex,
                temperature: temperature
            })),
            signal: controller.signal
        });
        const data = await response.json();
        if (response.status === 429) {
            const waitSec = Math.max(1, Number(data.retry_after) || 2);
            showLoading('Gateway rate limit. Waiting ' + waitSec + 's, then retrying this sample…');
            await sleepMs(waitSec * 1000);
            continue;
        }
        if (!response.ok) {
            throw new Error(data.error || 'Failed to generate a sample');
        }
        if (!data.content) {
            throw new Error('Model returned an empty sample');
        }
        return data;
    }
    throw new Error(
        'Rate limit persisted after several waits. Wait a minute and try again, or lower sample counts.'
    );
}

async function mapPool(items, limit, fn) {
    const results = new Array(items.length);
    let next = 0;
    async function worker() {
        while (true) {
            const i = next++;
            if (i >= items.length) return;
            results[i] = await fn(items[i], i);
        }
    }
    const n = Math.max(1, Math.min(limit, items.length));
    const workers = [];
    for (let w = 0; w < n; w++) workers.push(worker());
    await Promise.all(workers);
    return results;
}

function isClientAttributableFocus(focus) {
    if (!focus || focus.is_dynamic) return false;
    if (focus.verified === false) return false;
    if (focus.reason === 'overlap' || focus.reason === 'unverified' || focus.reason === 'dynamic_slot') {
        return false;
    }
    return true;
}

async function runPacedAblation(prompt, fociList, cfg, onProgress) {
    const report = typeof onProgress === 'function'
        ? onProgress
        : function (msg) { showLoading(msg); };
    const controller = new AbortController();
    const timeoutId = setTimeout(function () { controller.abort(); }, 600000);
    const concurrency = 6;
    try {
        const nBaseline = cfg.n_baseline;
        const nAblated = cfg.n_ablated;
        const jobs = [];
        for (let i = 0; i < nBaseline; i++) {
            jobs.push({ kind: 'baseline', focusIndex: null, slot: i });
        }
        for (let focusIndex = 0; focusIndex < fociList.length; focusIndex++) {
            if (!isClientAttributableFocus(fociList[focusIndex])) continue;
            for (let j = 0; j < nAblated; j++) {
                jobs.push({ kind: 'ablated', focusIndex: focusIndex, slot: j });
            }
        }

        let completed = 0;
        report('Generating samples (0 of ' + jobs.length + ')…');
        const samples = await mapPool(jobs, concurrency, async function (job) {
            const sample = await fetchAblationSample(
                prompt, fociList, job.kind, job.focusIndex, cfg.temperature, controller
            );
            completed += 1;
            report('Generating samples (' + completed + ' of ' + jobs.length + ')…');
            return sample;
        });

        const baselineOutputs = [];
        const ablatedOutputs = {};
        let inputTokens = 0;
        let outputTokens = 0;
        for (let i = 0; i < jobs.length; i++) {
            const job = jobs[i];
            const sample = samples[i];
            if (sample.usage) {
                inputTokens += sample.usage.prompt_tokens || 0;
                outputTokens += sample.usage.completion_tokens || 0;
            }
            if (job.kind === 'baseline') {
                baselineOutputs[job.slot] = sample.content;
            } else {
                if (!ablatedOutputs[job.focusIndex]) ablatedOutputs[job.focusIndex] = [];
                ablatedOutputs[job.focusIndex][job.slot] = sample.content;
            }
        }

        report('Scoring samples (permutation test)…');
        const response = await fetch('/api/ablation-score', {
            method: 'POST',
            headers: getApiHeaders(),
            body: JSON.stringify(getApiBody({
                prompt: prompt,
                foci: fociList,
                baseline_outputs: baselineOutputs,
                ablated_outputs: ablatedOutputs,
                temperature: cfg.temperature,
                input_tokens: inputTokens,
                output_tokens: outputTokens
            })),
            signal: controller.signal
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || 'Failed to score ablation samples');
        }
        return data;
    } finally {
        clearTimeout(timeoutId);
    }
}

if (runAblationBtn) {
    runAblationBtn.addEventListener('click', async () => {
        const prompt = promptInput.value.trim();
        
        if (!prompt) {
            showErrorModal('Please enter a prompt first.');
            return;
        }
        
        if (foci.length === 0) {
            showErrorModal('Please define foci first.');
            return;
        }

        var cfg = window.FocalPromptExperiment ? window.FocalPromptExperiment.getState() : {
            temperature: 0.7, n_baseline: 10, n_ablated: 5
        };
        if (window.FocalPromptExperiment) {
            var tempErr = window.FocalPromptExperiment.temperatureRejection(cfg.temperature);
            if (tempErr) {
                showErrorModal(tempErr);
                return;
            }
        }

        var nTested = window.FocalPromptExperiment
            ? window.FocalPromptExperiment.countPreviewAttributable(foci)
            : foci.filter(function (f) { return !f.is_dynamic; }).length;
        showLoading(
            window.FocalPromptExperiment
                ? window.FocalPromptExperiment.formatAblationLoading(
                    cfg.temperature, cfg.n_baseline, cfg.n_ablated, nTested
                )
                : ('Running ablation analysis at temperature ' + Number(cfg.temperature).toFixed(1) +
                   ': ' + cfg.n_baseline + ' baseline samples and ' + cfg.n_ablated +
                   ' ablated samples for each of ' + nTested +
                   (nTested === 1 ? ' focus' : ' foci') + '.')
        );
        
        try {
            const data = await runPacedAblation(prompt, foci, cfg);
            renderAblationResults(data);
            
        } catch (error) {
            if (error.name === 'AbortError') {
                showError('Ablation analysis timed out after 10 minutes. The analysis may still be running on the server. Please try again with fewer baseline samples or check the server logs.');
            } else {
                showError('Error running ablation analysis: ' + error.message);
            }
            console.error('Ablation analysis error:', error);
        } finally {
            hideLoading();
        }
    });
}

// Render Ablation Results
function renderAblationResults(data, options) {
    window.singleAblationResults = data;
    if (!ablationResults) return;
    if (!window.FocalPromptResults) {
        ablationResults.innerHTML = '<p class="empty-state">Results renderer failed to load.</p>';
        return;
    }

    // Insight-led report (Overview → Raw); classic diagnostic HTML lives under Raw.
    if (window.FocalPromptReport && typeof window.FocalPromptReport.render === 'function') {
        window.FocalPromptReport.render(data, ablationResults);
    } else {
        ablationResults.innerHTML = window.FocalPromptResults.renderAblationResultsHtml(data);
    }

    refreshQualityEvalPreview();

    refreshFocusOrderControls(data);

    const toggleOutputsBtn = document.getElementById('toggle-all-outputs');
    const allOutputsContainer = document.getElementById('all-outputs-container');
    const downloadBtn = document.getElementById('download-ablation-results');

    bindReportedFocusDynamicsHandlers(data);

    if (toggleOutputsBtn && allOutputsContainer) {
        toggleOutputsBtn.addEventListener('click', () => {
            if (allOutputsContainer.classList.contains('hidden')) {
                allOutputsContainer.classList.remove('hidden');
                toggleOutputsBtn.textContent = 'Hide sampled outputs';
            } else {
                allOutputsContainer.classList.add('hidden');
                toggleOutputsBtn.textContent = 'Show sampled outputs';
            }
        });
    }

    if (downloadBtn) {
        downloadBtn.addEventListener('click', () => {
            // Export the full scored result: all n_baseline full-prompt samples
            // (baseline_outputs), every focus's ablated_outputs, stats, and prompt.
            // Do not slim to baseline_output[0] only.
            const baselineOutputs = Array.isArray(data.baseline_outputs) && data.baseline_outputs.length
                ? data.baseline_outputs
                : (data.baseline_output ? [data.baseline_output] : []);
            const downloadData = Object.assign({}, data, {
                timestamp: new Date().toISOString(),
                baseline_outputs: baselineOutputs,
                baseline_output: data.baseline_output || (baselineOutputs[0] || null),
                num_baseline_samples: data.num_baseline_samples != null
                    ? data.num_baseline_samples
                    : baselineOutputs.length,
            });
            const blob = new Blob([JSON.stringify(downloadData, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `ablation-analysis-${new Date().toISOString().split('T')[0]}.json`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        });
    }

    bindBehavioralDifferenceReviewHandlers(data);
    bindShuffleRobustnessHandlers(data);
    bindAblationStabilityHandlers(data);
    if (!options || !options.skipExperimentCRefresh) {
        refreshExperimentCComparison({ scroll: true });
    }
}

function bindReportedFocusDynamicsHandlers(data) {
    const btn = document.getElementById('run-reported-focus-dynamics-btn');
    const mount = document.getElementById('reported-focus-dynamics-results');
    if (!btn || !mount) return;

    if (data.reported_focus_dynamics && window.FocalPromptResults) {
        mount.innerHTML = window.FocalPromptResults.renderReportedFocusDynamicsHtml(
            data.reported_focus_dynamics
        );
    }

    btn.addEventListener('click', async function () {
        const prompt = (data && data.prompt) || (promptInput ? promptInput.value.trim() : '');
        const fociList = (data && (data.foci_list || data.foci)) || foci;
        const baselines = (data && data.baseline_outputs && data.baseline_outputs.length)
            ? data.baseline_outputs
            : (data && data.baseline_output ? [data.baseline_output] : []);
        if (!prompt || !fociList || !fociList.length || !baselines.length) {
            showErrorModal('Need prompt, foci, and baseline samples from the ablation run.');
            return;
        }

        // Build ablated_outputs map from influence / ablation rows
        const ablatedMap = {};
        const scores = Array.isArray(data.influence_scores) ? data.influence_scores : [];
        const rows = Array.isArray(data.ablation_results) ? data.ablation_results : [];
        function addOutputs(item) {
            if (!item || item.attributable === false) return;
            const idx = item.focus_index;
            if (idx == null) return;
            const outs = item.ablated_outputs || (item.ablated_output ? [item.ablated_output] : []);
            if (outs.length) ablatedMap[String(idx)] = outs;
        }
        scores.forEach(addOutputs);
        rows.forEach(addOutputs);
        if (!Object.keys(ablatedMap).length) {
            showErrorModal('No ablated sample texts found to assess.');
            return;
        }

        const associationFocus = window.prompt
            ? window.prompt(
                'Optional: focus name to associate with behaviour labels (Cancel to skip):',
                ''
            )
            : '';

        btn.disabled = true;
        const prev = btn.textContent;
        btn.textContent = 'Running reported-focus dynamics…';
        showLoading('Assessing reported focus on every sample (this uses extra LLM calls)…');
        try {
            const response = await fetch('/api/ablation-reported-focus-dynamics', {
                method: 'POST',
                headers: getApiHeaders(),
                body: JSON.stringify(getApiBody({
                    prompt: prompt,
                    foci: fociList,
                    baseline_outputs: baselines,
                    ablated_outputs: ablatedMap,
                    association_focus: associationFocus || null
                }))
            });
            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.error || 'Reported-focus dynamics failed');
            }
            data.reported_focus_dynamics = result;
            window.singleAblationResults = data;
            if (window.FocalPromptResults) {
                mount.innerHTML = window.FocalPromptResults.renderReportedFocusDynamicsHtml(result);
            }
        } catch (err) {
            showErrorModal('Reported-focus dynamics: ' + (err.message || String(err)));
            console.error(err);
        } finally {
            btn.disabled = false;
            btn.textContent = prev;
            hideLoading();
        }
    });
}

function setExperimentCMessage(html) {
    if (experimentCResults) {
        experimentCResults.innerHTML = html;
    }
}

function buildExperimentCComparisonHtml(data) {
    const summary = data.summary || {};
    const rows = data.rows || [];
    const rho = summary.spearman_reported_vs_normalized_influence;
    const rhoTxt = (rho === null || rho === undefined || Number.isNaN(Number(rho)))
        ? 'n/a'
        : Number(rho).toFixed(2);

    let html = '<div class="experiment-c-summary">';
    html += '<p><strong>Experiment C — per-focus comparison</strong></p>';
    html += '<p>Compared ' + (summary.n_foci_compared || rows.length) + ' foci';
    if (summary.n_tagged_foci) {
        html += ' (' + summary.n_tagged_foci + ' tagged)';
    }
    html += '. Agree (high): ' + (summary.n_concordant_high || 0) + '. ';
    html += 'Agree (quiet): ' + (summary.n_concordant_quiet || 0) + '. ';
    html += 'Disagreements: ' + (summary.n_disagreements || 0);
    if (summary.disagreement_foci && summary.disagreement_foci.length) {
        html += ' (' + summary.disagreement_foci.map(escapeHtml).join(', ') + ')';
    }
    if (summary.n_incomplete) {
        html += '. Incomplete: ' + summary.n_incomplete;
    }
    html += '.</p>';
    html += '<p>Rank correlation (A reported score vs B normalized T<sub>obs</sub> share): ρ = ' +
        escapeHtml(rhoTxt) + '. ' + escapeHtml(summary.interpretation || '') + '</p>';
    html += '<p style="font-size:0.9em;color:#64748b;margin:0">High reported (A) uses threshold ≥ ' +
        escapeHtml(String(summary.reported_high_threshold != null ? summary.reported_high_threshold : 15)) +
        ' points. B significance uses BH q &lt; α. Bars show relative level within each experiment.</p>';
    html += '</div>';

    html += '<table class="experiment-c-table"><thead><tr>';
    html += '<th>Focus</th><th>A vs B levels</th>';
    html += '<th>A score</th><th>B signal</th><th>Ranks (A / B)</th><th>Concordance</th>';
    html += '</tr></thead><tbody>';

    const sorted = rows.slice().sort(function (a, b) {
        const sa = Number(a.reported_score);
        const sb = Number(b.reported_score);
        if (Number.isFinite(sb) && Number.isFinite(sa) && sb !== sa) return sb - sa;
        const na = Number(a.normalized_influence);
        const nb = Number(b.normalized_influence);
        if (Number.isFinite(nb) && Number.isFinite(na) && nb !== na) return nb - na;
        return String(a.focus || '').localeCompare(String(b.focus || ''));
    });

    sorted.forEach(function (row) {
        const conc = row.concordance || {};
        const key = conc.key || 'incomplete';
        const faith = row.faithfulness || {};
        const sig = row.is_significant;
        const scoreNum = Number(row.reported_score);
        const shareNum = Number(row.normalized_influence);
        const score = row.reported_score != null && Number.isFinite(scoreNum)
            ? scoreNum.toFixed(1)
            : '—';
        const share = row.normalized_influence != null && Number.isFinite(shareNum)
            ? shareNum.toFixed(1) + '%'
            : '—';
        const tObs = row.t_obs != null ? Number(row.t_obs).toFixed(4) : '—';
        const effect = row.standardized_effect != null
            ? Number(row.standardized_effect).toFixed(2)
            : '—';
        let sigTxt = 'n/a';
        if (sig === true) sigTxt = 'significant (q=' + formatExperimentCQ(row.q_value) + ')';
        else if (sig === false) sigTxt = 'not significant (q=' + formatExperimentCQ(row.q_value) + ')';

        const scoreBarW = Number.isFinite(scoreNum) ? Math.min(100, Math.max(0, scoreNum)) : 0;
        const shareBarW = Number.isFinite(shareNum) ? Math.min(100, Math.max(0, shareNum)) : 0;

        html += '<tr class="experiment-c-row-' + escapeHtml(key) + '">';
        html += '<td><strong>' + escapeHtml(row.focus || '') + '</strong>';
        if (row.prompt_section) {
            html += '<div class="experiment-c-span">' + escapeHtml(
                row.prompt_section.length > 80
                    ? row.prompt_section.slice(0, 77) + '...'
                    : row.prompt_section
            ) + '</div>';
        }
        html += '</td>';
        html += '<td class="experiment-c-bars-cell">';
        html += '<div class="experiment-c-bar-row"><span class="experiment-c-bar-label">A</span>';
        html += '<div class="experiment-c-bar-track"><div class="experiment-c-bar-fill experiment-c-bar-a" style="width:' +
            scoreBarW + '%"></div></div></div>';
        html += '<div class="experiment-c-bar-row"><span class="experiment-c-bar-label">B</span>';
        html += '<div class="experiment-c-bar-track"><div class="experiment-c-bar-fill experiment-c-bar-b" style="width:' +
            shareBarW + '%"></div></div></div>';
        html += '</td>';
        html += '<td>' + escapeHtml(score);
        if (!row.has_experiment_a) {
            html += '<div class="experiment-c-missing">No A score — run Assess Focus</div>';
        }
        html += '</td>';
        html += '<td><div>' + escapeHtml(sigTxt) + '</div>';
        html += '<div class="experiment-c-metrics">T<sub>obs</sub>=' + escapeHtml(tObs) +
            ', share=' + escapeHtml(share) + ', z=' + escapeHtml(effect) + '</div>';
        if (!row.has_experiment_b) {
            html += '<div class="experiment-c-missing">No B result</div>';
        }
        html += '</td>';
        html += '<td>' + escapeHtml(
            (row.reported_rank != null ? row.reported_rank : '—') + ' / ' +
            (row.revealed_rank != null ? row.revealed_rank : '—')
        );
        if (row.rank_delta != null) {
            html += '<div class="experiment-c-metrics">Δrank=' + escapeHtml(String(row.rank_delta)) + '</div>';
        }
        html += '</td>';
        html += '<td>' + escapeHtml(conc.label || key);
        if (faith.primary_label && faith.primary_label !== 'inconclusive') {
            html += '<div class="experiment-c-metrics">' + escapeHtml(faith.primary_label) + '</div>';
        }
        html += '</td>';
        html += '</tr>';
    });
    html += '</tbody></table>';
    return html;
}

function paintExperimentCComparison(data, includeExplanation) {
    if (!data) return;
    const html = buildExperimentCComparisonHtml(data);
    const fullHtml = includeExplanation && window.experimentCExplanationHtml
        ? html + window.experimentCExplanationHtml
        : html;
    if (experimentCResults) {
        experimentCResults.innerHTML = fullHtml;
    }
}

function resolveShuffleFocusIndex(btn, data) {
    let idx = parseInt(btn.getAttribute('data-focus-index'), 10);
    if (!Number.isNaN(idx)) return idx;
    const name = btn.getAttribute('data-focus');
    const list = (data && data.foci_list) || foci || [];
    for (let i = 0; i < list.length; i++) {
        const itemName = list[i].focus || list[i].name || '';
        if (itemName && name && itemName === name) return i;
    }
    return null;
}

function bindShuffleRobustnessHandlers(data) {
    if (!ablationResults) return;
    ablationResults.querySelectorAll('.btn-shuffle-robustness').forEach(function (btn) {
        btn.addEventListener('click', async function () {
            const focusIndex = resolveShuffleFocusIndex(btn, data);
            if (focusIndex == null) {
                showErrorModal('Could not determine which focus to re-test. Re-run ablation and try again.');
                return;
            }
            await runShuffleRobustnessForFocus(focusIndex, data, btn.getAttribute('data-focus'));
        });
    });
}

async function runShuffleRobustnessForFocus(focusIndex, data, focusNameHint) {
    const prompt = (data && data.prompt) || (promptInput ? promptInput.value.trim() : '');
    const fociList = (data && data.foci_list) || foci;
    const baselines = (data && data.baseline_outputs && data.baseline_outputs.length)
        ? data.baseline_outputs
        : (data && data.baseline_output ? [data.baseline_output] : []);
    if (!prompt || !fociList || !fociList.length || !baselines.length) {
        showErrorModal('Need prompt, foci, and baseline samples from the original ablation run.');
        return;
    }

    const cfg = window.FocalPromptExperiment ? window.FocalPromptExperiment.getState() : {
        temperature: data.temperature || 0.7,
        n_ablated: data.n_ablated || 5,
        n_permutations: data.n_permutations || 10000,
        alpha: data.alpha || 0.05
    };

    const inputs = Object.assign({}, data.inputs || {});
    if (!inputs.chat_content) {
        const chatEl = document.getElementById('chat-input') || document.getElementById('manual-pair-input');
        if (chatEl && chatEl.value && chatEl.value.trim()) {
            inputs.chat_content = chatEl.value.trim();
        }
    }

    function setShuffleState(state) {
        const scores = data.influence_scores;
        const apply = function (item) {
            if (Number(item.focus_index) === focusIndex) {
                item.shuffle_robustness = state;
                return;
            }
            if (focusNameHint && (item.focus || item.name) === focusNameHint) {
                item.shuffle_robustness = state;
            }
        };
        if (Array.isArray(scores)) scores.forEach(apply);
        if (data.ablation_results) data.ablation_results.forEach(apply);
        window.singleAblationResults = data;
        renderAblationResults(data);
    }

    setShuffleState({ status: 'running' });
    showLoading('Re-testing focus with shuffled remaining order…');
    try {
        const response = await fetch('/api/ablation-shuffle-robustness', {
            method: 'POST',
            headers: getApiHeaders(),
            body: JSON.stringify(getApiBody({
                prompt: prompt,
                foci: fociList,
                focus_index: focusIndex,
                baseline_outputs: baselines,
                n_ablated: cfg.n_ablated,
                n_permutations: cfg.n_permutations || data.n_permutations || 10000,
                alpha: cfg.alpha || data.alpha || 0.05,
                permutation_seed: data.permutation_seed,
                temperature: cfg.temperature,
                inputs: inputs
            }))
        });
        const result = await response.json();
        if (!response.ok) {
            throw new Error(result.error || 'Shuffle robustness check failed');
        }
        setShuffleState(Object.assign({ status: 'complete' }, result));
    } catch (err) {
        setShuffleState({ status: 'failed', error: err.message || String(err) });
        showError('Shuffle robustness check: ' + (err.message || String(err)));
        console.error(err);
    } finally {
        hideLoading();
    }
}

function buildAblatedOutputsMap(data) {
    const map = {};
    const records = (window.FocalPromptResults && window.FocalPromptResults.collectFocusRecords)
        ? window.FocalPromptResults.collectFocusRecords(data)
        : (data.ablation_results || []);
    records.forEach(function (rec) {
        if (rec.attributable === false) return;
        const idx = rec.focus_index;
        if (idx == null) return;
        const outs = rec.ablated_outputs || (rec.ablated_output ? [rec.ablated_output] : []);
        if (outs.length) map[String(idx)] = outs;
    });
    return map;
}

function recomputeStabilityExperimentFields(data) {
    const records = (window.FocalPromptResults && window.FocalPromptResults.collectFocusRecords)
        ? window.FocalPromptResults.collectFocusRecords(data)
        : [];
    const points = [];
    records.forEach(function (item) {
        if (item.attributable === false) return;
        const stab = item.ablation_stability;
        if (!stab) return;
        points.push({
            focus: item.focus || item.focus_name,
            focus_index: item.focus_index,
            x_semantic_shift: item.t_obs,
            x_standardized_effect: item.standardized_effect,
            x_normalized_influence: item.normalized_influence,
            y_dispersion_ratio: stab.mean_pairwise_noise_ratio != null
                ? stab.mean_pairwise_noise_ratio
                : stab.centroid_noise_ratio,
            q_value: item.q_value,
            p_value: item.p_value,
            n_ablated_samples: stab.n_samples,
        });
    });
    data.stability_scatter = points;
}

function mergeAblationStabilityIntoData(data, focusIndex, patch, options) {
    const skipRender = options && options.skipRender;
    function apply(item) {
        if (Number(item.focus_index) !== Number(focusIndex)) return;
        if (patch.ablated_outputs) {
            item.ablated_outputs = patch.ablated_outputs;
            item.ablated_output = patch.ablated_outputs[0];
        }
        if (patch.ablation_stability) item.ablation_stability = patch.ablation_stability;
        if (patch.behavioral_outcome) {
            item.behavioral_outcome = patch.behavioral_outcome;
            if (item.ablation_stability) {
                item.ablation_stability.behavioral_outcome = patch.behavioral_outcome;
            }
        }
        if (patch.permutation) {
            Object.assign(item, patch.permutation);
            item.t_obs = patch.permutation.t_obs;
            item.influence = patch.permutation.t_obs;
        }
    }
    if (Array.isArray(data.influence_scores)) data.influence_scores.forEach(apply);
    if (data.ablation_results) data.ablation_results.forEach(apply);
    recomputeStabilityExperimentFields(data);
    window.singleAblationResults = data;
    if (!skipRender) {
        renderAblationResults(data);
    }
}

function bindAblationStabilityHandlers(data) {
    if (!ablationResults) return;

    ablationResults.querySelectorAll('.btn-refine-ablation-stability').forEach(function (btn) {
        btn.addEventListener('click', async function () {
            const focusIndex = parseInt(btn.getAttribute('data-focus-index'), 10);
            if (Number.isNaN(focusIndex)) {
                showErrorModal('Could not determine focus for refinement.');
                return;
            }
            await runRefineAblationStability(focusIndex, data);
        });
    });

    const outcomeBtn = document.getElementById('run-ablation-outcome-dispersion-btn');
    if (outcomeBtn) {
        outcomeBtn.addEventListener('click', async function () {
            await runAblationOutcomeDispersion(data);
        });
    }
}

async function runRefineAblationStability(focusIndex, data) {
    const prompt = (data && data.prompt) || (promptInput ? promptInput.value.trim() : '');
    const fociList = (data && data.foci_list) || foci;
    const baselines = (data && data.baseline_outputs && data.baseline_outputs.length)
        ? data.baseline_outputs
        : (data && data.baseline_output ? [data.baseline_output] : []);
    const records = (window.FocalPromptResults && window.FocalPromptResults.collectFocusRecords)
        ? window.FocalPromptResults.collectFocusRecords(data)
        : [];
    const rec = records.find(function (r) { return Number(r.focus_index) === Number(focusIndex); });
    const existing = (rec && rec.ablated_outputs) || [];
    if (!prompt || !fociList.length || !baselines.length || !existing.length) {
        showErrorModal('Need prompt, foci, baseline samples, and existing ablated outputs.');
        return;
    }
    const nAdditional = parseInt(
        window.prompt('How many additional ablated samples to generate?', '5') || '0',
        10
    );
    if (!nAdditional || nAdditional < 1) return;

    const criterion = evalCriteriaInput ? evalCriteriaInput.value.trim() : '';
    const runJudge = criterion
        ? window.confirm('Also run task-specific criterion judge on baseline vs ablated outputs?')
        : false;

    showLoading('Generating additional ablated samples for stability estimate…');
    try {
        const response = await fetch('/api/ablation-refine-stability', {
            method: 'POST',
            headers: getApiHeaders(),
            body: JSON.stringify(getApiBody({
                prompt: prompt,
                foci: fociList,
                focus_index: focusIndex,
                baseline_outputs: baselines,
                ablated_outputs: existing,
                n_additional: nAdditional,
                temperature: data.temperature || 0.7,
                n_permutations: data.n_permutations || 10000,
                alpha: data.alpha || 0.05,
                permutation_seed: data.permutation_seed,
                behavioral_criterion: criterion,
                run_behavioral_judge: runJudge,
            })),
        });
        const result = await response.json();
        if (!response.ok) {
            throw new Error(result.error || 'Refinement failed');
        }
        mergeAblationStabilityIntoData(data, focusIndex, {
            ablated_outputs: result.ablated_outputs,
            ablation_stability: result.ablation_stability,
            behavioral_outcome: result.behavioral_outcome,
            permutation: result.permutation,
        });
        alert('Stability estimate updated with ' + nAdditional + ' additional sample(s).');
    } catch (err) {
        showError('Refine stability: ' + (err.message || String(err)));
    } finally {
        hideLoading();
    }
}

async function runAblationOutcomeDispersion(data) {
    const criterion = evalCriteriaInput ? evalCriteriaInput.value.trim() : '';
    if (!criterion) {
        showErrorModal('Enter evaluation criteria in section 9 first, or provide a behavioural criterion.');
        return;
    }
    const baselines = (data && data.baseline_outputs && data.baseline_outputs.length)
        ? data.baseline_outputs
        : (data && data.baseline_output ? [data.baseline_output] : []);
    const ablatedMap = buildAblatedOutputsMap(data);
    if (!baselines.length || !Object.keys(ablatedMap).length) {
        showErrorModal('Need baseline and ablated outputs from Experiment B.');
        return;
    }
    showLoading('Running task-specific outcome dispersion analysis…');
    try {
        const response = await fetch('/api/ablation-behavioral-outcome-dispersion', {
            method: 'POST',
            headers: getApiHeaders(),
            body: JSON.stringify(getApiBody({
                baseline_outputs: baselines,
                ablated_outputs: ablatedMap,
                behavioral_criterion: criterion,
            })),
        });
        const result = await response.json();
        if (!response.ok) {
            throw new Error(result.error || 'Outcome dispersion failed');
        }
        const byFocus = result.by_focus_index || {};
        Object.keys(byFocus).forEach(function (key) {
            mergeAblationStabilityIntoData(data, parseInt(key, 10), {
                behavioral_outcome: byFocus[key],
            }, { skipRender: true });
        });
        renderAblationResults(data);
        const mount = document.getElementById('ablation-outcome-dispersion-results');
        if (mount) {
            mount.innerHTML = '<p class="info-text">Task-specific outcome dispersion attached to each focus card.</p>';
        }
    } catch (err) {
        showError('Outcome dispersion: ' + (err.message || String(err)));
    } finally {
        hideLoading();
    }
}

function bindBehavioralDifferenceReviewHandlers(data) {
    if (!ablationResults) return;
    const collect = window.FocalPromptResults && window.FocalPromptResults.collectFocusRecords;
    const records = collect ? collect(data) : [];
    const byName = {};
    records.forEach((r) => {
        const n = r.focus || r.focus_name;
        if (n) byName[n] = r;
    });

    ablationResults.querySelectorAll('.btn-review-llm-diff').forEach((btn) => {
        btn.addEventListener('click', async () => {
            const focus = btn.getAttribute('data-focus');
            const rec = byName[focus];
            if (!rec) {
                alert('Could not find stored samples for focus: ' + focus);
                return;
            }
            const baselineOutputs = data.baseline_outputs || (data.baseline_output ? [data.baseline_output] : []);
            const ablatedOutputs = rec.ablated_outputs || (rec.ablated_output ? [rec.ablated_output] : []);
            if (!baselineOutputs.length || !ablatedOutputs.length) {
                alert('Need stored baseline and ablated outputs for qualitative difference review.');
                return;
            }
            btn.disabled = true;
            const prev = btn.textContent;
            btn.textContent = 'Judging difference…';
            try {
                const response = await fetch('/api/behavioral-difference/llm-judge', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        focus: focus,
                        removed_span: rec.prompt_section || rec.focus_text || '',
                        baseline_outputs: baselineOutputs,
                        ablated_outputs: ablatedOutputs,
                        prompt: data.prompt || '',
                        blind: true,
                        n_judges: 1,
                        provider: userProvider,
                        model: userModel,
                        api_key: userApiKey,
                    }),
                });
                const result = await response.json();
                if (!response.ok) {
                    throw new Error(result.error || result.message || 'LLM difference review failed');
                }
                const scores = data.influence_scores;
                const apply = (item) => {
                    if ((item.focus || item.focus_name) === focus) {
                        item.llm_behavioral_difference = result;
                    }
                };
                if (Array.isArray(scores)) scores.forEach(apply);
                else if (scores && typeof scores === 'object') Object.values(scores).forEach(apply);
                if (rec) rec.llm_behavioral_difference = result;
                window.singleAblationResults = data;
                renderAblationResults(data);
            } catch (err) {
                alert(err.message || String(err));
                btn.disabled = false;
                btn.textContent = prev;
            }
        });
    });

    ablationResults.querySelectorAll('.btn-review-human-diff').forEach((btn) => {
        btn.addEventListener('click', async () => {
            const focus = btn.getAttribute('data-focus');
            const materialRaw = window.prompt(
                'Material behavioral difference for "' + focus + '"?\n' +
                'Enter yes / no / uncertain\n' +
                '(Do NOT judge which output is better — only whether they differ.)',
                'yes'
            );
            if (materialRaw === null) return;
            const scoreRaw = window.prompt('Overall difference score 0–5 (change magnitude only):', '4');
            if (scoreRaw === null) return;
            const notes = window.prompt('Optional notes on how they differ (not which is better):', '') || '';
            const structure = window.prompt('structure_format difference 0–5 (optional):', '0') || '0';
            const compliance = window.prompt('instruction_compliance difference 0–5 (optional):', '0') || '0';
            try {
                const response = await fetch('/api/behavioral-difference/human-review', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        material_behavioral_difference: materialRaw,
                        overall_difference_score: Number(scoreRaw),
                        dimensions: {
                            structure_format: Number(structure),
                            instruction_compliance: Number(compliance),
                        },
                        notes: notes,
                        blinded: false,
                    }),
                });
                const result = await response.json();
                if (!response.ok) throw new Error(result.error || 'Human review failed');
                const scores = data.influence_scores;
                const apply = (item) => {
                    if ((item.focus || item.focus_name) === focus) {
                        item.human_behavioral_difference = result;
                    }
                };
                if (Array.isArray(scores)) scores.forEach(apply);
                else if (scores && typeof scores === 'object') Object.values(scores).forEach(apply);
                window.singleAblationResults = data;
                renderAblationResults(data);
            } catch (err) {
                alert(err.message || String(err));
            }
        });
    });
}


// ---------------------------------------------------------------------------
// Experiment C — Reported focus (A) vs perturbation sensitivity (B)
// ---------------------------------------------------------------------------
const experimentCResults = document.getElementById('experiment-c-results');
const refreshExperimentCBtn = document.getElementById('refresh-experiment-c-btn');
const explainExperimentCBtn = document.getElementById('explain-experiment-c-btn');
const evalCriteriaInput = document.getElementById('eval-criteria-input');
const runQualityEvalBtn = document.getElementById('run-quality-eval-btn');
const qualityEvalResults = document.getElementById('quality-eval-results');
const qualityEvalOutputPreview = document.getElementById('quality-eval-output-preview');
const qualityEvalSamplePct = document.getElementById('quality-eval-sample-pct');
const runFocusOrderBtn = document.getElementById('run-focus-order-btn');
const focusOrderResults = document.getElementById('focus-order-results');
const focusOrderKSel = document.getElementById('focus-order-k');
const focusOrderMSel = document.getElementById('focus-order-m');
const focusOrderSweepFocus = document.getElementById('focus-order-sweep-focus');
const focusOrderRunSweep = document.getElementById('focus-order-run-sweep');
const focusOrderRunJudge = document.getElementById('focus-order-run-judge');
const focusOrderCriterion = document.getElementById('focus-order-criterion');
const focusOrderCostEstimate = document.getElementById('focus-order-cost-estimate');
window.experimentCComparison = null;

function getExperimentAReportedPayload() {
    const tagged = (foci && foci.length) ? foci : [];
    const assessed = (assessmentFoci && assessmentFoci.length) ? assessmentFoci : [];
    let source = tagged.length ? tagged : assessed;
    if (!source.length && window.singleAblationResults) {
        const perturbation = buildExperimentCPerturbationPayload(window.singleAblationResults);
        const records = (perturbation && perturbation.influence_scores) || [];
        source = records.map(function (r) {
            return {
                focus: r.focus || r.focus_name || 'Focus',
                prompt_section: r.prompt_section || '',
                score: null,
                explanation: ''
            };
        });
    }
    return {
        foci: source.map(function (f) {
            const matched = assessed.length ? matchFocus(f, assessed) : null;
            const score = matched
                ? (typeof matched.score === 'number' ? matched.score : (matched.reported_focus_score || 0))
                : (typeof f.score === 'number' ? f.score : (f.reported_focus_score || null));
            return {
                focus: f.focus,
                score: score,
                explanation: (matched && matched.explanation) || f.explanation || '',
                prompt_section: f.prompt_section || (matched && matched.prompt_section) || ''
            };
        })
    };
}

function buildExperimentCPerturbationPayload(ablation) {
    if (!ablation) return null;
    const records = (window.FocalPromptResults && window.FocalPromptResults.collectFocusRecords)
        ? window.FocalPromptResults.collectFocusRecords(ablation)
        : (ablation.influence_scores || ablation.ablation_results || []);
    return {
        influence_scores: ablation.influence_scores || records,
        ablation_results: ablation.ablation_results || []
    };
}

async function refreshExperimentCComparison(options) {
    const scroll = options && options.scroll;
    const reported = getExperimentAReportedPayload();
    const ablation = window.singleAblationResults;
    const perturbation = buildExperimentCPerturbationPayload(ablation);
    const explainBtn = explainExperimentCBtn;
    const hasFoci = reported.foci.length > 0;
    const hasB = perturbation && (
        (perturbation.influence_scores && perturbation.influence_scores.length) ||
        (perturbation.ablation_results && perturbation.ablation_results.length)
    );

    if (!hasB) {
        setExperimentCMessage(
            '<p class="empty-state">Run <strong>Ablation Analysis</strong> (Experiment B) first. ' +
            'Experiment C compares each focus: A assigned level vs B measured signal strength. ' +
            'Run <strong>Assess Focus Distribution</strong> (Experiment A) for reported scores.</p>'
        );
        if (explainBtn) explainBtn.disabled = true;
        window.experimentCComparison = null;
        return;
    }

    if (!hasFoci) {
        setExperimentCMessage('<p class="empty-state">No foci found to compare. Tag foci or re-run ablation.</p>');
        if (explainBtn) explainBtn.disabled = true;
        window.experimentCComparison = null;
        return;
    }

    try {
        const response = await fetch('/api/compare-reported-vs-revealed', {
            method: 'POST',
            headers: getApiHeaders(),
            body: JSON.stringify(getApiBody({
                reported: reported,
                perturbation: perturbation,
                tagged_foci: foci || [],
                influence_scores: perturbation.influence_scores
            }))
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || 'Comparison failed');
        }
        window.experimentCComparison = data;
        paintExperimentCComparison(data, true);
        if (window.FocalPromptReport && typeof window.FocalPromptReport.refresh === 'function') {
            window.FocalPromptReport.refresh();
        }
        if (explainBtn) {
            const nDis = (data.summary && data.summary.n_disagreements) || 0;
            explainBtn.disabled = nDis === 0;
            explainBtn.title = nDis
                ? 'Ask the LLM for hypotheses about A↔B disagreements'
                : 'No disagreements to explain at the current thresholds';
        }
        if (scroll) {
            const target = document.getElementById('experiment-c-section');
            if (target && target.scrollIntoView) {
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }
    } catch (err) {
        console.error('Experiment C comparison error:', err);
        setExperimentCMessage(
            '<p class="error-message">Could not compare Experiment A and B: ' +
            escapeHtml(err.message || String(err)) + '</p>'
        );
        if (explainBtn) explainBtn.disabled = true;
    }
}

function renderExperimentCComparison(data) {
    paintExperimentCComparison(data, true);
}

function formatExperimentCQ(q) {
    if (q === null || q === undefined) return 'n/a';
    const n = Number(q);
    if (Number.isNaN(n)) return String(q);
    if (window.FocalPromptResults && window.FocalPromptResults.formatQValue) {
        return window.FocalPromptResults.formatQValue(n);
    }
    return n.toPrecision(3);
}

function renderExperimentCExplanation(explanation) {
    if (!explanation) return '';
    let html = '<div class="experiment-c-explain" id="experiment-c-explanation">';
    html += '<h4>LLM hypotheses for disagreements</h4>';
    html += '<p style="font-size:0.9em;color:#64748b">' +
        escapeHtml(explanation.note || 'Hypotheses only — not adjudication of A vs B.') +
        '</p>';
    if (explanation.status === 'skipped') {
        html += '<p>' + escapeHtml(explanation.overall_summary || explanation.reason || 'Skipped.') + '</p>';
    } else {
        if (explanation.overall_summary) {
            html += '<p>' + escapeHtml(explanation.overall_summary) + '</p>';
        }
        (explanation.per_focus || []).forEach(function (item) {
            html += '<div style="margin-top:12px;padding-top:12px;border-top:1px solid var(--border-color)">';
            html += '<strong>' + escapeHtml(item.focus || '') + '</strong>';
            html += '<p style="margin:6px 0">' + escapeHtml(item.hypothesis || '') + '</p>';
            if (item.likely_mechanisms && item.likely_mechanisms.length) {
                html += '<p style="font-size:0.9em;margin:4px 0"><em>Mechanisms:</em> ' +
                    escapeHtml(item.likely_mechanisms.join(', ')) + '</p>';
            }
            if (item.what_would_resolve) {
                html += '<p style="font-size:0.9em;margin:4px 0"><em>Next check:</em> ' +
                    escapeHtml(item.what_would_resolve) + '</p>';
            }
            html += '</div>';
        });
        if (explanation.caveats && explanation.caveats.length) {
            html += '<ul style="margin-top:12px">';
            explanation.caveats.forEach(function (c) {
                html += '<li>' + escapeHtml(c) + '</li>';
            });
            html += '</ul>';
        }
    }
    html += '</div>';
    return html;
}

if (refreshExperimentCBtn) {
    refreshExperimentCBtn.addEventListener('click', function () {
        window.experimentCExplanationHtml = '';
        refreshExperimentCComparison();
    });
}

if (explainExperimentCBtn) {
    explainExperimentCBtn.addEventListener('click', async function () {
        if (!window.experimentCComparison) {
            showErrorModal('Refresh the Experiment C comparison first.');
            return;
        }
        const nDis = (window.experimentCComparison.summary || {}).n_disagreements || 0;
        if (!nDis) {
            showErrorModal('No disagreements to explain at the current thresholds.');
            return;
        }
        showLoading('Asking the LLM to hypothesize about A↔B disagreements…');
        explainExperimentCBtn.disabled = true;
        try {
            const response = await fetch('/api/explain-reported-vs-revealed', {
                method: 'POST',
                headers: getApiHeaders(),
                body: JSON.stringify(getApiBody({
                    comparison: window.experimentCComparison,
                    prompt: promptInput ? promptInput.value : '',
                    temperature: 0.3
                }))
            });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || 'Explanation failed');
            }
            window.experimentCExplanationHtml = renderExperimentCExplanation(data.explanation || data);
            renderExperimentCComparison(window.experimentCComparison);
            const el = document.getElementById('experiment-c-explanation');
            if (el && el.scrollIntoView) {
                el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
        } catch (err) {
            showError('Error explaining disagreements: ' + err.message);
            console.error(err);
        } finally {
            hideLoading();
            const n = (window.experimentCComparison && window.experimentCComparison.summary
                && window.experimentCComparison.summary.n_disagreements) || 0;
            explainExperimentCBtn.disabled = n === 0;
        }
    });
}

function collectOutputsForQualityEval() {
    const outputs = [];
    const ab = window.singleAblationResults;
    if (!ab) {
        return outputs;
    }

    const baselines = (ab.baseline_outputs && ab.baseline_outputs.length)
        ? ab.baseline_outputs
        : (ab.baseline_output ? [ab.baseline_output] : []);
    baselines.forEach(function (t, i) {
        const text = (t || '').trim();
        if (!text) return;
        outputs.push({
            label: 'Baseline (full prompt) — sample ' + (i + 1),
            text: text,
            group: 'baseline',
        });
    });

    const records = (window.FocalPromptResults && window.FocalPromptResults.collectFocusRecords)
        ? window.FocalPromptResults.collectFocusRecords(ab)
        : (ab.ablation_results || []);
    records.forEach(function (rec) {
        const name = rec.focus || rec.focus_name || 'Focus';
        const ablated = rec.ablated_outputs || (rec.ablated_output ? [rec.ablated_output] : []);
        ablated.forEach(function (t, i) {
            const text = (t || '').trim();
            if (!text) return;
            outputs.push({
                label: 'Ablated: ' + name + ' — sample ' + (i + 1),
                text: text,
                group: 'ablated',
                focus: name,
            });
        });
    });
    return outputs;
}

function getQualityEvalSampleFraction() {
    if (!qualityEvalSamplePct) return 1.0;
    const pct = parseFloat(qualityEvalSamplePct.value);
    if (!Number.isFinite(pct) || pct >= 100) return 1.0;
    return Math.max(0.01, pct / 100.0);
}

function countSampledOutputs(total, fraction) {
    if (fraction >= 1.0 || total <= 0) return total;
    return Math.max(1, Math.round(total * fraction));
}

function summarizeQualityEvalOutputs(outputs) {
    if (!outputs || !outputs.length) {
        return 'Run Experiment B (section 6) first. Baseline and ablated samples from that run will be scored here against your criteria.';
    }
    const baselineCount = outputs.filter(function (o) { return o.group === 'baseline'; }).length;
    const ablatedRows = outputs.filter(function (o) { return o.group === 'ablated'; });
    const focusNames = [];
    ablatedRows.forEach(function (o) {
        if (o.focus && focusNames.indexOf(o.focus) === -1) {
            focusNames.push(o.focus);
        }
    });
    let text = 'Will evaluate <strong>' + outputs.length + ' Experiment B output(s)</strong>';
    const fraction = getQualityEvalSampleFraction();
    if (fraction < 1.0) {
        const sampled = countSampledOutputs(outputs.length, fraction);
        text = 'Will evaluate <strong>' + sampled + ' of ' + outputs.length +
            ' outputs</strong> (' + Math.round(fraction * 100) + '% stratified sample)';
    }
    text += ': ';
    text += baselineCount + ' baseline sample' + (baselineCount === 1 ? '' : 's') + ' (full prompt)';
    if (ablatedRows.length) {
        text += ' and ' + ablatedRows.length + ' ablated sample' +
            (ablatedRows.length === 1 ? '' : 's') + ' across ' +
            focusNames.length + ' focus' + (focusNames.length === 1 ? '' : 'es');
        if (focusNames.length) {
            text += ' (' + focusNames.join(', ') + ')';
        }
    }
    text += '. Section 3 output is not included.';
    return text;
}

function refreshQualityEvalPreview() {
    if (!qualityEvalOutputPreview) return;
    qualityEvalOutputPreview.innerHTML = summarizeQualityEvalOutputs(collectOutputsForQualityEval());
}

if (qualityEvalSamplePct) {
    qualityEvalSamplePct.addEventListener('change', refreshQualityEvalPreview);
}

function buildQualityEvalOutputLookup() {
    const map = {};
    collectOutputsForQualityEval().forEach(function (o) {
        if (o.label && o.text) {
            map[o.label] = o.text;
        }
    });
    return map;
}

function renderQualityEvalCard(row, outputLookup) {
    const score = row.overall_score;
    const scoreTxt = (score == null || Number.isNaN(Number(score)))
        ? 'n/a'
        : Number(score).toFixed(0) + '/100';
    const outputText = (row.output_text || (outputLookup && outputLookup[row.label]) || '').trim();
    let html = '<div class="quality-eval-card">';
    html += '<h4><span>' + escapeHtml(row.label || 'Output') + '</span>';
    html += '<span class="quality-eval-score">' + escapeHtml(scoreTxt) + '</span></h4>';
    if (outputText) {
        html += '<details class="quality-eval-output-details">';
        html += '<summary>View evaluated output</summary>';
        html += '<pre class="quality-eval-output-preview">' + escapeHtml(outputText) + '</pre>';
        html += '</details>';
    }
    if (row.summary) {
        html += '<p>' + escapeHtml(row.summary) + '</p>';
    }
    if (row.meets_primary_criterion != null) {
        html += '<p style="font-size:0.9em;margin:4px 0"><strong>Meets primary criterion:</strong> ' +
            (row.meets_primary_criterion ? 'Yes' : 'No') + '</p>';
    }
    const breakdown = row.criterion_breakdown || [];
    if (breakdown.length) {
        html += '<ul style="margin:8px 0 0 18px;font-size:0.92em">';
        breakdown.forEach(function (c) {
            html += '<li><strong>' + escapeHtml(c.name || 'Criterion') + '</strong>: ' +
                escapeHtml(String(c.score != null ? c.score : '')) + '/5' +
                (c.met === true ? ' ✓' : (c.met === false ? ' ✗' : '')) +
                (c.notes ? ' — ' + escapeHtml(c.notes) : '') + '</li>';
        });
        html += '</ul>';
    }
    if (row.strengths && row.strengths.length) {
        html += '<p style="font-size:0.9em;margin-top:8px"><strong>Strengths:</strong> ' +
            escapeHtml(row.strengths.join('; ')) + '</p>';
    }
    if (row.weaknesses && row.weaknesses.length) {
        html += '<p style="font-size:0.9em"><strong>Weaknesses:</strong> ' +
            escapeHtml(row.weaknesses.join('; ')) + '</p>';
    }
    html += '</div>';
    return html;
}

function renderQualityEvalResults(data) {
    if (!qualityEvalResults) return;
    const evals = data.evaluations || [];
    if (!evals.length) {
        qualityEvalResults.innerHTML = '<p class="empty-state">No evaluations returned.</p>';
        return;
    }

    const outputLookup = buildQualityEvalOutputLookup();

    let html = '';
    html += '<p class="info-text"><strong>Scope:</strong> Experiment B outputs only — baseline samples (full prompt) and ablated samples (focus removed). Not section 3.</p>';
    if (data.n_outputs_total && data.n_outputs_evaluated &&
        data.n_outputs_evaluated < data.n_outputs_total) {
        html += '<p class="info-text">Evaluated ' + data.n_outputs_evaluated + ' of ' +
            data.n_outputs_total + ' outputs (' +
            Math.round((data.sample_fraction || 0) * 100) + '% stratified sample).</p>';
    }
    if (data.cost_breakdown && data.cost_breakdown.total_cost != null) {
        html += '<p class="info-text">Evaluation cost: $' +
            Number(data.cost_breakdown.total_cost).toFixed(4) + '</p>';
    }
    if (data.n_batches && data.n_batches > 1) {
        html += '<p class="info-text">Scored in ' + data.n_batches + ' batches of up to 4 outputs each.</p>';
    }

    const baselineEvals = evals.filter(function (row) {
        return String(row.label || '').indexOf('Baseline (full prompt)') === 0;
    });
    const ablatedEvals = evals.filter(function (row) {
        return String(row.label || '').indexOf('Ablated:') === 0;
    });

    if (baselineEvals.length) {
        html += '<h3 style="margin:16px 0 8px;font-size:1.05em">Baseline (full prompt)</h3>';
        baselineEvals.forEach(function (row) {
            html += renderQualityEvalCard(row, outputLookup);
        });
    }
    if (ablatedEvals.length) {
        html += '<h3 style="margin:16px 0 8px;font-size:1.05em">Ablated outputs (Experiment B)</h3>';
        ablatedEvals.forEach(function (row) {
            html += renderQualityEvalCard(row, outputLookup);
        });
    }
    evals.filter(function (row) {
        return baselineEvals.indexOf(row) === -1 && ablatedEvals.indexOf(row) === -1;
    }).forEach(function (row) {
        html += renderQualityEvalCard(row, outputLookup);
    });

    if (data.comparative_notes) {
        html += '<div class="quality-eval-comparative"><strong>Comparative notes</strong><p>' +
            escapeHtml(data.comparative_notes) + '</p></div>';
    }

    html += '<p style="font-size:0.85em;color:#64748b;margin-top:12px">' +
        'Task quality on Experiment B samples — not behavioral difference or reported focus.</p>';
    qualityEvalResults.innerHTML = html;
    window.lastQualityEvalResults = data;
}

function refreshFocusOrderControls(abData) {
    const ab = abData || window.singleAblationResults;
    if (!runFocusOrderBtn || !focusOrderSweepFocus) return;
    const baselines = (ab && ab.baseline_outputs && ab.baseline_outputs.length)
        ? ab.baseline_outputs
        : (ab && ab.baseline_output ? [ab.baseline_output] : []);
    runFocusOrderBtn.disabled = !baselines.length;
    focusOrderSweepFocus.innerHTML = '';
    if (!ab || !baselines.length) {
        focusOrderSweepFocus.disabled = true;
        focusOrderSweepFocus.innerHTML = '<option value="">— run Experiment B first —</option>';
        if (focusOrderCostEstimate) {
            focusOrderCostEstimate.textContent = 'Run Experiment B (section 6) first to reuse baseline samples.';
        }
        return;
    }
    focusOrderSweepFocus.disabled = false;
    const records = (window.FocalPromptResults && window.FocalPromptResults.collectFocusRecords)
        ? window.FocalPromptResults.collectFocusRecords(ab)
        : (ab.ablation_results || []);
    focusOrderSweepFocus.innerHTML = '<option value="">— select focus —</option>';
    records.forEach(function (rec) {
        if (!rec.attributable) return;
        const idx = rec.focus_index != null ? rec.focus_index : rec.index;
        const name = rec.focus || rec.focus_name || ('Focus ' + idx);
        focusOrderSweepFocus.innerHTML += '<option value="' + String(idx) + '">' +
            escapeHtml(name) + '</option>';
    });
    updateFocusOrderCostEstimate();
}

async function updateFocusOrderCostEstimate() {
    if (!focusOrderCostEstimate) return;
    const ab = window.singleAblationResults;
    const baselines = (ab && ab.baseline_outputs) ? ab.baseline_outputs : [];
    if (!baselines.length) {
        focusOrderCostEstimate.textContent = 'Run Experiment B (section 6) first to reuse baseline samples.';
        return;
    }
    const k = focusOrderKSel ? parseInt(focusOrderKSel.value, 10) || 5 : 5;
    const m = focusOrderMSel ? parseInt(focusOrderMSel.value, 10) || 3 : 3;
    try {
        const response = await fetch('/api/focus-order-sensitivity/estimate-cost', {
            method: 'POST',
            headers: getApiHeaders(),
            body: JSON.stringify(getApiBody({
                k_permutations: k,
                m_samples: m,
                run_position_sweep: focusOrderRunSweep && focusOrderRunSweep.checked,
                run_behavioral_judge: focusOrderRunJudge && focusOrderRunJudge.checked,
                baseline_outputs: baselines,
            })),
        });
        const est = await response.json();
        if (response.ok) {
            focusOrderCostEstimate.textContent =
                'Estimated model calls: ' + est.total_model_calls +
                ' (global ' + est.global_order_model_calls +
                (est.position_sweep_model_calls ? ', sweep ' + est.position_sweep_model_calls : '') +
                (est.behavioral_judge_calls ? ', judge ' + est.behavioral_judge_calls : '') +
                '). Baseline outputs reused from Experiment B.';
        }
    } catch (_e) {
        focusOrderCostEstimate.textContent = 'Configure K and M above; baseline samples reused from Experiment B.';
    }
}

if (focusOrderKSel) focusOrderKSel.addEventListener('change', updateFocusOrderCostEstimate);
if (focusOrderMSel) focusOrderMSel.addEventListener('change', updateFocusOrderCostEstimate);
if (focusOrderRunSweep) focusOrderRunSweep.addEventListener('change', updateFocusOrderCostEstimate);
if (focusOrderRunJudge) focusOrderRunJudge.addEventListener('change', updateFocusOrderCostEstimate);

if (runFocusOrderBtn) {
    runFocusOrderBtn.addEventListener('click', async function () {
        const ab = window.singleAblationResults;
        const baselines = (ab && ab.baseline_outputs && ab.baseline_outputs.length)
            ? ab.baseline_outputs
            : (ab && ab.baseline_output ? [ab.baseline_output] : []);
        if (!baselines.length || !promptInput || !foci.length) {
            showErrorModal('Run Experiment B (section 6) with tagged foci first.');
            return;
        }
        const k = focusOrderKSel ? parseInt(focusOrderKSel.value, 10) || 5 : 5;
        const m = focusOrderMSel ? parseInt(focusOrderMSel.value, 10) || 3 : 3;
        const runSweep = focusOrderRunSweep && focusOrderRunSweep.checked;
        const sweepFocus = focusOrderSweepFocus ? focusOrderSweepFocus.value : '';
        if (runSweep && !sweepFocus) {
            showErrorModal('Select a focus for the position sweep.');
            return;
        }
        const criterion = (focusOrderCriterion && focusOrderCriterion.value.trim()) ||
            (evalCriteriaInput ? evalCriteriaInput.value.trim() : '');
        const runJudge = focusOrderRunJudge && focusOrderRunJudge.checked;
        if (runJudge && !criterion) {
            showErrorModal('Enter a behavioural criterion for the judge.');
            return;
        }
        showLoading('Running focus order sensitivity…');
        runFocusOrderBtn.disabled = true;
        try {
            const response = await fetch('/api/focus-order-sensitivity', {
                method: 'POST',
                headers: getApiHeaders(),
                body: JSON.stringify(getApiBody({
                    prompt: promptInput.value,
                    foci: foci,
                    baseline_outputs: baselines,
                    k_permutations: k,
                    m_samples: m,
                    temperature: ab.temperature || 0.7,
                    run_position_sweep: runSweep,
                    focus_index_for_sweep: runSweep ? parseInt(sweepFocus, 10) : null,
                    run_behavioral_judge: runJudge,
                    behavioral_criterion: criterion,
                })),
            });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || data.reason || 'Order sensitivity failed');
            }
            window.focusOrderSensitivityResults = data;
            if (ab) {
                ab.focus_order_sensitivity = data;
                window.singleAblationResults = ab;
            }
            if (focusOrderResults && window.FocalPromptResults) {
                focusOrderResults.innerHTML =
                    window.FocalPromptResults.renderFocusOrderSensitivityHtml(data);
            }
            if (window.FocalPromptReport && typeof window.FocalPromptReport.refresh === 'function') {
                window.FocalPromptReport.refresh();
            }
        } catch (err) {
            showError('Focus order sensitivity: ' + err.message);
        } finally {
            hideLoading();
            runFocusOrderBtn.disabled = false;
        }
    });
}

if (runQualityEvalBtn) {
    runQualityEvalBtn.addEventListener('click', async function () {
        const criteria = evalCriteriaInput ? evalCriteriaInput.value.trim() : '';
        if (!criteria) {
            showErrorModal('Enter evaluation criteria describing what a good output should do.');
            return;
        }
        const outputs = collectOutputsForQualityEval();
        if (!outputs.length) {
            showErrorModal(
                'No Experiment B outputs to evaluate. Run ablation analysis in section 6 first.'
            );
            return;
        }
        const samplePct = qualityEvalSamplePct ? parseFloat(qualityEvalSamplePct.value) || 100 : 100;

        showLoading('Evaluating Experiment B outputs against your criteria…');
        runQualityEvalBtn.disabled = true;
        try {
            const response = await fetch('/api/evaluate-outputs-quality', {
                method: 'POST',
                headers: getApiHeaders(),
                body: JSON.stringify(getApiBody({
                    eval_criteria: criteria,
                    outputs: outputs,
                    prompt: promptInput ? promptInput.value : '',
                    task_context: '',
                    temperature: 0.2,
                    evaluation_scope: 'experiment_b',
                    sample_pct: samplePct,
                }))
            });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || 'Evaluation failed');
            }
            renderQualityEvalResults(data);
            if (qualityEvalResults && qualityEvalResults.scrollIntoView) {
                qualityEvalResults.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
        } catch (err) {
            showError('Error running quality evaluation: ' + err.message);
            console.error(err);
        } finally {
            hideLoading();
            runQualityEvalBtn.disabled = false;
        }
    });
}

// Make removeFocus available globally
window.removeFocus = removeFocus;

// Agent Builder: Import Foci from Prompt Analysis
if (importFociBtn) {
    importFociBtn.addEventListener('click', () => {
        if (foci.length === 0) {
            showErrorModal('No foci defined in Prompt Analysis tab. Please define foci there first.');
            return;
        }
        agentFoci = JSON.parse(JSON.stringify(foci)); // Deep copy
        renderAgentFoci();
    });
}

// Agent Builder: Render Foci
function renderAgentFoci() {
    if (!agentFociContainer) return;
    
    if (agentFoci.length === 0) {
        agentFociContainer.innerHTML = '<p class="empty-state">No foci defined yet. Click "Auto-Detect Foci" or "Import from Prompt Analysis" to get started.</p>';
        assessChatBtn.disabled = true;
        return;
    }
    
    let html = '';
    agentFoci.forEach((focus, index) => {
        html += `
            <div class="focus-item" style="margin-bottom: 12px; padding: 12px; background: #f8fafc; border-radius: 6px; border: 1px solid var(--border-color);">
                <div style="display: flex; justify-content: space-between; align-items: start;">
                    <div style="flex: 1;">
                        <strong style="color: var(--primary-color);">${escapeHtml(focus.focus)}</strong>
                        <p style="margin: 4px 0; font-size: 0.9em; color: var(--text-secondary);">${escapeHtml(focus.prompt_section.substring(0, 150))}${focus.prompt_section.length > 150 ? '...' : ''}</p>
                    </div>
                    <button onclick="removeAgentFocus(${index})" class="btn btn-outline btn-small" style="margin-left: 12px;">Remove</button>
                </div>
            </div>
        `;
    });
    
    agentFociContainer.innerHTML = html;
    
    // Enable assess button if chat content exists
    if (chatInput && chatInput.value.trim()) {
        assessChatBtn.disabled = false;
    }
}

// Agent Builder: Remove Focus
function removeAgentFocus(index) {
    agentFoci.splice(index, 1);
    renderAgentFoci();
}

// Agent Builder: Clear Foci
if (agentClearFociBtn) {
    agentClearFociBtn.addEventListener('click', () => {
        if (confirm('Are you sure you want to clear all foci?')) {
            agentFoci = [];
            renderAgentFoci();
        }
    });
}

// Agent Builder: Auto-Detect Foci (needs prompt input)
if (agentDetectFociBtn) {
    agentDetectFociBtn.addEventListener('click', async () => {
        const prompt = promptInput ? promptInput.value.trim() : '';
        if (!prompt) {
            showErrorModal('Please enter a prompt in the Prompt Analysis tab first, or manually add foci.');
            return;
        }
        
        showLoading('Detecting foci...');
        
        try {
            const response = await fetch('/api/detect-foci', {
                method: 'POST',
                headers: getApiHeaders(),
                body: JSON.stringify(getApiBody({ prompt: prompt })),
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to detect foci');
            }
            
            agentFoci = (data.foci || []).map(f => ({
                ...f,
                is_dynamic: f.is_dynamic || false,
                dynamic_type: f.dynamic_type || null
            }));
            renderAgentFoci();
            
        } catch (error) {
            showError('Error detecting foci: ' + error.message);
            console.error('Detect foci error:', error);
        } finally {
            hideLoading();
        }
    });
}

// Agent Builder: Enable/Disable Assess Button
if (chatInput) {
    chatInput.addEventListener('input', () => {
        if (chatInput.value.trim() && agentFoci.length > 0) {
            assessChatBtn.disabled = false;
        } else {
            assessChatBtn.disabled = true;
        }
    });
}

// Agent Builder: Assess Chat & Select Foci
if (assessChatBtn) {
    assessChatBtn.addEventListener('click', async () => {
        const chatContent = chatInput ? chatInput.value.trim() : '';
        
        if (!chatContent) {
            showErrorModal('Please enter chat content first.');
            return;
        }
        
        if (agentFoci.length === 0) {
            showErrorModal('Please define foci first.');
            return;
        }
        
        showLoading('Assessing chat and selecting relevant foci...');
        
        try {
            const response = await fetch('/api/assess-chat-foci', {
                method: 'POST',
                headers: getApiHeaders(),
                body: JSON.stringify(getApiBody({
                    chat_content: chatContent,
                    foci: agentFoci
                })),
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to assess chat');
            }
            
            // Validate response data
            if (!data.foci_weights || !Array.isArray(data.foci_weights)) {
                console.error('Invalid response data:', data);
                throw new Error('Invalid response: missing or invalid foci_weights');
            }
            
            // Make sure results container is visible
            if (fociWeightsResults) {
                fociWeightsResults.style.display = 'block';
            }
            
            renderFociWeights(data);
            generateAgentResponseBtn.disabled = false;
            
            // Store cost data
            window.assessChatCost = data.cost_breakdown || null;
            
        } catch (error) {
            showError('Error assessing chat: ' + error.message);
            console.error('Assess chat error:', error);
        } finally {
            hideLoading();
        }
    });
}

// Agent Builder: Render Foci Weights
function renderFociWeights(data) {
    if (!fociWeightsResults) {
        console.error('fociWeightsResults element not found');
        return;
    }
    
    // Validate data structure
    if (!data || !data.foci_weights || !Array.isArray(data.foci_weights)) {
        console.error('Invalid data structure:', data);
        fociWeightsResults.innerHTML = '<p class="error-message">Error: Invalid response data structure</p>';
        return;
    }
    
    let html = '<h3 style="margin-bottom: 16px;">Selected Foci with Weights</h3>';
    
    // Add cost breakdown if available
    if (data.cost_breakdown) {
        const cost = data.cost_breakdown;
        html += '<div class="cost-breakdown" style="margin-bottom: 20px; padding: 16px; background: #e8f4f8; border-radius: 6px; border: 1px solid #bee5eb;">';
        html += '<h4 style="margin: 0 0 12px 0; color: #0c5460;">💰 Cost Breakdown (Assess Chat)</h4>';
        html += '<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; font-size: 0.9em;">';
        html += '<div><strong>Chat Completions:</strong><br>';
        html += `Input: ${cost.chat_completions.input_tokens.toLocaleString()} tokens<br>`;
        html += `Output: ${cost.chat_completions.output_tokens.toLocaleString()} tokens<br>`;
        html += `Cost: $${cost.chat_completions.cost.toFixed(4)}</div>`;
        html += '</div>';
        html += `<div style="margin-top: 12px; padding-top: 12px; border-top: 2px solid #bee5eb; font-size: 1.1em; font-weight: bold; color: #0c5460;">`;
        html += `Total Cost: $${cost.total_cost.toFixed(4)}`;
        html += ` <span style="font-size: 0.85em; font-weight: normal; color: #666;">(Model: ${cost.model || 'gpt-4o-mini'})</span>`;
        html += '</div>';
        html += '</div>';
    }
    
    // Sort by weight descending
    const sortedFoci = [...data.foci_weights].sort((a, b) => b.weight - a.weight);
    
    sortedFoci.forEach(item => {
        const weightPercent = (item.weight * 100).toFixed(1);
        html += `
            <div class="weight-display">
                <div style="flex: 1;">
                    <strong>${escapeHtml(item.focus)}</strong>
                    <p style="margin: 4px 0; font-size: 0.85em; color: var(--text-secondary);">${escapeHtml(item.explanation || '')}</p>
                </div>
                <div class="weight-value">${weightPercent}%</div>
                <div class="weight-bar">
                    <div class="weight-bar-fill" style="width: ${weightPercent}%">
                        ${item.weight >= 0.1 ? weightPercent + '%' : ''}
                    </div>
                </div>
            </div>
        `;
    });
    
    // Calculate total weight (foci + chat) for display
    const totalFociWeight = sortedFoci.reduce((sum, item) => sum + item.weight, 0);
    const chatWeight = data.chat_weight || 0;
    const totalWeight = totalFociWeight + chatWeight;
    const totalWeightPercent = (totalWeight * 100).toFixed(1);
    
    // Chat weight (part of the 100% total)
    const chatWeightPercent = (chatWeight * 100).toFixed(1);
    html += `
        <div style="margin-top: 24px; padding-top: 24px; border-top: 2px solid var(--border-color);">
            <div style="margin-bottom: 16px; padding: 12px; background: #f0f9ff; border-radius: 6px; border: 1px solid #bae6fd;">
                <strong>Total Weight:</strong> ${totalWeightPercent}%
                <p style="margin: 4px 0 0 0; font-size: 0.85em; color: var(--text-secondary);">
                    Foci weights and chat weight are normalized together to sum to 100%.
                </p>
            </div>
            <div class="chat-weight-display">
                <h4 style="margin: 0 0 8px 0;">Chat Content Weight</h4>
                <p style="margin: 4px 0; font-size: 0.9em;">${escapeHtml(data.chat_weight_explanation || '')}</p>
                <div style="display: flex; align-items: center; gap: 12px; margin-top: 12px;">
                    <div class="weight-value">${chatWeightPercent}%</div>
                    <div class="weight-bar">
                        <div class="weight-bar-fill" style="width: ${chatWeightPercent}%">
                            ${chatWeight >= 0.1 ? chatWeightPercent + '%' : ''}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Store for later use
    window.fociWeightsData = data;
    
    fociWeightsResults.innerHTML = html;
}

// Agent Builder: Generate Response
if (generateAgentResponseBtn) {
    generateAgentResponseBtn.addEventListener('click', async () => {
        if (!window.fociWeightsData) {
            showErrorModal('Please assess chat and select foci first.');
            return;
        }
        
        const chatContent = chatInput ? chatInput.value.trim() : '';
        if (!chatContent) {
            showErrorModal('Please enter chat content first.');
            return;
        }
        
        showLoading('Building prompt and generating response...');
        
        try {
            // First build the prompt
            const buildResponse = await fetch('/api/build-agent-prompt', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    foci: window.fociWeightsData.foci_weights.map(fw => {
                        // Find the original focus to get prompt_section + dynamic flags
                        const originalFocus = agentFoci.find(f => f.focus === fw.focus);
                        if (!originalFocus) {
                            console.warn(`Could not find original focus for: ${fw.focus}`);
                        }
                        return {
                            focus: fw.focus,
                            weight: fw.weight,
                            prompt_section: originalFocus ? originalFocus.prompt_section : '',
                            is_dynamic: originalFocus ? !!originalFocus.is_dynamic : false,
                            dynamic_type: originalFocus ? (originalFocus.dynamic_type || null) : null
                        };
                    }),
                    all_foci: agentFoci,
                    chat_content: chatContent,
                    chat_weight: window.fociWeightsData.chat_weight,
                    model: userModel || 'gpt-4o-mini',
                    provider: userProvider || 'openai'
                }),
            });
            
            const buildData = await buildResponse.json();
            
            if (!buildResponse.ok) {
                throw new Error(buildData.error || 'Failed to build prompt');
            }
            
            // Then generate response
            const genResponse = await fetch('/api/generate-agent-response', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    constructed_prompt: buildData.constructed_prompt,
                    chat_content: chatContent,
                    model: 'gpt-4o-mini',
                    temperature: 0.7
                }),
            });
            
            const genData = await genResponse.json();
            
            if (!genResponse.ok) {
                throw new Error(genData.error || 'Failed to generate response');
            }
            
            // Calculate total cost (assess + generate)
            const totalCost = (window.assessChatCost ? window.assessChatCost.total_cost : 0) + 
                            (genData.cost_breakdown ? genData.cost_breakdown.total_cost : 0);
            
            renderAgentResponse(buildData, genData, totalCost, window.assessChatCost, genData.cost_breakdown);
            
        } catch (error) {
            showError('Error generating response: ' + error.message);
            console.error('Generate response error:', error);
        } finally {
            hideLoading();
        }
    });
}

// Agent Builder: Render Response
function renderAgentResponse(buildData, genData, totalCost, assessCost, generateCost) {
    if (!agentResponseResults) return;
    
    let html = '<h3 style="margin-bottom: 16px;">Generated Response</h3>';
    
    // Cost breakdown
    if (assessCost || generateCost) {
        html += '<div class="cost-breakdown" style="margin-bottom: 20px; padding: 16px; background: #e8f4f8; border-radius: 6px; border: 1px solid #bee5eb;">';
        html += '<h4 style="margin: 0 0 12px 0; color: #0c5460;">💰 Cost Breakdown</h4>';
        html += '<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; font-size: 0.9em;">';
        
        if (assessCost) {
            html += '<div><strong>Assess Chat & Select Foci:</strong><br>';
            html += `Input: ${assessCost.chat_completions.input_tokens.toLocaleString()} tokens<br>`;
            html += `Output: ${assessCost.chat_completions.output_tokens.toLocaleString()} tokens<br>`;
            html += `Cost: $${assessCost.chat_completions.cost.toFixed(4)}</div>`;
        }
        
        if (generateCost) {
            html += '<div><strong>Generate Response:</strong><br>';
            html += `Input: ${generateCost.chat_completions.input_tokens.toLocaleString()} tokens<br>`;
            html += `Output: ${generateCost.chat_completions.output_tokens.toLocaleString()} tokens<br>`;
            html += `Cost: $${generateCost.chat_completions.cost.toFixed(4)}</div>`;
        }
        
        html += '</div>';
        html += `<div style="margin-top: 12px; padding-top: 12px; border-top: 2px solid #bee5eb; font-size: 1.1em; font-weight: bold; color: #0c5460;">`;
        html += `Total Cost: $${totalCost.toFixed(4)}`;
        html += '</div>';
        html += '</div>';
    }
    
    html += `
        <div class="constructed-prompt-display">
            <h4 style="margin: 0 0 12px 0; color: var(--primary-color);">Constructed Prompt:</h4>
            <div>${escapeHtml(buildData.constructed_prompt)}</div>
        </div>
    `;
    
    html += `
        <div class="agent-output-display">
            <h4 style="margin: 0 0 12px 0; color: var(--success-color);">Agent Output:</h4>
            <div>${escapeHtml(genData.output)}</div>
        </div>
    `;
    
    agentResponseResults.innerHTML = html;
}

// ==================== BATCH ANALYSIS ====================

// Batch Analysis: CSV Upload
if (csvUpload) {
    csvUpload.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        
        showLoading('Parsing CSV file...');
        
        try {
            const formData = new FormData();
            formData.append('file', file);
            
            const response = await fetch('/api/parse-batch-csv', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to parse CSV');
            }
            
            batchPairs = data.pairs || [];
            renderPairs();
            updateBatchAnalysisButton();
            updateCostEstimate();
            
            if (data.errors && data.errors.length > 0) {
                showError('CSV parsed with some errors: ' + data.errors.join(', '));
            }
            
        } catch (error) {
            showError('Error parsing CSV: ' + error.message);
            console.error('CSV parse error:', error);
        } finally {
            hideLoading();
            e.target.value = ''; // Reset file input
        }
    });
}

// Extra manual fields (RAG, tools, …). Primary pair input is always #manual-pair-input (chat_content).
function updateManualInputFields() {
    if (!manualInputFields) return;
    
    const dynamicTypes = new Set();
    batchFoci.forEach(focus => {
        if (focus.is_dynamic && focus.dynamic_type) {
            dynamicTypes.add(focus.dynamic_type);
        }
    });
    
    const fieldLabels = {
        'rag': 'RAG context (this pair)',
        'tools': 'Tool results (this pair)',
        'other': 'Other dynamic input (this pair)'
    };
    const fieldIds = {
        'rag': 'manual-rag-context',
        'tools': 'manual-tool-results',
        'other': 'manual-other-input'
    };
    
    let html = '';
    ['rag', 'tools', 'other'].forEach(type => {
        if (dynamicTypes.has(type)) {
            html += `<label for="${fieldIds[type]}" style="display:block;font-weight:600;margin-bottom:6px;">${fieldLabels[type]}</label>`;
            html += `<textarea 
                id="${fieldIds[type]}" 
                class="textarea-large" 
                placeholder="${fieldLabels[type]} — optional if unused"
                rows="3"
            ></textarea>`;
        }
    });
    
    manualInputFields.innerHTML = html;
}

// Batch Analysis: Manual Entry
if (addPairBtn) {
    addPairBtn.addEventListener('click', () => {
        const inputText = manualPairInput ? manualPairInput.value.trim() : '';
        const output = manualOutput ? manualOutput.value.trim() : '';
        
        if (!inputText) {
            showErrorModal('Please fill in the Input field.');
            return;
        }
        if (!output) {
            showErrorModal('Please fill in the Output field.');
            return;
        }
        
        const inputs = { chat_content: inputText };
        
        const dynamicTypes = new Set();
        batchFoci.forEach(focus => {
            if (focus.is_dynamic && focus.dynamic_type) {
                dynamicTypes.add(focus.dynamic_type);
            }
        });
        
        const fieldIds = {
            'chat': 'manual-pair-input',
            'rag': 'manual-rag-context',
            'tools': 'manual-tool-results',
            'other': 'manual-other-input'
        };
        
        dynamicTypes.forEach(type => {
            if (type === 'chat') {
                return;
            }
            const fieldId = fieldIds[type];
            const field = document.getElementById(fieldId);
            if (field) {
                const value = field.value.trim();
                if (type === 'rag') {
                    inputs.rag_context = value;
                } else if (type === 'tools') {
                    inputs.tool_results = value;
                } else if (type === 'other') {
                    inputs.other_input = value;
                }
            }
        });
        
        batchPairs.push({
            inputs: inputs,
            output: output
        });
        
        renderPairs();
        updateBatchAnalysisButton();
        updateCostEstimate();
        
        if (manualPairInput) manualPairInput.value = '';
        if (manualInputFields) {
            manualInputFields.querySelectorAll('textarea').forEach(ta => { ta.value = ''; });
        }
        if (manualOutput) manualOutput.value = '';
    });
}

// Batch Analysis: Render Pairs (collapsible — keep step 2 reachable)
let pairsListExpanded = false;

function renderPairs() {
    if (!pairsContainer) return;
    
    if (batchPairs.length === 0) {
        pairsListExpanded = false;
        pairsContainer.innerHTML = '<p class="empty-state">No pairs added yet. Upload a CSV file or add pairs manually.</p>';
        return;
    }
    
    const n = batchPairs.length;
    const collapsible = n > 2;
    const previewCount = collapsible ? 2 : n;
    const hiddenCount = Math.max(0, n - previewCount);
    const showAll = !collapsible || pairsListExpanded;
    
    let html = `
        <div class="pairs-list-header" style="display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 12px; flex-wrap: wrap;">
            <h3 style="margin: 0;">${n} Pair${n === 1 ? '' : 's'} Added</h3>
            ${collapsible ? `
            <button type="button" id="toggle-pairs-list-btn" class="btn btn-outline btn-small">
                ${pairsListExpanded ? 'Hide pairs' : `Show all ${n} pairs`}
            </button>` : ''}
        </div>
    `;
    
    if (collapsible && !pairsListExpanded) {
        html += `<p class="info-text" style="margin: 0 0 12px; font-size: 0.9em;">
            Showing first ${previewCount} of ${n}. Pairs are collapsed so you can continue to
            <strong>2. Define Foci</strong> without scrolling.
        </p>`;
    }
    
    const listStyle = showAll && collapsible
        ? 'display: flex; flex-direction: column; gap: 12px; max-height: 420px; overflow-y: auto; padding-right: 4px;'
        : 'display: flex; flex-direction: column; gap: 12px;';
    html += `<div style="${listStyle}">`;
    const limit = showAll ? n : previewCount;
    for (let index = 0; index < limit; index++) {
        html += renderPairItem(batchPairs[index], index);
    }
    html += '</div>';
    
    pairsContainer.innerHTML = html;
    
    const toggleBtn = document.getElementById('toggle-pairs-list-btn');
    if (toggleBtn) {
        toggleBtn.addEventListener('click', () => {
            pairsListExpanded = !pairsListExpanded;
            renderPairs();
        });
    }
}

function renderPairItem(pair, index) {
    const inputs = pair.inputs || {};
    const chatContent = inputs.chat_content || pair.chat_content || '';
    const ragContext = inputs.rag_context || '';
    const toolResults = inputs.tool_results || '';
    const otherInput = inputs.other_input || '';
    const output = pair.output || '';
    const rowPrompt = (typeof pair.prompt === 'string') ? pair.prompt : '';
    
    return `
        <div class="pair-item" style="padding: 12px; background: #f8fafc; border-radius: 6px; border: 1px solid var(--border-color);">
            <div style="display: flex; justify-content: space-between; align-items: start;">
                <div style="flex: 1;">
                    <strong>Pair ${index + 1}</strong>
                    ${rowPrompt ? `<p style="margin: 4px 0; font-size: 0.9em; color: var(--text-secondary);">
                        Prompt: ${escapeHtml(rowPrompt.substring(0, 100))}${rowPrompt.length > 100 ? '...' : ''}
                    </p>` : ''}
                    ${chatContent ? `<p style="margin: 4px 0; font-size: 0.9em; color: var(--text-secondary);">
                        Chat: ${escapeHtml(chatContent.substring(0, 100))}${chatContent.length > 100 ? '...' : ''}
                    </p>` : ''}
                    ${ragContext ? `<p style="margin: 4px 0; font-size: 0.9em; color: var(--text-secondary);">
                        RAG: ${escapeHtml(ragContext.substring(0, 100))}${ragContext.length > 100 ? '...' : ''}
                    </p>` : ''}
                    ${toolResults ? `<p style="margin: 4px 0; font-size: 0.9em; color: var(--text-secondary);">
                        Tools: ${escapeHtml(toolResults.substring(0, 100))}${toolResults.length > 100 ? '...' : ''}
                    </p>` : ''}
                    ${otherInput ? `<p style="margin: 4px 0; font-size: 0.9em; color: var(--text-secondary);">
                        Other: ${escapeHtml(otherInput.substring(0, 100))}${otherInput.length > 100 ? '...' : ''}
                    </p>` : ''}
                    <p style="margin: 4px 0; font-size: 0.9em; color: var(--text-secondary);">
                        Output: ${escapeHtml(output.substring(0, 100))}${output.length > 100 ? '...' : ''}
                    </p>
                </div>
                <button onclick="removePair(${index})" class="btn btn-outline btn-small" style="margin-left: 12px;">Remove</button>
            </div>
        </div>
    `;
}

// Batch Analysis: Remove Pair
function removePair(index) {
    batchPairs.splice(index, 1);
    renderPairs();
    updateBatchAnalysisButton();
    updateCostEstimate();
}

// Batch Analysis: Clear Pairs
if (clearPairsBtn) {
    clearPairsBtn.addEventListener('click', () => {
        if (confirm('Are you sure you want to clear all pairs?')) {
            batchPairs = [];
            renderPairs();
            updateBatchAnalysisButton();
            updateCostEstimate();
        }
    });
}

// Batch Analysis: Update Run Button State
function updateBatchAnalysisButton() {
    const btn = document.getElementById('run-batch-analysis-btn');
    if (btn) {
        // Check if we have prompt from input OR per-row CSV prompts OR can reconstruct from foci
        const hasPromptInput = batchPromptInput ? batchPromptInput.value.trim().length > 0 : false;
        const hasRowPrompts = batchPairs.length > 0 && batchPairs.every(
            p => typeof p.prompt === 'string' && p.prompt.length > 0
        );
        const canReconstructFromFoci = batchFoci.length > 0 && batchFoci.every(f => f.prompt_section && f.prompt_section.trim().length > 0);
        const hasPrompt = hasPromptInput || hasRowPrompts || canReconstructFromFoci;
        
        const shouldBeDisabled = batchPairs.length === 0 || batchFoci.length === 0 || !hasPrompt;
        
        // CRITICAL: Remove disabled attribute entirely - it blocks ALL click events
        btn.removeAttribute('disabled');
        
        // Style it to look disabled but keep it clickable
        if (shouldBeDisabled) {
            btn.classList.add('btn-disabled');
            btn.style.opacity = '0.6';
            btn.style.cursor = 'not-allowed';
            btn.setAttribute('aria-disabled', 'true');
        } else {
            btn.classList.remove('btn-disabled');
            btn.style.opacity = '1';
            btn.style.cursor = 'pointer';
            btn.removeAttribute('aria-disabled');
        }
        
        // The click handler will check state and show appropriate messages
    }
}

// Batch Analysis: Calculate and Display Cost Estimate
function updateCostEstimate() {
    if (!batchCostEstimate || !batchCostEstimateContent) return;
    
    const numPairs = batchPairs.length;
    const numFoci = window.FocalPromptExperiment
        ? window.FocalPromptExperiment.countPreviewAttributable(batchFoci)
        : batchFoci.filter(function (f) { return !f.is_dynamic; }).length;
    const cfg = window.FocalPromptExperiment ? window.FocalPromptExperiment.getState() : {
        temperature: 0.7, n_baseline: 10, n_ablated: 5
    };
    const nBaseline = cfg.n_baseline;
    const nAblated = cfg.n_ablated;
    const callsPerPair = window.FocalPromptExperiment
        ? window.FocalPromptExperiment.modelCallCount(nBaseline, nAblated, numFoci)
        : nBaseline + nAblated * numFoci;
    const model = 'gpt-4o-mini'; // Default model
    
    // Hide if no pairs or no foci
    if (numPairs === 0 || numFoci === 0) {
        batchCostEstimate.classList.add('hidden');
        return;
    }
    
    // Pricing per million tokens (matching backend)
    const PRICING = {
        'gpt-4o-mini': { input: 0.15 / 1_000_000, output: 0.60 / 1_000_000 },
        'gpt-4o': { input: 2.50 / 1_000_000, output: 10.00 / 1_000_000 },
        'gpt-4-turbo': { input: 10.00 / 1_000_000, output: 30.00 / 1_000_000 },
        'gpt-3.5-turbo': { input: 0.50 / 1_000_000, output: 1.50 / 1_000_000 },
        'embedding': 0.02 / 1_000_000
    };
    
    const modelPricing = PRICING[model] || PRICING['gpt-4o-mini'];
    
    // Token estimates per pair (conservative estimates)
    const promptTokens = 2500; // Full prompt
    const ablatedPromptTokens = 2000; // Ablated prompt (slightly shorter)
    const outputTokens = 200; // Typical output length

    const baselineInputTokensPerPair = nBaseline * promptTokens;
    const baselineOutputTokensPerPair = nBaseline * outputTokens;
    const ablatedInputTokensPerPair = nAblated * numFoci * ablatedPromptTokens;
    const ablatedOutputTokensPerPair = nAblated * numFoci * outputTokens;
    const totalInputTokensPerPair = baselineInputTokensPerPair + ablatedInputTokensPerPair;
    const totalOutputTokensPerPair = baselineOutputTokensPerPair + ablatedOutputTokensPerPair;
    const embeddingTokensPerPair = callsPerPair * outputTokens;
    const totalInputTokens = totalInputTokensPerPair * numPairs;
    const totalOutputTokens = totalOutputTokensPerPair * numPairs;
    const totalEmbeddingTokens = embeddingTokensPerPair * numPairs;
    
    // Calculate costs
    const chatInputCost = totalInputTokens * modelPricing.input;
    const chatOutputCost = totalOutputTokens * modelPricing.output;
    const embeddingCost = totalEmbeddingTokens * PRICING.embedding;
    const totalCost = chatInputCost + chatOutputCost + embeddingCost;
    const costPerPair = totalCost / numPairs;
    
    // Display estimate
    let html = '<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px;">';
    html += '<div><strong>Configuration:</strong><br>';
    html += `Pairs: ${numPairs.toLocaleString()}<br>`;
    html += `Foci: ${numFoci}<br>`;
    html += `Temperature: ${Number(cfg.temperature).toFixed(1)}<br>`;
    html += `Baseline samples: ${nBaseline} per pair<br>`;
    html += `Ablated samples: ${nAblated} per focus per pair<br>`;
    html += `Model calls: ${callsPerPair.toLocaleString()} per pair (${(callsPerPair * numPairs).toLocaleString()} total)<br>`;
    html += `Model: ${model}</div>`;
    html += '<div><strong>Estimated Tokens:</strong><br>';
    html += `Input: ${totalInputTokens.toLocaleString()}<br>`;
    html += `Output: ${totalOutputTokens.toLocaleString()}<br>`;
    html += `Embeddings: ${totalEmbeddingTokens.toLocaleString()}</div>`;
    html += '</div>';
    html += '<div style="padding-top: 12px; border-top: 2px solid #ffc107; font-size: 1.1em; font-weight: bold; color: #856404;">';
    html += `Estimated Total Cost: $${totalCost.toFixed(2)}`;
    html += ` <span style="font-size: 0.85em; font-weight: normal; color: #666;">($${costPerPair.toFixed(4)} per pair)</span>`;
    html += '</div>';
    html += '<p style="margin-top: 8px; font-size: 0.85em; color: #856404;">⚠️ This is an estimate. Actual costs may vary based on actual token usage.</p>';
    
    batchCostEstimateContent.innerHTML = html;
    batchCostEstimate.classList.remove('hidden');
}

// Batch Analysis: Update button state when prompt changes
if (batchPromptInput) {
    batchPromptInput.addEventListener('input', () => {
        updateBatchAnalysisButton();
    });
}

// Batch Analysis: Import Foci
if (batchImportFociBtn) {
    batchImportFociBtn.addEventListener('click', () => {
        if (foci.length === 0) {
            showErrorModal('No foci defined in Prompt Analysis tab. Please define foci there first.');
            return;
        }
        batchFoci = JSON.parse(JSON.stringify(foci)).map(f => ({
            ...f,
            is_dynamic: f.is_dynamic || false,
            dynamic_type: f.dynamic_type || null
        })); // Deep copy with dynamic properties
        updateManualInputFields();
        renderBatchFoci();
        updateBatchAnalysisButton();
        updateCostEstimate();
    });
}

// Batch Analysis: Auto-Detect Dynamic Foci
if (batchDetectDynamicFociBtn) {
    batchDetectDynamicFociBtn.addEventListener('click', async () => {
        const prompt = batchPromptInput ? batchPromptInput.value.trim() : '';
        if (!prompt) {
            showErrorModal('Please enter the prompt first.');
            return;
        }
        if (batchFoci.length === 0) {
            showErrorModal('Please detect or define foci first.');
            return;
        }
        if (batchPairs.length === 0) {
            showErrorModal('Please add at least one pair to detect dynamic patterns.');
            return;
        }
        
        showLoading('Analyzing prompt structure and input patterns to detect dynamic foci...');
        
        try {
            const response = await fetch('/api/detect-dynamic-foci', {
                method: 'POST',
                headers: getApiHeaders(),
                body: JSON.stringify(getApiBody({
                    prompt: prompt,
                    foci: batchFoci,
                    pairs: batchPairs
                })),
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to detect dynamic foci');
            }
            
            // Update foci with dynamic suggestions
            batchFoci = data.foci || batchFoci;
            updateManualInputFields();
            renderBatchFoci();
            updateBatchAnalysisButton();
            updateCostEstimate();
            
            // Show summary of suggestions
            const suggestions = data.suggestions || [];
            const dynamicCount = suggestions.filter(s => s.should_be_dynamic && s.confidence > 0.6).length;
            if (dynamicCount > 0) {
                alert(`✓ Detected ${dynamicCount} dynamic focus/foci based on prompt structure and input patterns. Review the foci to see which ones were marked as dynamic.`);
            } else {
                alert('No dynamic foci detected. All foci appear to be static instructions.');
            }
            
        } catch (error) {
            showError('Error detecting dynamic foci: ' + error.message);
            console.error('Detect dynamic foci error:', error);
        } finally {
            hideLoading();
        }
    });
}

// Batch Analysis: Auto-Detect Foci
if (batchDetectFociBtn) {
    batchDetectFociBtn.addEventListener('click', async () => {
        const prompt = batchPromptInput ? batchPromptInput.value.trim() : '';
        if (!prompt) {
            showErrorModal('Please enter the prompt first.');
            return;
        }
        
        showLoading('Detecting foci from first prompt...');
        
        try {
            const response = await fetch('/api/detect-foci', {
                method: 'POST',
                headers: getApiHeaders(),
                body: JSON.stringify(getApiBody({ prompt: prompt })),
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to detect foci');
            }
            
            batchFoci = (data.foci || []).map(f => ({
                ...f,
                is_dynamic: f.is_dynamic || false,
                dynamic_type: f.dynamic_type || null
            }));
            window.rejectedFocusProposals = data.rejected_proposals || [];
            if (window.rejectedFocusProposals.length) {
                console.info(
                    'Omitted',
                    window.rejectedFocusProposals.length,
                    'auto-detected proposal(s) lacking source provenance',
                    window.rejectedFocusProposals
                );
            }
            updateManualInputFields();
            renderBatchFoci();
            updateBatchAnalysisButton();
            updateCostEstimate();
            
        } catch (error) {
            showError('Error detecting foci: ' + error.message);
            console.error('Detect foci error:', error);
        } finally {
            hideLoading();
        }
    });
}

// Batch Analysis: Render Foci
function renderBatchFoci() {
    if (!batchFociContainer) return;
    
    if (batchFoci.length === 0) {
        batchFociContainer.innerHTML = '<p class="empty-state">No foci defined yet. Click "Auto-Detect from First Prompt" or "Import from Prompt Analysis" to get started.</p>';
        updateBatchAnalysisButton();
        if (window.FocalPromptExperiment) window.FocalPromptExperiment.refreshAll();
        return;
    }
    
    let html = '';
    batchFoci.forEach((focus, index) => {
        html += `
            <div class="focus-item" style="margin-bottom: 12px; padding: 12px; background: #f8fafc; border-radius: 6px; border: 1px solid var(--border-color);">
                <div style="display: flex; justify-content: space-between; align-items: start;">
                    <div style="flex: 1;">
                        <strong style="color: var(--primary-color);">${escapeHtml(focus.focus)}</strong>
                        <p style="margin: 4px 0; font-size: 0.9em; color: var(--text-secondary);">${escapeHtml(focus.prompt_section.substring(0, 150))}${focus.prompt_section.length > 150 ? '...' : ''}</p>
                    </div>
                    <button onclick="removeBatchFocus(${index})" class="btn btn-outline btn-small" style="margin-left: 12px;">Remove</button>
                </div>
            </div>
        `;
    });
    
    batchFociContainer.innerHTML = html;
    updateBatchAnalysisButton();
    if (window.FocalPromptExperiment) window.FocalPromptExperiment.refreshAll();
}

// Batch Analysis: Remove Focus
function removeBatchFocus(index) {
    batchFoci.splice(index, 1);
    renderBatchFoci();
    updateBatchAnalysisButton();
    updateCostEstimate();
}

// Batch Analysis: Clear Foci
if (batchClearFociBtn) {
    batchClearFociBtn.addEventListener('click', () => {
        if (confirm('Are you sure you want to clear all foci?')) {
            batchFoci = [];
            renderBatchFoci();
            updateManualInputFields();
            updateBatchAnalysisButton();
            updateCostEstimate();
        }
    });
}

// Batch Analysis: Run Analysis
async function handleRunBatchAnalysis(e) {
    if (e && e.preventDefault) e.preventDefault();
    if (e && e.stopPropagation) e.stopPropagation();
    
    console.log('=== handleRunBatchAnalysis CALLED ===');
    console.log('Event:', e);
    
    // Get the button (prefer currentTarget which is the element the handler is attached to)
    const btn = e?.currentTarget || document.getElementById('run-batch-analysis-btn');
    
    if (!btn) {
        console.error('Button not found');
        return;
    }
    
    console.log('Button found in handler:', btn);
    console.log('Button disabled attribute:', btn.disabled);
    
    // Check state directly - can use prompt input OR reconstruct from foci
    const hasPromptInput = batchPromptInput ? batchPromptInput.value.trim().length > 0 : false;
    const canReconstructFromFoci = batchFoci.length > 0 && batchFoci.every(f => f.prompt_section && f.prompt_section.trim().length > 0);
    const hasPrompt = hasPromptInput || canReconstructFromFoci;
    const canRun = batchPairs.length > 0 && batchFoci.length > 0 && hasPrompt;
    
    console.log('State check - Pairs:', batchPairs.length, 'Foci:', batchFoci.length);
    console.log('Has prompt input?', hasPromptInput, 'Can reconstruct from foci?', canReconstructFromFoci);
    console.log('Can run?', canRun);
    
    if (!canRun) {
        console.warn('Cannot run analysis - missing requirements');
        let promptMsg = 'No prompt';
        if (hasPromptInput) {
            promptMsg = 'Prompt input: ' + (batchPromptInput.value.trim().length) + ' chars';
        } else if (canReconstructFromFoci) {
            promptMsg = 'Can reconstruct from ' + batchFoci.length + ' foci';
        }
        showErrorModal('Please ensure you have:\n- At least one pair (you have ' + batchPairs.length + ')\n- At least one focus (you have ' + batchFoci.length + ')\n- A prompt: ' + promptMsg);
        return;
    }

    var cfg = window.FocalPromptExperiment ? window.FocalPromptExperiment.getState() : {
        temperature: 0.7, n_baseline: 10, n_ablated: 5
    };
    if (window.FocalPromptExperiment) {
        var tempErr = window.FocalPromptExperiment.temperatureRejection(cfg.temperature);
        if (tempErr) {
            showErrorModal(tempErr);
            return;
        }
    }
    
    console.log('All checks passed - proceeding with batch analysis');
    
    console.log('Run batch analysis button clicked');
    console.log('Pairs:', batchPairs.length, 'Foci:', batchFoci.length);
    
    if (batchPairs.length === 0) {
        showErrorModal('Please add at least one pair first.');
        return;
    }
    
    if (batchFoci.length === 0) {
        alert('Please define foci first.');
        return;
    }
    
    // Get prompt - either from input or reconstruct from foci
    let prompt = batchPromptInput ? batchPromptInput.value.trim() : '';
    
    if (!prompt && batchFoci.length > 0) {
        // Reconstruct prompt from foci (join all prompt_section values)
        prompt = batchFoci.map(f => f.prompt_section || '').filter(s => s.trim().length > 0).join('\n\n');
        console.log('Reconstructed prompt from foci, length:', prompt.length);
    }
    
    if (!prompt) {
        showErrorModal('Please enter the prompt that was used for all pairs, or ensure foci contain prompt sections.');
        return;
    }
    
    console.log('Starting batch analysis with', batchPairs.length, 'pairs and', batchFoci.length, 'foci');
    console.log('Using prompt (length:', prompt.length, ')');
    
    // Add prompt to all pairs (ensure new structure)
    const pairsWithPrompt = batchPairs.map(pair => {
        // Ensure pair is in new structure
        const inputs = pair.inputs || {
            chat_content: pair.chat_content || '',
            rag_context: pair.rag_context || '',
            tool_results: pair.tool_results || ''
        };
        // Prefer per-row CSV prompt when present (exact text; do not trim —
        // ablation spans depend on byte-for-text fidelity). Else shared prompt
        // (typed or reconstructed from foci above).
        const rowPrompt = (typeof pair.prompt === 'string') ? pair.prompt : null;
        return {
            inputs: inputs,
            output: pair.output,
            prompt: (rowPrompt !== null && rowPrompt.length > 0) ? rowPrompt : prompt
        };
    });

    if (pairsWithPrompt.some(p => !(p.prompt && String(p.prompt).length > 0))) {
        showErrorModal(
            'Every pair needs a non-empty prompt. Enter the shared prompt above, include a per-row prompt column in the CSV, or ensure foci cover the source text.'
        );
        return;
    }    
    // Client-paced batch: one short serverless call per sample (same path as
    // single ablation). Avoids the hosted SSE timeout that left users with
    // zero pair results.
    const sessionId = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
    const totalPairs = pairsWithPrompt.length;
    const pairResults = [];
    let failedPairs = 0;

    function setBatchProgress(message) {
        if (batchProgressText) batchProgressText.textContent = message;
        showLoading(message);
    }

    function scoreToBatchPairResult(scored, pair, pairIndex) {
        const influenceScores = {};
        (scored.influence_scores || []).forEach(function (item) {
            const name = item && (item.focus || item.focus_name);
            if (!name) return;
            influenceScores[name] = Object.assign({}, item);
        });
        const tokens = scored.tokens || {};
        const cost = scored.cost_breakdown || {};
        if (cost.chat_completions) {
            tokens.input = tokens.input || cost.chat_completions.input_tokens || 0;
            tokens.output = tokens.output || cost.chat_completions.output_tokens || 0;
        }
        if (cost.embeddings) {
            tokens.embedding = tokens.embedding || cost.embeddings.tokens || 0;
        }
        return {
            success: true,
            pair_index: pairIndex,
            pair_data: pair,
            influence_scores: influenceScores,
            ablation_results: scored.ablation_results || [],
            foci_list: scored.foci_list || batchFoci,
            baseline_outputs: scored.baseline_outputs || [],
            n_baseline: scored.n_baseline,
            n_ablated: scored.n_ablated,
            n_permutations: scored.n_permutations,
            alpha: scored.alpha,
            temperature: scored.temperature || cfg.temperature,
            test_type: scored.test_type,
            power_warning: scored.power_warning,
            significance_method: scored.significance_method || 'permutation_bh',
            summary: scored.summary || {},
            model: scored.model,
            provider: scored.provider,
            tokens: tokens,
            cost_breakdown: scored.cost_breakdown || null
        };
    }

    if (batchProgress) {
        batchProgress.classList.remove('hidden');
    }
    setBatchProgress('Starting client-paced batch analysis for ' + totalPairs + ' pair(s)…');

    try {
        for (let pairIndex = 0; pairIndex < totalPairs; pairIndex++) {
            const pair = pairsWithPrompt[pairIndex];
            const pairLabel = 'Pair ' + (pairIndex + 1) + '/' + totalPairs;
            try {
                setBatchProgress(pairLabel + ': sampling…');
                const scored = await runPacedAblation(
                    pair.prompt,
                    batchFoci,
                    cfg,
                    function (msg) {
                        setBatchProgress(pairLabel + ': ' + msg);
                    }
                );
                pairResults.push(scoreToBatchPairResult(scored, pair, pairIndex));
                setBatchProgress(
                    pairLabel + ' complete (' + pairResults.length + ' succeeded' +
                    (failedPairs ? ', ' + failedPairs + ' failed' : '') + ').'
                );
            } catch (pairErr) {
                failedPairs += 1;
                console.error('Batch pair failed', pairIndex, pairErr);
                pairResults.push({
                    success: false,
                    pair_index: pairIndex,
                    pair_data: pair,
                    error: (pairErr && pairErr.message) ? pairErr.message : String(pairErr)
                });
                setBatchProgress(
                    pairLabel + ' failed: ' +
                    ((pairErr && pairErr.message) ? pairErr.message : 'unknown error')
                );
            }
        }

        let statistics = {};
        let focusDistributionStatistics = {};
        const successful = pairResults.filter(function (r) { return r && r.success !== false; });
        if (successful.length) {
            setBatchProgress('Aggregating statistics across ' + successful.length + ' pair(s)…');
            try {
                const aggResp = await fetch('/api/batch-aggregate', {
                    method: 'POST',
                    headers: getApiHeaders(),
                    body: JSON.stringify(getApiBody({ pair_results: pairResults }))
                });
                const aggData = await aggResp.json();
                if (!aggResp.ok) {
                    throw new Error(aggData.error || 'Failed to aggregate batch statistics');
                }
                statistics = aggData.statistics || {};
                focusDistributionStatistics = aggData.focus_distribution_statistics || {};
            } catch (aggErr) {
                console.warn('Batch aggregate failed; showing pair results only.', aggErr);
            }
        }

        const completeData = {
            results: pairResults,
            pair_results: pairResults,
            statistics: statistics,
            focus_distribution_statistics: focusDistributionStatistics,
            cost_breakdown: {},
            session_id: sessionId
        };
        window.batchResultsData = completeData;
        renderBatchResults(completeData);
        if (exportResultsBtn) exportResultsBtn.disabled = false;
        if (exportResultsJsonBtn) exportResultsJsonBtn.disabled = false;
        if (batchResults && batchResults.scrollIntoView) {
            batchResults.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }

        if (!successful.length) {
            showError(
                'Batch analysis finished but every pair failed. ' +
                (pairResults[0] && pairResults[0].error
                    ? ('First error: ' + pairResults[0].error)
                    : 'Check the console for details.')
            );
        } else if (failedPairs) {
            showError(
                'Batch analysis finished with ' + successful.length +
                ' successful pair(s) and ' + failedPairs + ' failure(s).'
            );
        } else if (batchProgressText) {
            batchProgressText.textContent =
                'Analysis complete! ' + successful.length + ' pair(s) processed.';
        }
    } catch (error) {
        console.error('Batch analysis error:', error);
        if (pairResults.length) {
            window.batchResultsData = {
                results: pairResults,
                pair_results: pairResults,
                statistics: {},
                focus_distribution_statistics: {},
                cost_breakdown: {}
            };
            renderBatchResults(window.batchResultsData);
            if (exportResultsBtn) exportResultsBtn.disabled = false;
            if (exportResultsJsonBtn) exportResultsJsonBtn.disabled = false;
            showError(
                'Batch analysis interrupted: ' + error.message +
                '\n\nShowing ' + pairResults.length + ' completed pair(s).'
            );
        } else {
            showError('Error running batch analysis: ' + error.message);
        }
    } finally {
        hideLoading();
    }
}


// Attach handler using event delegation on parent container
function attachBatchAnalysisHandler() {
    // Try multiple selectors to find the button's parent
    const buttonGroup = document.querySelector('#batch-analysis-tab .button-group') ||
                        document.querySelector('#batch-analysis-tab .card-header .button-group') ||
                        document.querySelector('#run-batch-analysis-btn')?.parentElement;
    
    const btn = document.getElementById('run-batch-analysis-btn');
    
    if (!buttonGroup) {
        console.warn('Button group not found for batch analysis');
    }
    
    if (!btn) {
        console.warn('Button not found');
        return null;
    }
    
    console.log('Button found:', btn);
    console.log('Button disabled?', btn.disabled);
    console.log('Button group found:', buttonGroup);
    
    // Create handler function with extensive logging
    const newHandler = (e) => {
        console.log('=== CLICK EVENT DETECTED ===');
        console.log('Target:', e.target);
        console.log('Current target:', e.currentTarget);
        
        // Check if click was on button or inside it
        const clickedBtn = e.target.closest('#run-batch-analysis-btn') || 
                          (e.target.id === 'run-batch-analysis-btn' ? e.target : null);
        
        if (clickedBtn) {
            console.log('Button clicked via delegation!');
            console.log('Button disabled?', clickedBtn.disabled);
            
            if (clickedBtn.disabled) {
                console.warn('Button is disabled - showing alert');
                showErrorModal('Please ensure you have:\n- At least one pair\n- At least one focus\n- A prompt entered');
                return;
            }
            
            console.log('Button is enabled - calling handleRunBatchAnalysis');
            // Create a synthetic event with currentTarget set to the button
            const syntheticEvent = {
                ...e,
                currentTarget: clickedBtn,
                target: e.target,
                preventDefault: () => e.preventDefault(),
                stopPropagation: () => e.stopPropagation()
            };
            handleRunBatchAnalysis(syntheticEvent);
        } else {
            console.log('Click was not on the batch analysis button');
        }
    };
    
    // Remove old handler if it exists
    if (buttonGroup && buttonGroup._batchHandler) {
        buttonGroup.removeEventListener('click', buttonGroup._batchHandler);
        console.log('Removed old batch handler');
    }
    
    // Attach to button group if found
    if (buttonGroup) {
        buttonGroup.addEventListener('click', newHandler, true); // Use capture phase
        buttonGroup._batchHandler = newHandler;
        console.log('Handler attached to button group via delegation');
    }
    
    // ALSO attach at document level to catch ALL clicks on the button (bypasses disabled state)
    const documentClickHandler = (e) => {
        // Check if click was on our button
        const clickedBtn = e.target.closest('#run-batch-analysis-btn');
        if (!clickedBtn || clickedBtn !== btn) {
            return; // Not our button
        }
        
        console.log('=== DOCUMENT-LEVEL CLICK DETECTED ===');
        console.log('Button disabled?', btn.disabled);
        console.log('Pairs:', batchPairs.length, 'Foci:', batchFoci.length);
        console.log('Prompt:', batchPromptInput ? batchPromptInput.value.trim().length : 'no input element');
        
        // ALWAYS prevent default and stop propagation
        e.preventDefault();
        e.stopPropagation();
        
        // Check state directly - can use prompt input OR reconstruct from foci
        const hasPromptInput = batchPromptInput ? batchPromptInput.value.trim().length > 0 : false;
        const canReconstructFromFoci = batchFoci.length > 0 && batchFoci.every(f => f.prompt_section && f.prompt_section.trim().length > 0);
        const hasPrompt = hasPromptInput || canReconstructFromFoci;
        const shouldBeDisabled = batchPairs.length === 0 || batchFoci.length === 0 || !hasPrompt;
        
        console.log('Should be disabled?', shouldBeDisabled);
        console.log('Has prompt input?', hasPromptInput, 'Can reconstruct?', canReconstructFromFoci);
        
        if (shouldBeDisabled) {
            console.warn('Cannot run - missing requirements');
            let promptMsg = 'No prompt';
            if (hasPromptInput) {
                promptMsg = 'Prompt input: ' + (batchPromptInput.value.trim().length) + ' chars';
            } else if (canReconstructFromFoci) {
                promptMsg = 'Can reconstruct from ' + batchFoci.length + ' foci';
            }
            showErrorModal('Please ensure you have:\n- At least one pair (you have ' + batchPairs.length + ')\n- At least one focus (you have ' + batchFoci.length + ')\n- A prompt: ' + promptMsg);
            return;
        }
        
        console.log('All requirements met - calling handleRunBatchAnalysis');
        // Call handler directly with proper event object
        handleRunBatchAnalysis({
            type: 'click',
            currentTarget: btn,
            target: btn,
            preventDefault: () => {},
            stopPropagation: () => {},
            bubbles: true,
            cancelable: true
        });
    };
    
    // Remove old document handler if it exists
    if (document._batchClickHandler) {
        document.removeEventListener('click', document._batchClickHandler, true);
    }
    
    // Attach at document level with capture phase (catches events before they reach the button)
    document.addEventListener('click', documentClickHandler, true);
    document._batchClickHandler = documentClickHandler;
    console.log('Document-level click handler attached (capture phase)');
    
    return buttonGroup || btn;
}

// Try to attach immediately and when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        attachBatchAnalysisHandler();
        updateBatchAnalysisButton();
    });
} else {
    attachBatchAnalysisHandler();
    updateBatchAnalysisButton();
}

// Also ensure batch-progress starts hidden
window.addEventListener('DOMContentLoaded', () => {
    const batchProgress = document.getElementById('batch-progress');
    if (batchProgress && !batchProgress.classList.contains('hidden')) {
        batchProgress.classList.add('hidden');
        console.log('Ensured batch-progress is hidden on load');
    }
});

// Batch Analysis: Load Checkpoint Functions
async function listCheckpoints(checkpointType = 'batch_analysis') {
    try {
        const response = await fetch(`/api/list-checkpoints?type=${encodeURIComponent(checkpointType)}`);
        if (!response.ok) {
            throw new Error('Failed to list checkpoints');
        }
        const data = await response.json();
        return data.checkpoints || [];
    } catch (error) {
        console.error('Error listing checkpoints:', error);
        showError('Failed to list checkpoints: ' + error.message);
        return [];
    }
}

async function loadCheckpointData(sessionId, checkpointType = 'batch_analysis') {
    try {
        showLoading('Loading checkpoint...');
        const response = await fetch(`/api/get-checkpoint?session_id=${encodeURIComponent(sessionId)}&type=${encodeURIComponent(checkpointType)}`);
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Failed to load checkpoint');
        }
        const checkpoint = await response.json();
        
        if (checkpointType === 'single_assessment') {
            // Load single assessment results
            const resultData = checkpoint.result_data || checkpoint;
            
            // Restore prompt and output if available
            if (resultData.prompt && promptInput) {
                promptInput.value = resultData.prompt;
            }
            if (resultData.output && outputInput) {
                outputInput.value = resultData.output;
            }
            
            // Render the assessment results
            renderAssessment(resultData);
            
            hideLoading();
            alert(`Assessment checkpoint loaded successfully!`);
        } else if (checkpointType === 'single_ablation') {
            // Load single ablation analysis results
            const resultData = checkpoint.result_data || checkpoint;
            
            // Store globally for optimization analysis
            window.singleAblationResults = resultData;
            
            // Render the results
            renderAblationResults(resultData);
            
            hideLoading();
            alert(`Ablation analysis checkpoint loaded successfully!`);
        } else if (checkpointType === 'batch_agents') {
            // Load batch agent building results
            batchAgentResultsData = checkpoint.results || [];
            window.batchAgentCostBreakdown = checkpoint.cost_breakdown || null;
            
            // Render the results
            renderBatchAgentResults(batchAgentResultsData, window.batchAgentCostBreakdown);
            
            // Show reporting section
            if (batchAgentReportingSection) {
                batchAgentReportingSection.style.display = 'block';
            }
            if (promptOptimizationSection) {
                promptOptimizationSection.style.display = 'block';
            }
            updateBatchAgentReporting();
            
            // Enable export button
            if (exportBatchAgentResultsBtn) {
                exportBatchAgentResultsBtn.disabled = false;
            }
            
            hideLoading();
            alert(`Batch agent checkpoint loaded successfully! ${batchAgentResultsData.length} result(s) loaded.`);
        } else {
            // Load batch analysis results
            const checkpointData = {
                results: checkpoint.pair_results || [],
                pair_results: checkpoint.pair_results || [],
                statistics: checkpoint.statistics || {},
                focus_distribution_statistics: checkpoint.focus_distribution_statistics || {},
                cost_breakdown: checkpoint.cost_breakdown || {}
            };
            
            // Store globally for batch agent building
            window.batchResultsData = checkpointData;
            
            renderBatchResults(checkpointData);
            
            if (exportResultsBtn) exportResultsBtn.disabled = false;
            if (exportResultsJsonBtn) exportResultsJsonBtn.disabled = false;
            
            hideLoading();
            alert(`Checkpoint loaded successfully! ${checkpoint.pair_results?.length || 0} pairs loaded.`);
        }
        
        // Hide checkpoint list after loading
        if (checkpointList) checkpointList.classList.add('hidden');
        
        return true;
    } catch (error) {
        console.error('Error loading checkpoint:', error);
        hideLoading();
        showError('Failed to load checkpoint: ' + error.message);
        return false;
    }
}

// Make it globally accessible for onclick handlers
window.loadCheckpointData = loadCheckpointData;

async function displayCheckpointList(checkpointType = 'batch_analysis') {
    // Always show loading first
    showLoading(`Loading ${checkpointType === 'batch_agents' ? 'agent' : checkpointType === 'single_ablation' ? 'ablation' : checkpointType === 'single_assessment' ? 'assessment' : 'batch analysis'} checkpoints...`);
    
    const checkpoints = await listCheckpoints(checkpointType);
    hideLoading();
    
    if (checkpoints.length === 0) {
        const typeLabel = checkpointType === 'batch_agents' ? 'agent building' : checkpointType === 'single_ablation' ? 'ablation analysis' : checkpointType === 'single_assessment' ? 'assessment' : 'batch analysis';
        showErrorModal(`No ${typeLabel} checkpoints found. Previous runs before checkpoint saving was implemented were not saved. Future runs will be automatically saved.`);
        return;
    }
    
    // Create a modal overlay for checkpoint selection
    const modal = document.createElement('div');
    modal.style.cssText = 'position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 10000; display: flex; align-items: center; justify-content: center;';
    
    const modalContent = document.createElement('div');
    modalContent.style.cssText = 'background: white; padding: 24px; border-radius: 8px; max-width: 800px; max-height: 80vh; overflow-y: auto; box-shadow: 0 4px 6px rgba(0,0,0,0.1);';
    
    const typeLabels = {
        'batch_analysis': 'Batch Analysis',
        'batch_agents': 'Batch Agent Building',
        'single_ablation': 'Single Ablation Analysis',
        'single_assessment': 'Single Assessment'
    };
    const typeLabel = typeLabels[checkpointType] || 'Checkpoints';
    
    let html = `<h3 style="margin-bottom: 16px;">${typeLabel} Checkpoints</h3>`;
    html += '<table style="width: 100%; border-collapse: collapse; margin-bottom: 16px;">';
    html += '<thead><tr style="background: #f8fafc; border-bottom: 2px solid var(--border-color);">';
    html += '<th style="padding: 8px; text-align: left;">Session ID</th>';
    html += '<th style="padding: 8px; text-align: left;">Date</th>';
    if (checkpointType === 'single_ablation' || checkpointType === 'single_assessment') {
        html += '<th style="padding: 8px; text-align: right;">Foci</th>';
        if (checkpointType === 'single_ablation') {
            html += '<th style="padding: 8px; text-align: left;">Model</th>';
        } else {
            html += '<th style="padding: 8px; text-align: left;">Has Output</th>';
        }
    } else {
        html += '<th style="padding: 8px; text-align: right;">Completed</th>';
        html += '<th style="padding: 8px; text-align: right;">Total</th>';
    }
    html += '<th style="padding: 8px; text-align: center;">Action</th>';
    html += '</tr></thead><tbody>';
    
    checkpoints.forEach(cp => {
        const date = cp.timestamp ? new Date(cp.timestamp).toLocaleString() : 'Unknown';
        const isCorrupted = cp.corrupted || false;
        html += '<tr style="border-bottom: 1px solid #e5e7eb;">';
        html += `<td style="padding: 8px; font-family: monospace; font-size: 0.85em;">${escapeHtml(cp.session_id.substring(0, 20))}${cp.session_id.length > 20 ? '...' : ''}</td>`;
        html += `<td style="padding: 8px; font-size: 0.9em;">${escapeHtml(date)}</td>`;
        
        if (checkpointType === 'single_ablation' || checkpointType === 'single_assessment') {
            html += `<td style="padding: 8px; text-align: right;">${cp.num_foci || '?'}</td>`;
            if (checkpointType === 'single_ablation') {
                html += `<td style="padding: 8px;">${escapeHtml(cp.model || 'unknown')}</td>`;
            } else {
                html += `<td style="padding: 8px;">${cp.has_output ? '✅' : '❌'}</td>`;
            }
        } else {
            html += `<td style="padding: 8px; text-align: right;">${cp.completed || 0}</td>`;
            html += `<td style="padding: 8px; text-align: right;">${cp.total_pairs || 0}</td>`;
        }
        
        if (isCorrupted) {
            html += `<td style="padding: 8px; text-align: center; color: #ef4444;">⚠️ Corrupted</td>`;
        } else {
            html += `<td style="padding: 8px; text-align: center;"><button onclick="window.selectCheckpoint('${cp.session_id}', '${checkpointType}')" class="btn btn-primary btn-small">Load</button></td>`;
        }
        html += '</tr>';
    });
    
    html += '</tbody></table>';
    html += '<div style="text-align: right;"><button onclick="window.closeCheckpointModal()" class="btn btn-outline">Close</button></div>';
    
    modalContent.innerHTML = html;
    modal.appendChild(modalContent);
    document.body.appendChild(modal);
    
    // Store modal reference and checkpoint type for cleanup
    window.currentCheckpointModal = modal;
    window.currentCheckpointType = checkpointType;
    
    // Close modal function
    window.closeCheckpointModal = function() {
        if (window.currentCheckpointModal) {
            document.body.removeChild(window.currentCheckpointModal);
            window.currentCheckpointModal = null;
        }
    };
    
    // Select checkpoint function
    window.selectCheckpoint = async function(sessionId, type) {
        window.closeCheckpointModal();
        await loadCheckpointData(sessionId, type);
    };
    
    // Close on background click
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            window.closeCheckpointModal();
        }
    });
    
    // Also try to use the existing checkpoint list if it exists and we're in the batch analysis tab
    const listContainer = checkpointList || document.getElementById('checkpoint-list');
    const listContent = checkpointListContent || document.getElementById('checkpoint-list-content');
    
    if (listContainer && listContent && checkpointType === 'batch_analysis') {
        // Update the existing list as well (for batch analysis tab)
        const tableHtml = html.replace(/<h3.*?<\/h3>/, '').replace(/<div style="text-align: right;">.*?<\/div>/, '');
        listContent.innerHTML = tableHtml;
        listContainer.classList.remove('hidden');
    }
}

// Batch Analysis: Render Results
function renderBatchResults(data) {
    if (!batchResults) return;
    
    let html = '<h3 style="margin-bottom: 16px;">Batch Analysis Results</h3>';
    const pairResults = data.pair_results || data.results || [];
    if (window.FocalPromptResults) {
        html += window.FocalPromptResults.renderDefinition();
        const firstOk = pairResults.find(function (p) {
            return p && p.success !== false;
        });
        const headerSource = firstOk || data;
        if (window.FocalPromptResults.renderRunHeader) {
            html += window.FocalPromptResults.renderRunHeader(headerSource);
        }
        const warned = pairResults.find(function (p) { return p && p.power_warning; });
        if (warned) {
            html += window.FocalPromptResults.renderPowerBannerHtml(warned);
        }
        const first = pairResults.find(function (p) {
            return p && p.success !== false && (p.ablation_results || p.influence_scores);
        });
        if (first) {
            const records = window.FocalPromptResults.collectFocusRecords(first);
            const excluded = records.filter(function (r) {
                return window.FocalPromptResults.excludedExplanation(r);
            });
            if (excluded.length) {
                html += '<div class="focus-verdict-list">';
                excluded.forEach(function (rec) {
                    html += window.FocalPromptResults.renderFocusCard(rec, first.alpha);
                });
                html += '</div>';
            }
        }
        html += window.FocalPromptResults.renderMethodsPanel();
        if (pairResults.length) {
            html += '<div class="batch-pair-verdicts" style="margin: 16px 0 24px 0;">';
            html += '<h4>Per-pair sensitivity</h4>';
            pairResults.forEach(function (pair, i) {
                if (!pair || pair.success === false) {
                    html += '<details class="batch-pair-results"><summary>Pair ' + (i + 1) + ' — not tested</summary>';
                    html += '<p>' + escapeHtml(pair && pair.error ? pair.error : 'This pair did not complete.') + '</p></details>';
                    return;
                }
                html += '<details class="batch-pair-results"><summary>Pair ' + (i + 1) + '</summary>';
                if (pair.power_warning) {
                    html += window.FocalPromptResults.renderPowerBannerHtml(pair);
                }
                const recs = window.FocalPromptResults.collectFocusRecords(pair);
                html += '<div class="focus-verdict-list">';
                recs.forEach(function (rec) {
                    html += window.FocalPromptResults.renderFocusCard(rec, pair.alpha);
                });
                html += '</div></details>';
            });
            html += '</div>';
        }
    }
    
    const fdStats = data.focus_distribution_statistics || {};
    const fdKeys = Object.keys(fdStats);
    if (fdKeys.length > 0) {
        html += '<div style="margin-bottom: 28px;">';
        html += '<h4 style="margin-bottom: 8px;">1. Focus distribution (LLM assessment)</h4>';
        html += '<p style="margin: 0 0 12px 0; font-size: 0.9em; color: var(--text-secondary); max-width: 900px;">';
        html += 'Per pair, the same scoring step as <strong>Assess Focus Distribution</strong> in the main tab: ';
        html += 'the model assigns points (total 100 per pair) to each focus for how much attention the ';
        html += 'output gives them. If a pair includes a saved <strong>output</strong>, that text is assessed; ';
        html += 'otherwise the freshly generated baseline for that pair is used. Below are averages across pairs.';
        html += '</p>';
        html += '<table class="batch-stats-table" style="width: 100%; border-collapse: collapse;">';
        html += '<thead><tr style="background: #eef2ff; border-bottom: 2px solid var(--border-color);">';
        html += '<th style="padding: 12px; text-align: left;">Focus</th>';
        html += '<th style="padding: 12px; text-align: right;">Mean points</th>';
        html += '<th style="padding: 12px; text-align: right;">Variance</th>';
        html += '<th style="padding: 12px; text-align: right;">Std Dev</th>';
        html += '<th style="padding: 12px; text-align: right;">Min</th>';
        html += '<th style="padding: 12px; text-align: right;">Max</th>';
        html += '<th style="padding: 12px; text-align: right;">Pairs</th>';
        html += '</tr></thead><tbody>';
        const meanVarFd = Math.max(...fdKeys.map(k => fdStats[k].variance || 0), 0);
        fdKeys.forEach(focusName => {
            const st = fdStats[focusName];
            const variance = st.variance || 0;
            const varianceColor = variance > meanVarFd * 0.7 ? '#ef4444' : variance > meanVarFd * 0.4 ? '#f59e0b' : '#10b981';
            html += `<tr style="border-bottom: 1px solid var(--border-color);">`;
            html += `<td style="padding: 12px;"><strong>${escapeHtml(focusName)}</strong></td>`;
            html += `<td style="padding: 12px; text-align: right;">${(st.mean || 0).toFixed(2)}</td>`;
            html += `<td style="padding: 12px; text-align: right; color: ${varianceColor};">${(variance).toFixed(4)}</td>`;
            html += `<td style="padding: 12px; text-align: right;">${(st.std_dev || 0).toFixed(2)}</td>`;
            html += `<td style="padding: 12px; text-align: right;">${(st.min || 0).toFixed(2)}</td>`;
            html += `<td style="padding: 12px; text-align: right;">${(st.max || 0).toFixed(2)}</td>`;
            html += `<td style="padding: 12px; text-align: right;">${st.n_pairs != null ? st.n_pairs : '—'}</td>`;
            html += `</tr>`;
        });
        html += '</tbody></table></div>';
    }
    
    // Statistics Table — primary metric is normalized share (same idea as single-run ablation)
    html += '<div style="margin-bottom: 24px;">';
    html += '<h4 style="margin-bottom: 8px;">2. Descriptive T_obs shares across pairs</h4>';
    html += '<p style="margin: 0 0 12px 0; font-size: 0.9em; color: var(--text-secondary); max-width: 900px;">';
    html += 'These percentages renormalise the observed centroid distance (T_obs) within each pair so shares sum to 100%. ';
    html += 'They are a descriptive breakdown of measured shift, not a test and not an importance ranking. ';
    html += 'Use the per-pair verdicts above for significance.';
    html += '</p>';
    html += '<table class="batch-stats-table" style="width: 100%; border-collapse: collapse;">';
    html += '<thead><tr style="background: #f8fafc; border-bottom: 2px solid var(--border-color);">';
    html += '<th style="padding: 12px; text-align: left;">Focus</th>';
    html += '<th style="padding: 12px; text-align: right;" title="Average share of per-pair ablation effect">Mean share</th>';
    html += '<th style="padding: 12px; text-align: right;">Variance</th>';
    html += '<th style="padding: 12px; text-align: right;">Std Dev</th>';
    html += '<th style="padding: 12px; text-align: right;">Min</th>';
    html += '<th style="padding: 12px; text-align: right;">Max</th>';
    html += '</tr></thead><tbody>';
    
    // Regular foci
    const stats = data.statistics || {};
    Object.keys(stats).forEach(focusName => {
        if (focusName === 'chat_content' || focusName === 'noise') return;
        
        const stat = stats[focusName];
        const variance = stat.variance || 0;
        const meanVar = Math.max(...Object.values(stats).filter(s => s.variance).map(s => s.variance || 0));
        const varianceColor = variance > meanVar * 0.7 ? '#ef4444' : variance > meanVar * 0.4 ? '#f59e0b' : '#10b981';
        
        html += `<tr style="border-bottom: 1px solid var(--border-color);">`;
        html += `<td style="padding: 12px;"><strong>${escapeHtml(focusName)}</strong></td>`;
        html += `<td style="padding: 12px; text-align: right;">${Number(stat.mean).toFixed(2)}%</td>`;
        html += `<td style="padding: 12px; text-align: right; color: ${varianceColor};">${Number(stat.variance).toFixed(4)}</td>`;
        html += `<td style="padding: 12px; text-align: right;">${Number(stat.std_dev).toFixed(2)}%</td>`;
        html += `<td style="padding: 12px; text-align: right;">${Number(stat.min).toFixed(2)}%</td>`;
        html += `<td style="padding: 12px; text-align: right;">${Number(stat.max).toFixed(2)}%</td>`;
        html += `</tr>`;
    });
    
    // Chat content (special focus)
    if (stats.chat_content) {
        const stat = stats.chat_content;
        html += `<tr style="border-bottom: 2px solid var(--border-color); background: #e8f4f8;">`;
        html += `<td style="padding: 12px;"><strong>📱 Chat Content (Special Focus)</strong></td>`;
        html += `<td style="padding: 12px; text-align: right;">${Number(stat.mean).toFixed(2)}%</td>`;
        html += `<td style="padding: 12px; text-align: right;">${Number(stat.variance).toFixed(4)}</td>`;
        html += `<td style="padding: 12px; text-align: right;">${Number(stat.std_dev).toFixed(2)}%</td>`;
        html += `<td style="padding: 12px; text-align: right;">${Number(stat.min).toFixed(2)}%</td>`;
        html += `<td style="padding: 12px; text-align: right;">${Number(stat.max).toFixed(2)}%</td>`;
        html += `</tr>`;
    }
    
    html += '</tbody></table>';
    html += '</div>';
    
    // Cost breakdown
    if (data.cost_breakdown) {
        const cost = data.cost_breakdown;
        html += '<div class="cost-breakdown" style="margin-top: 20px; padding: 16px; background: #e8f4f8; border-radius: 6px; border: 1px solid #bee5eb;">';
        html += '<h4 style="margin: 0 0 12px 0; color: #0c5460;">💰 Total Cost Breakdown</h4>';
        html += '<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; font-size: 0.9em; margin-bottom: 12px;">';
        html += '<div><strong>Chat Completions:</strong><br>';
        html += `Input: ${cost.chat_completions.input_tokens.toLocaleString()} tokens<br>`;
        html += `Output: ${cost.chat_completions.output_tokens.toLocaleString()} tokens<br>`;
        html += `Cost: $${cost.chat_completions.cost.toFixed(4)}</div>`;
        html += '<div><strong>Embeddings:</strong><br>';
        html += `Tokens: ${cost.embeddings.tokens.toLocaleString()}<br>`;
        html += `Cost: $${cost.embeddings.cost.toFixed(4)}</div>`;
        html += '</div>';
        html += `<div style="margin-top: 12px; padding-top: 12px; border-top: 2px solid #bee5eb; font-size: 1.1em; font-weight: bold; color: #0c5460;">`;
        html += `Total Cost: $${cost.total_cost.toFixed(4)}`;
        html += ` <span style="font-size: 0.85em; font-weight: normal; color: #666;">(Model: ${cost.model || 'gpt-4o-mini'})</span>`;
        html += '</div>';
        html += `<p style="margin-top: 12px; font-size: 0.9em;"><strong>Total Pairs Analyzed:</strong> ${data.results ? data.results.length : 0}</p>`;
        html += `<p style="margin-top: 4px; font-size: 0.9em;"><strong>Cost per Pair:</strong> $${(cost.total_cost / ((data.pair_results || data.results) ? (data.pair_results || data.results).length : 1)).toFixed(4)}</p>`;
        html += '</div>';
    }
    
    // Store for export
    window.batchResultsData = data;
    
    batchResults.innerHTML = html;
}

// Batch Analysis: Export Results
if (exportResultsBtn) {
    exportResultsBtn.addEventListener('click', () => {
        if (!window.batchResultsData) {
            showErrorModal('No results to export.');
            return;
        }
        
        const data = window.batchResultsData;
        const stats = data.statistics || {};
        const fdStats = data.focus_distribution_statistics || {};
        
        // Create CSV (ablation section first, then optional LLM focus-distribution aggregates)
        let csv = '=== ABLATION (descriptive T_obs shares; not a test) ===\n';
        csv += 'Focus,Mean_Share_pct,Variance,Std_Dev_pct,Min_pct,Max_pct,Mean_Raw_Shift_pct,Variance_Raw,Std_Dev_Raw_pct,Min_Raw_pct,Max_Raw_pct\n';
        
        Object.keys(stats).forEach(focusName => {
            if (focusName === 'noise') return;
            const stat = stats[focusName];
            const raw = stat.mean_raw !== undefined ? [
                (stat.mean_raw * 100).toFixed(4),
                stat.variance_raw ?? '',
                stat.std_dev_raw !== undefined ? (stat.std_dev_raw * 100).toFixed(4) : '',
                stat.min_raw !== undefined ? (stat.min_raw * 100).toFixed(4) : '',
                stat.max_raw !== undefined ? (stat.max_raw * 100).toFixed(4) : ''
            ].join(',') : ',,,,';
            csv += `"${focusName}",${Number(stat.mean).toFixed(4)},${stat.variance},${Number(stat.std_dev).toFixed(4)},${Number(stat.min).toFixed(4)},${Number(stat.max).toFixed(4)},${raw}\n`;
        });
        
        if (Object.keys(fdStats).length > 0) {
            csv += '\n=== FOCUS DISTRIBUTION (LLM assessment, mean points per pair) ===\n';
            csv += 'Focus,Mean_Points,Variance,Std_Dev,Min,Max,N_Pairs\n';
            Object.keys(fdStats).forEach(focusName => {
                const s = fdStats[focusName];
                csv += `"${focusName}",${(s.mean || 0).toFixed(4)},${(s.variance || 0).toFixed(6)},${(s.std_dev || 0).toFixed(4)},${(s.min || 0).toFixed(4)},${(s.max || 0).toFixed(4)},${s.n_pairs != null ? s.n_pairs : ''}\n`;
            });
        }
        
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `batch-analysis-results-${new Date().toISOString().split('T')[0]}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    });
}

// Batch Analysis: Export full JSON (includes all baseline_outputs / ablated_outputs per pair)
if (exportResultsJsonBtn) {
    exportResultsJsonBtn.addEventListener('click', () => {
        if (!window.batchResultsData) {
            showErrorModal('No results to export.');
            return;
        }
        const data = window.batchResultsData;
        const pairResults = data.pair_results || data.results || [];
        const missingBaselines = pairResults.filter(function (r) {
            return r && r.success !== false && !(r.baseline_outputs && r.baseline_outputs.length);
        }).length;
        if (missingBaselines) {
            console.warn(
                'JSON export: ' + missingBaselines +
                ' pair(s) lack baseline_outputs (likely slimmed SSE payload). ' +
                'Load a full checkpoint or re-run client-paced batch to include all samples.'
            );
        }
        const downloadData = Object.assign({}, data, {
            timestamp: new Date().toISOString(),
            pair_results: pairResults,
            results: pairResults,
        });
        const blob = new Blob([JSON.stringify(downloadData, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `batch-analysis-results-${new Date().toISOString().split('T')[0]}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    });
}

// ============================================
// Batch Agent Building Functions
// ============================================

// Update Batch Agent Cost Estimate
function updateBatchAgentCostEstimate() {
    const costEstimateDiv = document.getElementById('batch-agent-cost-estimate');
    const costEstimateContent = document.getElementById('batch-agent-cost-estimate-content');
    
    if (!costEstimateDiv || !costEstimateContent) return;
    
    // Updated: Check for pairs instead of results
    if (!batchAgentData || !batchAgentData.pairs || batchAgentData.pairs.length === 0) {
        costEstimateDiv.style.display = 'none';
        return;
    }
    
    if (batchFoci.length === 0) {
        costEstimateDiv.style.display = 'none';
        return;
    }
    
    // Pricing per million tokens (gpt-4o-mini)
    const PRICING = {
        input: 0.15 / 1_000_000,
        output: 0.60 / 1_000_000
    };
    
    const numPairs = batchAgentData.pairs.length;
    
    // Estimate tokens per pair (3 API calls, same as single agent builder):
    // 1. Assess Chat Foci:
    //    - Input: ~3500 tokens (system prompt + chat content + all foci descriptions)
    //    - Output: ~650 tokens (JSON with weights for all foci)
    // 2. Generate Response:
    //    - Input: ~2000 tokens (constructed prompt)
    //    - Output: ~500 tokens (generated response)
    const assessInputTokens = 3500;
    const assessOutputTokens = 650;
    const genInputTokens = 2000;
    const genOutputTokens = 500;
    
    const totalInputTokens = numPairs * (assessInputTokens + genInputTokens);
    const totalOutputTokens = numPairs * (assessOutputTokens + genOutputTokens);
    
    const inputCost = totalInputTokens * PRICING.input;
    const outputCost = totalOutputTokens * PRICING.output;
    const totalCost = inputCost + outputCost;
    
    costEstimateContent.innerHTML = `
        <p style="margin: 4px 0;"><strong>Estimated Input Tokens:</strong> ${totalInputTokens.toLocaleString()}</p>
        <p style="margin: 4px 0;"><strong>Estimated Output Tokens:</strong> ${totalOutputTokens.toLocaleString()}</p>
        <p style="margin: 8px 0 0 0; font-size: 1.1em;"><strong>Estimated Total Cost:</strong> $${totalCost.toFixed(4)}</p>
        <p style="margin: 4px 0; font-size: 0.9em; color: var(--text-secondary);">
            Based on ${numPairs} pair(s) × (Assess: ~${assessInputTokens} input + ~${assessOutputTokens} output + Generate: ~${genInputTokens} input + ~${genOutputTokens} output tokens per pair)
        </p>
    `;
    
    costEstimateDiv.style.display = 'block';
}

// Load Agent Checkpoint
if (loadAgentCheckpointBtn) {
    loadAgentCheckpointBtn.addEventListener('click', async () => {
        try {
            const checkpoints = await listCheckpoints('batch_agents');
            if (checkpoints.length === 0) {
                showErrorModal('No agent building checkpoints found. Previous runs before checkpoint saving was implemented were not saved. Future runs will be automatically saved.');
                return;
            }
            // Use the batch analysis checkpoint list UI (it's in the same tab)
            await displayCheckpointList('batch_agents');
        } catch (error) {
            showError('Error loading checkpoints: ' + error.message);
            console.error('Checkpoint loading error:', error);
        }
    });
}

// Import Batch Results
if (importBatchResultsBtn) {
    importBatchResultsBtn.addEventListener('click', () => {
        // Option 1: Import from batchPairs (if available)
        if (batchPairs && batchPairs.length > 0) {
            batchAgentData = {
                pairs: batchPairs.map(p => {
                    // Handle both old and new structure
                    if (p.inputs) {
                        return {
                            inputs: p.inputs,
                            output: p.output
                        };
                    } else {
                        // Migrate old structure
                        return {
                            inputs: {
                                chat_content: p.chat_content || '',
                                rag_context: p.rag_context || '',
                                tool_results: p.tool_results || ''
                            },
                            output: p.output
                        };
                    }
                })
            };
        } 
        // Option 2: Import from batch analysis results (extract just pairs)
        else if (window.batchResultsData && window.batchResultsData.results && window.batchResultsData.results.length > 0) {
            batchAgentData = {
                pairs: window.batchResultsData.results.map(r => {
                    const pairData = r.pair_data || {};
                    // Handle both old and new structure
                    if (pairData.inputs) {
                        return {
                            inputs: pairData.inputs,
                            output: pairData.output || ''
                        };
                    } else {
                        // Migrate old structure
                        return {
                            inputs: {
                                chat_content: pairData.chat_content || '',
                                rag_context: pairData.rag_context || '',
                                tool_results: pairData.tool_results || ''
                            },
                            output: pairData.output || ''
                        };
                    }
                }).filter(p => {
                    // Filter out empty pairs - at least one input and output required
                    const hasInput = p.inputs && Object.values(p.inputs).some(v => v && v.trim());
                    return hasInput && p.output && p.output.trim();
                })
            };
        } else {
            showErrorModal('No pairs found. Please add pairs in Batch Analysis tab or run batch analysis first.');
            return;
        }
        
        if (batchFoci.length === 0) {
            showErrorModal('No foci found. Please ensure foci are defined in the Batch Analysis tab.');
            return;
        }
        
        // Update status
        if (batchAgentStatus) {
            batchAgentStatus.innerHTML = `
                <div style="padding: 12px; background: #e8f4f8; border-radius: 6px; border: 1px solid var(--primary-color);">
                    <strong>✅ Batch Data Imported</strong>
                    <p style="margin: 4px 0 0 0; font-size: 0.9em;">
                        ${batchAgentData.pairs.length} pair(s) ready for agent building.
                        Foci: ${batchFoci.length} available.
                    </p>
                </div>
            `;
        }
        
        // Update cost estimate
        updateBatchAgentCostEstimate();
        
        // Enable the run button
        if (runBatchAgentBtn) {
            runBatchAgentBtn.disabled = false;
        }
    });
}

// Run Batch Agent Building
if (runBatchAgentBtn) {
    runBatchAgentBtn.addEventListener('click', async () => {
        if (!batchAgentData || !batchAgentData.pairs || batchAgentData.pairs.length === 0) {
            showErrorModal('No batch data imported. Please import pairs first.');
            return;
        }
        
        if (batchFoci.length === 0) {
            showErrorModal('No foci available. Please ensure foci are defined.');
            return;
        }
        
        showLoading(`Building agents for ${batchAgentData.pairs.length} input(s)... This may take a while.`);
        
        // Initialize results array
        batchAgentResultsData = [];
        window.batchAgentCostBreakdown = null;
        
        // Clear previous results and show initial state
        if (batchAgentResults) {
            batchAgentResults.innerHTML = '<h3 style="margin-bottom: 16px;">Agent Building Results</h3><p class="empty-state">Processing pairs...</p>';
        }
        
        try {
            const response = await fetch('/api/build-batch-agents-stream', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    pairs: batchAgentData.pairs,
                    foci: batchFoci,
                    model: 'gpt-4o-mini'
                })
            });
            
            if (!response.ok) {
                // Try to get error message from response
                let errorMessage = 'Failed to build batch agents';
                try {
                    const errorData = await response.json();
                    errorMessage = errorData.error || errorMessage;
                } catch (e) {
                    errorMessage = `HTTP ${response.status}: ${response.statusText}`;
                }
                throw new Error(errorMessage);
            }
            
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            handleBatchAgentStreamEvent(data);
                        } catch (e) {
                            console.error('Error parsing SSE data:', e, line);
                        }
                    }
                }
            }
            
            // Process any remaining buffer
            if (buffer.startsWith('data: ')) {
                try {
                    const data = JSON.parse(buffer.slice(6));
                    handleBatchAgentStreamEvent(data);
                } catch (e) {
                    console.error('Error parsing final SSE data:', e);
                }
            }
            
        } catch (error) {
            showError('Error building batch agents: ' + error.message);
            console.error('Batch agent building error:', error);
        } finally {
            hideLoading();
        }
    });
}

// Handle streaming events for batch agent building
function handleBatchAgentStreamEvent(data) {
    console.log('Batch Agent SSE Event:', data.type, data);
    
    switch (data.type) {
        case 'progress':
            // Update progress message if needed
            break;
            
        case 'pair_complete':
            // Add result to array
            if (data.result) {
                batchAgentResultsData.push(data.result);
                // Render results progressively
                renderBatchAgentResults(batchAgentResultsData, window.batchAgentCostBreakdown, true);
            }
            break;
            
        case 'complete':
            // Final results and cost breakdown
            batchAgentResultsData = data.results || [];
            window.batchAgentCostBreakdown = data.cost_breakdown || null;
            
            // Final render with cost breakdown
            renderBatchAgentResults(batchAgentResultsData, window.batchAgentCostBreakdown);
            
            // Show reporting section and update it
            if (batchAgentReportingSection) {
                batchAgentReportingSection.style.display = 'block';
            }
            // Show optimization section
            if (promptOptimizationSection) {
                promptOptimizationSection.style.display = 'block';
            }
            updateBatchAgentReporting();
            
            // Enable export button
            if (exportBatchAgentResultsBtn) {
                exportBatchAgentResultsBtn.disabled = false;
            }
            
            // Enable LLM eval button
            if (runLLMEvalBtn) {
                runLLMEvalBtn.disabled = false;
            }
            break;
            
        case 'error':
            showError('Error: ' + (data.message || 'Unknown error'));
            if (data.pair_index !== undefined) {
                console.error(`Error processing pair ${data.pair_index}:`, data.message);
            }
            break;
    }
}

// Render Batch Agent Results
function renderBatchAgentResults(results, costBreakdown = null, isProgressive = false) {
    if (!batchAgentResults) return;
    
    if (results.length === 0) {
        batchAgentResults.innerHTML = '<p class="empty-state">No results to display.</p>';
        return;
    }
    
    let html = `<h3 style="margin-bottom: 16px;">Agent Building Results (${results.length} pair(s))</h3>`;
    
    // Add cost breakdown if available (only show on final render)
    if (costBreakdown && !isProgressive) {
        html += '<div style="margin-bottom: 16px; padding: 12px; background: #e8f4f8; border-radius: 6px; border: 1px solid var(--primary-color);">';
        html += '<h4 style="margin-bottom: 8px;">💰 Cost Breakdown</h4>';
        html += `<p style="margin: 4px 0;"><strong>Input Tokens:</strong> ${(costBreakdown.chat_completions?.input_tokens || 0).toLocaleString()}</p>`;
        html += `<p style="margin: 4px 0;"><strong>Output Tokens:</strong> ${(costBreakdown.chat_completions?.output_tokens || 0).toLocaleString()}</p>`;
        html += `<p style="margin: 4px 0;"><strong>Model:</strong> ${costBreakdown.model || 'gpt-4o-mini'}</p>`;
        html += `<p style="margin: 8px 0 0 0; font-size: 1.1em;"><strong>Total Cost:</strong> $${(costBreakdown.total_cost || 0).toFixed(4)}</p>`;
        html += `<p style="margin: 4px 0; font-size: 0.9em;"><strong>Cost per Pair:</strong> $${((costBreakdown.total_cost || 0) / results.length).toFixed(4)}</p>`;
        html += '</div>';
    }
    
    // Show progress indicator if progressive
    if (isProgressive) {
        html += `<p style="margin-bottom: 12px; color: var(--text-secondary); font-size: 0.9em;">Processing... ${results.length} pair(s) completed</p>`;
    }
    
    results.forEach((result, index) => {
        const originalOutput = result.original_output || '';
        const newOutput = result.new_output || '';
        const selectedFoci = result.selected_foci || [];
        const evaluation = result.evaluation || null; // { type: 'thumbs_up' | 'thumbs_down' | 'llm_eval', value: number }
        
        html += `
            <div class="batch-agent-result-item" style="margin-bottom: 24px; padding: 16px; background: #f8fafc; border-radius: 8px; border: 1px solid var(--border-color);">
                <h4 style="margin-bottom: 12px; color: var(--primary-color);">Pair ${index + 1}</h4>
                
                <div style="margin-bottom: 12px;">
                    <strong>Input (Chat Content):</strong>
                    <div style="padding: 8px; background: white; border-radius: 4px; margin-top: 4px; font-size: 0.9em; max-height: 200px; overflow-y: auto; white-space: pre-wrap; word-wrap: break-word;">
                        ${escapeHtml(result.input || '')}
                    </div>
                </div>
                
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 12px;">
                    <div>
                        <strong>Original Output:</strong>
                        <div style="padding: 8px; background: white; border-radius: 4px; margin-top: 4px; font-size: 0.9em; min-height: 100px;">
                            ${escapeHtml(originalOutput)}
                        </div>
                    </div>
                    <div>
                        <strong>New Output (Optimized):</strong>
                        <div style="padding: 8px; background: #e8f4f8; border-radius: 4px; margin-top: 4px; font-size: 0.9em; min-height: 100px;">
                            ${escapeHtml(newOutput)}
                        </div>
                    </div>
                </div>
                
                <div style="margin-bottom: 12px;">
                    <strong>Selected Foci:</strong>
                    <div style="display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px;">
                        ${selectedFoci.map(f => `<span style="padding: 4px 8px; background: var(--primary-color); color: white; border-radius: 4px; font-size: 0.85em;">${escapeHtml(f)}</span>`).join('')}
                    </div>
                </div>
                
                <div style="margin-bottom: 12px;">
                    <strong>Evaluation:</strong>
                    <div style="display: flex; gap: 12px; align-items: center; margin-top: 8px; flex-wrap: wrap;">
                        <button 
                            class="btn ${evaluation && evaluation.type === 'thumbs_up' ? 'btn-success' : 'btn-outline'}" 
                            onclick="evaluateBatchAgent(${index}, 'thumbs_up')"
                            style="padding: 8px 16px; font-size: 1.2em;"
                            title="Thumbs up - New output is better"
                        >
                            👍
                        </button>
                        <button 
                            class="btn ${evaluation && evaluation.type === 'thumbs_down' ? 'btn-danger' : 'btn-outline'}" 
                            onclick="evaluateBatchAgent(${index}, 'thumbs_down')"
                            style="padding: 8px 16px; font-size: 1.2em;"
                            title="Thumbs down - Original output is better"
                        >
                            👎
                        </button>
                        ${evaluation && evaluation.type === 'llm_eval' ? `
                            <div style="display: flex; align-items: center; gap: 8px; padding: 8px 12px; background: #fff3cd; border-radius: 6px; border: 1px solid #ffc107; flex: 1; min-width: 200px;">
                                <span style="font-size: 1.5em;">
                                    ${evaluation.better_output === 'new' ? '🤖👍' : evaluation.better_output === 'original' ? '🤖👎' : '🤖➡️'}
                                </span>
                                <span style="font-weight: bold;">
                                    LLM: ${(evaluation.value * 100).toFixed(1)}%
                                </span>
                                ${evaluation.explanation ? `<span style="font-size: 0.85em; color: var(--text-secondary); margin-left: 8px;">${escapeHtml(evaluation.explanation)}</span>` : ''}
                            </div>
                        ` : ''}
                    </div>
                </div>
            </div>
        `;
    });
    
    batchAgentResults.innerHTML = html;
}

// Evaluate Batch Agent Result
window.evaluateBatchAgent = function(index, type) {
    if (!batchAgentResultsData || !batchAgentResultsData[index]) return;
    
    batchAgentResultsData[index].evaluation = {
        type: type,
        timestamp: new Date().toISOString()
    };
    
    // Re-render to update UI
    renderBatchAgentResults(batchAgentResultsData, window.batchAgentCostBreakdown);
    
    // Update reporting
    updateBatchAgentReporting();
};

// Update Batch Agent Reporting
function updateBatchAgentReporting() {
    if (!batchAgentReporting) return;
    
    if (!batchAgentResultsData || batchAgentResultsData.length === 0) {
        batchAgentReporting.innerHTML = '<p class="empty-state">No results to report on yet.</p>';
        return;
    }
    
    // Calculate focus usage frequency AND weights
    const focusStats = {}; // Track comprehensive stats per focus
    let totalEvaluations = 0;
    let thumbsUp = 0;
    let thumbsDown = 0;
    
    batchAgentResultsData.forEach(result => {
        const selectedFoci = result.selected_foci || [];
        const fociWeights = result.foci_weights || {};
        
        // Initialize stats for all foci that appear in this result
        Object.keys(fociWeights).forEach(focus => {
            if (!focusStats[focus]) {
                focusStats[focus] = {
                    rawCount: 0,           // Times selected
                    sumOfWeights: 0,       // Sum of all weights (including when not selected)
                    sumOfWeightsWhenUsed: 0 // Sum of weights only when selected
                };
            }
            
            const weight = fociWeights[focus] || 0;
            focusStats[focus].sumOfWeights += weight;
            
            // If this focus was selected, count it and add to "when used" sum
            if (selectedFoci.includes(focus)) {
                focusStats[focus].rawCount += 1;
                focusStats[focus].sumOfWeightsWhenUsed += weight;
            }
        });
        
        if (result.evaluation) {
            totalEvaluations++;
            if (result.evaluation.type === 'thumbs_up') {
                thumbsUp++;
            } else if (result.evaluation.type === 'thumbs_down') {
                thumbsDown++;
            }
        }
    });
    
    const totalPairs = batchAgentResultsData.length;
    const improvementRate = totalEvaluations > 0 ? (thumbsUp / totalEvaluations) * 100 : 0;
    
    let html = '<h3 style="margin-bottom: 16px;">Batch Agent Building Report</h3>';
    
    // Add cost summary if available
    if (window.batchAgentCostBreakdown) {
        html += '<div style="margin-bottom: 24px;">';
        html += '<h4 style="margin-bottom: 12px;">Cost Summary</h4>';
        html += '<div style="padding: 16px; background: #f8fafc; border-radius: 6px;">';
        html += `<p style="margin: 4px 0;"><strong>Agent Building Cost:</strong> $${(window.batchAgentCostBreakdown.total_cost || 0).toFixed(4)}</p>`;
        if (window.batchAgentLLMEvalCost) {
            html += `<p style="margin: 4px 0;"><strong>LLM Evaluation Cost:</strong> $${(window.batchAgentLLMEvalCost.total_cost || 0).toFixed(4)}</p>`;
            const totalCost = (window.batchAgentCostBreakdown.total_cost || 0) + (window.batchAgentLLMEvalCost.total_cost || 0);
            html += `<p style="margin: 8px 0 0 0; font-size: 1.1em;"><strong>Total Cost:</strong> $${totalCost.toFixed(4)}</p>`;
        }
        html += `<p style="margin: 4px 0; font-size: 0.9em;"><strong>Cost per Pair:</strong> $${((window.batchAgentCostBreakdown.total_cost || 0) / totalPairs).toFixed(4)}</p>`;
        html += '</div>';
        html += '</div>';
    }
    
    // Focus Usage Statistics
    html += '<div style="margin-bottom: 24px;">';
    html += '<h4 style="margin-bottom: 12px;">Focus Usage Frequency & Weights</h4>';
    html += '<table style="width: 100%; border-collapse: collapse;">';
    html += '<thead><tr style="background: #f8fafc; border-bottom: 2px solid var(--border-color);">';
    html += '<th style="padding: 8px; text-align: left;">Focus</th>';
    html += '<th style="padding: 8px; text-align: right;">Raw Count</th>';
    html += '<th style="padding: 8px; text-align: right;">Usage %</th>';
    html += '<th style="padding: 8px; text-align: right;">Sum of Weights</th>';
    html += '<th style="padding: 8px; text-align: right;">Avg Weight</th>';
    html += '<th style="padding: 8px; text-align: right;">Avg Weight (When Used)</th>';
    html += '</tr></thead><tbody>';
    
    // Sort by sum of weights to show most important foci first
    const sortedFoci = Object.entries(focusStats).sort((a, b) => {
        return b[1].sumOfWeights - a[1].sumOfWeights;
    });
    
    sortedFoci.forEach(([focus, stats]) => {
        const usagePercentage = (stats.rawCount / totalPairs) * 100;
        const avgWeight = totalPairs > 0 ? (stats.sumOfWeights / totalPairs) : 0;
        const avgWeightWhenUsed = stats.rawCount > 0 ? (stats.sumOfWeightsWhenUsed / stats.rawCount) : 0;
        
        html += `<tr style="border-bottom: 1px solid var(--border-color);">`;
        html += `<td style="padding: 8px;"><strong>${escapeHtml(focus)}</strong></td>`;
        html += `<td style="padding: 8px; text-align: right;">${stats.rawCount}</td>`;
        html += `<td style="padding: 8px; text-align: right;">${usagePercentage.toFixed(1)}%</td>`;
        html += `<td style="padding: 8px; text-align: right;">${stats.sumOfWeights.toFixed(2)}</td>`;
        html += `<td style="padding: 8px; text-align: right;">${avgWeight.toFixed(3)}</td>`;
        html += `<td style="padding: 8px; text-align: right;">${avgWeightWhenUsed.toFixed(3)}</td>`;
        html += `</tr>`;
    });
    
    html += '</tbody></table>';
    html += '</div>';
    
    // Evaluation Statistics
    html += '<div style="margin-bottom: 24px;">';
    html += '<h4 style="margin-bottom: 12px;">Improvement Evaluation</h4>';
    html += '<div style="padding: 16px; background: #f8fafc; border-radius: 6px;">';
    html += `<p style="margin: 4px 0;"><strong>Total Pairs:</strong> ${totalPairs}</p>`;
    html += `<p style="margin: 4px 0;"><strong>Evaluated:</strong> ${totalEvaluations}</p>`;
    html += `<p style="margin: 4px 0;"><strong>Thumbs Up (Better):</strong> ${thumbsUp} (${totalEvaluations > 0 ? (thumbsUp / totalEvaluations * 100).toFixed(1) : 0}%)</p>`;
    html += `<p style="margin: 4px 0;"><strong>Thumbs Down (Worse):</strong> ${thumbsDown} (${totalEvaluations > 0 ? (thumbsDown / totalEvaluations * 100).toFixed(1) : 0}%)</p>`;
    html += `<p style="margin: 8px 0 0 0; font-size: 1.1em;"><strong>Overall Improvement Rate:</strong> <span style="color: ${improvementRate >= 50 ? '#10b981' : '#ef4444'}; font-weight: bold;">${improvementRate.toFixed(1)}%</span></p>`;
    html += '</div>';
    html += '</div>';
    
    // LLM Evaluation Analysis
    const llmEvaluations = batchAgentResultsData.filter(r => r.evaluation && r.evaluation.type === 'llm_eval');
    if (llmEvaluations.length > 0) {
        html += '<div style="margin-bottom: 24px;">';
        html += '<h4 style="margin-bottom: 12px;">🤖 LLM Evaluation Analysis</h4>';
        html += '<div style="padding: 16px; background: #fff3cd; border-radius: 6px; border: 1px solid #ffc107;">';
        
        // Basic statistics
        const llmScores = llmEvaluations.map(e => e.evaluation.value);
        const avgScore = llmScores.reduce((a, b) => a + b, 0) / llmScores.length;
        const minScore = Math.min(...llmScores);
        const maxScore = Math.max(...llmScores);
        
        // Better output distribution
        const betterOutputCounts = {
            new: 0,
            original: 0,
            similar: 0
        };
        llmEvaluations.forEach(e => {
            const better = e.evaluation.better_output || 'similar';
            if (betterOutputCounts.hasOwnProperty(better)) {
                betterOutputCounts[better]++;
            } else {
                betterOutputCounts.similar++;
            }
        });
        
        // Score distribution
        const scoreRanges = {
            'Excellent (0.8-1.0)': 0,
            'Good (0.6-0.8)': 0,
            'Neutral (0.4-0.6)': 0,
            'Poor (0.2-0.4)': 0,
            'Very Poor (0.0-0.2)': 0
        };
        llmScores.forEach(score => {
            if (score >= 0.8) scoreRanges['Excellent (0.8-1.0)']++;
            else if (score >= 0.6) scoreRanges['Good (0.6-0.8)']++;
            else if (score >= 0.4) scoreRanges['Neutral (0.4-0.6)']++;
            else if (score >= 0.2) scoreRanges['Poor (0.2-0.4)']++;
            else scoreRanges['Very Poor (0.0-0.2)']++;
        });
        
        html += `<p style="margin: 4px 0;"><strong>Total LLM Evaluations:</strong> ${llmEvaluations.length}</p>`;
        html += `<p style="margin: 4px 0;"><strong>Average Score:</strong> <span style="color: ${avgScore >= 0.6 ? '#10b981' : avgScore >= 0.4 ? '#f59e0b' : '#ef4444'}; font-weight: bold;">${(avgScore * 100).toFixed(1)}%</span></p>`;
        html += `<p style="margin: 4px 0;"><strong>Score Range:</strong> ${(minScore * 100).toFixed(1)}% - ${(maxScore * 100).toFixed(1)}%</p>`;
        
        html += '<div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid #ffc107;">';
        html += '<p style="margin-bottom: 8px; font-weight: bold;">Better Output Distribution:</p>';
        html += `<p style="margin: 4px 0;">🤖👍 New Better: ${betterOutputCounts.new} (${(betterOutputCounts.new / llmEvaluations.length * 100).toFixed(1)}%)</p>`;
        html += `<p style="margin: 4px 0;">🤖👎 Original Better: ${betterOutputCounts.original} (${(betterOutputCounts.original / llmEvaluations.length * 100).toFixed(1)}%)</p>`;
        html += `<p style="margin: 4px 0;">🤖➡️ Similar: ${betterOutputCounts.similar} (${(betterOutputCounts.similar / llmEvaluations.length * 100).toFixed(1)}%)</p>`;
        html += '</div>';
        
        html += '<div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid #ffc107;">';
        html += '<p style="margin-bottom: 8px; font-weight: bold;">Score Distribution:</p>';
        Object.entries(scoreRanges).forEach(([range, count]) => {
            if (count > 0) {
                const percentage = (count / llmEvaluations.length * 100).toFixed(1);
                html += `<p style="margin: 4px 0;">${range}: ${count} (${percentage}%)</p>`;
            }
        });
        html += '</div>';
        
        // Correlation with manual evaluations (if both exist)
        const bothEvaluated = batchAgentResultsData.filter(r => {
            const eval = r.evaluation;
            return eval && (eval.type === 'thumbs_up' || eval.type === 'thumbs_down') && 
                   llmEvaluations.some(llm => llm === r);
        });
        
        if (bothEvaluated.length > 0) {
            let agreementCount = 0;
            bothEvaluated.forEach(result => {
                const manualEval = result.evaluation.type === 'thumbs_up';
                const llmEval = llmEvaluations.find(llm => llm === result);
                if (llmEval) {
                    const llmBetter = llmEval.evaluation.better_output === 'new';
                    if (manualEval === llmBetter) {
                        agreementCount++;
                    }
                }
            });
            const agreementRate = (agreementCount / bothEvaluated.length * 100).toFixed(1);
            html += '<div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid #ffc107;">';
            html += `<p style="margin: 4px 0;"><strong>Manual vs LLM Agreement:</strong> ${agreementCount}/${bothEvaluated.length} (${agreementRate}%)</p>`;
            html += '<p style="margin: 4px 0; font-size: 0.85em; color: var(--text-secondary);">Pairs evaluated by both manual and LLM</p>';
            html += '</div>';
        }
        
        html += '</div>';
        html += '</div>';
    }
    
    batchAgentReporting.innerHTML = html;
}

// Handle LLM Evaluation Stream Events
function handleLLMEvalStreamEvent(event) {
    try {
        const data = JSON.parse(event.data);
        
        switch (data.type) {
            case 'progress':
                showLoading(data.message || `Evaluating... (${data.completed || 0}/${data.total || 0})`);
                break;
                
            case 'eval_complete':
                // Update the specific result with evaluation
                const resultIndex = data.result_index;
                if (batchAgentResultsData && batchAgentResultsData[resultIndex]) {
                    batchAgentResultsData[resultIndex].evaluation = {
                        type: 'llm_eval',
                        value: data.evaluation.score,
                        explanation: data.evaluation.explanation,
                        better_output: data.evaluation.better_output
                    };
                    
                    // Re-render to show progressive updates
                    renderBatchAgentResults(batchAgentResultsData, window.batchAgentCostBreakdown);
                    updateBatchAgentReporting();
                }
                break;
                
            case 'complete':
                // Store LLM eval cost separately
                window.batchAgentLLMEvalCost = data.cost_breakdown || null;
                
                // Final render
                renderBatchAgentResults(batchAgentResultsData, window.batchAgentCostBreakdown);
                updateBatchAgentReporting();
                
                // Show LLM eval cost if available
                if (window.batchAgentLLMEvalCost && batchAgentResults) {
                    const costHtml = `
                        <div style="margin-top: 16px; padding: 12px; background: #fff3cd; border-radius: 6px; border: 1px solid #ffc107;">
                            <h4 style="margin-bottom: 8px;">🤖 LLM Evaluation Cost</h4>
                            <p style="margin: 4px 0;"><strong>Total Cost:</strong> $${(window.batchAgentLLMEvalCost.total_cost || 0).toFixed(4)}</p>
                            <p style="margin: 4px 0;"><strong>Input Tokens:</strong> ${(window.batchAgentLLMEvalCost.chat_completions?.input_tokens || 0).toLocaleString()}</p>
                            <p style="margin: 4px 0;"><strong>Output Tokens:</strong> ${(window.batchAgentLLMEvalCost.chat_completions?.output_tokens || 0).toLocaleString()}</p>
                        </div>
                    `;
                    batchAgentResults.insertAdjacentHTML('beforeend', costHtml);
                }
                
                hideLoading();
                break;
                
            case 'error':
                hideLoading();
                showError('Error running LLM evaluation: ' + (data.message || 'Unknown error'));
                console.error('LLM evaluation error:', data);
                break;
        }
    } catch (error) {
        console.error('Error parsing SSE event:', error);
    }
}

// Run LLM Evaluation
if (runLLMEvalBtn) {
    runLLMEvalBtn.addEventListener('click', async () => {
        if (!batchAgentResultsData || batchAgentResultsData.length === 0) {
            showErrorModal('No agent results to evaluate. Please build agents first.');
            return;
        }
        
        showLoading(`Running LLM evaluation on ${batchAgentResultsData.length} pair(s)...`);
        
        try {
            const response = await fetch('/api/llm-evaluate-batch-agents-stream', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    results: batchAgentResultsData,
                    model: 'gpt-4o-mini'
                })
            });
            
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(errorText || 'Failed to start LLM evaluation');
            }
            
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let receivedComplete = false;
            
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || ''; // Keep incomplete line in buffer
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const event = { data: line.slice(6) };
                        handleLLMEvalStreamEvent(event);
                        // Check if this is the complete event
                        try {
                            const data = JSON.parse(event.data);
                            if (data.type === 'complete') {
                                receivedComplete = true;
                            }
                        } catch (e) {
                            // Ignore parse errors
                        }
                    }
                }
            }
            
            // Process any remaining buffer
            if (buffer.trim()) {
                if (buffer.startsWith('data: ')) {
                    const event = { data: buffer.slice(6) };
                    handleLLMEvalStreamEvent(event);
                    try {
                        const data = JSON.parse(event.data);
                        if (data.type === 'complete') {
                            receivedComplete = true;
                        }
                    } catch (e) {
                        // Ignore parse errors
                    }
                }
            }
            
            // Ensure loading is hidden if complete event wasn't received
            if (!receivedComplete) {
                hideLoading();
            }
            
        } catch (error) {
            hideLoading();
            showError('Error running LLM evaluation: ' + error.message);
            console.error('LLM evaluation error:', error);
        }
    });
}

// Analyze Prompt Optimization
if (analyzeOptimizationBtn) {
    analyzeOptimizationBtn.addEventListener('click', async () => {
        // Collect all available data
        const dataToSend = {
            // Single chat assessment (from prompt analysis tab)
            single_assessment: assessmentFoci || [],
            
            // Single ablation (if available)
            single_ablation: window.singleAblationResults || null,
            
            // Batch analysis
            batch_analysis: window.batchResultsData || {},
            
            // Agent building results
            agent_results: batchAgentResultsData || [],
            
            // Foci and prompt - use batch foci if available, otherwise regular foci
            foci: batchFoci.length > 0 ? batchFoci : foci,
            original_prompt: promptInput?.value || '',
            model: 'gpt-4o'
        };
        
        if (!dataToSend.batch_analysis.statistics && 
            (!dataToSend.agent_results || dataToSend.agent_results.length === 0) &&
            (!dataToSend.single_assessment || dataToSend.single_assessment.length === 0) &&
            !dataToSend.single_ablation) {
            showErrorModal('Please run at least one analysis (prompt assessment, ablation analysis, batch analysis, or agent building) first.');
            return;
        }
        
        showLoading('Analyzing comprehensive data and generating optimization recommendations...');
        
        try {
            const response = await fetch('/api/analyze-prompt-optimization', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(dataToSend)
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to get recommendations');
            }
            
            const data = await response.json();
            displayOptimizationRecommendations(data.recommendations, data.analysis_summary, data.cost_breakdown, data.optimized_prompt);
            
        } catch (error) {
            showError('Error getting recommendations: ' + error.message);
            console.error('Optimization analysis error:', error);
        } finally {
            hideLoading();
        }
    });
}

// Display Optimization Recommendations
function displayOptimizationRecommendations(recommendations, analysisSummary, costBreakdown, optimizedPrompt) {
    if (!optimizationResults) return;
    
    // Show the section
    if (promptOptimizationSection) {
        promptOptimizationSection.style.display = 'block';
    }
    
    let html = '<div style="max-width: 100%;">';
    
    // Analysis Summary (what was sent to LLM)
    if (analysisSummary) {
        html += '<div style="margin-bottom: 24px; padding: 16px; background: #f8fafc; border-radius: 6px; border: 1px solid var(--border-color);">';
        html += '<h3 style="margin-bottom: 12px;">📋 Analysis Summary (Data Sent to LLM)</h3>';
        html += '<details style="cursor: pointer;">';
        html += '<summary style="font-weight: bold; margin-bottom: 8px; padding: 8px; background: white; border-radius: 4px;">Click to view comprehensive analysis data</summary>';
        html += '<div style="margin-top: 12px; padding: 12px; background: white; border-radius: 4px; max-height: 600px; overflow-y: auto;">';
        html += `<pre style="white-space: pre-wrap; font-family: 'Courier New', monospace; font-size: 0.85em; line-height: 1.5; margin: 0;">${escapeHtml(analysisSummary)}</pre>`;
        html += '</div>';
        html += '</details>';
        html += '</div>';
    }
    
    // LLM Summary
    if (recommendations.summary) {
        html += '<div style="margin-bottom: 24px; padding: 16px; background: #e8f4f8; border-radius: 6px; border: 1px solid var(--primary-color);">';
        html += '<h3 style="margin-bottom: 12px;">📊 Summary</h3>';
        html += `<p style="white-space: pre-wrap;">${escapeHtml(recommendations.summary)}</p>`;
        html += '</div>';
    }
    
    // Key Insights
    if (recommendations.key_insights && recommendations.key_insights.length > 0) {
        html += '<div style="margin-bottom: 24px;">';
        html += '<h3 style="margin-bottom: 12px;">💡 Key Insights</h3>';
        html += '<ul style="margin-left: 20px;">';
        recommendations.key_insights.forEach(insight => {
            html += `<li style="margin-bottom: 8px;">${escapeHtml(insight)}</li>`;
        });
        html += '</ul>';
        html += '</div>';
    }
    
    // Recommendations by Type
    if (recommendations.recommendations && recommendations.recommendations.length > 0) {
        html += '<div style="margin-bottom: 24px;">';
        html += '<h3 style="margin-bottom: 16px;">🎯 Recommendations</h3>';
        
        // Group by type
        const byType = {};
        recommendations.recommendations.forEach(rec => {
            const type = rec.type || 'other';
            if (!byType[type]) byType[type] = [];
            byType[type].push(rec);
        });
        
        const typeLabels = {
            'consolidation': '🔗 Consolidation',
            'prioritization': '⭐ Prioritization',
            'tool_conversion': '🛠️ Tool Conversion',
            'removal': '🗑️ Removal',
            'enhancement': '✨ Enhancement',
            'structure': '📐 Structure',
            'consistency': '📊 Consistency'
        };
        
        Object.entries(byType).forEach(([type, recs]) => {
            html += `<div style="margin-bottom: 20px; padding: 16px; background: #f8fafc; border-radius: 6px; border: 1px solid var(--border-color);">`;
            html += `<h4 style="margin-bottom: 12px;">${typeLabels[type] || type}</h4>`;
            
            recs.forEach((rec, idx) => {
                const priorityColor = rec.priority === 'high' ? '#ef4444' : rec.priority === 'medium' ? '#f59e0b' : '#6b7280';
                html += `<div style="margin-bottom: 16px; padding: 12px; background: white; border-radius: 4px; border-left: 4px solid ${priorityColor};">`;
                if (rec.focus_name) {
                    html += `<p style="margin: 0 0 8px 0; font-weight: bold;">${escapeHtml(rec.focus_name)}</p>`;
                }
                html += `<p style="margin: 4px 0;"><strong>Current State:</strong> ${escapeHtml(rec.current_state || 'N/A')}</p>`;
                html += `<p style="margin: 4px 0;"><strong>Recommendation:</strong> ${escapeHtml(rec.recommendation || 'N/A')}</p>`;
                html += `<p style="margin: 4px 0;"><strong>Rationale:</strong> ${escapeHtml(rec.rationale || 'N/A')}</p>`;
                if (rec.data_evidence) {
                    html += `<p style="margin: 4px 0; font-size: 0.9em; color: var(--text-secondary);"><strong>Evidence:</strong> ${escapeHtml(rec.data_evidence)}</p>`;
                }
                html += `<p style="margin: 4px 0;"><strong>Expected Impact:</strong> ${escapeHtml(rec.expected_impact || 'N/A')}</p>`;
                html += `<span style="display: inline-block; padding: 4px 8px; background: ${priorityColor}; color: white; border-radius: 4px; font-size: 0.85em; margin-top: 8px;">${rec.priority || 'low'} priority</span>`;
                html += '</div>';
            });
            
            html += '</div>';
        });
        
        html += '</div>';
    }
    
    // Suggested Prompt Structure
    if (recommendations.suggested_prompt_structure) {
        const structure = recommendations.suggested_prompt_structure;
        html += '<div style="margin-bottom: 24px; padding: 16px; background: #fff3cd; border-radius: 6px; border: 1px solid #ffc107;">';
        html += '<h3 style="margin-bottom: 16px;">📋 Suggested Prompt Structure</h3>';
        
        if (structure.high_priority_foci && structure.high_priority_foci.length > 0) {
            html += '<div style="margin-bottom: 12px;">';
            html += '<strong>High Priority Foci:</strong>';
            html += '<ul style="margin: 4px 0 0 20px;">';
            structure.high_priority_foci.forEach(focus => {
                html += `<li>${escapeHtml(focus)}</li>`;
            });
            html += '</ul>';
            html += '</div>';
        }
        
        if (structure.medium_priority_foci && structure.medium_priority_foci.length > 0) {
            html += '<div style="margin-bottom: 12px;">';
            html += '<strong>Medium Priority Foci:</strong>';
            html += '<ul style="margin: 4px 0 0 20px;">';
            structure.medium_priority_foci.forEach(focus => {
                html += `<li>${escapeHtml(focus)}</li>`;
            });
            html += '</ul>';
            html += '</div>';
        }
        
        if (structure.low_priority_foci && structure.low_priority_foci.length > 0) {
            html += '<div style="margin-bottom: 12px;">';
            html += '<strong>Low Priority Foci:</strong>';
            html += '<ul style="margin: 4px 0 0 20px;">';
            structure.low_priority_foci.forEach(focus => {
                html += `<li>${escapeHtml(focus)}</li>`;
            });
            html += '</ul>';
            html += '</div>';
        }
        
        if (structure.tool_candidates && structure.tool_candidates.length > 0) {
            html += '<div style="margin-bottom: 12px;">';
            html += '<strong>🛠️ Tool Candidates:</strong>';
            html += '<ul style="margin: 4px 0 0 20px;">';
            structure.tool_candidates.forEach(item => {
                html += `<li>${escapeHtml(typeof item === 'string' ? item : JSON.stringify(item))}</li>`;
            });
            html += '</ul>';
            html += '</div>';
        }
        
        if (structure.knowledge_doc_candidates && structure.knowledge_doc_candidates.length > 0) {
            html += '<div style="margin-bottom: 12px;">';
            html += '<strong>📚 Knowledge Doc Candidates:</strong>';
            html += '<ul style="margin: 4px 0 0 20px;">';
            structure.knowledge_doc_candidates.forEach(item => {
                html += `<li>${escapeHtml(typeof item === 'string' ? item : JSON.stringify(item))}</li>`;
            });
            html += '</ul>';
            html += '</div>';
        }
        
        if (structure.removal_candidates && structure.removal_candidates.length > 0) {
            html += '<div style="margin-bottom: 12px;">';
            html += '<strong>🗑️ Removal Candidates:</strong>';
            html += '<ul style="margin: 4px 0 0 20px;">';
            structure.removal_candidates.forEach(item => {
                html += `<li>${escapeHtml(typeof item === 'string' ? item : JSON.stringify(item))}</li>`;
            });
            html += '</ul>';
            html += '</div>';
        }
        
        if (structure.consolidation_suggestions && structure.consolidation_suggestions.length > 0) {
            html += '<div style="margin-bottom: 12px;">';
            html += '<strong>🔗 Consolidation Suggestions:</strong>';
            html += '<ul style="margin: 4px 0 0 20px;">';
            structure.consolidation_suggestions.forEach(suggestion => {
                html += `<li>${escapeHtml(suggestion)}</li>`;
            });
            html += '</ul>';
            html += '</div>';
        }
        
        if (structure.organization_suggestion) {
            html += '<div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid #ffc107;">';
            html += '<strong>Organization Suggestion:</strong>';
            html += `<p style="margin: 4px 0; white-space: pre-wrap;">${escapeHtml(structure.organization_suggestion)}</p>`;
            html += '</div>';
        }
        
        html += '</div>';
    }
    
    // Data Quality Assessment
    if (recommendations.data_quality_assessment) {
        const quality = recommendations.data_quality_assessment;
        html += '<div style="margin-bottom: 24px; padding: 16px; background: #f8fafc; border-radius: 6px;">';
        html += '<h3 style="margin-bottom: 12px;">📊 Data Quality Assessment</h3>';
        html += `<p style="margin: 4px 0;"><strong>Coverage:</strong> ${escapeHtml(quality.coverage || 'N/A')}</p>`;
        html += `<p style="margin: 4px 0;"><strong>Confidence:</strong> ${escapeHtml(quality.confidence || 'N/A')}</p>`;
        if (quality.gaps) {
            html += `<p style="margin: 4px 0;"><strong>Gaps:</strong> ${escapeHtml(quality.gaps)}</p>`;
        }
        html += '</div>';
    }
    
    // Optimized Prompt
    if (optimizedPrompt) {
        html += '<div style="margin-bottom: 24px; padding: 16px; background: #d1fae5; border-radius: 6px; border: 1px solid #10b981;">';
        html += '<h3 style="margin-bottom: 12px;">✨ Optimized Prompt</h3>';
        html += '<p style="margin-bottom: 12px; color: #065f46; font-size: 0.9em;">This is a ready-to-use optimized version of your prompt based on all the analysis data and recommendations.</p>';
        html += '<div style="position: relative;">';
        html += '<textarea id="optimized-prompt-text" readonly style="width: 100%; min-height: 300px; padding: 12px; font-family: \'Courier New\', monospace; font-size: 0.9em; line-height: 1.5; border: 1px solid #10b981; border-radius: 4px; background: white; white-space: pre-wrap; word-wrap: break-word; resize: vertical;">';
        html += escapeHtml(optimizedPrompt);
        html += '</textarea>';
        html += '<button onclick="copyOptimizedPrompt()" class="btn btn-primary" style="margin-top: 8px; background: #10b981; border-color: #10b981;">📋 Copy Optimized Prompt</button>';
        html += '</div>';
        html += '</div>';
    }
    
    // Cost Breakdown
    if (costBreakdown) {
        html += '<div style="margin-top: 24px; padding: 12px; background: #e8f4f8; border-radius: 6px; border: 1px solid var(--primary-color);">';
        html += '<h4 style="margin-bottom: 8px;">💰 Analysis Cost</h4>';
        html += `<p style="margin: 4px 0;"><strong>Total Cost:</strong> $${(costBreakdown.cost || 0).toFixed(4)}</p>`;
        html += `<p style="margin: 4px 0;"><strong>Input Tokens:</strong> ${(costBreakdown.input_tokens || 0).toLocaleString()}</p>`;
        html += `<p style="margin: 4px 0;"><strong>Output Tokens:</strong> ${(costBreakdown.output_tokens || 0).toLocaleString()}</p>`;
        html += `<p style="margin: 4px 0;"><strong>Model:</strong> ${costBreakdown.model || 'gpt-4o'}</p>`;
        html += '</div>';
    }
    
    html += '</div>';
    optimizationResults.innerHTML = html;
}

// Copy optimized prompt to clipboard
function copyOptimizedPrompt() {
    const textarea = document.getElementById('optimized-prompt-text');
    if (textarea) {
        textarea.select();
        textarea.setSelectionRange(0, 99999); // For mobile devices
        try {
            document.execCommand('copy');
            // Show temporary success message
            const btn = event.target;
            const originalText = btn.textContent;
            btn.textContent = '✓ Copied!';
            btn.style.background = '#10b981';
            setTimeout(() => {
                btn.textContent = originalText;
                btn.style.background = '#10b981';
            }, 2000);
        } catch (err) {
            alert('Failed to copy. Please select and copy manually.');
        }
    }
}

// Export Batch Agent Results
if (exportBatchAgentResultsBtn) {
    exportBatchAgentResultsBtn.addEventListener('click', () => {
        if (!batchAgentResultsData || batchAgentResultsData.length === 0) {
            showErrorModal('No results to export.');
            return;
        }
        
        // Create CSV
        let csv = 'Index,Input,Original Output,New Output,Selected Foci,Evaluation Type,Evaluation Value\n';
        
        batchAgentResultsData.forEach((result, index) => {
            const input = (result.input || '').replace(/"/g, '""');
            const originalOutput = (result.original_output || '').replace(/"/g, '""');
            const newOutput = (result.new_output || '').replace(/"/g, '""');
            const selectedFoci = (result.selected_foci || []).join('; ');
            const evalType = result.evaluation ? result.evaluation.type : '';
            const evalValue = result.evaluation ? (result.evaluation.value || '') : '';
            
            csv += `${index + 1},"${input}","${originalOutput}","${newOutput}","${selectedFoci}","${evalType}","${evalValue}"\n`;
        });
        
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `batch-agent-results-${new Date().toISOString().split('T')[0]}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    });
}

// ---------------------------------------------------------------------------
// Workspace session export / import (full page state)
// ---------------------------------------------------------------------------
const WORKSPACE_SESSION_VERSION = 1;

function readAblationExperimentConfig(scope) {
    const root = scope || document.getElementById('prompt-analysis-tab');
    if (!root) {
        return {};
    }
    return {
        temperature: root.querySelector('.exp-temperature')?.value ?? '0.7',
        n_baseline: root.querySelector('.exp-n-baseline')?.value ?? '10',
        n_ablated: root.querySelector('.exp-n-ablated')?.value ?? '5',
    };
}

function applyAblationExperimentConfig(config, scope) {
    if (!config || !scope) {
        return;
    }
    const tempEl = scope.querySelector('.exp-temperature');
    const baseEl = scope.querySelector('.exp-n-baseline');
    const ablEl = scope.querySelector('.exp-n-ablated');
    if (tempEl && config.temperature != null) {
        tempEl.value = config.temperature;
    }
    if (baseEl && config.n_baseline != null) {
        baseEl.value = config.n_baseline;
    }
    if (ablEl && config.n_ablated != null) {
        ablEl.value = config.n_ablated;
    }
}

function collectPromptAnalysisWorkspace() {
    const paTab = document.getElementById('prompt-analysis-tab');
    const focusOrder = window.focusOrderSensitivityResults
        || (window.singleAblationResults && window.singleAblationResults.focus_order_sensitivity)
        || null;
    return {
        prompt: promptInput ? promptInput.value : '',
        output: outputInput ? outputInput.value : '',
        foci: foci,
        assessment_payload: window.lastAssessmentApiPayload || null,
        focus_control: {
            weights: { ...focusWeights },
            assessment_foci: assessmentFoci.map(function (f) { return { ...f }; }),
            rewritten_prompt: rewrittenPromptText,
            intended_distribution: { ...intendedDistribution },
            generated_from_adjusted: !!window.generatedFromAdjustedPrompt,
            adjusted_output: adjustedOutput ? adjustedOutput.textContent : '',
        },
        ablation_config: readAblationExperimentConfig(paTab),
        single_ablation: window.singleAblationResults || null,
        experiment_c: {
            comparison: window.experimentCComparison || null,
            explanation_html: window.experimentCExplanationHtml || '',
        },
        quality_eval: {
            criteria: evalCriteriaInput ? evalCriteriaInput.value : '',
            sample_pct: qualityEvalSamplePct ? qualityEvalSamplePct.value : '100',
            results: window.lastQualityEvalResults || null,
        },
        focus_order: {
            results: focusOrder,
            k: focusOrderKSel ? focusOrderKSel.value : '5',
            m: focusOrderMSel ? focusOrderMSel.value : '3',
            sweep_focus: focusOrderSweepFocus ? focusOrderSweepFocus.value : '',
            run_sweep: focusOrderRunSweep ? focusOrderRunSweep.checked : false,
            run_judge: focusOrderRunJudge ? focusOrderRunJudge.checked : false,
            criterion: focusOrderCriterion ? focusOrderCriterion.value : '',
        },
    };
}

function collectWorkspaceSession() {
    const batchTab = document.getElementById('batch-analysis-tab');
    return {
        focalprompt_workspace: true,
        version: WORKSPACE_SESSION_VERSION,
        exported_at: new Date().toISOString(),
        active_tab: currentTab,
        model: { provider: userProvider, model: userModel },
        prompt_analysis: collectPromptAnalysisWorkspace(),
        batch_analysis: {
            prompt: batchPromptInput ? batchPromptInput.value : '',
            foci: batchFoci,
            pairs: batchPairs,
            results: window.batchResultsData || null,
            batch_config: readAblationExperimentConfig(batchTab),
        },
        agent_builder: {
            foci: agentFoci,
            chat_input: chatInput ? chatInput.value : '',
            imported_batch: batchAgentData,
            results: batchAgentResultsData,
            cost_breakdown: window.batchAgentCostBreakdown || null,
        },
        optimization: {
            html: optimizationResults ? optimizationResults.innerHTML : '',
            visible: promptOptimizationSection
                ? promptOptimizationSection.style.display !== 'none'
                : false,
        },
    };
}

function validateWorkspaceSession(data) {
    if (!data || typeof data !== 'object') {
        return 'Invalid file: not a JSON object.';
    }
    if (data.focalprompt_workspace !== true) {
        if (data.baseline_outputs || data.influence_scores || data.ablation_results) {
            return { legacy_ablation: true };
        }
        return 'Unrecognized file: expected a FocalPrompt workspace export.';
    }
    if (data.version != null && data.version !== WORKSPACE_SESSION_VERSION) {
        return 'Unsupported workspace version ' + data.version +
            ' (expected ' + WORKSPACE_SESSION_VERSION + ').';
    }
    return null;
}

function restoreFocusControlState(fc) {
    if (!fc) {
        return;
    }
    if (fc.assessment_foci && fc.assessment_foci.length) {
        assessmentFoci = fc.assessment_foci.map(function (f) { return { ...f }; });
        if (focusControlSection) {
            focusControlSection.classList.remove('hidden');
        }
    }
    if (fc.weights && Object.keys(fc.weights).length && assessmentFoci.length) {
        focusWeights = { ...fc.weights };
        renderSliders();
        updateTotalBudget();
    }
    if (fc.rewritten_prompt) {
        rewrittenPromptText = fc.rewritten_prompt;
        if (rewrittenPrompt) {
            rewrittenPrompt.textContent = rewrittenPromptText;
        }
        if (rewrittenPromptContainer) {
            rewrittenPromptContainer.classList.remove('hidden');
        }
    } else {
        rewrittenPromptText = '';
        if (rewrittenPrompt) {
            rewrittenPrompt.textContent = '';
        }
        if (rewrittenPromptContainer) {
            rewrittenPromptContainer.classList.add('hidden');
        }
    }
    intendedDistribution = fc.intended_distribution ? { ...fc.intended_distribution } : {};
    window.generatedFromAdjustedPrompt = !!fc.generated_from_adjusted;
    if (fc.generated_from_adjusted && fc.adjusted_output) {
        if (adjustedOutput) {
            adjustedOutput.textContent = fc.adjusted_output;
        }
        if (adjustedOutputContainer) {
            adjustedOutputContainer.classList.remove('hidden');
        }
        if (compareIntentBtn) {
            compareIntentBtn.classList.remove('hidden');
        }
    } else {
        if (adjustedOutput) {
            adjustedOutput.textContent = '';
        }
        if (adjustedOutputContainer) {
            adjustedOutputContainer.classList.add('hidden');
        }
        if (compareIntentBtn) {
            compareIntentBtn.classList.add('hidden');
        }
    }
}

function restoreFocusOrderControls(fo) {
    if (!fo) {
        return;
    }
    if (focusOrderKSel && fo.k != null) {
        focusOrderKSel.value = fo.k;
    }
    if (focusOrderMSel && fo.m != null) {
        focusOrderMSel.value = fo.m;
    }
    if (focusOrderRunSweep && fo.run_sweep != null) {
        focusOrderRunSweep.checked = !!fo.run_sweep;
    }
    if (focusOrderRunJudge && fo.run_judge != null) {
        focusOrderRunJudge.checked = !!fo.run_judge;
    }
    if (focusOrderCriterion && fo.criterion != null) {
        focusOrderCriterion.value = fo.criterion;
    }
    refreshFocusOrderControls(window.singleAblationResults);
    if (focusOrderSweepFocus && fo.sweep_focus != null) {
        focusOrderSweepFocus.value = fo.sweep_focus;
    }
}

function restorePromptAnalysisWorkspace(pa) {
    if (!pa) {
        return;
    }
    if (pa.prompt != null && promptInput) {
        promptInput.value = pa.prompt;
    }
    if (pa.output != null && outputInput) {
        outputInput.value = pa.output;
    }
    if (Array.isArray(pa.foci)) {
        foci = pa.foci;
        renderFoci();
        if (foci.length > 0) {
            updateCoverageVisualization();
            updateCoverageStats();
        }
    }
    if (pa.assessment_payload) {
        renderAssessment(pa.assessment_payload);
    } else if (assessmentResults) {
        assessmentResults.innerHTML = '';
        assessmentFoci = [];
        if (focusControlSection) {
            focusControlSection.classList.add('hidden');
        }
    }
    restoreFocusControlState(pa.focus_control);
    if (pa.ablation_config) {
        applyAblationExperimentConfig(pa.ablation_config, document.getElementById('prompt-analysis-tab'));
    }
    if (pa.single_ablation) {
        window.singleAblationResults = pa.single_ablation;
        const skipExperimentC = !!(pa.experiment_c && pa.experiment_c.comparison);
        renderAblationResults(pa.single_ablation, { skipExperimentCRefresh: skipExperimentC });
    } else {
        window.singleAblationResults = null;
        if (ablationResults) {
            ablationResults.innerHTML = '';
        }
        refreshQualityEvalPreview();
        refreshFocusOrderControls(null);
    }
    if (pa.experiment_c && pa.experiment_c.comparison) {
        window.experimentCComparison = pa.experiment_c.comparison;
        window.experimentCExplanationHtml = pa.experiment_c.explanation_html || '';
        paintExperimentCComparison(pa.experiment_c.comparison, true);
        if (explainExperimentCBtn) {
            const nDis = (pa.experiment_c.comparison.summary || {}).n_disagreements || 0;
            explainExperimentCBtn.disabled = nDis === 0;
        }
    } else if (!pa.single_ablation) {
        window.experimentCComparison = null;
        window.experimentCExplanationHtml = '';
        setExperimentCMessage(
            '<p class="empty-state">Run <strong>Ablation Analysis</strong> (Experiment B) first.</p>'
        );
    }
    if (pa.quality_eval) {
        if (evalCriteriaInput && pa.quality_eval.criteria != null) {
            evalCriteriaInput.value = pa.quality_eval.criteria;
        }
        if (qualityEvalSamplePct && pa.quality_eval.sample_pct != null) {
            qualityEvalSamplePct.value = pa.quality_eval.sample_pct;
        }
        refreshQualityEvalPreview();
        if (pa.quality_eval.results) {
            renderQualityEvalResults(pa.quality_eval.results);
        } else if (qualityEvalResults) {
            qualityEvalResults.innerHTML = '';
            window.lastQualityEvalResults = null;
        }
    }
    if (pa.focus_order) {
        restoreFocusOrderControls(pa.focus_order);
        if (pa.focus_order.results) {
            window.focusOrderSensitivityResults = pa.focus_order.results;
            if (window.singleAblationResults) {
                window.singleAblationResults.focus_order_sensitivity = pa.focus_order.results;
            }
            if (focusOrderResults && window.FocalPromptResults) {
                focusOrderResults.innerHTML =
                    window.FocalPromptResults.renderFocusOrderSensitivityHtml(pa.focus_order.results);
            }
        } else if (focusOrderResults) {
            focusOrderResults.innerHTML = '';
            window.focusOrderSensitivityResults = null;
        }
    }
}

function restoreBatchAnalysisWorkspace(ba) {
    if (!ba) {
        return;
    }
    if (batchPromptInput && ba.prompt != null) {
        batchPromptInput.value = ba.prompt;
    }
    if (Array.isArray(ba.foci)) {
        batchFoci = ba.foci.map(function (f) {
            return {
                ...f,
                is_dynamic: f.is_dynamic || false,
                dynamic_type: f.dynamic_type || null,
            };
        });
        renderBatchFoci();
    }
    if (Array.isArray(ba.pairs)) {
        batchPairs = ba.pairs;
        renderPairs();
    }
    if (ba.batch_config) {
        applyAblationExperimentConfig(ba.batch_config, document.getElementById('batch-analysis-tab'));
    }
    if (ba.results) {
        window.batchResultsData = ba.results;
        renderBatchResults(ba.results);
        if (exportResultsBtn) {
            exportResultsBtn.disabled = false;
        }
        if (exportResultsJsonBtn) {
            exportResultsJsonBtn.disabled = false;
        }
    } else {
        window.batchResultsData = null;
        if (batchResults) {
            batchResults.innerHTML = '';
        }
        if (exportResultsBtn) {
            exportResultsBtn.disabled = true;
        }
        if (exportResultsJsonBtn) {
            exportResultsJsonBtn.disabled = true;
        }
    }
    updateBatchAnalysisButton();
}

function restoreAgentBuilderWorkspace(ab) {
    if (!ab) {
        return;
    }
    if (Array.isArray(ab.foci)) {
        agentFoci = ab.foci;
        renderAgentFoci();
    }
    if (chatInput && ab.chat_input != null) {
        chatInput.value = ab.chat_input;
    }
    batchAgentData = ab.imported_batch || null;
    batchAgentResultsData = ab.results || [];
    window.batchAgentCostBreakdown = ab.cost_breakdown || null;
    if (batchAgentResultsData.length) {
        renderBatchAgentResults(batchAgentResultsData, window.batchAgentCostBreakdown);
        if (batchAgentReportingSection) {
            batchAgentReportingSection.style.display = 'block';
        }
        if (exportBatchAgentResultsBtn) {
            exportBatchAgentResultsBtn.disabled = false;
        }
        updateBatchAgentReporting();
    } else if (batchAgentResults) {
        batchAgentResults.innerHTML = '';
        if (exportBatchAgentResultsBtn) {
            exportBatchAgentResultsBtn.disabled = true;
        }
    }
}

function restoreWorkspaceSession(data) {
    if (data.model && data.model.provider && data.model.model) {
        persistModelSelection(data.model.provider, data.model.model);
        updateModelSelector(data.model.provider);
    }
    restorePromptAnalysisWorkspace(data.prompt_analysis);
    restoreBatchAnalysisWorkspace(data.batch_analysis);
    restoreAgentBuilderWorkspace(data.agent_builder);
    if (data.optimization) {
        if (optimizationResults) {
            optimizationResults.innerHTML = data.optimization.html || '';
        }
        if (promptOptimizationSection) {
            promptOptimizationSection.style.display = data.optimization.visible ? 'block' : 'none';
        }
    }
    if (data.active_tab) {
        switchTab(data.active_tab);
    }
}

function exportWorkspaceSessionFile() {
    const payload = collectWorkspaceSession();
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'focalprompt-workspace-' + new Date().toISOString().split('T')[0] + '.json';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

function importWorkspaceSessionFile(file) {
    const reader = new FileReader();
    reader.onload = function () {
        let data;
        try {
            data = JSON.parse(reader.result);
        } catch (err) {
            showErrorModal('Could not parse workspace file: ' + err.message);
            return;
        }
        const validation = validateWorkspaceSession(data);
        if (typeof validation === 'string') {
            showErrorModal(validation);
            return;
        }
        if (validation && validation.legacy_ablation) {
            if (!confirm('This file looks like an ablation-only export. Import it into the current workspace?')) {
                return;
            }
            window.singleAblationResults = data;
            renderAblationResults(data);
            switchTab('prompt-analysis');
            alert('Ablation results imported. Run assessment or export a full workspace next time to save everything.');
            return;
        }
        if (!confirm('Import workspace? This replaces current data across all tabs.')) {
            return;
        }
        try {
            restoreWorkspaceSession(data);
            alert('Workspace imported successfully. You can continue from where you left off.');
        } catch (err) {
            showErrorModal('Failed to restore workspace: ' + err.message);
            console.error('Workspace import error:', err);
        }
    };
    reader.onerror = function () {
        showErrorModal('Could not read workspace file.');
    };
    reader.readAsText(file);
}

window.collectWorkspaceSession = collectWorkspaceSession;
window.restoreWorkspaceSession = restoreWorkspaceSession;

// Make functions available globally
window.removePair = removePair;
window.removeBatchFocus = removeBatchFocus;

// Account / credit / Stripe UI removed — local toolkit uses BYO inference credentials.
