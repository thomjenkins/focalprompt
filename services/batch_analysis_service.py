#!/usr/bin/env python3
"""
Batch analysis service.

Handles batch ablation analysis with streaming support.
"""

import json
import numpy as np
from typing import List, Dict, Optional, Generator
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from services.embedding_service import EmbeddingService
from services.cost_calculator import CostCalculator
from services.checkpoint_service import CheckpointService
from utils.prompt_builder import get_pair_inputs, build_prompt_with_dynamic_foci
from utils.data_processing import (
    calculate_statistics_from_results,
    calculate_focus_distribution_statistics,
)
from services.assessment_service import AssessmentService


class BatchAnalysisService:
    """Service for batch ablation analysis."""
    
    def __init__(
        self,
        provider,
        model: str,
        api_key: str,
        embedding_service: Optional[EmbeddingService] = None,
        cost_calculator: Optional[CostCalculator] = None,
        checkpoint_service: Optional[CheckpointService] = None,
        assessment_service: Optional[AssessmentService] = None,
        max_workers: int = 10
    ):
        """
        Initialize batch analysis service.
        
        Args:
            provider: LLM provider instance
            model: Model name to use
            api_key: API key (for embeddings)
            embedding_service: Optional EmbeddingService instance
            cost_calculator: Optional CostCalculator instance
            checkpoint_service: Optional CheckpointService instance
            max_workers: Maximum parallel workers
        """
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.embedding_service = embedding_service or EmbeddingService()
        self.cost_calculator = cost_calculator or CostCalculator()
        self.checkpoint_service = checkpoint_service or CheckpointService()
        self.assessment_service = assessment_service
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
    
    def process_single_pair(
        self,
        pair_data: Dict,
        pair_idx: int,
        foci_list: List[Dict],
        batch_noise_threshold: Optional[float],
        baseline_variance: float,
        baseline_std: float,
        baseline_mean_similarity: float
    ) -> Dict:
        """
        Process a single pair - designed to run in parallel.
        
        Args:
            pair_data: Pair data dictionary
            pair_idx: Index of the pair
            foci_list: List of foci
            batch_noise_threshold: Noise threshold for significance
            baseline_variance: Baseline variance
            baseline_std: Baseline standard deviation
            baseline_mean_similarity: Baseline mean similarity
            
        Returns:
            Dict with results
        """
        try:
            prompt = pair_data.get('prompt', '')
            inputs = get_pair_inputs(pair_data)
            chat_content = inputs['chat_content']
            
            # Generate baseline output
            response = self.provider.chat_completion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            baseline_output = response['content']
            
            input_tokens = response['usage']['prompt_tokens'] if 'usage' in response else 0
            output_tokens = response['usage']['completion_tokens'] if 'usage' in response else 0
            
            # Focus distribution assessment (same logic as /api/assess with user-defined foci)
            focus_distribution_assessment = None
            assessment_error = None
            if self.assessment_service:
                provided_out = (pair_data.get('output') or '').strip()
                output_for_assessment = provided_out if provided_out else baseline_output
                assessment_source = 'provided_output' if provided_out else 'generated_baseline'
                user_foci_for_assess = [
                    {'focus': f.get('focus', ''), 'prompt_section': f.get('prompt_section', '')}
                    for f in foci_list
                ]
                try:
                    fd = self.assessment_service.assess_focus(
                        prompt, output_for_assessment, user_foci=user_foci_for_assess
                    )
                    usage_fd = fd.pop('usage', None)
                    focus_distribution_assessment = {
                        'foci': fd.get('foci', []),
                        'overall_summary': fd.get('overall_summary', ''),
                        'assessment_source': assessment_source,
                    }
                    if usage_fd:
                        input_tokens += usage_fd.get('prompt_tokens', 0) or usage_fd.get('input_tokens', 0)
                        output_tokens += usage_fd.get('completion_tokens', 0) or usage_fd.get('output_tokens', 0)
                except Exception as ex:
                    assessment_error = str(ex)
            
            # Get baseline embedding
            baseline_embedding, embedding_tokens = self.embedding_service.get_embedding_with_usage(baseline_output)
            
            # Process each focus
            focus_influences = {}
            for focus_to_remove in foci_list:
                focus_section = focus_to_remove.get('prompt_section', '')
                focus_name = focus_to_remove.get('focus', '')
                
                # Create ablated prompt by reconstructing from remaining foci
                remaining_foci = [f for f in foci_list if f.get('focus', '') != focus_name]
                
                if len(remaining_foci) > 0:
                    # Reconstruct prompt from remaining foci
                    relevant_foci = []
                    for f in remaining_foci:
                        relevant_foci.append({
                            'focus': f.get('focus', ''),
                            'weight': 1.0,
                            'prompt_section': f.get('prompt_section', '')
                        })
                    
                    ablated_prompt = build_prompt_with_dynamic_foci(relevant_foci, remaining_foci, inputs, chat_weight=0.5)
                    
                    # Fallback
                    if not ablated_prompt or ablated_prompt.strip() == '':
                        if focus_section:
                            ablated_prompt = prompt.replace(focus_section, '').strip()
                            ablated_prompt = '\n'.join([line for line in ablated_prompt.split('\n') if line.strip()])
                        else:
                            ablated_prompt = prompt
                else:
                    # If no remaining foci, create minimal prompt
                    ablated_prompt = ''
                    if inputs.get('chat_content'):
                        ablated_prompt = inputs['chat_content']
                    if inputs.get('rag_context'):
                        ablated_prompt += '\n' + inputs['rag_context'] if ablated_prompt else inputs['rag_context']
                    if not ablated_prompt:
                        ablated_prompt = prompt
                
                # Generate ablated output
                response = self.provider.chat_completion(
                    model=self.model,
                    messages=[{"role": "user", "content": ablated_prompt}],
                    temperature=0.7
                )
                ablated_output = response['content']
                
                input_tokens += response['usage']['prompt_tokens'] if 'usage' in response else 0
                output_tokens += response['usage']['completion_tokens'] if 'usage' in response else 0
                
                # Calculate similarity and influence
                ablated_embedding, tokens = self.embedding_service.get_embedding_with_usage(ablated_output)
                embedding_tokens += tokens
                
                similarity = np.dot(baseline_embedding, ablated_embedding) / (
                    np.linalg.norm(baseline_embedding) * np.linalg.norm(ablated_embedding)
                )
                influence = 1 - similarity
                is_significant = bool(similarity < batch_noise_threshold) if batch_noise_threshold else None
                
                focus_influences[focus_name] = {
                    'influence': float(influence),
                    'similarity': float(similarity),
                    'is_significant': is_significant
                }
            
            # Calculate chat_content influence
            ablated_prompt_no_chat = prompt.replace(chat_content, '').strip()
            ablated_prompt_no_chat = '\n'.join([line for line in ablated_prompt_no_chat.split('\n') if line.strip()])
            
            response = self.provider.chat_completion(
                model=self.model,
                messages=[{"role": "user", "content": ablated_prompt_no_chat}],
                temperature=0.7
            )
            ablated_output_no_chat = response['content']
            
            input_tokens += response['usage']['prompt_tokens'] if 'usage' in response else 0
            output_tokens += response['usage']['completion_tokens'] if 'usage' in response else 0
            
            ablated_embedding_no_chat, tokens = self.embedding_service.get_embedding_with_usage(ablated_output_no_chat)
            embedding_tokens += tokens
            
            similarity_chat = np.dot(baseline_embedding, ablated_embedding_no_chat) / (
                np.linalg.norm(baseline_embedding) * np.linalg.norm(ablated_embedding_no_chat)
            )
            influence_chat = 1 - similarity_chat
            is_significant_chat = bool(similarity_chat < batch_noise_threshold) if batch_noise_threshold else None
            
            # Per-pair shares (consistent with single-run ablation): raw embedding shifts are not additive;
            # normalize so foci + chat sum to 100% for this pair.
            total_raw = sum(d['influence'] for d in focus_influences.values()) + float(influence_chat)
            if total_raw > 0:
                for d in focus_influences.values():
                    d['normalized_influence'] = d['influence'] / total_raw
                chat_normalized = float(influence_chat) / total_raw
            else:
                n = len(focus_influences) + 1
                share = 1.0 / n if n else 0.0
                for d in focus_influences.values():
                    d['normalized_influence'] = share
                chat_normalized = share
            
            out = {
                'success': True,
                'pair_index': pair_idx,
                'pair_data': pair_data,
                'influence_scores': focus_influences,
                'chat_content_influence': {
                    'influence': float(influence_chat),
                    'similarity': float(similarity_chat),
                    'is_significant': is_significant_chat,
                    'normalized_influence': chat_normalized
                },
                'noise_metrics': {
                    'variance': baseline_variance,
                    'std_dev': baseline_std,
                    'mean_similarity': baseline_mean_similarity,
                    'threshold': float(batch_noise_threshold) if batch_noise_threshold else None,
                    'is_batch_wide': True
                },
                'tokens': {
                    'input': input_tokens,
                    'output': output_tokens,
                    'embedding': embedding_tokens
                }
            }
            if focus_distribution_assessment is not None:
                out['focus_distribution_assessment'] = focus_distribution_assessment
            if assessment_error is not None:
                out['focus_distribution_assessment_error'] = assessment_error
            return out
        except Exception as e:
            return {
                'success': False,
                'pair_index': pair_idx,
                'error': str(e)
            }
    
    def stream_batch_analysis(
        self,
        pairs: List[Dict],
        foci_list: List[Dict],
        num_samples: int = 20,
        session_id: Optional[str] = None,
        resume: bool = False
    ) -> Generator[str, None, None]:
        """
        Stream batch analysis results.
        
        Args:
            pairs: List of input-output pairs
            foci_list: List of foci
            num_samples: Number of baseline samples for noise calculation
            session_id: Optional session ID for checkpointing
            resume: Whether to resume from checkpoint
            
        Yields:
            SSE-formatted strings with progress updates
        """
        if not session_id:
            session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Track costs
        total_input_tokens = 0
        total_output_tokens = 0
        total_embedding_tokens = 0
        
        # Initialize variables
        pair_results = []
        total_pairs = len(pairs)
        completed_count = 0
        
        # Load checkpoint if resuming
        completed_pairs = {}
        if resume:
            checkpoint = self.checkpoint_service.load_checkpoint(session_id, 'batch_analysis')
            if checkpoint:
                completed_pairs = {r['pair_index']: r for r in checkpoint.get('pair_results', [])}
                pair_results = list(completed_pairs.values())
                yield f"data: {json.dumps({'type': 'resume', 'completed': len(completed_pairs), 'total': len(pairs)})}\n\n"
        
        # Step 1: Calculate baseline noise ONCE for the entire batch
        batch_noise_threshold = None
        baseline_variance = 0.0
        baseline_std = 0.0
        baseline_mean_similarity = 1.0
        
        if len(pairs) > 0:
            first_pair = pairs[0]
            system_prompt = first_pair.get('prompt', '')
            inputs = get_pair_inputs(first_pair)
            chat_content = inputs['chat_content']
            
            # Use system prompt only (remove chat_content if present)
            if chat_content and chat_content in system_prompt:
                system_prompt = system_prompt.replace(chat_content, '').strip()
                system_prompt = '\n'.join([line for line in system_prompt.split('\n') if line.strip()])
            
            representative_prompt = system_prompt
            
            yield f"data: {json.dumps({'type': 'progress', 'stage': 'noise_calculation', 'message': f'Calculating baseline noise from {num_samples} samples...'})}\n\n"
            
            baseline_outputs = []
            for i in range(num_samples):
                response = self.provider.chat_completion(
                    model=self.model,
                    messages=[{"role": "user", "content": representative_prompt}],
                    temperature=0.7
                )
                baseline_outputs.append(response['content'])
                
                if 'usage' in response:
                    total_input_tokens += response['usage']['prompt_tokens']
                    total_output_tokens += response['usage']['completion_tokens']
                
                yield f"data: {json.dumps({'type': 'progress', 'stage': 'noise_calculation', 'sample': i+1, 'total': num_samples})}\n\n"
            
            baseline_embeddings = []
            for output in baseline_outputs:
                embedding, tokens = self.embedding_service.get_embedding_with_usage(output)
                baseline_embeddings.append(embedding)
                total_embedding_tokens += tokens
            
            similarities_between_baselines = []
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
                batch_noise_threshold = baseline_mean_similarity - (2 * baseline_std)
        
        # Step 2: Process pairs in parallel
        yield f"data: {json.dumps({'type': 'progress', 'stage': 'processing', 'message': f'Processing {total_pairs} pairs...'})}\n\n"
        
        futures = {}
        for pair_idx, pair in enumerate(pairs):
            if pair_idx in completed_pairs:
                continue  # Skip already completed pairs
            
            future = self.executor.submit(
                self.process_single_pair,
                pair,
                pair_idx,
                foci_list,
                batch_noise_threshold,
                baseline_variance,
                baseline_std,
                baseline_mean_similarity
            )
            futures[future] = pair_idx
        
        # Collect results as they complete
        for future in as_completed(futures):
            pair_idx = futures[future]
            result = future.result()
            pair_results.append(result)
            completed_count += 1
            
            # Update checkpoint
            checkpoint_data = {
                'session_id': session_id,
                'timestamp': datetime.now().isoformat(),
                'type': 'batch_analysis',
                'completed': completed_count,
                'total_pairs': total_pairs,
                'pair_results': pair_results,
                'complete': completed_count >= total_pairs
            }
            self.checkpoint_service.save_checkpoint(session_id, checkpoint_data, 'batch_analysis')
            
            yield f"data: {json.dumps({'type': 'progress', 'stage': 'processing', 'completed': completed_count, 'total': total_pairs, 'pair_index': pair_idx})}\n\n"
            
            if result.get('success'):
                yield f"data: {json.dumps({'type': 'pair_result', 'pair_index': pair_idx, 'result': result})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'error', 'pair_index': pair_idx, 'error': result.get('error', 'Unknown error')})}\n\n"
        
        # Calculate final statistics (normalized shares, consistent with single-run ablation)
        yield f"data: {json.dumps({'type': 'progress', 'stage': 'calculating_statistics', 'message': 'Calculating statistics...'})}\n\n"
        
        statistics = calculate_statistics_from_results(pair_results)
        focus_distribution_statistics = calculate_focus_distribution_statistics(pair_results)
        
        # Calculate costs
        cost_breakdown = self.cost_calculator.calculate_cost(
            total_input_tokens,
            total_output_tokens,
            total_embedding_tokens,
            self.model,
            'openai'  # Embeddings only work with OpenAI
        )
        
        # Persist checkpoint with statistics for reload / export
        checkpoint_data = {
            'session_id': session_id,
            'timestamp': datetime.now().isoformat(),
            'type': 'batch_analysis',
            'completed': completed_count,
            'total_pairs': total_pairs,
            'pair_results': pair_results,
            'statistics': statistics,
            'focus_distribution_statistics': focus_distribution_statistics,
            'cost_breakdown': cost_breakdown,
            'complete': True
        }
        self.checkpoint_service.save_checkpoint(session_id, checkpoint_data, 'batch_analysis')
        
        # Final result (include `results` alias for frontend)
        final_result = {
            'type': 'complete',
            'session_id': session_id,
            'completed': completed_count,
            'total_pairs': total_pairs,
            'pair_results': pair_results,
            'results': pair_results,
            'statistics': statistics,
            'focus_distribution_statistics': focus_distribution_statistics,
            'cost_breakdown': cost_breakdown
        }
        
        yield f"data: {json.dumps(final_result)}\n\n"


