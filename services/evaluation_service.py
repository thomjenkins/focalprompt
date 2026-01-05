#!/usr/bin/env python3
"""
Evaluation service.

Handles LLM evaluation of batch agent results.
"""

import json
from typing import List, Dict, Optional, Generator
from concurrent.futures import ThreadPoolExecutor, as_completed
from services.cost_calculator import CostCalculator


class EvaluationService:
    """Service for evaluating batch agent results."""
    
    def __init__(
        self,
        provider,
        model: str,
        cost_calculator: Optional[CostCalculator] = None,
        max_workers: int = 10
    ):
        """
        Initialize evaluation service.
        
        Args:
            provider: LLM provider instance
            model: Model name to use
            cost_calculator: Optional CostCalculator instance
            max_workers: Maximum parallel workers
        """
        self.provider = provider
        self.model = model
        self.cost_calculator = cost_calculator or CostCalculator()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
    
    def process_single_evaluation(
        self,
        result: Dict,
        result_idx: int
    ) -> Dict:
        """
        Process a single evaluation - designed to run in parallel.
        
        Args:
            result: Result dictionary with input, original_output, new_output
            result_idx: Index of the result
            
        Returns:
            Dict with success, evaluation, and tokens
        """
        try:
            input_text = result.get('input', '')
            original_output = result.get('original_output', '')
            new_output = result.get('new_output', '')
            
            if not input_text or not original_output or not new_output:
                return {
                    'success': False,
                    'result_index': result_idx,
                    'error': 'Missing required fields'
                }
            
            # Use LLM to evaluate which output is better
            response = self.provider.chat_completion(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert evaluator comparing two AI agent outputs. You assess which output is better based on relevance, quality, and appropriateness for the given input."
                    },
                    {
                        "role": "user",
                        "content": f"""Compare these two outputs for the given input and determine which is better.

INPUT:
{input_text}

ORIGINAL OUTPUT:
{original_output}

NEW OUTPUT (OPTIMIZED):
{new_output}

Evaluate which output is better considering:
1. Relevance to the input
2. Quality and coherence
3. Appropriateness and helpfulness
4. Completeness

Return a JSON object with this structure:
{{
  "score": 0.85,
  "explanation": "Brief explanation of why one output is better than the other, or if they are similar",
  "better_output": "original" or "new" or "similar"
}}

Score should be:
- 0.0-0.4 = Original is significantly better
- 0.5 = They are similar/equal
- 0.6-1.0 = New is better (higher = much better)

If the new output is better, score should be > 0.5. If original is better, score should be < 0.5."""
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )
            
            # Track token usage
            input_tokens = response['usage']['prompt_tokens'] if 'usage' in response else 0
            output_tokens = response['usage']['completion_tokens'] if 'usage' in response else 0
            
            eval_result = json.loads(response['content'])
            
            return {
                'success': True,
                'result_index': result_idx,
                'evaluation': {
                    'score': float(eval_result.get('score', 0.5)),
                    'explanation': eval_result.get('explanation', ''),
                    'better_output': eval_result.get('better_output', 'similar')
                },
                'tokens': {
                    'input': input_tokens,
                    'output': output_tokens
                }
            }
        except Exception as e:
            return {
                'success': False,
                'result_index': result_idx,
                'error': str(e)
            }
    
    def stream_evaluations(
        self,
        results: List[Dict]
    ) -> Generator[str, None, None]:
        """
        Stream evaluation results.
        
        Args:
            results: List of result dictionaries
            
        Yields:
            SSE-formatted strings with progress updates
        """
        total_results = len(results)
        completed_count = 0
        total_input_tokens = 0
        total_output_tokens = 0
        evaluations = []
        
        yield f"data: {json.dumps({'type': 'progress', 'stage': 'processing', 'message': f'Evaluating {total_results} result(s) in parallel...', 'completed': 0, 'total': total_results})}\n\n"
        
        # Process results in batches
        batch_size = 10
        result_list = [(idx, result) for idx, result in enumerate(results)]
        
        for batch_start in range(0, len(result_list), batch_size):
            batch_end = min(batch_start + batch_size, len(result_list))
            batch = result_list[batch_start:batch_end]
            
            # Submit batch to thread pool
            futures = {}
            for result_idx, result in batch:
                future = self.executor.submit(
                    self.process_single_evaluation,
                    result,
                    result_idx
                )
                futures[future] = result_idx
            
            # Collect results as they complete
            for future in as_completed(futures):
                result_idx = futures[future]
                try:
                    process_result = future.result()
                    if process_result['success']:
                        evaluation = process_result['evaluation']
                        evaluations.append(evaluation)
                        completed_count += 1
                        
                        # Update token counts
                        if 'tokens' in process_result:
                            total_input_tokens += process_result['tokens']['input']
                            total_output_tokens += process_result['tokens']['output']
                        
                        # Send eval_complete event
                        yield f"data: {json.dumps({'type': 'eval_complete', 'result_index': result_idx, 'evaluation': evaluation, 'completed': completed_count, 'total': total_results})}\n\n"
                    else:
                        yield f"data: {json.dumps({'type': 'error', 'result_index': result_idx, 'message': process_result.get('error', 'Unknown error')})}\n\n"
                except Exception as e:
                    yield f"data: {json.dumps({'type': 'error', 'result_index': result_idx, 'message': str(e)})}\n\n"
        
        # Calculate costs
        cost_breakdown = self.cost_calculator.calculate_cost(
            total_input_tokens,
            total_output_tokens,
            0,  # No embeddings
            self.model,
            'openai'  # Default, should be provider-specific
        )
        
        # Send complete event
        yield f"data: {json.dumps({'type': 'complete', 'evaluations': evaluations, 'cost_breakdown': cost_breakdown})}\n\n"


