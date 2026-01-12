#!/usr/bin/env python3
"""
Ablation analysis service.

Handles running ablation analysis to determine focus influence on outputs.
"""

import numpy as np
import time
from typing import List, Dict, Optional
from services.embedding_service import EmbeddingService
from services.cost_calculator import CostCalculator
from utils.prompt_builder import build_prompt_with_dynamic_foci


class AblationService:
    """Service for running ablation analysis."""
    
    def __init__(
        self,
        provider,
        model: str,
        api_key: Optional[str] = None,
        embedding_service: Optional[EmbeddingService] = None,
        cost_calculator: Optional[CostCalculator] = None
    ):
        """
        Initialize ablation service.
        
        Args:
            provider: LLM provider instance
            model: Model name to use
            api_key: API key (deprecated - not used, embeddings use AI Gateway)
            embedding_service: Optional EmbeddingService instance
            cost_calculator: Optional CostCalculator instance
        """
        self.provider = provider
        self.model = model
        self.api_key = api_key  # Kept for backward compatibility but not used
        self.embedding_service = embedding_service or EmbeddingService()
        self.cost_calculator = cost_calculator or CostCalculator()
    
    def run_ablation(
        self,
        prompt: str,
        foci_list: List[Dict],
        num_samples: int = 20,
        inputs: Optional[Dict] = None
    ) -> Dict:
        """
        Run ablation analysis to determine focus influence.
        
        Args:
            prompt: Original prompt
            foci_list: List of focus dictionaries
            num_samples: Number of baseline samples for noise calculation
            inputs: Optional dynamic inputs (for dynamic foci)
            
        Returns:
            Dict with ablation results
        """
        inputs = inputs or {}
        
        # Track costs
        total_input_tokens = 0
        total_output_tokens = 0
        total_embedding_tokens = 0
        
        # Step 1: Generate baseline output (full prompt)
        baseline_outputs = []
        for i in range(num_samples):
            # Add delay between requests to avoid rate limits (except for first request)
            if i > 0:
                time.sleep(0.5)  # 500ms delay between baseline samples
            
            # Retry logic for rate limits
            max_retries = 3
            retry_delay = 2  # Start with 2 seconds
            response = None
            
            for attempt in range(max_retries):
                try:
                    response = self.provider.chat_completion(
                        model=self.model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.7 if num_samples > 1 else 0.7
                    )
                    break  # Success, exit retry loop
                except Exception as e:
                    error_msg = str(e).lower()
                    if 'rate limit' in error_msg or '429' in error_msg:
                        if attempt < max_retries - 1:
                            # Exponential backoff: 2s, 4s, 8s
                            wait_time = retry_delay * (2 ** attempt)
                            time.sleep(wait_time)
                            continue
                        else:
                            raise Exception(f"Rate limit exceeded after {max_retries} retries. Please wait a few minutes and try again with fewer samples.")
                    else:
                        # Not a rate limit error, re-raise immediately
                        raise
            
            if response is None:
                raise Exception("Failed to generate baseline output after retries")
            
            baseline_outputs.append(response['content'])
            
            # Track token usage
            if 'usage' in response:
                total_input_tokens += response['usage']['prompt_tokens']
                total_output_tokens += response['usage']['completion_tokens']
        
        baseline_output = baseline_outputs[0]  # Use first as primary baseline
        
        # Step 2: Generate ablated outputs (one focus removed at a time)
        ablation_results = []
        
        for i, focus_to_remove in enumerate(foci_list):
            focus_section = focus_to_remove.get('prompt_section', '')
            focus_name = focus_to_remove.get('focus', '')
            
            # Create ablated prompt by reconstructing from remaining foci
            # This properly handles dynamic inputs
            remaining_foci = [f for f in foci_list if f.get('focus', '') != focus_name]
            
            if len(remaining_foci) > 0:
                # Reconstruct prompt from remaining foci using build_prompt_with_dynamic_foci
                # We need to create a "relevant_foci" list with all remaining foci (weight=1.0 for ablation)
                relevant_foci = []
                for f in remaining_foci:
                    relevant_foci.append({
                        'focus': f.get('focus', ''),
                        'weight': 1.0,  # Use weight 1.0 for ablation (all foci are equally important)
                        'prompt_section': f.get('prompt_section', '')
                    })
                
                # Build ablated prompt using the same method as agent building
                ablated_prompt = build_prompt_with_dynamic_foci(relevant_foci, remaining_foci, inputs, chat_weight=0.5)
                
                # Fallback: if build_prompt_with_dynamic_foci returns empty, use simple string replace
                if not ablated_prompt or ablated_prompt.strip() == '':
                    if focus_section:
                        ablated_prompt = prompt.replace(focus_section, '').strip()
                        ablated_prompt = '\n'.join([line for line in ablated_prompt.split('\n') if line.strip()])
                    else:
                        ablated_prompt = prompt
            else:
                # If no remaining foci, create minimal prompt (just dynamic inputs if any)
                ablated_prompt = ''
                if inputs.get('chat_content'):
                    ablated_prompt = inputs['chat_content']
                if inputs.get('rag_context'):
                    ablated_prompt += '\n' + inputs['rag_context'] if ablated_prompt else inputs['rag_context']
                if not ablated_prompt:
                    ablated_prompt = prompt  # Fallback to original if no dynamic inputs
            
            # Add delay between ablated requests to avoid rate limits
            time.sleep(0.5)  # 500ms delay between ablated outputs
            
            # Retry logic for rate limits
            max_retries = 3
            retry_delay = 2  # Start with 2 seconds
            response = None
            
            for attempt in range(max_retries):
                try:
                    response = self.provider.chat_completion(
                        model=self.model,
                        messages=[{"role": "user", "content": ablated_prompt}],
                        temperature=0.7
                    )
                    break  # Success, exit retry loop
                except Exception as e:
                    error_msg = str(e).lower()
                    if 'rate limit' in error_msg or '429' in error_msg:
                        if attempt < max_retries - 1:
                            # Exponential backoff: 2s, 4s, 8s
                            wait_time = retry_delay * (2 ** attempt)
                            time.sleep(wait_time)
                            continue
                        else:
                            raise Exception(f"Rate limit exceeded after {max_retries} retries. Please wait a few minutes and try again with fewer samples.")
                    else:
                        # Not a rate limit error, re-raise immediately
                        raise
            
            if response is None:
                raise Exception(f"Failed to generate ablated output for focus '{focus_name}' after retries")
            
            ablated_output = response['content']
            
            # Track token usage
            if 'usage' in response:
                total_input_tokens += response['usage']['prompt_tokens']
                total_output_tokens += response['usage']['completion_tokens']
            
            ablation_results.append({
                'focus_index': i,
                'focus': focus_name,
                'prompt_section': focus_section,
                'ablated_output': ablated_output
            })
        
        # Step 3: Calculate baseline noise/variance from multiple samples
        baseline_variance = None
        baseline_std = None
        baseline_mean_similarity = None
        similarities_between_baselines = []
        noise_threshold = None
        
        if num_samples > 1:
            # Use batch embedding API to get all baseline embeddings in one request
            baseline_embeddings_list, tokens = self.embedding_service.batch_embeddings_with_usage(baseline_outputs)
            baseline_embeddings = baseline_embeddings_list
            total_embedding_tokens += tokens
            
            for i in range(len(baseline_embeddings)):
                for j in range(i+1, len(baseline_embeddings)):
                    sim = np.dot(baseline_embeddings[i], baseline_embeddings[j]) / (
                        np.linalg.norm(baseline_embeddings[i]) * np.linalg.norm(baseline_embeddings[j])
                    )
                    similarities_between_baselines.append(sim)
            
            if similarities_between_baselines:
                baseline_variance = float(np.var(similarities_between_baselines))
                baseline_std = float(np.std(similarities_between_baselines))
                baseline_mean_similarity = float(np.mean(similarities_between_baselines))
                
                # Calculate noise threshold (mean - 2*std for 95% confidence)
                noise_threshold = baseline_mean_similarity - (2 * baseline_std)
        
        # Use first baseline embedding for comparison with ablated outputs
        # If we already have baseline embeddings from batch, use the first one
        if num_samples > 1 and baseline_embeddings:
            baseline_embedding = baseline_embeddings[0]
        else:
            # Single sample case - get embedding separately
            baseline_embedding, tokens = self.embedding_service.get_embedding_with_usage(baseline_output)
            total_embedding_tokens += tokens
        
        # Step 4: Calculate similarities and influence scores
        influence_scores = []
        similarities = []
        
        # Batch all ablated outputs into a single embedding request
        ablated_outputs = [ablation['ablated_output'] for ablation in ablation_results]
        if ablated_outputs:
            ablated_embeddings_list, tokens = self.embedding_service.batch_embeddings_with_usage(ablated_outputs)
            total_embedding_tokens += tokens
            
            # Match embeddings back to ablation results and calculate similarities
            for i, ablation in enumerate(ablation_results):
                ablated_embedding = ablated_embeddings_list[i]
                
                # Cosine similarity
                similarity = np.dot(baseline_embedding, ablated_embedding) / (
                    np.linalg.norm(baseline_embedding) * np.linalg.norm(ablated_embedding)
                )
                
                # Influence = 1 - similarity (higher influence = more different from baseline)
                influence = 1 - similarity
                
                similarities.append(similarity)
                
                # Get focus name from original foci list
                focus_name = foci_list[i].get('focus', f'Focus {i+1}')
                
                # Determine if influence is significant (beyond noise)
                is_significant = None
                if noise_threshold is not None:
                    is_significant = bool(similarity < noise_threshold)
                
                influence_scores.append({
                    'focus': focus_name,
                    'focus_name': focus_name,  # Include both for compatibility
                    'prompt_section': ablation['prompt_section'],
                    'similarity': float(similarity),
                    'influence': float(influence),
                    'is_significant': is_significant
                })
        
        # Step 5: Normalize influence scores to sum to 1
        total_influence = sum(item['influence'] for item in influence_scores)
        if total_influence > 0:
            for item in influence_scores:
                item['normalized_influence'] = (item['influence'] / total_influence) * 100
        else:
            # If all similarities are 1 (identical outputs), distribute equally
            equal_share = 100.0 / len(influence_scores)
            for item in influence_scores:
                item['normalized_influence'] = equal_share
        
        # Calculate costs
        cost_breakdown = self.cost_calculator.calculate_cost(
            total_input_tokens,
            total_output_tokens,
            total_embedding_tokens,
            self.model,
            'openai'  # Embeddings only work with OpenAI
        )
        
        # Build summary with proper focus names
        summary = {}
        for i, (focus, item) in enumerate(zip(foci_list, influence_scores)):
            focus_name = focus.get('focus', f'Focus {i+1}')
            summary[focus_name] = item['normalized_influence']
        
        result_data = {
            'baseline_output': baseline_output,
            'ablation_results': ablation_results,
            'influence_scores': influence_scores,
            'baseline_variance': baseline_variance,
            'baseline_std': baseline_std,
            'baseline_mean_similarity': baseline_mean_similarity,
            'noise_threshold': noise_threshold,
            'num_baseline_samples': num_samples,
            'summary': summary,
            'cost_breakdown': cost_breakdown,
            'prompt': prompt,
            'foci_list': foci_list,
            'model': self.model
        }
        
        return result_data


