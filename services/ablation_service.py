#!/usr/bin/env python3
"""
Ablation analysis service.

Handles running ablation analysis to determine focus influence on outputs.
"""

import numpy as np
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
        api_key: str,
        embedding_service: Optional[EmbeddingService] = None,
        cost_calculator: Optional[CostCalculator] = None
    ):
        """
        Initialize ablation service.
        
        Args:
            provider: LLM provider instance
            model: Model name to use
            api_key: API key (for embeddings)
            embedding_service: Optional EmbeddingService instance
            cost_calculator: Optional CostCalculator instance
        """
        self.provider = provider
        self.model = model
        self.api_key = api_key
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
        for _ in range(num_samples):
            response = self.provider.chat_completion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7 if num_samples > 1 else 0.7
            )
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
            
            # Generate output for ablated prompt
            response = self.provider.chat_completion(
                model=self.model,
                messages=[{"role": "user", "content": ablated_prompt}],
                temperature=0.7
            )
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
            baseline_embeddings = []
            for output in baseline_outputs:
                embedding, tokens = self.embedding_service.get_embedding_with_usage(output)
                baseline_embeddings.append(embedding)
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
        baseline_embedding, tokens = self.embedding_service.get_embedding_with_usage(baseline_output)
        total_embedding_tokens += tokens
        
        # Step 4: Calculate similarities and influence scores
        influence_scores = []
        similarities = []
        
        for i, ablation in enumerate(ablation_results):
            ablated_embedding, tokens = self.embedding_service.get_embedding_with_usage(ablation['ablated_output'])
            total_embedding_tokens += tokens
            
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


