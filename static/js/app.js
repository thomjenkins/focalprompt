// FocalPrompt Web Application JavaScript

let foci = [];
let agentFoci = []; // Separate foci for agent builder
let batchFoci = []; // Separate foci for batch analysis
let batchPairs = []; // Store input-output pairs for batch analysis
let currentTab = 'documentation'; // Track current tab (defaults to documentation)

// Settings management
let userProvider = localStorage.getItem('focalprompt_provider') || 'openai';
let userApiKey = localStorage.getItem('focalprompt_api_key') || '';
let userModel = localStorage.getItem('focalprompt_model') || 'gpt-4o-mini';

// Model lists for each provider
const providerModels = {
    openai: [
        { value: 'gpt-4o-mini', label: 'gpt-4o-mini (Fast, Cheap)' },
        { value: 'gpt-4o', label: 'gpt-4o (Balanced)' },
        { value: 'gpt-4-turbo', label: 'gpt-4-turbo (High Quality)' },
        { value: 'gpt-3.5-turbo', label: 'gpt-3.5-turbo (Legacy)' }
    ],
    anthropic: [
        { value: 'claude-3-5-sonnet-20241022', label: 'Claude 3.5 Sonnet (Recommended)' },
        { value: 'claude-3-5-haiku-20241022', label: 'Claude 3.5 Haiku (Fast)' },
        { value: 'claude-3-opus-20240229', label: 'Claude 3 Opus (High Quality)' },
        { value: 'claude-3-sonnet-20240229', label: 'Claude 3 Sonnet' },
        { value: 'claude-3-haiku-20240307', label: 'Claude 3 Haiku' }
    ],
    google: [
        { value: 'gemini-1.5-pro', label: 'Gemini 1.5 Pro (Recommended)' },
        { value: 'gemini-1.5-flash', label: 'Gemini 1.5 Flash (Fast)' },
        { value: 'gemini-pro', label: 'Gemini Pro' }
    ],
    grok: [
        { value: 'grok-beta', label: 'Grok Beta' },
        { value: 'grok-2', label: 'Grok 2' }
    ]
};

// Default models for each provider
const defaultModels = {
    openai: 'gpt-4o-mini',
    anthropic: 'claude-3-5-sonnet-20241022',
    google: 'gemini-1.5-pro',
    grok: 'grok-beta'
};

// Helper function to update model selector based on provider
function updateModelSelector(provider) {
    const modelSelect = document.getElementById('model-select');
    if (!modelSelect) return;
    
    const models = providerModels[provider] || providerModels.openai;
    modelSelect.innerHTML = models.map(m => 
        `<option value="${m.value}">${m.label}</option>`
    ).join('');
    
    // Set default model for provider if current model not available
    const currentModel = userModel;
    const availableModels = models.map(m => m.value);
    if (!availableModels.includes(currentModel)) {
        userModel = defaultModels[provider] || models[0].value;
        modelSelect.value = userModel;
    } else {
        modelSelect.value = currentModel;
    }
}

// Helper function to get API request headers
function getApiHeaders() {
    const headers = {
        'Content-Type': 'application/json',
    };
    
    // Add session ID if user is logged in
    const sessionId = localStorage.getItem('session_id');
    if (sessionId) {
        headers['X-Session-ID'] = sessionId;
    }
    
    return headers;
}

// Helper function to get API request body with API key, model, and provider
function getApiBody(additionalData = {}) {
    const body = { ...additionalData };
    if (userApiKey) {
        body.api_key = userApiKey;
    }
    body.model = userModel;
    body.provider = userProvider;
    return body;
}

// DOM Elements
const promptInput = document.getElementById('prompt-input');
const outputInput = document.getElementById('output-input');
const detectFociBtn = document.getElementById('detect-foci-btn');
const addFocusBtn = document.getElementById('add-focus-btn');
const clearFociBtn = document.getElementById('clear-foci-btn');
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

// Check health on page load
window.addEventListener('DOMContentLoaded', async () => {
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
            userProvider = newProvider;
            updateModelSelector(newProvider);
            userModel = modelSelect.value;
        });
    }
    
    if (apiKeyInput) {
        apiKeyInput.value = userApiKey;
    }
    if (modelSelect) {
        modelSelect.value = userModel;
    }
    
    // Toggle settings visibility
    if (toggleSettingsBtn && settingsContent) {
        let isExpanded = localStorage.getItem('focalprompt_settings_expanded') === 'true';
        if (isExpanded) {
            settingsContent.style.display = 'block';
            toggleSettingsBtn.textContent = 'Hide';
        }
        
        toggleSettingsBtn.addEventListener('click', () => {
            isExpanded = !isExpanded;
            settingsContent.style.display = isExpanded ? 'block' : 'none';
            toggleSettingsBtn.textContent = isExpanded ? 'Hide' : 'Show';
            localStorage.setItem('focalprompt_settings_expanded', isExpanded.toString());
        });
    }
    
    // Save settings
    if (saveSettingsBtn) {
        saveSettingsBtn.addEventListener('click', () => {
            const provider = providerSelect.value;
            const apiKey = apiKeyInput.value.trim();
            const model = modelSelect.value;
            
            localStorage.setItem('focalprompt_provider', provider);
            userProvider = provider;
            
            if (apiKey) {
                localStorage.setItem('focalprompt_api_key', apiKey);
                userApiKey = apiKey;
                apiKeyStatus.textContent = '✓ Settings saved';
                apiKeyStatus.style.color = '#28a745';
                setTimeout(() => {
                    apiKeyStatus.textContent = '';
                }, 3000);
            } else {
                localStorage.removeItem('focalprompt_api_key');
                userApiKey = '';
            }
            
            localStorage.setItem('focalprompt_model', model);
            userModel = model;
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
    
    try {
        const response = await fetch('/api/health');
        const data = await response.json();
        
        if (!data.api_key_set) {
            showError('⚠️ OPENAI_API_KEY is not set. Please set it in your environment and restart the server.');
        }
    } catch (error) {
        console.error('Health check failed:', error);
    }
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
    
    showLoading('Detecting foci from prompt...');
    
    try {
        const response = await fetch('/api/detect-foci', {
            method: 'POST',
            headers: getApiHeaders(),
            body: JSON.stringify(getApiBody({ prompt })),
        });
        
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
        renderFoci();
        
    } catch (error) {
        showError('Error detecting foci: ' + error.message);
        console.error('Detect foci error:', error);
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
            dynamic_type: null
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

// Color palette for foci
const focusColors = [
    '#dbeafe', '#d1fae5', '#fef3c7', '#fce7f3', '#e0e7ff',
    '#fef2f2', '#ecfdf5', '#f0fdfa', '#fefce8', '#fef2f2',
    '#f3e8ff', '#ede9fe', '#e0f2fe', '#f0f9ff', '#f5f3ff'
];

// Render Foci
function renderFoci() {
    if (foci.length === 0) {
        fociContainer.innerHTML = '<p class="empty-state">No foci defined yet. Click "Auto-Detect Foci" or "Add Focus Manually" to get started.</p>';
        promptVisualization.classList.add('hidden');
        coverageIndicator.classList.add('hidden');
        coverageWarning.classList.add('hidden');
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
        <div class="focus-item" data-focus-index="${index}" style="border-left: 4px solid ${focus.colorDark};">
            <div class="focus-item-header">
                <div class="focus-item-title">
                    ${index + 1}. ${escapeHtml(focus.focus)}
                    ${isDynamic ? `<span style="margin-left: 8px; padding: 2px 6px; background: #fef3c7; border-radius: 4px; font-size: 0.75em; color: #92400e;">Dynamic: ${dynamicType}</span>` : ''}
                </div>
                <button class="focus-item-remove" onclick="removeFocus(${index})">×</button>
            </div>
            <div class="focus-item-section">
                <strong>Prompt Section:</strong> ${escapeHtml(focus.prompt_section)}
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
    
    // Update visualization
    updateCoverageVisualization();
    updateCoverageStats();
    
    // Enable ablation analysis if we have foci
    if (foci.length > 0) {
        runAblationBtn.disabled = false;
    } else {
        runAblationBtn.disabled = true;
    }
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
        const section = focus.prompt_section;
        if (section) {
            const startIndex = prompt.toLowerCase().indexOf(section.toLowerCase());
            if (startIndex !== -1) {
                coveredRanges.push({
                    start: startIndex,
                    end: startIndex + section.length,
                    focusIndex: index,
                    focus: focus
                });
            }
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
    
    // Store for sliders
    assessmentFoci = allFoci;
    
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

// Initialize sliders from assessment results
function initializeSlidersFromAssessment(assessmentFoci) {
    if (!assessmentFoci || assessmentFoci.length === 0) {
        slidersContainer.innerHTML = '<p class="empty-state">No assessment data available.</p>';
        return;
    }
    
    // Initialize weights from assessment scores (including 0 scores)
    focusWeights = {};
    assessmentFoci.forEach((focus, index) => {
        focusWeights[index] = focus.score || 0;
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
                        if (otherSlider && otherDisplay) {
                            otherSlider.value = focusWeights[i];
                            otherDisplay.textContent = `${focusWeights[i].toFixed(1)}%`;
                        }
                    }
                });
            }
            
            focusWeights[index] = newValue;
            valueDisplay.textContent = `${newValue.toFixed(1)}%`;
            
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
            focusWeights[index] = focus.score || 0;
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
        
        showLoading('Rewriting prompt with focus emphasis...');
        
        try {
            // Use assessment foci with their weights
            const weights = assessmentFoci.map((focus, index) => ({
                focus: focus.focus,
                prompt_section: focus.prompt_section,
                weight: focusWeights[index] || 0
            }));
            
            const response = await fetch('/api/rewrite-prompt', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ 
                    prompt,
                    foci: weights
                }),
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to rewrite prompt');
            }
            
            rewrittenPromptText = data.rewritten_prompt;
            rewrittenPrompt.textContent = rewrittenPromptText;
            rewrittenPromptContainer.classList.remove('hidden');
            
            // Store intended distribution for comparison (normalize to 100)
            const totalWeight = weights.reduce((sum, w) => sum + w.weight, 0);
            weights.forEach(w => {
                intendedDistribution[w.focus] = totalWeight > 0 ? (w.weight / totalWeight) * 100 : 0;
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
        
        showLoading('Generating output with focused prompt...');
        
        try {
            const response = await fetch('/api/generate-output', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ prompt: rewrittenPromptText }),
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to generate output');
            }
            
            outputInput.value = data.output;
            
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
        
        showLoading('Running ablation analysis... This may take several minutes (20 baseline samples + ablated outputs).');
        
        try {
            // Create AbortController for timeout (10 minutes = 600000ms)
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 600000); // 10 minutes
            
            const response = await fetch('/api/ablation-analysis', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    prompt: prompt,
                    foci: foci,
                    model: 'gpt-4o-mini',
                    num_samples: 20  // Use 20 samples to determine baseline noise
                }),
                signal: controller.signal
            });
            
            clearTimeout(timeoutId);
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to run ablation analysis');
            }
            
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
function renderAblationResults(data) {
    // Store results globally for optimization analysis
    window.singleAblationResults = data;
    console.log('Ablation data:', data); // Debug log
    let html = '<div class="ablation-summary">';
    html += '<h3>Focus Influence Summary</h3>';
    html += '<p>Ablation analysis measures how much each focus section contributes to the output by removing one focus at a time and comparing the results to the baseline.</p>';
    html += '<div class="ablation-explanation" style="background: #f5f5f5; padding: 12px; border-radius: 6px; margin-top: 12px; font-size: 0.9em;">';
    html += '<strong>Understanding the Numbers:</strong><ul style="margin: 8px 0 0 20px; padding: 0;">';
    html += '<li><strong>Influence:</strong> How much removing this focus changes the output. Higher = more important. All values sum to 100%.</li>';
    html += '<li><strong>Similarity:</strong> How similar the output is when this focus is removed (compared to full prompt). Higher = less impact. Inverse of influence.</li>';
    html += '<li><strong>Visual:</strong> Bar chart representation of the influence percentage.</li>';
    html += '</ul></div>';
    html += '</div>';
    
    // Add noise information at the top
    if (data.noise_threshold !== null && data.noise_threshold !== undefined) {
        html += '<div class="noise-info" style="margin-bottom: 20px; padding: 16px; background: #fff3cd; border-radius: 6px; border: 1px solid #ffc107;">';
        html += '<h4 style="margin: 0 0 8px 0; color: #856404;">📊 Baseline Noise Analysis</h4>';
        html += `<p style="margin: 4px 0; font-size: 0.9em;"><strong>Baseline Samples:</strong> ${data.num_baseline_samples || 20}</p>`;
        if (data.baseline_mean_similarity !== null) {
            html += `<p style="margin: 4px 0; font-size: 0.9em;"><strong>Mean Baseline Similarity:</strong> ${(data.baseline_mean_similarity * 100).toFixed(2)}%</p>`;
        }
        if (data.baseline_std !== null) {
            html += `<p style="margin: 4px 0; font-size: 0.9em;"><strong>Baseline Std Dev:</strong> ${(data.baseline_std * 100).toFixed(2)}%</p>`;
        }
        html += `<p style="margin: 4px 0; font-size: 0.9em;"><strong>Noise Threshold (95% CI):</strong> ${(data.noise_threshold * 100).toFixed(2)}%</p>`;
        html += '<p style="margin: 8px 0 0 0; font-size: 0.85em; color: #856404;">If similarity is below the noise threshold, the influence is statistically significant (beyond baseline noise).</p>';
        html += '</div>';
    }
    
    html += '<table class="ablation-influence-table">';
    html += '<thead><tr><th>Focus</th><th>Influence</th><th>Similarity</th><th>Significant?</th><th>Visual</th></tr></thead>';
    html += '<tbody>';
    
    // Sort by influence (highest first)
    const sortedScores = [...data.influence_scores].sort((a, b) => 
        b.normalized_influence - a.normalized_influence
    );
    
    sortedScores.forEach((item, idx) => {
        // Try multiple ways to get the focus name
        let focusName = item.focus || item.focus_name;
        
        // If still not found, try to match with original foci
        if (!focusName && data.ablation_results && data.ablation_results[idx]) {
            focusName = data.ablation_results[idx].focus || data.ablation_results[idx].focus_name;
        }
        
        // If still not found, use index
        if (!focusName) {
            focusName = `Focus ${idx + 1}`;
        }
        
        // Ensure normalized_influence is treated as a number for calculations and display
        const normalizedInfluence = parseFloat(item.normalized_influence) || 0;
        const similarityValue = parseFloat(item.similarity) || 0;
        
        // Determine significance indicator
        let significanceHtml = '';
        if (item.is_significant === true) {
            significanceHtml = '<span style="color: #28a745; font-weight: bold;">✓ Significant</span>';
        } else if (item.is_significant === false) {
            significanceHtml = '<span style="color: #6c757d;">Within Noise</span>';
        } else {
            significanceHtml = '<span style="color: #6c757d;">N/A</span>';
        }
        
        html += `
            <tr>
                <td class="focus-name">${escapeHtml(focusName)}</td>
                <td class="influence-value">${normalizedInfluence.toFixed(1)}%</td>
                <td class="similarity-value">${(similarityValue * 100).toFixed(1)}%</td>
                <td class="significance-value">${significanceHtml}</td>
                <td>
                    <div class="influence-bar">
                        <div class="influence-bar-fill" style="width: ${normalizedInfluence}%"></div>
                    </div>
                </td>
            </tr>
        `;
    });
    
    html += '</tbody></table>';
    
    // Add expandable section for all outputs
    html += '<div class="ablation-outputs-section" style="margin-top: 24px;">';
    html += '<button id="toggle-all-outputs" class="btn btn-outline" style="margin-bottom: 12px;">📄 Show All Outputs</button>';
    html += '<div id="all-outputs-container" class="hidden" style="margin-top: 12px;">';
    
    // Baseline output
    html += '<div class="output-comparison-item" style="margin-bottom: 20px; padding: 16px; border: 1px solid #ddd; border-radius: 6px; background: #f9f9f9;">';
    html += '<h4 style="margin: 0 0 8px 0; color: #2c3e50;">📊 Baseline Output (Full Prompt)</h4>';
    html += `<div class="output-text" style="background: white; padding: 12px; border-radius: 4px; max-height: 300px; overflow-y: auto; font-family: monospace; font-size: 0.9em; white-space: pre-wrap;">${escapeHtml(data.baseline_output)}</div>`;
    html += '</div>';
    
    // Ablated outputs
    if (data.ablation_results && data.ablation_results.length > 0) {
        // Match ablation results with influence scores to show in order of influence
        const ablationMap = new Map();
        data.ablation_results.forEach(ablation => {
            ablationMap.set(ablation.focus || ablation.focus_name, ablation);
        });
        
        sortedScores.forEach((item, idx) => {
            const focusName = item.focus || item.focus_name || `Focus ${idx + 1}`;
            const ablation = ablationMap.get(focusName) || data.ablation_results[idx];
            
            if (ablation && ablation.ablated_output) {
                const itemInfluence = parseFloat(item.normalized_influence) || 0;
                const itemSimilarity = parseFloat(item.similarity) || 0;
                
                html += '<div class="output-comparison-item" style="margin-bottom: 20px; padding: 16px; border: 1px solid #ddd; border-radius: 6px; background: #f9f9f9;">';
                html += `<h4 style="margin: 0 0 8px 0; color: #2c3e50;">🔍 Ablated Output: ${escapeHtml(focusName)}</h4>`;
                html += `<p style="margin: 0 0 8px 0; font-size: 0.9em; color: #666;">Influence: ${itemInfluence.toFixed(1)}% | Similarity: ${(itemSimilarity * 100).toFixed(1)}%</p>`;
                html += `<div class="output-text" style="background: white; padding: 12px; border-radius: 4px; max-height: 300px; overflow-y: auto; font-family: monospace; font-size: 0.9em; white-space: pre-wrap;">${escapeHtml(ablation.ablated_output)}</div>`;
                html += '</div>';
            }
        });
    }
    
    html += '</div>'; // all-outputs-container
    html += '</div>'; // ablation-outputs-section
    
    // Add cost breakdown
    if (data.cost_breakdown) {
        const cost = data.cost_breakdown;
        html += '<div class="cost-breakdown" style="margin-top: 20px; padding: 16px; background: #e8f4f8; border-radius: 6px; border: 1px solid #bee5eb;">';
        html += '<h4 style="margin: 0 0 12px 0; color: #0c5460;">💰 Cost Breakdown</h4>';
        html += '<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; font-size: 0.9em;">';
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
        html += '</div>';
    }
    
    // Add download button
    html += '<div style="margin-top: 16px;">';
    html += '<button id="download-ablation-results" class="btn btn-primary">💾 Download All Results (JSON)</button>';
    html += '</div>';
    
    // Add details section
    html += '<div class="ablation-details" style="margin-top: 24px;">';
    html += '<h4>Analysis Details</h4>';
    
    if (data.baseline_variance !== null) {
        html += `<p><strong>Baseline Variance:</strong> ${data.baseline_variance.toFixed(6)}</p>`;
    }
    
    // Count significant influences
    if (data.influence_scores) {
        const significantCount = data.influence_scores.filter(item => item.is_significant === true).length;
        const totalCount = data.influence_scores.length;
        html += `<p style="margin-top: 12px;"><strong>Significant Influences:</strong> ${significantCount} out of ${totalCount} foci show influence beyond baseline noise.</p>`;
    }
    
    html += '<p style="margin-top: 16px;"><strong>How It Works:</strong></p>';
    html += '<ul style="margin-top: 8px; padding-left: 20px;">';
    html += '<li>1. Generate baseline output using the full prompt</li>';
    html += '<li>2. For each focus, remove it and generate a new output</li>';
    html += '<li>3. Compare each ablated output to the baseline using semantic similarity (embeddings)</li>';
    html += '<li>4. Calculate influence: <code>influence = 1 - similarity</code> (higher influence = more impact)</li>';
    html += '<li>5. Normalize all influence scores to sum to 100%</li>';
    html += '</ul>';
    html += '<p style="margin-top: 12px;"><strong>Key Insight:</strong> A focus with high influence (e.g., 15%) means removing it significantly changes the output. A focus with low influence (e.g., 3%) means the output stays similar even without it.</p>';
    html += '</div>';
    
    ablationResults.innerHTML = html;
    
    // Add event listeners for new buttons
    const toggleOutputsBtn = document.getElementById('toggle-all-outputs');
    const allOutputsContainer = document.getElementById('all-outputs-container');
    const downloadBtn = document.getElementById('download-ablation-results');
    
    if (toggleOutputsBtn && allOutputsContainer) {
        toggleOutputsBtn.addEventListener('click', () => {
            if (allOutputsContainer.classList.contains('hidden')) {
                allOutputsContainer.classList.remove('hidden');
                toggleOutputsBtn.textContent = '📄 Hide All Outputs';
            } else {
                allOutputsContainer.classList.add('hidden');
                toggleOutputsBtn.textContent = '📄 Show All Outputs';
            }
        });
    }
    
    if (downloadBtn) {
        downloadBtn.addEventListener('click', () => {
            // Create downloadable JSON with all results
            const downloadData = {
                timestamp: new Date().toISOString(),
                baseline_output: data.baseline_output,
                ablation_results: data.ablation_results,
                influence_scores: data.influence_scores,
                summary: data.summary,
                baseline_variance: data.baseline_variance,
                cost_breakdown: data.cost_breakdown || null
            };
            
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
    if (!fociWeightsResults) return;
    
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
    
    // Chat weight
    const chatWeightPercent = (data.chat_weight * 100).toFixed(1);
    html += `
        <div class="chat-weight-display">
            <h4 style="margin: 0 0 8px 0;">Chat Content Weight</h4>
            <p style="margin: 4px 0; font-size: 0.9em;">${escapeHtml(data.chat_weight_explanation || '')}</p>
            <div style="display: flex; align-items: center; gap: 12px; margin-top: 12px;">
                <div class="weight-value">${chatWeightPercent}%</div>
                <div class="weight-bar">
                    <div class="weight-bar-fill" style="width: ${chatWeightPercent}%">
                        ${data.chat_weight >= 0.1 ? chatWeightPercent + '%' : ''}
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
                        // Find the original focus to get prompt_section
                        const originalFocus = agentFoci.find(f => f.focus === fw.focus);
                        return {
                            ...fw,
                            prompt_section: originalFocus ? originalFocus.prompt_section : ''
                        };
                    }),
                    chat_content: chatContent,
                    chat_weight: window.fociWeightsData.chat_weight
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

// Update manual input fields based on dynamic foci
function updateManualInputFields() {
    if (!manualInputFields) return;
    
    // Get unique dynamic types from batchFoci
    const dynamicTypes = new Set();
    batchFoci.forEach(focus => {
        if (focus.is_dynamic && focus.dynamic_type) {
            dynamicTypes.add(focus.dynamic_type);
        }
    });
    
    // Field labels mapping
    const fieldLabels = {
        'chat': 'Chat Content',
        'rag': 'RAG Context',
        'tools': 'Tool Results',
        'other': 'Other Dynamic Input'
    };
    
    // Field IDs mapping
    const fieldIds = {
        'chat': 'manual-chat-content',
        'rag': 'manual-rag-context',
        'tools': 'manual-tool-results',
        'other': 'manual-other-input'
    };
    
    // Build HTML for dynamic input fields
    let html = '';
    if (dynamicTypes.size === 0) {
        // Default to chat_content if no dynamic foci
        html = `<textarea 
            id="manual-chat-content" 
            class="textarea-large" 
            placeholder="Chat Content (Input)..."
            rows="3"
        ></textarea>`;
    } else {
        // Show fields for each dynamic type
        ['chat', 'rag', 'tools', 'other'].forEach(type => {
            if (dynamicTypes.has(type)) {
                html += `<textarea 
                    id="${fieldIds[type]}" 
                    class="textarea-large" 
                    placeholder="${fieldLabels[type]} (Dynamic Input)..."
                    rows="3"
                ></textarea>`;
            }
        });
    }
    
    manualInputFields.innerHTML = html;
}

// Batch Analysis: Manual Entry
if (addPairBtn) {
    addPairBtn.addEventListener('click', () => {
        const output = manualOutput ? manualOutput.value.trim() : '';
        
        if (!output) {
            showErrorModal('Please fill in the Output field.');
            return;
        }
        
        // Collect all dynamic inputs
        const inputs = {};
        
        // Get dynamic types from foci
        const dynamicTypes = new Set();
        batchFoci.forEach(focus => {
            if (focus.is_dynamic && focus.dynamic_type) {
                dynamicTypes.add(focus.dynamic_type);
            }
        });
        
        // Field IDs mapping
        const fieldIds = {
            'chat': 'manual-chat-content',
            'rag': 'manual-rag-context',
            'tools': 'manual-tool-results',
            'other': 'manual-other-input'
        };
        
        // Collect values from each dynamic input field
        if (dynamicTypes.size === 0) {
            // Default to chat_content if no dynamic foci
            const chatField = document.getElementById('manual-chat-content');
            if (chatField) {
                inputs.chat_content = chatField.value.trim();
            }
        } else {
            dynamicTypes.forEach(type => {
                const fieldId = fieldIds[type];
                const field = document.getElementById(fieldId);
                if (field) {
                    const value = field.value.trim();
                    if (type === 'chat') {
                        inputs.chat_content = value;
                    } else if (type === 'rag') {
                        inputs.rag_context = value;
                    } else if (type === 'tools') {
                        inputs.tool_results = value;
                    } else if (type === 'other') {
                        inputs.other_input = value;
                    }
                }
            });
        }
        
        batchPairs.push({
            inputs: inputs,
            output: output
        });
        
        renderPairs();
        updateBatchAnalysisButton();
        updateCostEstimate();
        
        // Clear form
        if (manualInputFields) {
            const textareas = manualInputFields.querySelectorAll('textarea');
            textareas.forEach(ta => ta.value = '');
        }
        if (manualOutput) manualOutput.value = '';
    });
}

// Batch Analysis: Render Pairs
function renderPairs() {
    if (!pairsContainer) return;
    
    if (batchPairs.length === 0) {
        pairsContainer.innerHTML = '<p class="empty-state">No pairs added yet. Upload a CSV file or add pairs manually.</p>';
        return;
    }
    
    let html = `<h3 style="margin-bottom: 12px;">${batchPairs.length} Pair(s) Added</h3>`;
    html += '<div style="display: flex; flex-direction: column; gap: 12px;">';
    
    batchPairs.forEach((pair, index) => {
        // Handle both old and new structure
        const inputs = pair.inputs || {};
        const chatContent = inputs.chat_content || pair.chat_content || '';
        const ragContext = inputs.rag_context || '';
        const toolResults = inputs.tool_results || '';
        const output = pair.output || '';
        
        html += `
            <div class="pair-item" style="padding: 12px; background: #f8fafc; border-radius: 6px; border: 1px solid var(--border-color);">
                <div style="display: flex; justify-content: space-between; align-items: start;">
                    <div style="flex: 1;">
                        <strong>Pair ${index + 1}</strong>
                        ${chatContent ? `<p style="margin: 4px 0; font-size: 0.9em; color: var(--text-secondary);">
                            Chat: ${escapeHtml(chatContent.substring(0, 100))}${chatContent.length > 100 ? '...' : ''}
                        </p>` : ''}
                        ${ragContext ? `<p style="margin: 4px 0; font-size: 0.9em; color: var(--text-secondary);">
                            RAG: ${escapeHtml(ragContext.substring(0, 100))}${ragContext.length > 100 ? '...' : ''}
                        </p>` : ''}
                        ${toolResults ? `<p style="margin: 4px 0; font-size: 0.9em; color: var(--text-secondary);">
                            Tools: ${escapeHtml(toolResults.substring(0, 100))}${toolResults.length > 100 ? '...' : ''}
                        </p>` : ''}
                        <p style="margin: 4px 0; font-size: 0.9em; color: var(--text-secondary);">
                            Output: ${escapeHtml(output.substring(0, 100))}${output.length > 100 ? '...' : ''}
                        </p>
                    </div>
                    <button onclick="removePair(${index})" class="btn btn-outline btn-small" style="margin-left: 12px;">Remove</button>
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    pairsContainer.innerHTML = html;
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
        // Check if we have prompt from input OR can reconstruct from foci
        const hasPromptInput = batchPromptInput ? batchPromptInput.value.trim().length > 0 : false;
        const canReconstructFromFoci = batchFoci.length > 0 && batchFoci.every(f => f.prompt_section && f.prompt_section.trim().length > 0);
        const hasPrompt = hasPromptInput || canReconstructFromFoci;
        
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
    const numFoci = batchFoci.length;
    const numSamples = 20; // Default baseline samples
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
    const chatAblatedPromptTokens = 1800; // Prompt without chat content
    const outputTokens = 200; // Typical output length
    
    // Batch analysis optimization: noise calculated once for entire batch
    // 1. Baseline noise calculation: numSamples (once for entire batch, not per pair)
    const baselineNoiseInputTokens = numSamples * promptTokens;
    const baselineNoiseOutputTokens = numSamples * outputTokens;
    
    // 2. Per pair: ONE baseline output (not 20)
    const baselineInputTokensPerPair = promptTokens;
    const baselineOutputTokensPerPair = outputTokens;
    
    // 3. Ablated outputs: N foci per pair
    const ablatedInputTokensPerPair = numFoci * ablatedPromptTokens;
    const ablatedOutputTokensPerPair = numFoci * outputTokens;
    
    // 4. Chat ablation: 1 sample per pair
    const chatAblatedInputTokensPerPair = chatAblatedPromptTokens;
    const chatAblatedOutputTokensPerPair = outputTokens;
    
    // Total tokens per pair (excluding noise calculation)
    const totalInputTokensPerPair = baselineInputTokensPerPair + ablatedInputTokensPerPair + chatAblatedInputTokensPerPair;
    const totalOutputTokensPerPair = baselineOutputTokensPerPair + ablatedOutputTokensPerPair + chatAblatedOutputTokensPerPair;
    
    // Embeddings per pair
    // 1 baseline output + N ablated + 1 chat-ablated
    const embeddingTokensPerPair = (1 + numFoci + 1) * outputTokens;
    
    // Embeddings for noise calculation (once for entire batch)
    const embeddingTokensForNoise = numSamples * outputTokens;
    
    // Total for all pairs (including one-time noise calculation)
    const totalInputTokens = baselineNoiseInputTokens + (totalInputTokensPerPair * numPairs);
    const totalOutputTokens = baselineNoiseOutputTokens + (totalOutputTokensPerPair * numPairs);
    const totalEmbeddingTokens = embeddingTokensForNoise + (embeddingTokensPerPair * numPairs);
    
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
    html += `Baseline Samples: ${numSamples} (once for batch)<br>`;
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
    html += '<p style="margin-top: 4px; font-size: 0.85em; color: #856404;">💡 Optimized: Noise calculated once for entire batch (not per pair).</p>';
    
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
        return {
            inputs: inputs,
            output: pair.output,
            prompt: batchPromptInput.value.trim()
        };
    });
    
    // Generate session ID for checkpointing
    const sessionId = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
    
    showLoading(`Running batch analysis on ${batchPairs.length} pair(s)... This may take a very long time.`);
    if (batchProgress) {
        batchProgress.classList.remove('hidden');
        batchProgressText.textContent = `Starting analysis...`;
    }
    
    // Store interim results
    let interimResults = [];
    let interimStatistics = {};
    let completedCount = 0;
    
    try {
        console.log('Sending streaming request to /api/batch-ablation-analysis-stream');
        const response = await fetch('/api/batch-ablation-analysis-stream', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                pairs: pairsWithPrompt,
                foci: batchFoci,
                model: 'gpt-4o-mini',
                num_samples: 20,
                session_id: sessionId,
                resume: false
            })
        });
        
        if (!response.ok) {
            // Try to parse error, but SSE might not be JSON
            let errorMsg = 'Failed to start batch analysis';
            try {
                const errorData = await response.json();
                errorMsg = errorData.error || errorMsg;
            } catch (e) {
                errorMsg = `HTTP ${response.status}: ${response.statusText}`;
            }
            throw new Error(errorMsg);
        }
        
        // Read streaming response
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || ''; // Keep incomplete line in buffer
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        handleStreamEvent(data);
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
                handleStreamEvent(data);
            } catch (e) {
                console.error('Error parsing final SSE data:', e);
            }
        }
        
    } catch (error) {
        showError('Error running batch analysis: ' + error.message);
        console.error('Batch analysis error:', error);
    } finally {
        hideLoading();
        if (batchProgress) {
            batchProgress.classList.add('hidden');
        }
    }
    
    function handleStreamEvent(data) {
        console.log('SSE Event:', data.type, data);
        
        switch (data.type) {
            case 'progress':
                if (batchProgressText) {
                    if (data.stage === 'noise_calculation') {
                        if (data.sample) {
                            batchProgressText.textContent = `Calculating noise: ${data.sample}/${data.total} samples...`;
                        } else {
                            batchProgressText.textContent = data.message || 'Calculating baseline noise...';
                        }
                    } else if (data.stage === 'processing') {
                        batchProgressText.textContent = `${data.message} (${data.completed}/${data.total} completed)`;
                    } else if (data.stage === 'calculating_stats') {
                        batchProgressText.textContent = data.message || 'Calculating final statistics...';
                    } else {
                        batchProgressText.textContent = data.message || 'Processing...';
                    }
                }
                break;
                
            case 'pair_complete':
                completedCount = data.completed || 0;
                if (batchProgressText) {
                    batchProgressText.textContent = `Completed ${completedCount}/${data.total} pairs...`;
                }
                // Update interim results display if needed
                updateInterimResults();
                break;
                
            case 'checkpoint':
                console.log(`Checkpoint saved: ${data.completed} pairs completed`);
                if (batchProgressText) {
                    batchProgressText.textContent += ` (Checkpoint saved)`;
                }
                break;
                
            case 'resume':
                console.log(`Resuming: ${data.completed} pairs already completed`);
                completedCount = data.completed || 0;
                break;
                
            case 'complete':
                // Final results
                const completeData = {
                    results: data.results || [],
                    statistics: data.statistics || {},
                    cost_breakdown: data.cost_breakdown || {}
                };
                // Store globally for batch agent building
                window.batchResultsData = completeData;
                renderBatchResults(completeData);
                if (exportResultsBtn) exportResultsBtn.disabled = false;
                if (batchProgressText) {
                    batchProgressText.textContent = `Analysis complete! ${data.results.length} pairs processed.`;
                }
                break;
                
            case 'error':
                console.error('Error event received:', data);
                console.error('Error message:', data.message);
                
                // If we have a session ID and completed pairs, try to load checkpoint
                if (sessionId && completedCount > 0) {
                    console.log(`Error occurred but ${completedCount} pairs completed. Attempting to load checkpoint...`);
                    loadCheckpointData(sessionId).then(success => {
                        if (success) {
                            showError(`Analysis encountered an error: ${data.message || 'Unknown error'}\n\n` +
                                     `However, ${completedCount} pairs were completed and loaded from checkpoint.`);
                        } else {
                            showError(`Error: ${data.message || 'Unknown error'}. ${completedCount} pairs completed but checkpoint not found.`);
                        }
                    }).catch(e => {
                        console.error('Failed to load checkpoint:', e);
                        showError(`Error: ${data.message || 'Unknown error'}. ${completedCount} pairs completed.`);
                    });
                } else {
                    showError('Error: ' + (data.message || 'Unknown error'));
                }
                
                if (data.pair_index !== undefined) {
                    console.error(`Error processing pair ${data.pair_index}:`, data.message);
                }
                break;
        }
    }
    
    function updateInterimResults() {
        // Optionally show interim statistics as pairs complete
        // This can be expanded to show a live table or chart
        if (completedCount > 0 && completedCount % 10 === 0) {
            console.log(`Interim progress: ${completedCount} pairs completed`);
        }
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
                statistics: checkpoint.statistics || {},
                cost_breakdown: checkpoint.cost_breakdown || {}
            };
            
            // Store globally for batch agent building
            window.batchResultsData = checkpointData;
            
            renderBatchResults(checkpointData);
            
            if (exportResultsBtn) exportResultsBtn.disabled = false;
            
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
    
    // Statistics Table
    html += '<div style="margin-bottom: 24px;">';
    html += '<h4 style="margin-bottom: 12px;">Statistics Summary</h4>';
    html += '<table class="batch-stats-table" style="width: 100%; border-collapse: collapse;">';
    html += '<thead><tr style="background: #f8fafc; border-bottom: 2px solid var(--border-color);">';
    html += '<th style="padding: 12px; text-align: left;">Focus</th>';
    html += '<th style="padding: 12px; text-align: right;">Mean Influence</th>';
    html += '<th style="padding: 12px; text-align: right;">Variance</th>';
    html += '<th style="padding: 12px; text-align: right;">Std Dev</th>';
    html += '<th style="padding: 12px; text-align: right;">Min</th>';
    html += '<th style="padding: 12px; text-align: right;">Max</th>';
    html += '</tr></thead><tbody>';
    
    // Regular foci
    const stats = data.statistics || {};
    Object.keys(stats).forEach(focusName => {
        if (focusName === 'chat_content' || focusName === 'noise') return; // Handle separately
        
        const stat = stats[focusName];
        const variance = stat.variance || 0;
        const meanVar = Math.max(...Object.values(stats).filter(s => s.variance).map(s => s.variance || 0));
        const varianceColor = variance > meanVar * 0.7 ? '#ef4444' : variance > meanVar * 0.4 ? '#f59e0b' : '#10b981';
        
        html += `<tr style="border-bottom: 1px solid var(--border-color);">`;
        html += `<td style="padding: 12px;"><strong>${escapeHtml(focusName)}</strong></td>`;
        html += `<td style="padding: 12px; text-align: right;">${(stat.mean * 100).toFixed(2)}%</td>`;
        html += `<td style="padding: 12px; text-align: right; color: ${varianceColor};">${(stat.variance * 10000).toFixed(4)}</td>`;
        html += `<td style="padding: 12px; text-align: right;">${(stat.std_dev * 100).toFixed(2)}%</td>`;
        html += `<td style="padding: 12px; text-align: right;">${(stat.min * 100).toFixed(2)}%</td>`;
        html += `<td style="padding: 12px; text-align: right;">${(stat.max * 100).toFixed(2)}%</td>`;
        html += `</tr>`;
    });
    
    // Chat content (special focus)
    if (stats.chat_content) {
        const stat = stats.chat_content;
        html += `<tr style="border-bottom: 2px solid var(--border-color); background: #e8f4f8;">`;
        html += `<td style="padding: 12px;"><strong>📱 Chat Content (Special Focus)</strong></td>`;
        html += `<td style="padding: 12px; text-align: right;">${(stat.mean * 100).toFixed(2)}%</td>`;
        html += `<td style="padding: 12px; text-align: right;">${(stat.variance * 10000).toFixed(4)}</td>`;
        html += `<td style="padding: 12px; text-align: right;">${(stat.std_dev * 100).toFixed(2)}%</td>`;
        html += `<td style="padding: 12px; text-align: right;">${(stat.min * 100).toFixed(2)}%</td>`;
        html += `<td style="padding: 12px; text-align: right;">${(stat.max * 100).toFixed(2)}%</td>`;
        html += `</tr>`;
    }
    
    // Noise statistics
    if (stats.noise) {
        const noise = stats.noise;
        html += `<tr style="border-bottom: 2px solid var(--border-color); background: #fff3cd;">`;
        html += `<td style="padding: 12px;"><strong>📊 Noise (Baseline Similarity)</strong></td>`;
        html += `<td style="padding: 12px; text-align: right;" title="Mean similarity between baseline outputs">${(noise.mean * 100).toFixed(2)}%</td>`;
        html += `<td style="padding: 12px; text-align: right;" title="Variance of similarities between baseline outputs">${(noise.variance * 10000).toFixed(4)}</td>`;
        html += `<td style="padding: 12px; text-align: right;" title="Standard deviation of similarities">${(noise.std_dev * 100).toFixed(2)}%</td>`;
        html += `<td style="padding: 12px; text-align: right;" title="Noise threshold (mean - 2*std)">${noise.noise_threshold !== null && noise.noise_threshold !== undefined ? (noise.noise_threshold * 100).toFixed(2) + '%' : '-'}</td>`;
        html += `<td style="padding: 12px; text-align: right;" title="Number of baseline samples">${noise.num_samples || '-'}</td>`;
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
        html += `<p style="margin-top: 4px; font-size: 0.9em;"><strong>Cost per Pair:</strong> $${(cost.total_cost / (data.results ? data.results.length : 1)).toFixed(4)}</p>`;
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
        
        // Create CSV
        let csv = 'Focus,Mean Influence,Variance,Std Dev,Min,Max\n';
        
        Object.keys(stats).forEach(focusName => {
            if (focusName === 'noise') return; // Skip noise row
            const stat = stats[focusName];
            csv += `"${focusName}",${stat.mean},${stat.variance},${stat.std_dev},${stat.min},${stat.max}\n`;
        });
        
        // Add noise separately
        if (stats.noise) {
            csv += `"Noise (Baseline Similarity)",${stats.noise.mean},${stats.noise.variance},${stats.noise.std_dev || ''},${stats.noise.noise_threshold !== null && stats.noise.noise_threshold !== undefined ? stats.noise.noise_threshold : ''},${stats.noise.num_samples || ''}\n`;
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

// Make functions available globally
window.removePair = removePair;
window.removeBatchFocus = removeBatchFocus;

// Authentication handlers
document.addEventListener('DOMContentLoaded', () => {
    const loginBtn = document.getElementById('login-btn');
    const logoutBtn = document.getElementById('logout-btn');
    const userInfo = document.getElementById('user-info');
    
    // Check if user is logged in
    const sessionId = localStorage.getItem('session_id');
    const user = JSON.parse(localStorage.getItem('user') || 'null');
    
    if (sessionId && user) {
        // User is logged in
        if (loginBtn) loginBtn.style.display = 'none';
        if (logoutBtn) logoutBtn.style.display = 'inline-block';
        if (userInfo) {
            userInfo.textContent = `${user.email} (${user.tier})`;
            userInfo.style.display = 'inline-block';
        }
    } else {
        // User is not logged in
        if (loginBtn) loginBtn.style.display = 'inline-block';
        if (logoutBtn) logoutBtn.style.display = 'none';
        if (userInfo) userInfo.style.display = 'none';
    }
    
    // Login button handler
    if (loginBtn) {
        loginBtn.addEventListener('click', () => {
            window.location.href = '/login';
        });
    }
    
    // Logout button handler
    if (logoutBtn) {
        logoutBtn.addEventListener('click', async () => {
            const sessionId = localStorage.getItem('session_id');
            
            if (sessionId) {
                try {
                    await fetch('/api/auth/logout', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-Session-ID': sessionId
                        },
                        body: JSON.stringify({ session_id: sessionId })
                    });
                } catch (error) {
                    console.error('Logout error:', error);
                }
            }
            
            // Clear local storage
            localStorage.removeItem('session_id');
            localStorage.removeItem('user');
            
            // Reload page
            window.location.reload();
        });
    }
    
    // Verify session on page load
    if (sessionId) {
        fetch('/api/auth/me', {
            headers: {
                'X-Session-ID': sessionId
            }
        })
        .then(response => {
            if (!response.ok) {
                // Session invalid, clear it
                localStorage.removeItem('session_id');
                localStorage.removeItem('user');
                if (loginBtn) loginBtn.style.display = 'inline-block';
                if (logoutBtn) logoutBtn.style.display = 'none';
                if (userInfo) userInfo.style.display = 'none';
            }
        })
        .catch(error => {
            console.error('Session check error:', error);
        });
    }
});

