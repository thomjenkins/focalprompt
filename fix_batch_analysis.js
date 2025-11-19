// Run this in the browser console to fix the batch analysis button and show cost estimate
// Copy and paste this entire script into the browser console (F12 -> Console tab)

(function() {
    console.log('Fixing batch analysis button and cost estimate...');
    
    // 1. Fix the button handler
    const btn = document.getElementById('run-batch-analysis-btn');
    if (btn) {
        // Clone to remove old listeners
        const newBtn = btn.cloneNode(true);
        btn.parentNode.replaceChild(newBtn, btn);
        const freshBtn = document.getElementById('run-batch-analysis-btn');
        
        freshBtn.addEventListener('click', async function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            console.log('Run batch analysis button clicked');
            
            // Get data from global variables (they should exist)
            const batchPairs = window.batchPairs || [];
            const batchFoci = window.batchFoci || [];
            const batchPromptInput = document.getElementById('batch-prompt-input');
            
            console.log('Pairs:', batchPairs.length, 'Foci:', batchFoci.length);
            
            if (batchPairs.length === 0) {
                alert('Please add at least one pair first.');
                return;
            }
            
            if (batchFoci.length === 0) {
                alert('Please define foci first.');
                return;
            }
            
            const prompt = batchPromptInput ? batchPromptInput.value.trim() : '';
            if (!prompt) {
                alert('Please enter the prompt that was used for all pairs.');
                return;
            }
            
            console.log('Starting batch analysis...');
            
            const pairsWithPrompt = batchPairs.map(pair => ({
                ...pair,
                prompt: prompt
            }));
            
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 1800000);
            
            // Show loading
            const loadingOverlay = document.getElementById('loading-overlay');
            const loadingText = document.getElementById('loading-text');
            if (loadingOverlay && loadingText) {
                loadingText.textContent = `Running batch analysis on ${batchPairs.length} pair(s)... This may take a very long time.`;
                loadingOverlay.classList.remove('hidden');
            }
            
            const batchProgress = document.getElementById('batch-progress');
            const batchProgressText = document.getElementById('batch-progress-text');
            if (batchProgress) {
                batchProgress.classList.remove('hidden');
                if (batchProgressText) batchProgressText.textContent = 'Starting analysis...';
            }
            
            try {
                const response = await fetch('/api/batch-ablation-analysis', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        pairs: pairsWithPrompt,
                        foci: batchFoci,
                        model: 'gpt-4o-mini',
                        num_samples: 20
                    }),
                    signal: controller.signal
                });
                
                clearTimeout(timeoutId);
                const data = await response.json();
                
                if (!response.ok) {
                    throw new Error(data.error || 'Failed to run batch analysis');
                }
                
                // Render results (assuming renderBatchResults exists)
                if (typeof renderBatchResults === 'function') {
                    renderBatchResults(data);
                } else {
                    console.log('Results:', data);
                }
                
                const exportBtn = document.getElementById('export-results-btn');
                if (exportBtn) exportBtn.disabled = false;
                
            } catch (error) {
                if (error.name === 'AbortError') {
                    alert('Batch analysis timed out after 30 minutes.');
                } else {
                    alert('Error: ' + error.message);
                }
                console.error('Batch analysis error:', error);
            } finally {
                if (loadingOverlay) loadingOverlay.classList.add('hidden');
                if (batchProgress) batchProgress.classList.add('hidden');
            }
        });
        
        console.log('✓ Button handler attached');
    } else {
        console.error('Button not found');
    }
    
    // 2. Trigger cost estimate update
    if (typeof updateCostEstimate === 'function') {
        updateCostEstimate();
        console.log('✓ Cost estimate updated');
    } else {
        console.warn('updateCostEstimate function not found - cost estimate may not work');
    }
    
    console.log('Done! Try clicking the button now.');
})();

