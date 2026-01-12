#!/usr/bin/env python3
"""
Agent builder service.

Handles building optimized agents for specific inputs.
"""

import json
from typing import List, Dict, Optional, Generator
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from services.cost_calculator import CostCalculator
from services.checkpoint_service import CheckpointService
from utils.prompt_builder import build_prompt_with_dynamic_foci, get_pair_inputs


class AgentBuilderService:
    """Service for building optimized agents."""
    
    def __init__(
        self,
        provider,
        model: str,
        cost_calculator: Optional[CostCalculator] = None,
        checkpoint_service: Optional[CheckpointService] = None,
        max_workers: int = 10,
        provider_name: Optional[str] = None
    ):
        """
        Initialize agent builder service.
        
        Args:
            provider: LLM provider instance
            model: Model name to use
            cost_calculator: Optional CostCalculator instance
            checkpoint_service: Optional CheckpointService instance
            max_workers: Maximum parallel workers
            provider_name: Provider name (e.g., 'openai', 'xai') for AI Gateway routing
        """
        self.provider = provider
        self.model = model
        self.provider_name = provider_name or getattr(provider, 'provider_name', None) or 'openai'
        self.cost_calculator = cost_calculator or CostCalculator()
        self.checkpoint_service = checkpoint_service or CheckpointService()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
    
    def assess_chat_foci(
        self,
        chat_content: str,
        foci_list: List[Dict]
    ) -> Dict:
        """
        Assess chat content and assign weights to foci.
        
        Args:
            chat_content: Chat content to assess
            foci_list: List of foci
            
        Returns:
            Dict with foci_weights, chat_weight, and cost_breakdown
        """
        # Build foci list for prompt
        foci_text = '\n'.join([
            f"{i+1}. {f.get('focus', 'Unknown')}: {f.get('prompt_section', '')[:200]}..."
            for i, f in enumerate(foci_list)
        ])
        
        # Use LLM to assess relevance of each focus
        # Check if provider needs provider parameter (AI Gateway)
        import inspect
        sig = inspect.signature(self.provider.chat_completion)
        needs_provider = 'provider' in sig.parameters
        
        # Get provider name from the provider instance if available
        provider_name = getattr(self.provider, 'provider_name', None) or getattr(self, 'provider_name', 'openai')
        
        # Build chat_completion call with or without provider parameter
        chat_kwargs = {
            'model': self.model,
            'messages': [
                {
                    "role": "system",
                    "content": "You are an expert at analyzing chat conversations and determining which parts of a prompt (foci) are relevant for responding. You assign weights from 0.0 to 1.0 based on relevance."
                },
                {
                    "role": "user",
                    "content": f"""Analyze the following chat content and determine how relevant each focus is for responding to it.

CHAT CONTENT:
{chat_content}

AVAILABLE FOCI:
{foci_text}

For each focus, assign a weight from 0.0 to 1.0:
- 1.0 = Highly relevant, essential for responding to this chat
- 0.5 = Moderately relevant, may be useful for context
- 0.0 = Not relevant to this chat

Also assign a weight to the chat content itself (0.0 to 1.0) indicating how much emphasis should be placed on the chat content versus the foci when constructing the response prompt.

Return a JSON object with this structure:
{{
  "foci_weights": [
    {{
      "focus": "The exact focus name from the list above",
      "weight": 0.85,
      "explanation": "Brief explanation of why this focus is relevant/irrelevant"
    }}
  ],
  "chat_weight": 0.9,
  "chat_weight_explanation": "Brief explanation of how much emphasis to place on the chat content"
}}

CRITICAL: You must include ALL {len(foci_list)} foci from the list above, even if weight is 0.0."""
                }
            ],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        
        # Track token usage
        total_input_tokens = response['usage']['prompt_tokens'] if 'usage' in response else 0
        total_output_tokens = response['usage']['completion_tokens'] if 'usage' in response else 0
        
        result = json.loads(response['content'])
        
        # Calculate costs
        cost_breakdown = self.cost_calculator.calculate_cost(
            total_input_tokens,
            total_output_tokens,
            0,  # No embeddings
            self.model,
            'openai'  # Default, should be provider-specific
        )
        
        # Ensure all foci are included
        foci_weights = []
        for focus in foci_list:
            focus_name = focus.get('focus', '')
            # Find matching weight from result
            matched = None
            for item in result.get('foci_weights', []):
                if item.get('focus', '').lower() == focus_name.lower():
                    matched = item
                    break
            
            if matched:
                foci_weights.append({
                    'focus': focus_name,
                    'weight': float(matched.get('weight', 0.0)),
                    'explanation': matched.get('explanation', '')
                })
            else:
                # If not found, add with 0 weight
                foci_weights.append({
                    'focus': focus_name,
                    'weight': 0.0,
                    'explanation': 'Not assessed'
                })
        
        return {
            'foci_weights': foci_weights,
            'chat_weight': float(result.get('chat_weight', 0.5)),
            'chat_weight_explanation': result.get('chat_weight_explanation', ''),
            'cost_breakdown': cost_breakdown
        }
    
    def generate_agent_response(
        self,
        constructed_prompt: str,
        temperature: float = 0.7
    ) -> str:
        """
        Generate response using agent prompt.
        
        Args:
            constructed_prompt: The constructed prompt
            temperature: Sampling temperature
            
        Returns:
            Generated response
        """
        # Check if provider needs provider parameter (AI Gateway)
        import inspect
        sig = inspect.signature(self.provider.chat_completion)
        needs_provider = 'provider' in sig.parameters
        
        chat_kwargs = {
            'model': self.model,
            'messages': [{"role": "user", "content": constructed_prompt}],
            'temperature': temperature
        }
        
        if needs_provider:
            chat_kwargs['provider'] = self.provider_name
        
        response = self.provider.chat_completion(**chat_kwargs)
        return response['content']
    
    def process_single_agent_pair(
        self,
        pair_data: Dict,
        pair_idx: int,
        foci_list: List[Dict]
    ) -> Dict:
        """
        Process a single agent pair - assess foci and generate response.
        
        Args:
            pair_data: Pair data dictionary
            pair_idx: Index of the pair
            foci_list: List of foci
            
        Returns:
            Dict with results
        """
        try:
            inputs = get_pair_inputs(pair_data)
            chat_content = inputs.get('chat_content', '')
            expected_output = pair_data.get('output', '')
            
            # Assess chat foci
            assessment = self.assess_chat_foci(chat_content, foci_list)
            relevant_foci = []
            
            for weight_item in assessment['foci_weights']:
                focus_name = weight_item['focus']
                weight = weight_item['weight']
                
                # Find the full focus data
                for focus in foci_list:
                    if focus.get('focus', '') == focus_name:
                        relevant_foci.append({
                            'focus': focus_name,
                            'weight': weight,
                            'prompt_section': focus.get('prompt_section', '')
                        })
                        break
            
            # Build prompt
            constructed_prompt = build_prompt_with_dynamic_foci(
                relevant_foci,
                foci_list,
                inputs,
                assessment['chat_weight']
            )
            
            # Generate response
            generated_output = self.generate_agent_response(constructed_prompt)
            
            return {
                'success': True,
                'pair_index': pair_idx,
                'foci_weights': assessment['foci_weights'],
                'chat_weight': assessment['chat_weight'],
                'constructed_prompt': constructed_prompt,
                'generated_output': generated_output,
                'expected_output': expected_output
            }
        except Exception as e:
            return {
                'success': False,
                'pair_index': pair_idx,
                'error': str(e)
            }
    
    def stream_batch_agents(
        self,
        pairs: List[Dict],
        foci_list: List[Dict],
        session_id: Optional[str] = None,
        resume: bool = False
    ) -> Generator[str, None, None]:
        """
        Stream batch agent building results.
        
        Args:
            pairs: List of input-output pairs
            foci_list: List of foci
            session_id: Optional session ID for checkpointing
            resume: Whether to resume from checkpoint
            
        Yields:
            SSE-formatted strings with progress updates
        """
        if not session_id:
            session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Initialize variables
        results = []
        total_pairs = len(pairs)
        completed_count = 0
        
        # Load checkpoint if resuming
        completed_pairs = {}
        if resume:
            checkpoint = self.checkpoint_service.load_checkpoint(session_id, 'batch_agents')
            if checkpoint:
                completed_pairs = {r['pair_index']: r for r in checkpoint.get('results', [])}
                results = list(completed_pairs.values())
                yield f"data: {json.dumps({'type': 'resume', 'completed': len(completed_pairs), 'total': len(pairs)})}\n\n"
        
        # Process pairs in parallel
        yield f"data: {json.dumps({'type': 'progress', 'stage': 'processing', 'message': f'Processing {total_pairs} pairs...'})}\n\n"
        
        futures = {}
        for pair_idx, pair in enumerate(pairs):
            if pair_idx in completed_pairs:
                continue
            
            future = self.executor.submit(
                self.process_single_agent_pair,
                pair,
                pair_idx,
                foci_list
            )
            futures[future] = pair_idx
        
        # Collect results as they complete
        for future in as_completed(futures):
            pair_idx = futures[future]
            result = future.result()
            results.append(result)
            completed_count += 1
            
            # Update checkpoint
            checkpoint_data = {
                'session_id': session_id,
                'timestamp': datetime.now().isoformat(),
                'type': 'batch_agents',
                'completed': completed_count,
                'total_pairs': total_pairs,
                'results': results,
                'complete': completed_count >= total_pairs
            }
            self.checkpoint_service.save_checkpoint(session_id, checkpoint_data, 'batch_agents')
            
            yield f"data: {json.dumps({'type': 'progress', 'stage': 'processing', 'completed': completed_count, 'total': total_pairs, 'pair_index': pair_idx})}\n\n"
            
            if result.get('success'):
                yield f"data: {json.dumps({'type': 'pair_result', 'pair_index': pair_idx, 'result': result})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'error', 'pair_index': pair_idx, 'error': result.get('error', 'Unknown error')})}\n\n"
        
        # Final result
        final_result = {
            'type': 'complete',
            'session_id': session_id,
            'completed': completed_count,
            'total_pairs': total_pairs,
            'results': results
        }
        
        yield f"data: {json.dumps(final_result)}\n\n"


