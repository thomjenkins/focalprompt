#!/usr/bin/env python3
"""
Flask web application for FocalPrompt
"""

import os
import json
import numpy as np
from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from flask_cors import CORS
from focal_assessor import FocalAssessor, FocusAssessment
from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import threading
import time
import uuid

app = Flask(__name__)
CORS(app)

# Initialize assessor
assessor = None

# Checkpoint directory
CHECKPOINT_DIR = "checkpoints"
os.makedirs(CHECKPOINT_DIR, exist_ok=True)

# Thread pool for parallel processing
executor = ThreadPoolExecutor(max_workers=10)  # Process up to 10 pairs concurrently

def get_assessor():
    """Get or create the assessor instance."""
    global assessor
    if assessor is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        assessor = FocalAssessor(api_key=api_key, model="gpt-4o-mini")
    return assessor


@app.route('/')
def index():
    """Serve the main page."""
    return render_template('index.html')


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint."""
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        return jsonify({
            'status': 'ok',
            'api_key_set': api_key is not None and len(api_key) > 0
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/detect-foci', methods=['POST'])
def detect_foci():
    """Use an agent to automatically detect foci from the prompt."""
    try:
        data = request.json
        prompt = data.get('prompt', '')
        
        if not prompt:
            return jsonify({'error': 'Prompt is required'}), 400
        
        # Check API key first
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return jsonify({'error': 'OPENAI_API_KEY environment variable not set. Please set it and restart the server.'}), 500
        
        assessor = get_assessor()
        client = assessor.client
        
        # Use LLM to detect foci from the prompt structure
        response = client.chat.completions.create(
            model=assessor.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at analyzing prompts and breaking them down into distinct structural components (foci). Each focus should be a specific instruction, requirement, constraint, or task from the prompt."
                },
                {
                    "role": "user",
                    "content": f"""Analyze the following prompt and break it down into distinct structural foci. Each focus should be a specific, identifiable part of the prompt itself - such as:
- A specific instruction or requirement
- A specific constraint or rule
- A specific task or objective
- A specific format requirement
- A specific section with distinct content

PROMPT:
{prompt}

Return a JSON object with this structure:
{{
  "foci": [
    {{
      "focus": "A brief description of this focus point",
      "prompt_section": "The exact text from the prompt that defines this focus (quote it directly)",
      "description": "A more detailed explanation of what this focus represents"
    }}
  ]
}}

Identify all distinct structural components of the prompt."""
                }
            ],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        
        result = json.loads(response.choices[0].message.content)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/detect-dynamic-foci', methods=['POST'])
def detect_dynamic_foci():
    """Auto-detect which foci should be marked as dynamic based on prompt structure and input patterns."""
    try:
        data = request.json
        prompt = data.get('prompt', '')
        foci = data.get('foci', [])
        pairs = data.get('pairs', [])
        
        if not prompt:
            return jsonify({'error': 'Prompt is required'}), 400
        if not foci or len(foci) == 0:
            return jsonify({'error': 'Foci are required'}), 400
        if not pairs or len(pairs) == 0:
            return jsonify({'error': 'At least one pair is required to detect dynamic patterns'}), 400
        
        # Check API key first
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return jsonify({'error': 'OPENAI_API_KEY environment variable not set. Please set it and restart the server.'}), 500
        
        assessor = get_assessor()
        client = assessor.client
        
        # Extract input patterns from pairs
        input_samples = []
        for pair in pairs[:10]:  # Sample up to 10 pairs for analysis
            inputs = get_pair_inputs(pair)
            input_samples.append({
                'chat_content': inputs.get('chat_content', '')[:200],  # Truncate for analysis
                'rag_context': inputs.get('rag_context', '')[:200],
                'tool_results': inputs.get('tool_results', '')[:200]
            })
        
        # Build foci list for analysis
        foci_list_text = '\n'.join([
            f"{i+1}. {f.get('focus', 'Unknown')}: {f.get('prompt_section', '')[:300]}"
            for i, f in enumerate(foci)
        ])
        
        # Use LLM to analyze which foci correspond to dynamic inputs
        response = client.chat.completions.create(
            model=assessor.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at analyzing prompt structures and identifying which sections correspond to dynamic inputs (chat content, RAG context, tool results) versus static instructions."
                },
                {
                    "role": "user",
                    "content": f"""Analyze the prompt structure and the input patterns to determine which foci should be marked as dynamic.

PROMPT:
{prompt}

FOCI:
{foci_list_text}

INPUT SAMPLES (showing patterns across different pairs):
{json.dumps(input_samples, indent=2)}

For each focus, determine:
1. Does this focus section contain a placeholder or reference to dynamic content (like "current chat", "user message", "retrieved context", "tool results", etc.)?
2. Do the input samples show that different pairs have different values for chat_content, rag_context, or tool_results?
3. Does the prompt_section text suggest this is where dynamic content would be inserted?

Return a JSON object with this structure:
{{
  "dynamic_suggestions": [
    {{
      "focus_index": 0,
      "focus_name": "Name of the focus",
      "should_be_dynamic": true,
      "dynamic_type": "chat" | "rag" | "tools" | null,
      "confidence": 0.0-1.0,
      "reasoning": "Explanation of why this should/shouldn't be dynamic"
    }}
  ]
}}

Match foci to input types based on:
- Keywords in prompt_section: "chat", "conversation", "message", "user input" → chat
- Keywords: "retrieved", "context", "knowledge", "RAG", "search results" → rag
- Keywords: "tool", "function", "API", "execution result" → tools
- Pattern matching: If prompt_section contains placeholders or references to variable content
- Input variation: If different pairs have different values for a specific input type

Only mark as dynamic if confidence > 0.6."""
                }
            ],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        
        result = json.loads(response.choices[0].message.content)
        
        # Apply suggestions to foci
        suggestions = result.get('dynamic_suggestions', [])
        updated_foci = []
        
        for i, focus in enumerate(foci):
            # Find matching suggestion
            suggestion = next((s for s in suggestions if s.get('focus_index') == i or s.get('focus_name', '').lower() == focus.get('focus', '').lower()), None)
            
            if suggestion and suggestion.get('should_be_dynamic') and suggestion.get('confidence', 0) > 0.6:
                updated_foci.append({
                    **focus,
                    'is_dynamic': True,
                    'dynamic_type': suggestion.get('dynamic_type')
                })
            else:
                updated_foci.append({
                    **focus,
                    'is_dynamic': focus.get('is_dynamic', False),
                    'dynamic_type': focus.get('dynamic_type')
                })
        
        return jsonify({
            'foci': updated_foci,
            'suggestions': suggestions
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/generate-output', methods=['POST'])
def generate_output():
    """Generate output using an agent."""
    try:
        data = request.json
        prompt = data.get('prompt', '')
        model = data.get('model', 'gpt-4o-mini')
        temperature = data.get('temperature', 0.7)
        
        if not prompt:
            return jsonify({'error': 'Prompt is required'}), 400
        
        # Check API key first
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return jsonify({'error': 'OPENAI_API_KEY environment variable not set. Please set it and restart the server.'}), 500
        
        assessor = get_assessor()
        output = assessor.generate_output(prompt, temperature=temperature)
        
        return jsonify({'output': output})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/rewrite-prompt', methods=['POST'])
def rewrite_prompt():
    """Rewrite prompt with emphasis based on focus weights."""
    try:
        data = request.json
        prompt = data.get('prompt', '')
        foci_weights = data.get('foci', [])
        
        if not prompt:
            return jsonify({'error': 'Prompt is required'}), 400
        
        if not foci_weights:
            return jsonify({'error': 'Foci with weights are required'}), 400
        
        # Check API key first
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return jsonify({'error': 'OPENAI_API_KEY environment variable not set. Please set it and restart the server.'}), 500
        
        assessor = get_assessor()
        client = assessor.client
        
        # Build the rewrite instruction
        weights_text = '\n'.join([
            f"- {f['focus']}: {f['weight']}% emphasis (covers: {f['prompt_section'][:100]}...)"
            for f in foci_weights
        ])
        
        rewrite_instruction = f"""Rewrite the following prompt to emphasize different aspects based on the specified weights. 
The weights indicate how much attention/emphasis should be given to each focus area in the final output.

ORIGINAL PROMPT:
{prompt}

FOCUS WEIGHTS:
{weights_text}

INSTRUCTIONS:
1. Rewrite the prompt to naturally emphasize aspects with higher weights
2. For high-weight foci (70-100%), make them prominent and explicit
3. For medium-weight foci (30-70%), include them clearly but not as prominently
4. For low-weight foci (0-30%), mention them briefly or implicitly
5. Maintain the original structure and meaning
6. Use emphasis techniques like:
   - Repetition for high-weight items
   - Stronger language for important aspects
   - Positioning important items earlier
   - Adding explicit instructions for high-weight foci
7. The rewritten prompt should guide the LLM to produce output that matches the intended focus distribution

Return only the rewritten prompt, without any additional explanation or formatting."""

        response = client.chat.completions.create(
            model=assessor.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at rewriting prompts to emphasize different aspects while maintaining clarity and coherence."
                },
                {
                    "role": "user",
                    "content": rewrite_instruction
                }
            ],
            temperature=0.7
        )
        
        rewritten = response.choices[0].message.content.strip()
        
        return jsonify({'rewritten_prompt': rewritten})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/assess', methods=['POST'])
def assess():
    """Assess focus distribution."""
    try:
        data = request.json
        prompt = data.get('prompt', '')
        output = data.get('output', '')
        user_foci = data.get('foci', [])  # Optional: user-defined foci
        max_foci = data.get('max_foci', None)
        
        if not prompt:
            return jsonify({'error': 'Prompt is required'}), 400
        if not output:
            return jsonify({'error': 'Output is required'}), 400
        
        # Check API key first
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return jsonify({'error': 'OPENAI_API_KEY environment variable not set. Please set it and restart the server.'}), 500
        
        assessor = get_assessor()
        
        # If user provided foci, use them for assessment
        if user_foci and len(user_foci) > 0:
            # Build a custom assessment that uses the user-defined foci
            assessment_prompt = assessor._build_assessment_prompt_with_foci(
                prompt, output, user_foci, max_foci
            )
            
            response = assessor.client.chat.completions.create(
                model=assessor.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at analyzing how well LLM outputs address different aspects of prompts. You assess the level of attention given to each specified focus point."
                    },
                    {
                        "role": "user",
                        "content": assessment_prompt
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Parse the response
            from focal_assessor import FocusScore, FocusAssessment
            foci_list = [
                FocusScore(
                    focus=item['focus'],
                    prompt_section=item.get('prompt_section', ''),
                    score=float(item['score']),
                    explanation=item['explanation']
                )
                for item in result['foci']
            ]
            
            # Verify total equals 100
            total = sum(f.score for f in foci_list)
            if abs(total - 100.0) > 0.1:
                if total > 0:
                    for focus in foci_list:
                        focus.score = (focus.score / total) * 100.0
            
            assessment = FocusAssessment(
                foci=foci_list,
                overall_summary=result.get('overall_summary', '')
            )
        else:
            # Use standard assessment
            assessment = assessor.assess(prompt, output, max_foci=max_foci)
        
        # Convert to dictionary for JSON response
        result = assessment.to_dict()
        
        # Save checkpoint for single assessment
        session_id = str(uuid.uuid4())
        checkpoint_data = {
            'session_id': session_id,
            'timestamp': datetime.now().isoformat(),
            'type': 'single_assessment',
            'result_data': {
                **result,
                'prompt': prompt,
                'output': output,
                'user_foci': user_foci if user_foci else None,
                'max_foci': max_foci
            },
            'complete': True
        }
        save_checkpoint(session_id, checkpoint_data, 'single_assessment')
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/ablation-analysis', methods=['POST'])
def ablation_analysis():
    """Run ablation analysis to determine focus influence."""
    try:
        data = request.json
        prompt = data.get('prompt', '')
        foci_list = data.get('foci', [])
        model = data.get('model', 'gpt-4o-mini')
        num_samples = data.get('num_samples', 1)  # For variance calculation
        
        if not prompt:
            return jsonify({'error': 'Prompt is required'}), 400
        
        if not foci_list or len(foci_list) == 0:
            return jsonify({'error': 'Foci are required for ablation analysis'}), 400
        
        # Check API key first
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return jsonify({'error': 'OPENAI_API_KEY environment variable not set. Please set it and restart the server.'}), 500
        
        assessor = get_assessor()
        client = assessor.client
        
        # Pricing per million tokens (as of 2024)
        # gpt-4o-mini: $0.15/$0.60 per million tokens (input/output)
        # text-embedding-3-small: $0.02 per million tokens
        PRICING = {
            'gpt-4o-mini': {'input': 0.15 / 1_000_000, 'output': 0.60 / 1_000_000},
            'gpt-4o': {'input': 2.50 / 1_000_000, 'output': 10.00 / 1_000_000},
            'gpt-4-turbo': {'input': 10.00 / 1_000_000, 'output': 30.00 / 1_000_000},
            'gpt-3.5-turbo': {'input': 0.50 / 1_000_000, 'output': 1.50 / 1_000_000},
            'embedding': 0.02 / 1_000_000
        }
        
        # Get pricing for the model being used
        model_pricing = PRICING.get(model, PRICING['gpt-4o-mini'])
        
        # Track costs
        total_input_tokens = 0
        total_output_tokens = 0
        total_embedding_tokens = 0
        cost_breakdown = {
            'chat_completions': {'input_tokens': 0, 'output_tokens': 0, 'cost': 0.0},
            'embeddings': {'tokens': 0, 'cost': 0.0},
            'total_cost': 0.0
        }
        
        # Step 1: Generate baseline output (full prompt)
        baseline_outputs = []
        for _ in range(num_samples):
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7 if num_samples > 1 else 0.7
            )
            baseline_outputs.append(response.choices[0].message.content)
            
            # Track token usage
            if hasattr(response, 'usage'):
                total_input_tokens += response.usage.prompt_tokens
                total_output_tokens += response.usage.completion_tokens
        
        baseline_output = baseline_outputs[0]  # Use first as primary baseline
        
        # Step 2: Generate ablated outputs (one focus removed at a time)
        ablation_results = []
        
        for i, focus in enumerate(foci_list):
            # Create ablated prompt by removing this focus's section from the full prompt
            focus_section = focus.get('prompt_section', '')
            
            if focus_section:
                # Remove the focus section from the prompt
                # Try to find and remove the exact text
                ablated_prompt = prompt.replace(focus_section, '').strip()
                # Clean up any double newlines that might result
                ablated_prompt = '\n'.join([line for line in ablated_prompt.split('\n') if line.strip()])
            else:
                # If no prompt_section, try to remove by focus name
                focus_name = focus.get('focus', '')
                if focus_name:
                    # Try to find lines containing the focus name
                    lines = prompt.split('\n')
                    ablated_lines = [line for line in lines if focus_name.lower() not in line.lower()]
                    ablated_prompt = '\n'.join(ablated_lines).strip()
                else:
                    # Fallback: reconstruct from other foci
                    ablated_prompt_parts = []
                    for j, f in enumerate(foci_list):
                        if i != j:
                            focus_text = f.get('prompt_section', '') or f.get('focus', '')
                            if focus_text:
                                ablated_prompt_parts.append(focus_text)
                    ablated_prompt = '\n\n'.join(ablated_prompt_parts)
            
            # Generate output for ablated prompt
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": ablated_prompt}],
                temperature=0.7
            )
            ablated_output = response.choices[0].message.content
            
            # Track token usage
            if hasattr(response, 'usage'):
                total_input_tokens += response.usage.prompt_tokens
                total_output_tokens += response.usage.completion_tokens
            
            ablation_results.append({
                'focus_index': i,
                'focus': focus.get('focus', f'Focus {i+1}'),
                'prompt_section': focus.get('prompt_section', ''),
                'ablated_output': ablated_output
            })
        
        # Step 3: Compute embeddings and similarities
        def get_embedding(text):
            """Get embedding for text using OpenAI."""
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            # Track embedding token usage
            if hasattr(response, 'usage'):
                nonlocal total_embedding_tokens
                total_embedding_tokens += response.usage.total_tokens
            return np.array(response.data[0].embedding)
        
        # Step 3: Calculate baseline noise/variance from multiple samples FIRST
        # This needs to be done before comparing ablated outputs
        baseline_variance = None
        baseline_std = None
        baseline_mean_similarity = None
        similarities_between_baselines = []
        noise_threshold = None
        
        if num_samples > 1:
            baseline_embeddings = [get_embedding(output) for output in baseline_outputs]
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
                # If similarity is below this threshold, the influence is significant
                # (i.e., removing this focus causes more change than baseline noise)
                noise_threshold = baseline_mean_similarity - (2 * baseline_std)
        
        # Use first baseline embedding for comparison with ablated outputs
        baseline_embedding = get_embedding(baseline_output)
        
        # Step 4: Calculate similarities and influence scores
        influence_scores = []
        similarities = []
        
        for i, ablation in enumerate(ablation_results):
            ablated_embedding = get_embedding(ablation['ablated_output'])
            
            # Cosine similarity
            similarity = np.dot(baseline_embedding, ablated_embedding) / (
                np.linalg.norm(baseline_embedding) * np.linalg.norm(ablated_embedding)
            )
            
            # Influence = 1 - similarity (higher influence = more different from baseline)
            influence = 1 - similarity
            
            similarities.append(similarity)
            
            # Get focus name from original foci list to ensure we have it
            focus_name = foci_list[i].get('focus', f'Focus {i+1}')
            
            # Determine if influence is significant (beyond noise)
            is_significant = None
            if noise_threshold is not None:
                # If similarity is below noise threshold, the difference is significant
                # (i.e., removing this focus causes more change than baseline noise)
                # Convert NumPy boolean to Python bool for JSON serialization
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
        chat_input_cost = total_input_tokens * model_pricing['input']
        chat_output_cost = total_output_tokens * model_pricing['output']
        embedding_cost = total_embedding_tokens * PRICING['embedding']
        total_cost = chat_input_cost + chat_output_cost + embedding_cost
        
        cost_breakdown['chat_completions'] = {
            'input_tokens': total_input_tokens,
            'output_tokens': total_output_tokens,
            'cost': chat_input_cost + chat_output_cost
        }
        cost_breakdown['embeddings'] = {
            'tokens': total_embedding_tokens,
            'cost': embedding_cost
        }
        cost_breakdown['total_cost'] = total_cost
        cost_breakdown['model'] = model
        
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
            'model': model
        }
        
        # Save checkpoint for single ablation analysis
        session_id = str(uuid.uuid4())
        checkpoint_data = {
            'session_id': session_id,
            'timestamp': datetime.now().isoformat(),
            'type': 'single_ablation',
            'result_data': result_data,
            'complete': True
        }
        save_checkpoint(session_id, checkpoint_data, 'single_ablation')
        
        return jsonify(result_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/assess-chat-foci', methods=['POST'])
def assess_chat_foci():
    """Assess chat content and assign weights to foci."""
    try:
        data = request.json
        chat_content = data.get('chat_content', '')
        foci_list = data.get('foci', [])
        
        if not chat_content:
            return jsonify({'error': 'Chat content is required'}), 400
        
        if not foci_list or len(foci_list) == 0:
            return jsonify({'error': 'Foci are required'}), 400
        
        # Check API key first
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return jsonify({'error': 'OPENAI_API_KEY environment variable not set. Please set it and restart the server.'}), 500
        
        assessor = get_assessor()
        client = assessor.client
        
        # Pricing per million tokens
        PRICING = {
            'gpt-4o-mini': {'input': 0.15 / 1_000_000, 'output': 0.60 / 1_000_000},
            'gpt-4o': {'input': 2.50 / 1_000_000, 'output': 10.00 / 1_000_000},
            'gpt-4-turbo': {'input': 10.00 / 1_000_000, 'output': 30.00 / 1_000_000},
            'gpt-3.5-turbo': {'input': 0.50 / 1_000_000, 'output': 1.50 / 1_000_000}
        }
        
        model_pricing = PRICING.get(assessor.model, PRICING['gpt-4o-mini'])
        
        # Track costs
        total_input_tokens = 0
        total_output_tokens = 0
        
        # Build foci list for prompt
        foci_text = '\n'.join([
            f"{i+1}. {f.get('focus', 'Unknown')}: {f.get('prompt_section', '')[:200]}..."
            for i, f in enumerate(foci_list)
        ])
        
        # Use LLM to assess relevance of each focus
        response = client.chat.completions.create(
            model=assessor.model,
            messages=[
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
        if hasattr(response, 'usage'):
            total_input_tokens += response.usage.prompt_tokens
            total_output_tokens += response.usage.completion_tokens
        
        result = json.loads(response.choices[0].message.content)
        
        # Calculate costs
        chat_input_cost = total_input_tokens * model_pricing['input']
        chat_output_cost = total_output_tokens * model_pricing['output']
        total_cost = chat_input_cost + chat_output_cost
        
        cost_breakdown = {
            'chat_completions': {
                'input_tokens': total_input_tokens,
                'output_tokens': total_output_tokens,
                'cost': total_cost
            },
            'total_cost': total_cost,
            'model': assessor.model
        }
        
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
        
        return jsonify({
            'foci_weights': foci_weights,
            'chat_weight': float(result.get('chat_weight', 0.5)),
            'chat_weight_explanation': result.get('chat_weight_explanation', ''),
            'cost_breakdown': cost_breakdown
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/build-agent-prompt', methods=['POST'])
def build_agent_prompt():
    """Build a prompt from weighted foci and chat content."""
    try:
        data = request.json
        foci_weights = data.get('foci', [])
        chat_content = data.get('chat_content', '')
        chat_weight = data.get('chat_weight', 0.5)
        
        if not foci_weights:
            return jsonify({'error': 'Foci weights are required'}), 400
        
        # We need to get the original foci with prompt_sections
        # The foci_weights should include prompt_section, but if not, we'll need to look it up
        # For now, assume foci_weights includes all necessary info
        
        # Filter foci with weight > 0.1 threshold
        relevant_foci = [f for f in foci_weights if f.get('weight', 0) > 0.1]
        
        # Sort by weight descending
        relevant_foci.sort(key=lambda x: x.get('weight', 0), reverse=True)
        
        # Build prompt sections
        prompt_parts = []
        
        # Add high-weight foci first (weight > 0.7)
        high_weight_foci = [f for f in relevant_foci if f.get('weight', 0) > 0.7]
        if high_weight_foci:
            prompt_parts.append("## Primary Instructions (High Priority)")
            for f in high_weight_foci:
                focus_name = f.get('focus', '')
                prompt_section = f.get('prompt_section', '')
                if prompt_section:
                    prompt_parts.append(f"\n### {focus_name}")
                    prompt_parts.append(prompt_section)
                else:
                    prompt_parts.append(f"\n### {focus_name}")
                    prompt_parts.append(f"[Focus: {focus_name} - Weight: {f.get('weight', 0):.2f}]")
        
        # Add medium-weight foci (0.3 < weight <= 0.7)
        medium_weight_foci = [f for f in relevant_foci if 0.3 < f.get('weight', 0) <= 0.7]
        if medium_weight_foci:
            prompt_parts.append("\n## Secondary Instructions (Medium Priority)")
            for f in medium_weight_foci:
                focus_name = f.get('focus', '')
                prompt_section = f.get('prompt_section', '')
                if prompt_section:
                    prompt_parts.append(f"\n### {focus_name}")
                    prompt_parts.append(prompt_section)
                else:
                    prompt_parts.append(f"\n### {focus_name}")
                    prompt_parts.append(f"[Focus: {focus_name} - Weight: {f.get('weight', 0):.2f}]")
        
        # Add low-weight but relevant foci (0.1 < weight <= 0.3)
        low_weight_foci = [f for f in relevant_foci if 0.1 < f.get('weight', 0) <= 0.3]
        if low_weight_foci:
            prompt_parts.append("\n## Context (Low Priority)")
            for f in low_weight_foci:
                focus_name = f.get('focus', '')
                prompt_section = f.get('prompt_section', '')
                if prompt_section:
                    prompt_parts.append(f"\n### {focus_name}")
                    prompt_parts.append(prompt_section)
                else:
                    prompt_parts.append(f"\n### {focus_name}")
                    prompt_parts.append(f"[Focus: {focus_name} - Weight: {f.get('weight', 0):.2f}]")
        
        # Get inputs (for /api/build-agent-prompt, chat_content is passed directly)
        inputs = {
            'chat_content': chat_content,
            'rag_context': '',
            'tool_results': ''
        }
        
        # Build prompt with dynamic foci support
        # Note: foci_weights should include is_dynamic and dynamic_type from original foci_list
        # We need to get the original foci_list to check dynamic types
        # For now, we'll build it manually but ideally this endpoint should receive foci_list
        constructed_prompt = build_prompt_with_dynamic_foci(relevant_foci, [], inputs, chat_weight)
        
        # Fallback: if no dynamic foci handling, use old method
        if not constructed_prompt or constructed_prompt.strip() == '':
            prompt_parts = []
            # Add high-weight foci first (weight > 0.7)
            high_weight_foci = [f for f in relevant_foci if f.get('weight', 0) > 0.7]
            if high_weight_foci:
                prompt_parts.append("## Primary Instructions (High Priority)")
                for f in high_weight_foci:
                    focus_name = f.get('focus', '')
                    prompt_section = f.get('prompt_section', '')
                    if prompt_section:
                        prompt_parts.append(f"\n### {focus_name}")
                        prompt_parts.append(prompt_section)
            
            # Add medium-weight foci (0.3 < weight <= 0.7)
            medium_weight_foci = [f for f in relevant_foci if 0.3 < f.get('weight', 0) <= 0.7]
            if medium_weight_foci:
                prompt_parts.append("\n## Secondary Instructions (Medium Priority)")
                for f in medium_weight_foci:
                    focus_name = f.get('focus', '')
                    prompt_section = f.get('prompt_section', '')
                    if prompt_section:
                        prompt_parts.append(f"\n### {focus_name}")
                        prompt_parts.append(prompt_section)
            
            # Add low-weight but relevant foci (0.1 < weight <= 0.3)
            low_weight_foci = [f for f in relevant_foci if 0.1 < f.get('weight', 0) <= 0.3]
            if low_weight_foci:
                prompt_parts.append("\n## Context (Low Priority)")
                for f in low_weight_foci:
                    focus_name = f.get('focus', '')
                    prompt_section = f.get('prompt_section', '')
                    if prompt_section:
                        prompt_parts.append(f"\n### {focus_name}")
                        prompt_parts.append(prompt_section)
            
            # Add chat content based on its weight
            if chat_weight > 0.1:
                prompt_parts.append(f"\n## Current Chat Context (Weight: {chat_weight:.2f})")
                prompt_parts.append(f"\n{chat_content}")
            
            constructed_prompt = '\n'.join(prompt_parts)
        
        return jsonify({
            'constructed_prompt': constructed_prompt,
            'selected_foci': [f.get('focus') for f in relevant_foci],
            'chat_included': chat_weight > 0.1
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/generate-agent-response', methods=['POST'])
def generate_agent_response():
    """Generate agent response using constructed prompt."""
    try:
        data = request.json
        constructed_prompt = data.get('constructed_prompt', '')
        chat_content = data.get('chat_content', '')
        model = data.get('model', 'gpt-4o-mini')
        temperature = data.get('temperature', 0.7)
        
        if not constructed_prompt:
            return jsonify({'error': 'Constructed prompt is required'}), 400
        
        # Check API key first
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return jsonify({'error': 'OPENAI_API_KEY environment variable not set. Please set it and restart the server.'}), 500
        
        assessor = get_assessor()
        client = assessor.client
        
        # Pricing per million tokens
        PRICING = {
            'gpt-4o-mini': {'input': 0.15 / 1_000_000, 'output': 0.60 / 1_000_000},
            'gpt-4o': {'input': 2.50 / 1_000_000, 'output': 10.00 / 1_000_000},
            'gpt-4-turbo': {'input': 10.00 / 1_000_000, 'output': 30.00 / 1_000_000},
            'gpt-3.5-turbo': {'input': 0.50 / 1_000_000, 'output': 1.50 / 1_000_000}
        }
        
        model_pricing = PRICING.get(model, PRICING['gpt-4o-mini'])
        
        # Track costs
        total_input_tokens = 0
        total_output_tokens = 0
        
        # Generate output
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": constructed_prompt}],
            temperature=temperature
        )
        output = response.choices[0].message.content
        
        # Track token usage
        if hasattr(response, 'usage'):
            total_input_tokens += response.usage.prompt_tokens
            total_output_tokens += response.usage.completion_tokens
        
        # Calculate costs
        chat_input_cost = total_input_tokens * model_pricing['input']
        chat_output_cost = total_output_tokens * model_pricing['output']
        total_cost = chat_input_cost + chat_output_cost
        
        cost_breakdown = {
            'chat_completions': {
                'input_tokens': total_input_tokens,
                'output_tokens': total_output_tokens,
                'cost': total_cost
            },
            'total_cost': total_cost,
            'model': model
        }
        
        return jsonify({
            'output': output,
            'constructed_prompt': constructed_prompt,
            'cost_breakdown': cost_breakdown
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def get_checkpoint_path(session_id, checkpoint_type='batch_analysis'):
    """Get checkpoint file path for a session."""
    return os.path.join(CHECKPOINT_DIR, f"{checkpoint_type}_{session_id}.json")


def save_checkpoint(session_id, checkpoint_data, checkpoint_type='batch_analysis'):
    """Save checkpoint data to file using atomic writes."""
    checkpoint_path = get_checkpoint_path(session_id, checkpoint_type)
    temp_path = checkpoint_path + '.tmp'
    
    try:
        # Write to temporary file first
        with open(temp_path, 'w') as f:
            json.dump(checkpoint_data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())  # Force write to disk
        
        # Verify the temp file is valid JSON
        try:
            with open(temp_path, 'r') as f:
                loaded = json.load(f)  # Verify it's valid JSON
                # Verify it has the expected structure
                if loaded.get('session_id') != session_id:
                    print(f"Warning: Session ID mismatch in checkpoint")
        except json.JSONDecodeError as e:
            print(f"Error: Written checkpoint is invalid JSON: {e}")
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return False
        
        # Atomic rename (this is atomic on most filesystems)
        os.rename(temp_path, checkpoint_path)
        
        # Verify final file exists and is readable
        if os.path.exists(checkpoint_path):
            with open(checkpoint_path, 'r') as f:
                loaded = json.load(f)
                if loaded.get('session_id') == session_id:
                    pair_count = len(checkpoint_data.get('pair_results', []))
                    print(f"Checkpoint saved successfully: {checkpoint_path} ({pair_count} pairs)")
                    return True
        
        return False
    except Exception as e:
        print(f"Error saving checkpoint: {e}")
        # Clean up temp file if it exists
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass
        return False


def load_checkpoint(session_id, checkpoint_type='batch_analysis'):
    """Load checkpoint data from file."""
    checkpoint_path = get_checkpoint_path(session_id, checkpoint_type)
    try:
        if os.path.exists(checkpoint_path):
            with open(checkpoint_path, 'r') as f:
                content = f.read().strip()
                if not content:
                    print(f"Checkpoint file {session_id} is empty")
                    return None
                
                # Try to parse JSON
                try:
                    return json.loads(content)
                except json.JSONDecodeError as e:
                    # File might be incomplete/corrupted - try to recover what we can
                    print(f"Warning: Checkpoint {session_id} has invalid JSON: {e}")
                    print(f"Attempting to recover data from incomplete file...")
                    
                    # Try to extract pair_results if possible
                    # Look for the last complete pair_result entry
                    try:
                        # Find the last complete pair_result by looking for closing braces
                        # This is a simple heuristic - find the last "}" that might close a pair_result
                        import re
                        # Try to find all complete pair_result entries
                        # Look for pattern: {"success": true, ... } with proper nesting
                        pair_results = []
                        # Simple recovery: try to parse up to the error point
                        # Find the last complete object in pair_results array
                        brace_count = 0
                        last_valid_pos = 0
                        in_pair_result = False
                        
                        # For now, just try to extract what we can
                        # Look for "pair_results": [ and try to extract complete entries
                        if '"pair_results"' in content and '[' in content:
                            start_idx = content.find('"pair_results"')
                            array_start = content.find('[', start_idx)
                            if array_start > 0:
                                # Try to extract complete entries by finding matching braces
                                # This is a simplified recovery - in production you might want more robust parsing
                                pass
                        
                        # If we can't recover, return None and let the caller handle it
                        print(f"Could not recover data from corrupted checkpoint {session_id}")
                        return None
                    except Exception as recovery_error:
                        print(f"Error during recovery attempt: {recovery_error}")
                        return None
    except Exception as e:
        print(f"Error loading checkpoint: {e}")
    return None


def calculate_statistics_from_results(pair_results):
    """Calculate statistics from pair results if they're missing from checkpoint."""
    all_focus_influences = {}
    all_chat_influences = []
    
    for result in pair_results:
        if not result.get('success', False):
            continue
        
        # Collect focus influences
        influence_scores = result.get('influence_scores', {})
        for focus_name, influence_data in influence_scores.items():
            if focus_name not in all_focus_influences:
                all_focus_influences[focus_name] = []
            all_focus_influences[focus_name].append(influence_data.get('influence', 0.0))
        
        # Collect chat content influence
        chat_influence = result.get('chat_content_influence', {})
        if 'influence' in chat_influence:
            all_chat_influences.append(chat_influence['influence'])
    
    # Calculate statistics
    statistics = {}
    for focus_name, influences in all_focus_influences.items():
        if len(influences) > 0:
            statistics[focus_name] = {
                'mean': float(np.mean(influences)),
                'variance': float(np.var(influences)),
                'std_dev': float(np.std(influences)),
                'min': float(np.min(influences)),
                'max': float(np.max(influences))
            }
    
    if len(all_chat_influences) > 0:
        statistics['chat_content'] = {
            'mean': float(np.mean(all_chat_influences)),
            'variance': float(np.var(all_chat_influences)),
            'std_dev': float(np.std(all_chat_influences)),
            'min': float(np.min(all_chat_influences)),
            'max': float(np.max(all_chat_influences))
        }
    
    # Extract noise statistics from the first pair's noise_metrics (batch-wide calculation)
    if pair_results and len(pair_results) > 0:
        first_result = pair_results[0]
        if first_result.get('success', False):
            noise_metrics = first_result.get('noise_metrics', {})
            if noise_metrics and noise_metrics.get('is_batch_wide', False):
                # Extract noise statistics from the first pair (they're all the same for batch-wide)
                statistics['noise'] = {
                    'mean': noise_metrics.get('mean_similarity', 1.0),
                    'variance': noise_metrics.get('variance', 0.0),
                    'std_dev': noise_metrics.get('std_dev', 0.0),
                    'noise_threshold': noise_metrics.get('threshold'),
                    'num_samples': 20  # Default, could be stored in checkpoint if needed
                }
    
    return statistics


@app.route('/api/list-checkpoints', methods=['GET'])
def list_checkpoints():
    """List all available checkpoints."""
    try:
        checkpoint_type = request.args.get('type', 'batch_analysis')  # 'batch_analysis', 'batch_agents', 'single_ablation', 'single_assessment'
        checkpoints = []
        if os.path.exists(CHECKPOINT_DIR):
            # Map checkpoint types to their file prefixes
            prefix_map = {
                'batch_analysis': 'batch_analysis_',
                'batch_agents': 'batch_agents_',
                'single_ablation': 'single_ablation_',
                'single_assessment': 'single_assessment_'
            }
            prefix = prefix_map.get(checkpoint_type, 'batch_analysis_')
            
            for filename in os.listdir(CHECKPOINT_DIR):
                if filename.startswith(prefix) and filename.endswith('.json'):
                    session_id = filename.replace(prefix, '').replace('.json', '')
                    checkpoint_path = get_checkpoint_path(session_id, checkpoint_type)
                    try:
                        stat = os.stat(checkpoint_path)
                        checkpoint = load_checkpoint(session_id, checkpoint_type)
                        
                        if checkpoint:
                            # Successfully loaded checkpoint
                            checkpoint_info = {
                                'session_id': session_id,
                                'timestamp': checkpoint.get('timestamp', ''),
                                'complete': checkpoint.get('complete', False),
                                'file_size': stat.st_size,
                                'modified': stat.st_mtime,
                                'corrupted': False,
                                'type': checkpoint_type
                            }
                            
                            # Add type-specific fields
                            if checkpoint_type == 'single_assessment':
                                checkpoint_info['num_foci'] = len(checkpoint.get('result_data', {}).get('foci', []))
                                checkpoint_info['has_output'] = bool(checkpoint.get('result_data', {}).get('output'))
                            elif checkpoint_type == 'single_ablation':
                                checkpoint_info['num_foci'] = len(checkpoint.get('result_data', {}).get('influence_scores', []))
                                checkpoint_info['model'] = checkpoint.get('result_data', {}).get('model', 'unknown')
                            elif checkpoint_type == 'batch_agents':
                                checkpoint_info['completed'] = checkpoint.get('completed', 0)
                                checkpoint_info['total_pairs'] = checkpoint.get('total_pairs', 0)
                                checkpoint_info['total_results'] = len(checkpoint.get('results', []))
                            else:  # batch_analysis
                                checkpoint_info['completed'] = checkpoint.get('completed', 0)
                                checkpoint_info['total_pairs'] = checkpoint.get('total_pairs', 0)
                            
                            checkpoints.append(checkpoint_info)
                        else:
                            # File exists but couldn't be loaded (corrupted/incomplete)
                            # Try to get basic info from file metadata
                            checkpoints.append({
                                'session_id': session_id,
                                'timestamp': '',
                                'completed': 0,
                                'total_pairs': 0,
                                'complete': False,
                                'file_size': stat.st_size,
                                'modified': stat.st_mtime,
                                'corrupted': True,
                                'error': 'File exists but is corrupted or incomplete'
                            })
                    except Exception as e:
                        print(f"Error reading checkpoint {session_id}: {e}")
                        # Still add it to the list with error info
                        try:
                            stat = os.stat(checkpoint_path)
                            checkpoints.append({
                                'session_id': session_id,
                                'timestamp': '',
                                'completed': 0,
                                'total_pairs': 0,
                                'complete': False,
                                'file_size': stat.st_size,
                                'modified': stat.st_mtime,
                                'corrupted': True,
                                'error': str(e)
                            })
                        except:
                            pass
        
        # Sort by modified time (newest first)
        checkpoints.sort(key=lambda x: x.get('modified', 0), reverse=True)
        return jsonify({'checkpoints': checkpoints})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/get-checkpoint', methods=['GET'])
def get_checkpoint():
    """Retrieve checkpoint data for a session."""
    try:
        session_id = request.args.get('session_id')
        checkpoint_type = request.args.get('type', 'batch_analysis')
        if not session_id:
            return jsonify({'error': 'session_id required'}), 400
        
        checkpoint = load_checkpoint(session_id, checkpoint_type)
        if checkpoint:
            # If statistics are missing, calculate them from results
            if 'statistics' not in checkpoint or not checkpoint.get('statistics'):
                print(f"Statistics missing from checkpoint {session_id}, calculating from results...")
                pair_results = checkpoint.get('pair_results', [])
                if pair_results:
                    checkpoint['statistics'] = calculate_statistics_from_results(pair_results)
            
            return jsonify(checkpoint)
        else:
            return jsonify({'error': 'Checkpoint not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def get_pair_inputs(pair_data):
    """Extract inputs from pair data, handling both old and new structure."""
    if 'inputs' in pair_data:
        # New structure
        inputs = pair_data.get('inputs', {})
        return {
            'chat_content': inputs.get('chat_content', ''),
            'rag_context': inputs.get('rag_context', ''),
            'tool_results': inputs.get('tool_results', '')
        }
    else:
        # Old structure - backward compatibility
        return {
            'chat_content': pair_data.get('chat_content', '') or pair_data.get('input', ''),
            'rag_context': pair_data.get('rag_context', ''),
            'tool_results': pair_data.get('tool_results', '')
        }

def build_prompt_with_dynamic_foci(relevant_foci, foci_list, inputs, chat_weight=0.5):
    """Build prompt with placeholders for dynamic foci, then replace with actual values."""
    prompt_parts = []
    
    # Helper to get dynamic type for a focus
    def get_focus_dynamic_type(focus_name):
        for f in foci_list:
            if f.get('focus', '') == focus_name:
                return f.get('dynamic_type') if f.get('is_dynamic') else None
        return None
    
    # Helper to get placeholder for dynamic type
    def get_placeholder(dynamic_type):
        placeholders = {
            'chat': '{{CHAT_CONTENT}}',
            'rag': '{{RAG_CONTEXT}}',
            'tools': '{{TOOL_RESULTS}}',
            'other': '{{OTHER_INPUT}}'
        }
        return placeholders.get(dynamic_type, '{{DYNAMIC_CONTENT}}')
    
    # Helper to get actual value for dynamic type
    def get_actual_value(dynamic_type):
        if dynamic_type == 'chat':
            return inputs.get('chat_content', '')
        elif dynamic_type == 'rag':
            return inputs.get('rag_context', '')
        elif dynamic_type == 'tools':
            return inputs.get('tool_results', '')
        elif dynamic_type == 'other':
            return inputs.get('other_input', '')
        return ''
    
    # Add high-weight foci (weight > 0.7)
    high_weight_foci = [f for f in relevant_foci if f.get('weight', 0) > 0.7]
    if high_weight_foci:
        prompt_parts.append("## Primary Instructions (High Priority)")
        for f in high_weight_foci:
            focus_name = f.get('focus', '')
            prompt_section = f.get('prompt_section', '')
            dynamic_type = get_focus_dynamic_type(focus_name)
            
            prompt_parts.append(f"\n### {focus_name}")
            if dynamic_type:
                # For dynamic foci, replace content with placeholder
                # Keep structural context but replace actual content
                placeholder = get_placeholder(dynamic_type)
                # Try to replace the actual dynamic content with placeholder
                # For now, append placeholder after the section
                prompt_parts.append(prompt_section)
                prompt_parts.append(f"\n{placeholder}")
            else:
                # Static focus - include as-is
                prompt_parts.append(prompt_section)
    
    # Add medium-weight foci (0.3 < weight <= 0.7)
    medium_weight_foci = [f for f in relevant_foci if 0.3 < f.get('weight', 0) <= 0.7]
    if medium_weight_foci:
        prompt_parts.append("\n## Secondary Instructions (Medium Priority)")
        for f in medium_weight_foci:
            focus_name = f.get('focus', '')
            prompt_section = f.get('prompt_section', '')
            dynamic_type = get_focus_dynamic_type(focus_name)
            
            prompt_parts.append(f"\n### {focus_name}")
            if dynamic_type:
                prompt_parts.append(prompt_section)
                prompt_parts.append(f"\n{get_placeholder(dynamic_type)}")
            else:
                prompt_parts.append(prompt_section)
    
    # Add low-weight but relevant foci (0.1 < weight <= 0.3)
    low_weight_foci = [f for f in relevant_foci if 0.1 < f.get('weight', 0) <= 0.3]
    if low_weight_foci:
        prompt_parts.append("\n## Context (Low Priority)")
        for f in low_weight_foci:
            focus_name = f.get('focus', '')
            prompt_section = f.get('prompt_section', '')
            dynamic_type = get_focus_dynamic_type(focus_name)
            
            prompt_parts.append(f"\n### {focus_name}")
            if dynamic_type:
                prompt_parts.append(prompt_section)
                prompt_parts.append(f"\n{get_placeholder(dynamic_type)}")
            else:
                prompt_parts.append(prompt_section)
    
    # Replace placeholders with actual values
    constructed_prompt = '\n'.join(prompt_parts)
    
    # Replace all placeholders with actual values
    constructed_prompt = constructed_prompt.replace('{{CHAT_CONTENT}}', inputs.get('chat_content', ''))
    constructed_prompt = constructed_prompt.replace('{{RAG_CONTEXT}}', inputs.get('rag_context', ''))
    constructed_prompt = constructed_prompt.replace('{{TOOL_RESULTS}}', inputs.get('tool_results', ''))
    constructed_prompt = constructed_prompt.replace('{{OTHER_INPUT}}', inputs.get('other_input', ''))
    
    # Also handle chat_weight for backward compatibility (if chat_weight > 0.1 and no chat focus)
    # This is for the old way where chat was added separately
    if chat_weight > 0.1 and '{{CHAT_CONTENT}}' not in constructed_prompt:
        chat_content = inputs.get('chat_content', '')
        if chat_content:
            prompt_parts.append(f"\n## Current Chat Context (Weight: {chat_weight:.2f})")
            prompt_parts.append(f"\n{chat_content}")
            constructed_prompt = '\n'.join(prompt_parts)
    
    return constructed_prompt

def process_single_pair(pair_data, pair_idx, foci_list, model, batch_noise_threshold, baseline_variance, baseline_std, baseline_mean_similarity, client, get_embedding_func):
    """Process a single pair - designed to run in parallel."""
    try:
        prompt = pair_data.get('prompt', '')
        inputs = get_pair_inputs(pair_data)
        chat_content = inputs['chat_content']
        
        # Generate baseline output
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        baseline_output = response.choices[0].message.content
        
        input_tokens = response.usage.prompt_tokens if hasattr(response, 'usage') else 0
        output_tokens = response.usage.completion_tokens if hasattr(response, 'usage') else 0
        
        # Get baseline embedding
        baseline_embedding = get_embedding_func(baseline_output)
        embedding_tokens = 0  # Tracked separately
        
        # Process each focus
        focus_influences = {}
        for focus_to_remove in foci_list:
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
            
            # Generate ablated output
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": ablated_prompt}],
                temperature=0.7
            )
            ablated_output = response.choices[0].message.content
            
            input_tokens += response.usage.prompt_tokens if hasattr(response, 'usage') else 0
            output_tokens += response.usage.completion_tokens if hasattr(response, 'usage') else 0
            
            # Calculate similarity and influence
            ablated_embedding = get_embedding_func(ablated_output)
            similarity = np.dot(baseline_embedding, ablated_embedding) / (
                np.linalg.norm(baseline_embedding) * np.linalg.norm(ablated_embedding)
            )
            influence = 1 - similarity
            # Convert NumPy boolean to Python bool for JSON serialization
            is_significant = bool(similarity < batch_noise_threshold) if batch_noise_threshold else None
            
            focus_influences[focus_name] = {
                'influence': float(influence),
                'similarity': float(similarity),
                'is_significant': is_significant
            }
        
        # Calculate chat_content influence
        ablated_prompt_no_chat = prompt.replace(chat_content, '').strip()
        ablated_prompt_no_chat = '\n'.join([line for line in ablated_prompt_no_chat.split('\n') if line.strip()])
        
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": ablated_prompt_no_chat}],
            temperature=0.7
        )
        ablated_output_no_chat = response.choices[0].message.content
        
        input_tokens += response.usage.prompt_tokens if hasattr(response, 'usage') else 0
        output_tokens += response.usage.completion_tokens if hasattr(response, 'usage') else 0
        
        ablated_embedding_no_chat = get_embedding_func(ablated_output_no_chat)
        similarity_chat = np.dot(baseline_embedding, ablated_embedding_no_chat) / (
            np.linalg.norm(baseline_embedding) * np.linalg.norm(ablated_embedding_no_chat)
        )
        influence_chat = 1 - similarity_chat
        # Convert NumPy boolean to Python bool for JSON serialization
        is_significant_chat = bool(similarity_chat < batch_noise_threshold) if batch_noise_threshold else None
        
        return {
            'success': True,
            'pair_index': pair_idx,
            'pair_data': pair_data,
            'influence_scores': focus_influences,
            'chat_content_influence': {
                'influence': float(influence_chat),
                'similarity': float(similarity_chat),
                'is_significant': is_significant_chat
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
                'embedding': embedding_tokens  # Will be calculated separately
            }
        }
    except Exception as e:
        return {
            'success': False,
            'pair_index': pair_idx,
            'error': str(e)
        }


@app.route('/api/batch-ablation-analysis-stream', methods=['POST'])
@stream_with_context
def batch_ablation_analysis_stream():
    """Run ablation analysis with streaming progress updates via SSE."""
    def generate():
        try:
            data = request.json
            pairs = data.get('pairs', [])
            foci_list = data.get('foci', [])
            model = data.get('model', 'gpt-4o-mini')
            num_samples = data.get('num_samples', 20)
            session_id = data.get('session_id', datetime.now().strftime('%Y%m%d_%H%M%S'))
            resume = data.get('resume', False)
            
            if not pairs or len(pairs) == 0:
                yield f"data: {json.dumps({'type': 'error', 'message': 'At least one pair is required'})}\n\n"
                return
            
            if not foci_list or len(foci_list) == 0:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Foci are required'})}\n\n"
                return
            
            # Check API key
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                yield f"data: {json.dumps({'type': 'error', 'message': 'OPENAI_API_KEY not set'})}\n\n"
                return
            
            assessor = get_assessor()
            client = assessor.client
            
            # Pricing
            PRICING = {
                'gpt-4o-mini': {'input': 0.15 / 1_000_000, 'output': 0.60 / 1_000_000},
                'gpt-4o': {'input': 2.50 / 1_000_000, 'output': 10.00 / 1_000_000},
                'gpt-4-turbo': {'input': 10.00 / 1_000_000, 'output': 30.00 / 1_000_000},
                'gpt-3.5-turbo': {'input': 0.50 / 1_000_000, 'output': 1.50 / 1_000_000},
                'embedding': 0.02 / 1_000_000
            }
            model_pricing = PRICING.get(model, PRICING['gpt-4o-mini'])
            
            # Track costs
            total_input_tokens = 0
            total_output_tokens = 0
            total_embedding_tokens = 0
            
            # Helper for embeddings with token tracking
            def get_embedding(text):
                response = client.embeddings.create(
                    model="text-embedding-3-small",
                    input=text
                )
                nonlocal total_embedding_tokens
                if hasattr(response, 'usage'):
                    total_embedding_tokens += response.usage.total_tokens
                return np.array(response.data[0].embedding)
            
            # Initialize variables for emergency checkpoint saving
            pair_results = []
            total_pairs = len(pairs)
            completed_count = 0
            
            # Load checkpoint if resuming
            completed_pairs = {}
            if resume:
                checkpoint = load_checkpoint(session_id)
                if checkpoint:
                    completed_pairs = {r['pair_index']: r for r in checkpoint.get('pair_results', [])}
                    pair_results = list(completed_pairs.values())
                    yield f"data: {json.dumps({'type': 'resume', 'completed': len(completed_pairs), 'total': len(pairs)})}\n\n"
            
            # Step 1: Calculate baseline noise ONCE for the entire batch
            # Use system prompt only (without chat content) for noise calculation
            if len(pairs) > 0:
                first_pair = pairs[0]
                system_prompt = first_pair.get('prompt', '')
                inputs = get_pair_inputs(first_pair)
                chat_content = inputs['chat_content']
                
                # Explicitly ensure we use system prompt only (remove chat_content if present)
                if chat_content and chat_content in system_prompt:
                    system_prompt = system_prompt.replace(chat_content, '').strip()
                    system_prompt = '\n'.join([line for line in system_prompt.split('\n') if line.strip()])
                
                representative_prompt = system_prompt
                
                yield f"data: {json.dumps({'type': 'progress', 'stage': 'noise_calculation', 'message': f'Calculating baseline noise from {num_samples} samples (using system prompt only)...'})}\n\n"
                
                baseline_outputs = []
                for i in range(num_samples):
                    response = client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": representative_prompt}],
                        temperature=0.7
                    )
                    baseline_outputs.append(response.choices[0].message.content)
                    
                    if hasattr(response, 'usage'):
                        total_input_tokens += response.usage.prompt_tokens
                        total_output_tokens += response.usage.completion_tokens
                    
                    yield f"data: {json.dumps({'type': 'progress', 'stage': 'noise_calculation', 'sample': i+1, 'total': num_samples})}\n\n"
                
                baseline_embeddings = [get_embedding(output) for output in baseline_outputs]
                similarities_between_baselines = []
                for i in range(len(baseline_embeddings)):
                    for j in range(i+1, len(baseline_embeddings)):
                        sim = np.dot(baseline_embeddings[i], baseline_embeddings[j]) / (
                            np.linalg.norm(baseline_embeddings[i]) * np.linalg.norm(baseline_embeddings[j])
                        )
                        similarities_between_baselines.append(sim)
                
                baseline_variance = float(np.var(similarities_between_baselines)) if similarities_between_baselines else 0.0
                baseline_std = float(np.std(similarities_between_baselines)) if similarities_between_baselines else 0.0
                baseline_mean_similarity = float(np.mean(similarities_between_baselines)) if similarities_between_baselines else 1.0
                batch_noise_threshold = baseline_mean_similarity - (2 * baseline_std) if baseline_std else None
            else:
                batch_noise_threshold = None
                baseline_variance = 0.0
                baseline_std = 0.0
                baseline_mean_similarity = 1.0
            
            # Step 2: Process pairs in parallel
            remaining_pairs = [(idx, pair) for idx, pair in enumerate(pairs) if idx not in completed_pairs]
            # Update counts if resuming
            if resume and len(completed_pairs) > 0:
                completed_count = len(completed_pairs)
                pair_results = list(completed_pairs.values())
            checkpoint_interval = 10  # Save checkpoint every 10 pairs
            
            yield f"data: {json.dumps({'type': 'progress', 'stage': 'processing', 'message': f'Processing {len(remaining_pairs)} pairs in parallel...', 'completed': completed_count, 'total': total_pairs})}\n\n"
            
            # Process pairs in batches for better control
            batch_size = 10  # Process 10 pairs at a time
            all_focus_influences = {}
            all_chat_influences = []
            
            for batch_start in range(0, len(remaining_pairs), batch_size):
                batch_end = min(batch_start + batch_size, len(remaining_pairs))
                batch = remaining_pairs[batch_start:batch_end]
                
                # Submit batch to thread pool
                futures = {}
                for pair_idx, pair in batch:
                    future = executor.submit(
                        process_single_pair,
                        pair, pair_idx, foci_list, model,
                        batch_noise_threshold, baseline_variance, baseline_std, baseline_mean_similarity,
                        client, get_embedding
                    )
                    futures[future] = pair_idx
                
                # Collect results as they complete
                batch_results_collected = []
                for future in as_completed(futures):
                    pair_idx = futures[future]
                    try:
                        result = future.result()
                        if result['success']:
                            pair_results.append(result)
                            batch_results_collected.append(result)
                            completed_count += 1
                            
                            # Track influences for statistics
                            for focus_name, influence_data in result['influence_scores'].items():
                                if focus_name not in all_focus_influences:
                                    all_focus_influences[focus_name] = []
                                all_focus_influences[focus_name].append(influence_data['influence'])
                            
                            all_chat_influences.append(result['chat_content_influence']['influence'])
                            
                            # Update token counts
                            total_input_tokens += result['tokens']['input']
                            total_output_tokens += result['tokens']['output']
                            
                            # Send progress update
                            yield f"data: {json.dumps({'type': 'pair_complete', 'pair_index': pair_idx, 'completed': completed_count, 'total': total_pairs})}\n\n"
                            
                            # Save checkpoint periodically (every 10 pairs)
                            if completed_count % checkpoint_interval == 0:
                                checkpoint_data = {
                                    'session_id': session_id,
                                    'timestamp': datetime.now().isoformat(),
                                    'pair_results': pair_results,
                                    'total_pairs': total_pairs,
                                    'completed': completed_count
                                }
                                if save_checkpoint(session_id, checkpoint_data):
                                    yield f"data: {json.dumps({'type': 'checkpoint', 'completed': completed_count})}\n\n"
                        else:
                            yield f"data: {json.dumps({'type': 'error', 'pair_index': pair_idx, 'message': result.get('error', 'Unknown error')})}\n\n"
                    except Exception as e:
                        yield f"data: {json.dumps({'type': 'error', 'pair_index': pair_idx, 'message': str(e)})}\n\n"
                
                # Save checkpoint after each batch completes (in addition to periodic saves)
                # This ensures we have a checkpoint even if we don't hit the interval
                if len(batch_results_collected) > 0:
                    checkpoint_data = {
                        'session_id': session_id,
                        'timestamp': datetime.now().isoformat(),
                        'pair_results': pair_results,
                        'total_pairs': total_pairs,
                        'completed': completed_count
                    }
                    # Only save if we haven't just saved (to avoid duplicate saves)
                    if completed_count % checkpoint_interval != 0:
                        save_checkpoint(session_id, checkpoint_data)
            
            # Calculate final statistics
            yield f"data: {json.dumps({'type': 'progress', 'stage': 'calculating_stats', 'message': 'Calculating final statistics...'})}\n\n"
            
            statistics = {}
            for focus_name, influences in all_focus_influences.items():
                if len(influences) > 0:
                    statistics[focus_name] = {
                        'mean': float(np.mean(influences)),
                        'variance': float(np.var(influences)),
                        'std_dev': float(np.std(influences)),
                        'min': float(np.min(influences)),
                        'max': float(np.max(influences))
                    }
            
            if len(all_chat_influences) > 0:
                statistics['chat_content'] = {
                    'mean': float(np.mean(all_chat_influences)),
                    'variance': float(np.var(all_chat_influences)),
                    'std_dev': float(np.std(all_chat_influences)),
                    'min': float(np.min(all_chat_influences)),
                    'max': float(np.max(all_chat_influences))
                }
            
            # Add noise statistics (calculated once for the entire batch)
            statistics['noise'] = {
                'mean': baseline_mean_similarity,  # Mean similarity between baseline outputs
                'variance': baseline_variance,  # Variance of similarities between baseline outputs
                'std_dev': baseline_std,  # Standard deviation of similarities
                'noise_threshold': float(batch_noise_threshold) if batch_noise_threshold is not None else None,
                'num_samples': num_samples  # Number of baseline samples used
            }
            
            # Calculate costs
            chat_input_cost = total_input_tokens * model_pricing['input']
            chat_output_cost = total_output_tokens * model_pricing['output']
            embedding_cost = total_embedding_tokens * PRICING['embedding']
            total_cost = chat_input_cost + chat_output_cost + embedding_cost
            
            cost_breakdown = {
                'chat_completions': {
                    'input_tokens': total_input_tokens,
                    'output_tokens': total_output_tokens,
                    'cost': chat_input_cost + chat_output_cost
                },
                'embeddings': {
                    'tokens': total_embedding_tokens,
                    'cost': embedding_cost
                },
                'total_cost': total_cost,
                'model': model
            }
            
            # Final result
            final_result = {
                'type': 'complete',
                'results': pair_results,
                'statistics': statistics,
                'cost_breakdown': cost_breakdown
            }
            
            yield f"data: {json.dumps(final_result)}\n\n"
            
            # Save final checkpoint
            checkpoint_data = {
                'session_id': session_id,
                'timestamp': datetime.now().isoformat(),
                'pair_results': pair_results,
                'statistics': statistics,
                'cost_breakdown': cost_breakdown,
                'total_pairs': total_pairs,
                'completed': completed_count,
                'complete': True
            }
            # Save final checkpoint before returning
            if save_checkpoint(session_id, checkpoint_data):
                yield f"data: {json.dumps({'type': 'checkpoint', 'completed': completed_count, 'final': True})}\n\n"
            
        except Exception as e:
            # Try to save checkpoint even on error (if we have any results)
            # Variables are initialized at the start of the function, so they should be accessible
            try:
                if len(pair_results) > 0:
                    emergency_checkpoint = {
                        'session_id': session_id,
                        'timestamp': datetime.now().isoformat(),
                        'pair_results': pair_results,
                        'total_pairs': total_pairs,
                        'completed': completed_count,
                        'error_occurred': True,
                        'error_message': str(e)
                    }
                    if save_checkpoint(session_id, emergency_checkpoint):
                        print(f"Emergency checkpoint saved after error: {len(pair_results)} pairs")
            except Exception as save_error:
                print(f"Failed to save emergency checkpoint: {save_error}")
            
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no'  # Disable buffering in nginx
    })


@app.route('/api/parse-batch-csv', methods=['POST'])
def parse_batch_csv():
    """Parse CSV file for batch analysis."""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        import csv
        import io
        
        # Read file content
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_reader = csv.DictReader(stream)
        
        # Find column mappings (case-insensitive)
        fieldnames = csv_reader.fieldnames
        if not fieldnames:
            return jsonify({'error': 'CSV file is empty or invalid'}), 400
        
        # Normalize fieldnames to lowercase for matching
        fieldnames_lower = {f.lower(): f for f in fieldnames}
        
        # Map expected columns (support multiple dynamic inputs)
        chat_col = None
        rag_col = None
        tools_col = None
        output_col = None
        
        # Find chat content column
        for expected in ['chat_content', 'input', 'chat']:
            if expected.lower() in fieldnames_lower:
                chat_col = fieldnames_lower[expected.lower()]
                break
        
        # Find RAG context column
        for expected in ['rag_context', 'rag', 'context', 'retrieved_context']:
            if expected.lower() in fieldnames_lower:
                rag_col = fieldnames_lower[expected.lower()]
                break
        
        # Find tool results column
        for expected in ['tool_results', 'tools', 'tool_outputs', 'function_results']:
            if expected.lower() in fieldnames_lower:
                tools_col = fieldnames_lower[expected.lower()]
                break
        
        # Find output column
        for expected in ['output', 'suggested_message', 'response']:
            if expected.lower() in fieldnames_lower:
                output_col = fieldnames_lower[expected.lower()]
                break
        
        errors = []
        if not chat_col and not rag_col and not tools_col:
            errors.append('Missing at least one input column (chat_content/input/chat, rag_context/rag, or tool_results/tools)')
        if not output_col:
            errors.append('Missing output/suggested_message/response column')
        
        if errors:
            return jsonify({'error': '; '.join(errors)}), 400
        
        # Parse rows
        pairs = []
        row_num = 1
        for row in csv_reader:
            row_num += 1
            inputs = {}
            
            if chat_col:
                inputs['chat_content'] = row.get(chat_col, '').strip()
            if rag_col:
                inputs['rag_context'] = row.get(rag_col, '').strip()
            if tools_col:
                inputs['tool_results'] = row.get(tools_col, '').strip()
            
            output = row.get(output_col, '').strip()
            
            # At least one input and output required
            has_input = any(inputs.values())
            if not has_input or not output:
                errors.append(f'Row {row_num}: Missing required fields')
                continue
            
            pairs.append({
                'inputs': inputs,
                'output': output
            })
        
        return jsonify({
            'pairs': pairs,
            'errors': errors if errors else []
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/batch-ablation-analysis', methods=['POST'])
def batch_ablation_analysis():
    """Run ablation analysis on multiple input-output pairs."""
    try:
        data = request.json
        pairs = data.get('pairs', [])
        foci_list = data.get('foci', [])
        model = data.get('model', 'gpt-4o-mini')
        num_samples = data.get('num_samples', 20)
        
        if not pairs or len(pairs) == 0:
            return jsonify({'error': 'At least one pair is required'}), 400
        
        if not foci_list or len(foci_list) == 0:
            return jsonify({'error': 'Foci are required'}), 400
        
        # Check API key first
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return jsonify({'error': 'OPENAI_API_KEY environment variable not set. Please set it and restart the server.'}), 500
        
        assessor = get_assessor()
        client = assessor.client
        
        # Pricing per million tokens
        PRICING = {
            'gpt-4o-mini': {'input': 0.15 / 1_000_000, 'output': 0.60 / 1_000_000},
            'gpt-4o': {'input': 2.50 / 1_000_000, 'output': 10.00 / 1_000_000},
            'gpt-4-turbo': {'input': 10.00 / 1_000_000, 'output': 30.00 / 1_000_000},
            'gpt-3.5-turbo': {'input': 0.50 / 1_000_000, 'output': 1.50 / 1_000_000},
            'embedding': 0.02 / 1_000_000
        }
        
        model_pricing = PRICING.get(model, PRICING['gpt-4o-mini'])
        
        # Track costs
        total_input_tokens = 0
        total_output_tokens = 0
        total_embedding_tokens = 0
        
        # Helper function for embeddings
        def get_embedding(text):
            """Get embedding for text using OpenAI."""
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            nonlocal total_embedding_tokens
            if hasattr(response, 'usage'):
                total_embedding_tokens += response.usage.total_tokens
            return np.array(response.data[0].embedding)
        
        # Store results for each pair
        pair_results = []
        all_focus_influences = {}  # {focus_name: [influence1, influence2, ...]}
        all_chat_influences = []  # [influence1, influence2, ...]
        all_noise_values = []  # [noise1, noise2, ...]
        
        # Step 1: Calculate baseline noise ONCE for the entire batch
        # Use system prompt only (without chat content) for noise calculation
        if len(pairs) > 0:
            first_pair = pairs[0]
            system_prompt = first_pair.get('prompt', '')
            inputs = get_pair_inputs(first_pair)
            chat_content = inputs['chat_content']
            
            # Explicitly ensure we use system prompt only (remove chat_content if present)
            if chat_content and chat_content in system_prompt:
                system_prompt = system_prompt.replace(chat_content, '').strip()
                system_prompt = '\n'.join([line for line in system_prompt.split('\n') if line.strip()])
            
            representative_prompt = system_prompt
            
            print(f"Calculating baseline noise from {num_samples} samples using system prompt only (applied to all {len(pairs)} pairs)...")
            baseline_outputs = []
            for _ in range(num_samples):
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": representative_prompt}],
                    temperature=0.7
                )
                baseline_outputs.append(response.choices[0].message.content)
                
                if hasattr(response, 'usage'):
                    total_input_tokens += response.usage.prompt_tokens
                    total_output_tokens += response.usage.completion_tokens
            
            # Calculate baseline noise from these samples
            baseline_embeddings = [get_embedding(output) for output in baseline_outputs]
            similarities_between_baselines = []
            for i in range(len(baseline_embeddings)):
                for j in range(i+1, len(baseline_embeddings)):
                    sim = np.dot(baseline_embeddings[i], baseline_embeddings[j]) / (
                        np.linalg.norm(baseline_embeddings[i]) * np.linalg.norm(baseline_embeddings[j])
                    )
                    similarities_between_baselines.append(sim)
            
            baseline_variance = float(np.var(similarities_between_baselines)) if similarities_between_baselines else 0.0
            baseline_std = float(np.std(similarities_between_baselines)) if similarities_between_baselines else 0.0
            baseline_mean_similarity = float(np.mean(similarities_between_baselines)) if similarities_between_baselines else 1.0
            batch_noise_threshold = baseline_mean_similarity - (2 * baseline_std) if baseline_std else None
            
            print(f"Batch noise threshold calculated: {batch_noise_threshold:.4f} (mean: {baseline_mean_similarity:.4f}, std: {baseline_std:.4f})")
        else:
            batch_noise_threshold = None
            baseline_variance = 0.0
            baseline_std = 0.0
            baseline_mean_similarity = 1.0
        
        # Process each pair
        for pair_idx, pair in enumerate(pairs):
            prompt = pair.get('prompt', '')
            inputs = get_pair_inputs(pair)
            chat_content = inputs['chat_content']
            provided_output = pair.get('output', '')
            
            # Step 2: Generate ONE baseline output for this pair (not 20)
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            baseline_output = response.choices[0].message.content
            
            if hasattr(response, 'usage'):
                total_input_tokens += response.usage.prompt_tokens
                total_output_tokens += response.usage.completion_tokens
            
            # Use the batch-wide noise threshold for all pairs
            noise_threshold = batch_noise_threshold
            all_noise_values.append(baseline_variance)  # Store the same variance for all pairs
            
            # Step 3: Generate ablated outputs for each focus
            baseline_embedding = get_embedding(baseline_output)
            focus_influences = {}
            
            for focus in foci_list:
                focus_section = focus.get('prompt_section', '')
                focus_name = focus.get('focus', '')
                
                # Create ablated prompt
                if focus_section:
                    ablated_prompt = prompt.replace(focus_section, '').strip()
                    ablated_prompt = '\n'.join([line for line in ablated_prompt.split('\n') if line.strip()])
                else:
                    ablated_prompt = prompt
                
                # Generate ablated output
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": ablated_prompt}],
                    temperature=0.7
                )
                ablated_output = response.choices[0].message.content
                
                if hasattr(response, 'usage'):
                    total_input_tokens += response.usage.prompt_tokens
                    total_output_tokens += response.usage.completion_tokens
                
                # Calculate similarity and influence
                ablated_embedding = get_embedding(ablated_output)
                similarity = np.dot(baseline_embedding, ablated_embedding) / (
                    np.linalg.norm(baseline_embedding) * np.linalg.norm(ablated_embedding)
                )
                influence = 1 - similarity
                
                # Determine significance
                # Convert NumPy boolean to Python bool for JSON serialization
                is_significant = bool(similarity < noise_threshold) if noise_threshold else None
                
                focus_influences[focus_name] = {
                    'influence': float(influence),
                    'similarity': float(similarity),
                    'is_significant': is_significant
                }
                
                # Track for statistics
                if focus_name not in all_focus_influences:
                    all_focus_influences[focus_name] = []
                all_focus_influences[focus_name].append(float(influence))
            
            # Step 4: Calculate chat_content influence (special focus)
            # Remove chat_content from prompt if it exists
            ablated_prompt_no_chat = prompt.replace(chat_content, '').strip()
            ablated_prompt_no_chat = '\n'.join([line for line in ablated_prompt_no_chat.split('\n') if line.strip()])
            
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": ablated_prompt_no_chat}],
                temperature=0.7
            )
            ablated_output_no_chat = response.choices[0].message.content
            
            if hasattr(response, 'usage'):
                total_input_tokens += response.usage.prompt_tokens
                total_output_tokens += response.usage.completion_tokens
            
            ablated_embedding_no_chat = get_embedding(ablated_output_no_chat)
            similarity_chat = np.dot(baseline_embedding, ablated_embedding_no_chat) / (
                np.linalg.norm(baseline_embedding) * np.linalg.norm(ablated_embedding_no_chat)
            )
            influence_chat = 1 - similarity_chat
            # Convert NumPy boolean to Python bool for JSON serialization
            is_significant_chat = bool(similarity_chat < noise_threshold) if noise_threshold else None
            
            all_chat_influences.append(float(influence_chat))
            
            # Store pair results
            pair_results.append({
                'pair_index': pair_idx,
                'pair_data': pair,
                'influence_scores': focus_influences,
                'chat_content_influence': {
                    'influence': float(influence_chat),
                    'similarity': float(similarity_chat),
                    'is_significant': is_significant_chat
                },
                'noise_metrics': {
                    'variance': baseline_variance,
                    'std_dev': baseline_std,
                    'mean_similarity': baseline_mean_similarity,
                    'threshold': float(noise_threshold) if noise_threshold else None,
                    'is_batch_wide': True  # Indicate this is a batch-wide calculation
                }
            })
        
        # Step 5: Calculate statistics across all pairs
        statistics = {}
        
        # Statistics for each focus
        for focus_name, influences in all_focus_influences.items():
            if len(influences) > 0:
                mean = float(np.mean(influences))
                variance = float(np.var(influences))
                std_dev = float(np.std(influences))
                min_val = float(np.min(influences))
                max_val = float(np.max(influences))
                
                statistics[focus_name] = {
                    'mean': mean,
                    'variance': variance,
                    'std_dev': std_dev,
                    'min': min_val,
                    'max': max_val
                }
        
        # Statistics for chat_content
        if len(all_chat_influences) > 0:
            statistics['chat_content'] = {
                'mean': float(np.mean(all_chat_influences)),
                'variance': float(np.var(all_chat_influences)),
                'std_dev': float(np.std(all_chat_influences)),
                'min': float(np.min(all_chat_influences)),
                'max': float(np.max(all_chat_influences))
            }
        
        # Statistics for noise (calculated once for the entire batch)
        statistics['noise'] = {
            'mean': baseline_mean_similarity,  # Mean similarity between baseline outputs
            'variance': baseline_variance,  # Variance of similarities between baseline outputs
            'std_dev': baseline_std,  # Standard deviation of similarities
            'noise_threshold': float(batch_noise_threshold) if batch_noise_threshold is not None else None,
            'num_samples': num_samples  # Number of baseline samples used
        }
        
        # Calculate costs
        chat_input_cost = total_input_tokens * model_pricing['input']
        chat_output_cost = total_output_tokens * model_pricing['output']
        embedding_cost = total_embedding_tokens * PRICING['embedding']
        total_cost = chat_input_cost + chat_output_cost + embedding_cost
        
        cost_breakdown = {
            'chat_completions': {
                'input_tokens': total_input_tokens,
                'output_tokens': total_output_tokens,
                'cost': chat_input_cost + chat_output_cost
            },
            'embeddings': {
                'tokens': total_embedding_tokens,
                'cost': embedding_cost
            },
            'total_cost': total_cost,
            'model': model
        }
        
        return jsonify({
            'results': pair_results,
            'statistics': statistics,
            'cost_breakdown': cost_breakdown
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/build-batch-agents', methods=['POST'])
def build_batch_agents():
    """Build optimized agents for each input using LLM assessment (same as single agent builder)."""
    try:
        data = request.json
        pairs = data.get('pairs', [])  # Changed: expect pairs, not batch_results
        foci_list = data.get('foci', [])
        model = data.get('model', 'gpt-4o-mini')
        
        if not pairs or len(pairs) == 0:
            return jsonify({'error': 'Pairs are required'}), 400
        
        if not foci_list or len(foci_list) == 0:
            return jsonify({'error': 'Foci are required'}), 400
        
        # Check API key first
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return jsonify({'error': 'OPENAI_API_KEY environment variable not set. Please set it and restart the server.'}), 500
        
        assessor = get_assessor()
        client = assessor.client
        
        # Pricing per million tokens
        PRICING = {
            'gpt-4o-mini': {'input': 0.15 / 1_000_000, 'output': 0.60 / 1_000_000},
            'gpt-4o': {'input': 2.50 / 1_000_000, 'output': 10.00 / 1_000_000},
            'gpt-4-turbo': {'input': 10.00 / 1_000_000, 'output': 30.00 / 1_000_000},
            'gpt-3.5-turbo': {'input': 0.50 / 1_000_000, 'output': 1.50 / 1_000_000}
        }
        
        model_pricing = PRICING.get(model, PRICING['gpt-4o-mini'])
        
        # Track costs
        total_input_tokens = 0
        total_output_tokens = 0
        
        results = []
        
        for pair in pairs:
            # Extract input and original output
            inputs = get_pair_inputs(pair)
            input_text = inputs['chat_content']  # Use chat_content as primary input for agent building
            original_output = pair.get('output', '')
            
            if not input_text:
                continue
            
            # Step 1: Assess chat and get foci weights (same as single agent builder)
            # Build foci list for prompt
            foci_text = '\n'.join([
                f"{i+1}. {f.get('focus', 'Unknown')}: {f.get('prompt_section', '')[:200]}..."
                for i, f in enumerate(foci_list)
            ])
            
            # Use LLM to assess relevance (same as /api/assess-chat-foci)
            assess_response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at analyzing chat conversations and determining which parts of a prompt (foci) are relevant for responding. You assign weights from 0.0 to 1.0 based on relevance."
                    },
                    {
                        "role": "user",
                        "content": f"""Analyze the following chat content and determine how relevant each focus is for responding to it.

CHAT CONTENT:
{input_text}

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
            
            if hasattr(assess_response, 'usage'):
                total_input_tokens += assess_response.usage.prompt_tokens
                total_output_tokens += assess_response.usage.completion_tokens
            
            assess_result = json.loads(assess_response.choices[0].message.content)
            
            # Build foci_weights list (same as /api/assess-chat-foci)
            foci_weights = []
            for focus in foci_list:
                focus_name = focus.get('focus', '')
                matched = None
                for item in assess_result.get('foci_weights', []):
                    if item.get('focus', '').lower() == focus_name.lower():
                        matched = item
                        break
                
                if matched:
                    foci_weights.append({
                        'focus': focus_name,
                        'weight': float(matched.get('weight', 0.0)),
                        'explanation': matched.get('explanation', ''),
                        'prompt_section': focus.get('prompt_section', '')
                    })
                else:
                    foci_weights.append({
                        'focus': focus_name,
                        'weight': 0.0,
                        'explanation': 'Not assessed',
                        'prompt_section': focus.get('prompt_section', '')
                    })
            
            chat_weight = float(assess_result.get('chat_weight', 0.5))
            
            # Step 2: Build prompt (same as /api/build-agent-prompt)
            relevant_foci = [f for f in foci_weights if f.get('weight', 0) > 0.1]
            relevant_foci.sort(key=lambda x: x.get('weight', 0), reverse=True)
            
            prompt_parts = []
            
            # Get all inputs for this pair
            inputs = get_pair_inputs(pair)
            
            # Build prompt with placeholders for dynamic foci, then replace with actual values
            constructed_prompt = build_prompt_with_dynamic_foci(relevant_foci, foci_list, inputs, chat_weight)
            
            # Step 3: Generate response (same as /api/generate-agent-response)
            gen_response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": constructed_prompt}],
                temperature=0.7
            )
            
            new_output = gen_response.choices[0].message.content
            
            if hasattr(gen_response, 'usage'):
                total_input_tokens += gen_response.usage.prompt_tokens
                total_output_tokens += gen_response.usage.completion_tokens
            
            # Get selected foci names
            selected_foci = [f['focus'] for f in relevant_foci]
            
            results.append({
                'input': input_text,
                'original_output': original_output,
                'new_output': new_output,
                'selected_foci': selected_foci,
                'constructed_prompt': constructed_prompt,
                'foci_weights': {f['focus']: f['weight'] for f in foci_weights}
            })
        
        # Calculate costs
        chat_input_cost = total_input_tokens * model_pricing['input']
        chat_output_cost = total_output_tokens * model_pricing['output']
        total_cost = chat_input_cost + chat_output_cost
        
        cost_breakdown = {
            'chat_completions': {
                'input_tokens': total_input_tokens,
                'output_tokens': total_output_tokens,
                'cost': total_cost
            },
            'total_cost': total_cost,
            'model': model
        }
        
        return jsonify({
            'results': results,
            'cost_breakdown': cost_breakdown
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def process_single_agent_pair(pair, pair_idx, foci_list, model, client):
    """Process a single pair for agent building - designed to run in parallel."""
    try:
        # Extract input and original output
        inputs = get_pair_inputs(pair)
        input_text = inputs['chat_content']  # Use chat_content as primary input for agent building
        original_output = pair.get('output', '')
        
        if not input_text:
            return {
                'success': False,
                'pair_index': pair_idx,
                'error': 'No input text provided'
            }
        
        # Step 1: Assess chat and get foci weights
        foci_text = '\n'.join([
            f"{i+1}. {f.get('focus', 'Unknown')}: {f.get('prompt_section', '')[:200]}..."
            for i, f in enumerate(foci_list)
        ])
        
        assess_response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at analyzing chat conversations and determining which parts of a prompt (foci) are relevant for responding. You assign weights from 0.0 to 1.0 based on relevance."
                },
                {
                    "role": "user",
                    "content": f"""Analyze the following chat content and determine how relevant each focus is for responding to it.

CHAT CONTENT:
{input_text}

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
        
        assess_result = json.loads(assess_response.choices[0].message.content)
        
        # Track tokens
        input_tokens = assess_response.usage.prompt_tokens if hasattr(assess_response, 'usage') else 0
        output_tokens = assess_response.usage.completion_tokens if hasattr(assess_response, 'usage') else 0
        
        # Build foci_weights list
        foci_weights = []
        for focus in foci_list:
            focus_name = focus.get('focus', '')
            matched = None
            for item in assess_result.get('foci_weights', []):
                if item.get('focus', '').lower() == focus_name.lower():
                    matched = item
                    break
            
            if matched:
                foci_weights.append({
                    'focus': focus_name,
                    'weight': float(matched.get('weight', 0.0)),
                    'explanation': matched.get('explanation', ''),
                    'prompt_section': focus.get('prompt_section', '')
                })
            else:
                foci_weights.append({
                    'focus': focus_name,
                    'weight': 0.0,
                    'explanation': 'Not assessed',
                    'prompt_section': focus.get('prompt_section', '')
                })
        
        chat_weight = float(assess_result.get('chat_weight', 0.5))
        
        # Step 2: Build prompt with dynamic foci support
        relevant_foci = [f for f in foci_weights if f.get('weight', 0) > 0.1]
        relevant_foci.sort(key=lambda x: x.get('weight', 0), reverse=True)
        
        # Get all inputs for this pair
        inputs = get_pair_inputs(pair)
        
        # Build prompt with placeholders for dynamic foci, then replace with actual values
        constructed_prompt = build_prompt_with_dynamic_foci(relevant_foci, foci_list, inputs, chat_weight)
        
        # Step 3: Generate response
        gen_response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": constructed_prompt}],
            temperature=0.7
        )
        
        new_output = gen_response.choices[0].message.content
        
        # Update token counts
        if hasattr(gen_response, 'usage'):
            input_tokens += gen_response.usage.prompt_tokens
            output_tokens += gen_response.usage.completion_tokens
        
        # Get selected foci names
        selected_foci = [f['focus'] for f in relevant_foci]
        
        return {
            'success': True,
            'pair_index': pair_idx,
            'result': {
                'input': input_text,
                'original_output': original_output,
                'new_output': new_output,
                'selected_foci': selected_foci,
                'constructed_prompt': constructed_prompt,
                'foci_weights': {f['focus']: f['weight'] for f in foci_weights}
            },
            'tokens': {
                'input': input_tokens,
                'output': output_tokens
            }
        }
    except Exception as e:
        return {
            'success': False,
            'pair_index': pair_idx,
            'error': str(e)
        }


@app.route('/api/build-batch-agents-stream', methods=['POST'])
@stream_with_context
def build_batch_agents_stream():
    """Build optimized agents for each input using LLM assessment with streaming progress."""
    def generate():
        try:
            data = request.json
            pairs = data.get('pairs', [])
            foci_list = data.get('foci', [])
            model = data.get('model', 'gpt-4o-mini')
            
            if not pairs or len(pairs) == 0:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Pairs are required'})}\n\n"
                return
            
            if not foci_list or len(foci_list) == 0:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Foci are required'})}\n\n"
                return
            
            # Check API key
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                yield f"data: {json.dumps({'type': 'error', 'message': 'OPENAI_API_KEY not set'})}\n\n"
                return
            
            assessor = get_assessor()
            client = assessor.client
            
            # Pricing per million tokens
            PRICING = {
                'gpt-4o-mini': {'input': 0.15 / 1_000_000, 'output': 0.60 / 1_000_000},
                'gpt-4o': {'input': 2.50 / 1_000_000, 'output': 10.00 / 1_000_000},
                'gpt-4-turbo': {'input': 10.00 / 1_000_000, 'output': 30.00 / 1_000_000},
                'gpt-3.5-turbo': {'input': 0.50 / 1_000_000, 'output': 1.50 / 1_000_000}
            }
            model_pricing = PRICING.get(model, PRICING['gpt-4o-mini'])
            
            # Track costs
            total_input_tokens = 0
            total_output_tokens = 0
            
            results = []
            total_pairs = len(pairs)
            completed_count = 0
            
            # Generate session ID for checkpointing
            session_id = str(uuid.uuid4())
            checkpoint_interval = 10  # Save checkpoint every 10 pairs
            
            yield f"data: {json.dumps({'type': 'progress', 'stage': 'processing', 'message': f'Building agents for {total_pairs} pair(s) in parallel...', 'completed': 0, 'total': total_pairs})}\n\n"
            
            # Process pairs in batches for better control
            batch_size = 10  # Process 10 pairs at a time
            pair_list = [(idx, pair) for idx, pair in enumerate(pairs)]
            
            with ThreadPoolExecutor(max_workers=10) as executor:
                for batch_start in range(0, len(pair_list), batch_size):
                    batch_end = min(batch_start + batch_size, len(pair_list))
                    batch = pair_list[batch_start:batch_end]
                    
                    # Submit batch to thread pool
                    futures = {}
                    for pair_idx, pair in batch:
                        future = executor.submit(
                            process_single_agent_pair,
                            pair, pair_idx, foci_list, model, client
                        )
                        futures[future] = pair_idx
                    
                    # Collect results as they complete
                    for future in as_completed(futures):
                        pair_idx = futures[future]
                        try:
                            process_result = future.result()
                            if process_result['success']:
                                result = process_result['result']
                                results.append(result)
                                completed_count += 1
                                
                                # Update token counts
                                if 'tokens' in process_result:
                                    total_input_tokens += process_result['tokens']['input']
                                    total_output_tokens += process_result['tokens']['output']
                                
                                # Send pair_complete event
                                yield f"data: {json.dumps({'type': 'pair_complete', 'pair_index': pair_idx, 'result': result, 'completed': completed_count, 'total': total_pairs})}\n\n"
                                
                                # Save checkpoint periodically
                                if completed_count % checkpoint_interval == 0:
                                    checkpoint_data = {
                                        'session_id': session_id,
                                        'timestamp': datetime.now().isoformat(),
                                        'results': results,
                                        'total_pairs': total_pairs,
                                        'completed': completed_count,
                                        'foci_list': foci_list,
                                        'model': model
                                    }
                                    if save_checkpoint(session_id, checkpoint_data, 'batch_agents'):
                                        yield f"data: {json.dumps({'type': 'checkpoint', 'completed': completed_count})}\n\n"
                            else:
                                yield f"data: {json.dumps({'type': 'error', 'pair_index': pair_idx, 'message': process_result.get('error', 'Unknown error')})}\n\n"
                        except Exception as e:
                            print(f"Error processing pair {pair_idx}: {e}")
                            yield f"data: {json.dumps({'type': 'error', 'pair_index': pair_idx, 'message': str(e)})}\n\n"
            
            # Calculate costs
            chat_input_cost = total_input_tokens * model_pricing['input']
            chat_output_cost = total_output_tokens * model_pricing['output']
            total_cost = chat_input_cost + chat_output_cost
            
            cost_breakdown = {
                'chat_completions': {
                    'input_tokens': total_input_tokens,
                    'output_tokens': total_output_tokens,
                    'cost': total_cost
                },
                'total_cost': total_cost,
                'model': model
            }
            
            # Save final checkpoint
            checkpoint_data = {
                'session_id': session_id,
                'timestamp': datetime.now().isoformat(),
                'results': results,
                'total_pairs': total_pairs,
                'completed': completed_count,
                'foci_list': foci_list,
                'model': model,
                'cost_breakdown': cost_breakdown,
                'complete': True
            }
            if save_checkpoint(session_id, checkpoint_data, 'batch_agents'):
                yield f"data: {json.dumps({'type': 'checkpoint', 'completed': completed_count, 'final': True})}\n\n"
            
            # Send complete event
            yield f"data: {json.dumps({'type': 'complete', 'results': results, 'cost_breakdown': cost_breakdown})}\n\n"
            
        except Exception as e:
            # Try to save emergency checkpoint
            try:
                if 'results' in locals() and len(results) > 0:
                    emergency_checkpoint = {
                        'session_id': session_id if 'session_id' in locals() else str(uuid.uuid4()),
                        'timestamp': datetime.now().isoformat(),
                        'results': results,
                        'total_pairs': total_pairs if 'total_pairs' in locals() else len(results),
                        'completed': completed_count if 'completed_count' in locals() else len(results),
                        'foci_list': foci_list if 'foci_list' in locals() else [],
                        'model': model if 'model' in locals() else 'gpt-4o-mini',
                        'complete': False,
                        'error': str(e)
                    }
                    if save_checkpoint(emergency_checkpoint['session_id'], emergency_checkpoint, 'batch_agents'):
                        print(f"Emergency checkpoint saved after error: {len(results)} results")
            except Exception as save_error:
                print(f"Failed to save emergency checkpoint: {save_error}")
            
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')


def process_single_evaluation(result, result_idx, model, client):
    """Process a single evaluation - designed to run in parallel."""
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
        response = client.chat.completions.create(
            model=model,
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
        input_tokens = response.usage.prompt_tokens if hasattr(response, 'usage') else 0
        output_tokens = response.usage.completion_tokens if hasattr(response, 'usage') else 0
        
        eval_result = json.loads(response.choices[0].message.content)
        
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


@app.route('/api/llm-evaluate-batch-agents-stream', methods=['POST'])
@stream_with_context
def llm_evaluate_batch_agents_stream():
    """Run LLM evaluation with streaming progress."""
    def generate():
        try:
            data = request.json
            results = data.get('results', [])
            model = data.get('model', 'gpt-4o-mini')
            
            if not results or len(results) == 0:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Results are required'})}\n\n"
                return
            
            # Check API key first
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                yield f"data: {json.dumps({'type': 'error', 'message': 'OPENAI_API_KEY environment variable not set. Please set it and restart the server.'})}\n\n"
                return
            
            assessor = get_assessor()
            client = assessor.client
            
            # Pricing per million tokens
            PRICING = {
                'gpt-4o-mini': {'input': 0.15 / 1_000_000, 'output': 0.60 / 1_000_000},
                'gpt-4o': {'input': 2.50 / 1_000_000, 'output': 10.00 / 1_000_000},
                'gpt-4-turbo': {'input': 10.00 / 1_000_000, 'output': 30.00 / 1_000_000},
                'gpt-3.5-turbo': {'input': 0.50 / 1_000_000, 'output': 1.50 / 1_000_000}
            }
            
            model_pricing = PRICING.get(model, PRICING['gpt-4o-mini'])
            
            # Track costs
            total_input_tokens = 0
            total_output_tokens = 0
            
            evaluations = []
            total_results = len(results)
            completed_count = 0
            
            yield f"data: {json.dumps({'type': 'progress', 'stage': 'processing', 'message': f'Evaluating {total_results} result(s) in parallel...', 'completed': 0, 'total': total_results})}\n\n"
            
            # Process results in batches for better control
            batch_size = 10  # Process 10 evaluations at a time
            result_list = [(idx, result) for idx, result in enumerate(results)]
            
            with ThreadPoolExecutor(max_workers=10) as executor:
                for batch_start in range(0, len(result_list), batch_size):
                    batch_end = min(batch_start + batch_size, len(result_list))
                    batch = result_list[batch_start:batch_end]
                    
                    # Submit batch to thread pool
                    futures = {}
                    for result_idx, result in batch:
                        future = executor.submit(
                            process_single_evaluation,
                            result, result_idx, model, client
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
                            print(f"Error processing evaluation {result_idx}: {e}")
                            yield f"data: {json.dumps({'type': 'error', 'result_index': result_idx, 'message': str(e)})}\n\n"
            
            # Calculate costs
            chat_input_cost = total_input_tokens * model_pricing['input']
            chat_output_cost = total_output_tokens * model_pricing['output']
            total_cost = chat_input_cost + chat_output_cost
            
            cost_breakdown = {
                'chat_completions': {
                    'input_tokens': total_input_tokens,
                    'output_tokens': total_output_tokens,
                    'cost': total_cost
                },
                'total_cost': total_cost,
                'model': model
            }
            
            # Send complete event
            yield f"data: {json.dumps({'type': 'complete', 'evaluations': evaluations, 'cost_breakdown': cost_breakdown})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')


def build_comprehensive_analysis_summary(single_assessment, single_ablation, batch_analysis, agent_results, foci_list, original_prompt):
    """Build a comprehensive summary of all analysis data."""
    summary_parts = []
    
    # 1. Single Chat Focus Assessment
    if single_assessment and isinstance(single_assessment, list) and len(single_assessment) > 0:
        summary_parts.append("## 1. SINGLE CHAT FOCUS ASSESSMENT")
        summary_parts.append("How attention was distributed across foci for a single example:")
        for focus in single_assessment:
            summary_parts.append(
                f"- {focus.get('focus', 'Unknown')}: {focus.get('score', 0):.1f} points - "
                f"{focus.get('explanation', 'No explanation')[:200]}"
            )
        summary_parts.append("")
    
    # 2. Single Pair Ablation Analysis
    if single_ablation:
        summary_parts.append("## 2. SINGLE PAIR ABLATION ANALYSIS")
        if single_ablation.get('influence_scores'):
            summary_parts.append("Influence scores (how much removing each focus affects output):")
            for item in single_ablation['influence_scores']:
                focus_name = item.get('focus', 'Unknown')
                influence = item.get('influence', 0)
                normalized = item.get('normalized_influence', 0)
                summary_parts.append(
                    f"- {focus_name}: Influence={influence:.3f}, Normalized={normalized:.1f}%"
                )
        if single_ablation.get('baseline_variance'):
            summary_parts.append(
                f"Baseline noise: Variance={single_ablation.get('baseline_variance', 0):.4f}, "
                f"StdDev={single_ablation.get('baseline_std', 0):.4f}"
            )
        summary_parts.append("")
    
    # 3. Batch Ablation Analysis
    if batch_analysis and batch_analysis.get('statistics'):
        summary_parts.append("## 3. BATCH ABLATION ANALYSIS (Statistical Summary)")
        stats = batch_analysis['statistics']
        summary_parts.append("Average influence scores across multiple pairs:")
        for focus_name, focus_stats in sorted(stats.items(), key=lambda x: x[1].get('mean', 0), reverse=True):
            if focus_name == 'noise':
                continue  # Skip noise stats here, handle separately
            mean = focus_stats.get('mean', 0)
            std_dev = focus_stats.get('std_dev', 0)
            min_val = focus_stats.get('min', 0)
            max_val = focus_stats.get('max', 0)
            summary_parts.append(
                f"- {focus_name}: Mean={mean:.3f}, StdDev={std_dev:.3f}, "
                f"Range=[{min_val:.3f}, {max_val:.3f}]"
            )
            # High variance indicates inconsistent impact
            if std_dev > 0.1:
                summary_parts.append(f"  ⚠️ High variance - inconsistent impact across pairs")
        
        # Noise statistics
        if batch_analysis.get('statistics', {}).get('noise'):
            noise = batch_analysis['statistics']['noise']
            summary_parts.append(
                f"\nBaseline noise (prompt-only variability): "
                f"Mean={noise.get('mean', 0):.4f}, StdDev={noise.get('std_dev', 0):.4f}, "
                f"Threshold={noise.get('noise_threshold', 0):.4f}"
            )
        summary_parts.append("")
    
    # 4. Batch Agent Building Results
    if agent_results and len(agent_results) > 0:
        summary_parts.append("## 4. BATCH AGENT BUILDING RESULTS")
        
        # Focus usage frequency and weight statistics
        focus_stats = {}  # Track comprehensive stats per focus
        focus_performance = {}  # Track which foci correlate with better outputs
        
        for result in agent_results:
            selected_foci = result.get('selected_foci', [])
            foci_weights = result.get('foci_weights', {})
            evaluation = result.get('evaluation', {})
            
            # Initialize stats for all foci that appear in this result
            for focus_name, weight in foci_weights.items():
                if focus_name not in focus_stats:
                    focus_stats[focus_name] = {
                        'raw_count': 0,           # Times selected
                        'sum_of_weights': 0.0,    # Sum of all weights (including when not selected)
                        'sum_of_weights_when_used': 0.0  # Sum of weights only when selected
                    }
                
                weight_float = float(weight)
                focus_stats[focus_name]['sum_of_weights'] += weight_float
                
                # If this focus was selected, count it and add to "when used" sum
                if focus_name in selected_foci:
                    focus_stats[focus_name]['raw_count'] += 1
                    focus_stats[focus_name]['sum_of_weights_when_used'] += weight_float
            
            # Track performance correlation
            is_better = False
            eval_score = 0.5
            if evaluation:
                if evaluation.get('type') == 'thumbs_up':
                    is_better = True
                    eval_score = 1.0
                elif evaluation.get('type') == 'thumbs_down':
                    is_better = False
                    eval_score = 0.0
                elif evaluation.get('type') == 'llm_eval':
                    eval_score = evaluation.get('value', 0.5)
                    is_better = eval_score > 0.5
            
            for focus in selected_foci:
                if focus not in focus_performance:
                    focus_performance[focus] = {'better': 0, 'total': 0, 'scores': []}
                focus_performance[focus]['total'] += 1
                focus_performance[focus]['scores'].append(eval_score)
                if is_better:
                    focus_performance[focus]['better'] += 1
        
        total_pairs = len(agent_results)
        summary_parts.append("\n### Focus Usage & Weight Statistics:")
        for focus_name, stats in sorted(focus_stats.items(), key=lambda x: x[1]['sum_of_weights'], reverse=True):
            raw_count = stats['raw_count']
            usage_percentage = (raw_count / total_pairs) * 100 if total_pairs > 0 else 0
            sum_of_weights = stats['sum_of_weights']
            avg_weight = sum_of_weights / total_pairs if total_pairs > 0 else 0
            avg_weight_when_used = stats['sum_of_weights_when_used'] / raw_count if raw_count > 0 else 0
            
            summary_parts.append(
                f"- {focus_name}: "
                f"Raw Count={raw_count} ({usage_percentage:.1f}%), "
                f"Sum of Weights={sum_of_weights:.2f}, "
                f"Avg Weight={avg_weight:.3f}, "
                f"Avg Weight When Used={avg_weight_when_used:.3f}"
            )
        
        summary_parts.append("\n### Focus Performance Correlation:")
        for focus, perf in sorted(focus_performance.items(), key=lambda x: x[1]['total'], reverse=True):
            success_rate = (perf['better'] / perf['total'] * 100) if perf['total'] > 0 else 0
            avg_score = sum(perf['scores']) / len(perf['scores']) if perf['scores'] else 0.5
            summary_parts.append(
                f"- {focus}: {perf['better']}/{perf['total']} better outputs ({success_rate:.1f}%), "
                f"Avg eval score: {avg_score:.2f}"
            )
        
        summary_parts.append("")
    
    # 5. Evaluation Summary
    if agent_results:
        llm_evals = [r for r in agent_results if r.get('evaluation', {}).get('type') == 'llm_eval']
        manual_evals = [r for r in agent_results if r.get('evaluation', {}).get('type') in ['thumbs_up', 'thumbs_down']]
        
        if llm_evals or manual_evals:
            summary_parts.append("## 5. EVALUATION SUMMARY")
            if llm_evals:
                llm_scores = [e['evaluation']['value'] for e in llm_evals]
                avg_llm_score = sum(llm_scores) / len(llm_scores) if llm_scores else 0
                summary_parts.append(
                    f"LLM Evaluations: {len(llm_evals)} pairs, Average score: {avg_llm_score:.2f}"
                )
            if manual_evals:
                thumbs_up = len([e for e in manual_evals if e['evaluation']['type'] == 'thumbs_up'])
                summary_parts.append(
                    f"Manual Evaluations: {len(manual_evals)} pairs, "
                    f"Thumbs Up: {thumbs_up}/{len(manual_evals)} ({thumbs_up/len(manual_evals)*100:.1f}%)"
                )
            summary_parts.append("")
    
    return '\n'.join(summary_parts)


@app.route('/api/analyze-prompt-optimization', methods=['POST'])
def analyze_prompt_optimization():
    """Analyze all data and get LLM recommendations for prompt optimization."""
    try:
        data = request.json
        # Single chat analysis data
        single_assessment = data.get('single_assessment', [])  # assessmentFoci from prompt analysis tab
        single_ablation = data.get('single_ablation', {})  # Results from /api/ablation-analysis
        
        # Batch analysis data
        batch_analysis = data.get('batch_analysis', {})  # window.batchResultsData
        agent_results = data.get('agent_results', [])  # batchAgentResultsData
        
        # Foci and prompt
        foci_list = data.get('foci', [])
        original_prompt = data.get('original_prompt', '')
        model = data.get('model', 'gpt-4o')
        
        # Check API key
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return jsonify({'error': 'OPENAI_API_KEY not set'}), 500
        
        assessor = get_assessor()
        client = assessor.client
        
        # Build comprehensive analysis summary
        analysis_summary = build_comprehensive_analysis_summary(
            single_assessment=single_assessment,
            single_ablation=single_ablation,
            batch_analysis=batch_analysis,
            agent_results=agent_results,
            foci_list=foci_list,
            original_prompt=original_prompt
        )
        
        # Create LLM prompt for recommendations
        foci_json = json.dumps([{'focus': f.get('focus', ''), 'prompt_section': f.get('prompt_section', '')[:500]} for f in foci_list], indent=2)
        
        recommendation_prompt = f"""You are an expert at optimizing AI agent prompts based on comprehensive empirical data.

You have access to multiple types of analysis data:

1. **Single Chat Focus Assessment**: How the output distributed attention across foci for a single example
2. **Single Pair Ablation Analysis**: Influence scores showing how removing each focus affects output
3. **Batch Ablation Analysis**: Statistical analysis across multiple pairs showing average influence, variance, and consistency
4. **Batch Agent Building Results**: Which foci were selected for each input and how the optimized outputs performed
5. **Focus Usage Frequency**: How often each focus was selected across all agent building attempts
6. **Evaluation Data**: Both LLM and human ratings showing which outputs were better

COMPREHENSIVE ANALYSIS DATA:
{analysis_summary}

ORIGINAL PROMPT:
{original_prompt}

CURRENT FOCI:
{foci_json}

TASK:
Analyze this comprehensive data and provide structured recommendations for optimizing the prompt. Consider:

1. **Focus Consolidation**: Which foci are redundant, overlapping, or should be merged based on similar influence patterns?
2. **Focus Prioritization**: Which foci should be high/medium/low priority based on their impact across all analyses?
3. **Tool vs Knowledge**: Which foci should become:
   - Tools (function calls/APIs that need dynamic execution)
   - RAG knowledge documents (static reference material)
   - Remain in prompt (core instructions)
4. **Removal Candidates**: Which foci add minimal value (low influence, rarely selected, don't correlate with better outputs)?
5. **Enhancement Suggestions**: How to improve underperforming but important foci?
6. **Prompt Structure**: Recommended organization, hierarchy, and ordering based on priority and dependencies
7. **Consistency Analysis**: Which foci show high variance (unreliable) vs low variance (consistent impact)?

Return a JSON object with this structure:
{{
  "summary": "Overall assessment and key findings from all analyses",
  "recommendations": [
    {{
      "type": "consolidation" | "prioritization" | "tool_conversion" | "removal" | "enhancement" | "structure" | "consistency",
      "focus_name": "Name of focus (if applicable)",
      "current_state": "Description of current state based on the data",
      "recommendation": "Specific recommendation",
      "rationale": "Why this recommendation based on the comprehensive data",
      "priority": "high" | "medium" | "low",
      "expected_impact": "Expected impact on output quality",
      "data_evidence": "Specific data points that support this recommendation"
    }}
  ],
  "suggested_prompt_structure": {{
    "high_priority_foci": ["list of focus names"],
    "medium_priority_foci": ["list of focus names"],
    "low_priority_foci": ["list of focus names"],
    "tool_candidates": ["list of focus names with reasoning"],
    "knowledge_doc_candidates": ["list of focus names with reasoning"],
    "removal_candidates": ["list of focus names with reasoning"],
    "consolidation_suggestions": ["suggestions for merging foci"],
    "organization_suggestion": "How to organize the prompt structure with rationale"
  }},
  "key_insights": [
    "List of key insights from cross-analyzing all the data sources"
  ],
  "data_quality_assessment": {{
    "coverage": "Assessment of how well the data covers different aspects",
    "confidence": "Overall confidence in recommendations based on data quality",
    "gaps": "Any gaps in the data that limit recommendations"
  }},
  "optimized_prompt": "A complete, optimized version of the prompt that incorporates all the recommendations. This should be a ready-to-use prompt that the user can copy and use directly. Include all high and medium priority foci, remove or consolidate low priority ones based on recommendations, and organize it according to the suggested structure. For dynamic foci (chat, RAG, tools), use placeholders like {{CHAT_CONTENT}}, {{RAG_CONTEXT}}, {{TOOL_RESULTS}} where appropriate. The optimized prompt should be well-structured, clear, and implement the key recommendations."
}}"""
        
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at analyzing prompt performance data and providing actionable optimization recommendations based on multiple data sources."
                },
                {
                    "role": "user",
                    "content": recommendation_prompt
                }
            ],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        
        recommendations = json.loads(response.choices[0].message.content)
        
        # Track costs
        PRICING = {
            'gpt-4o-mini': {'input': 0.15 / 1_000_000, 'output': 0.60 / 1_000_000},
            'gpt-4o': {'input': 2.50 / 1_000_000, 'output': 10.00 / 1_000_000},
            'gpt-4-turbo': {'input': 10.00 / 1_000_000, 'output': 30.00 / 1_000_000},
        }
        model_pricing = PRICING.get(model, PRICING['gpt-4o'])
        
        cost_breakdown = {
            'input_tokens': response.usage.prompt_tokens,
            'output_tokens': response.usage.completion_tokens,
            'cost': (response.usage.prompt_tokens * model_pricing['input'] + 
                    response.usage.completion_tokens * model_pricing['output']),
            'model': model
        }
        
        return jsonify({
            'recommendations': recommendations,
            'analysis_summary': analysis_summary,  # Include the summary sent to LLM
            'optimized_prompt': recommendations.get('optimized_prompt', ''),  # Include optimized prompt
            'cost_breakdown': cost_breakdown
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/llm-evaluate-batch-agents', methods=['POST'])
def llm_evaluate_batch_agents():
    """Run LLM evaluation to compare original vs new outputs."""
    try:
        data = request.json
        results = data.get('results', [])
        model = data.get('model', 'gpt-4o-mini')
        
        if not results or len(results) == 0:
            return jsonify({'error': 'Results are required'}), 400
        
        # Check API key first
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return jsonify({'error': 'OPENAI_API_KEY environment variable not set. Please set it and restart the server.'}), 500
        
        assessor = get_assessor()
        client = assessor.client
        
        # Pricing per million tokens
        PRICING = {
            'gpt-4o-mini': {'input': 0.15 / 1_000_000, 'output': 0.60 / 1_000_000},
            'gpt-4o': {'input': 2.50 / 1_000_000, 'output': 10.00 / 1_000_000},
            'gpt-4-turbo': {'input': 10.00 / 1_000_000, 'output': 30.00 / 1_000_000},
            'gpt-3.5-turbo': {'input': 0.50 / 1_000_000, 'output': 1.50 / 1_000_000}
        }
        
        model_pricing = PRICING.get(model, PRICING['gpt-4o-mini'])
        
        # Track costs
        total_input_tokens = 0
        total_output_tokens = 0
        
        evaluations = []
        
        for result in results:
            input_text = result.get('input', '')
            original_output = result.get('original_output', '')
            new_output = result.get('new_output', '')
            
            # Use LLM to evaluate which output is better
            response = client.chat.completions.create(
                model=model,
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
            if hasattr(response, 'usage'):
                total_input_tokens += response.usage.prompt_tokens
                total_output_tokens += response.usage.completion_tokens
            
            eval_result = json.loads(response.choices[0].message.content)
            evaluations.append({
                'score': float(eval_result.get('score', 0.5)),
                'explanation': eval_result.get('explanation', ''),
                'better_output': eval_result.get('better_output', 'similar')
            })
        
        # Calculate costs
        chat_input_cost = total_input_tokens * model_pricing['input']
        chat_output_cost = total_output_tokens * model_pricing['output']
        total_cost = chat_input_cost + chat_output_cost
        
        cost_breakdown = {
            'chat_completions': {
                'input_tokens': total_input_tokens,
                'output_tokens': total_output_tokens,
                'cost': total_cost
            },
            'total_cost': total_cost,
            'model': model
        }
        
        return jsonify({
            'evaluations': evaluations,
            'cost_breakdown': cost_breakdown
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    from waitress import serve
    port = int(os.environ.get('PORT', 5001))  # Changed default from 5000 to 5001 to avoid AirPlay conflict
    host = os.environ.get('HOST', '127.0.0.1')  # Use 127.0.0.1 for local dev, 0.0.0.0 for production
    # Use waitress with 10-minute timeout for long-running ablation analysis
    # This prevents timeouts when generating 20 baseline samples + all ablated outputs
    serve(app, host=host, port=port, threads=4, channel_timeout=600)

