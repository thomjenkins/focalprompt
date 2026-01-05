#!/usr/bin/env python3
"""
Optimization service.

Handles prompt optimization analysis based on comprehensive data.
"""

import json
from typing import List, Dict, Optional
from services.cost_calculator import CostCalculator


class OptimizationService:
    """Service for prompt optimization analysis."""
    
    def __init__(
        self,
        provider,
        model: str,
        cost_calculator: Optional[CostCalculator] = None
    ):
        """
        Initialize optimization service.
        
        Args:
            provider: LLM provider instance
            model: Model name to use
            cost_calculator: Optional CostCalculator instance
        """
        self.provider = provider
        self.model = model
        self.cost_calculator = cost_calculator or CostCalculator()
    
    def build_comprehensive_analysis_summary(
        self,
        single_assessment: List[Dict],
        single_ablation: Dict,
        batch_analysis: Dict,
        agent_results: List[Dict],
        foci_list: List[Dict],
        original_prompt: str
    ) -> str:
        """
        Build a comprehensive summary of all analysis data.
        
        Args:
            single_assessment: Single chat focus assessment data
            single_ablation: Single pair ablation analysis results
            batch_analysis: Batch analysis results
            agent_results: Agent building results
            foci_list: List of foci
            original_prompt: Original prompt text
            
        Returns:
            Formatted summary string
        """
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
                    continue
                mean = focus_stats.get('mean', 0)
                std_dev = focus_stats.get('std_dev', 0)
                min_val = focus_stats.get('min', 0)
                max_val = focus_stats.get('max', 0)
                summary_parts.append(
                    f"- {focus_name}: Mean={mean:.3f}, StdDev={std_dev:.3f}, "
                    f"Range=[{min_val:.3f}, {max_val:.3f}]"
                )
                if std_dev > 0.1:
                    summary_parts.append(f"  ⚠️ High variance - inconsistent impact across pairs")
            
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
            
            focus_stats = {}
            focus_performance = {}
            
            for result in agent_results:
                selected_foci = result.get('selected_foci', [])
                foci_weights = result.get('foci_weights', {})
                evaluation = result.get('evaluation', {})
                
                for focus_name, weight in foci_weights.items():
                    if focus_name not in focus_stats:
                        focus_stats[focus_name] = {
                            'raw_count': 0,
                            'sum_of_weights': 0.0,
                            'sum_of_weights_when_used': 0.0
                        }
                    
                    weight_float = float(weight)
                    focus_stats[focus_name]['sum_of_weights'] += weight_float
                    
                    if focus_name in selected_foci:
                        focus_stats[focus_name]['raw_count'] += 1
                        focus_stats[focus_name]['sum_of_weights_when_used'] += weight_float
                
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
    
    def analyze_prompt_optimization(
        self,
        single_assessment: List[Dict],
        single_ablation: Dict,
        batch_analysis: Dict,
        agent_results: List[Dict],
        foci_list: List[Dict],
        original_prompt: str
    ) -> Dict:
        """
        Analyze all data and get LLM recommendations for prompt optimization.
        
        Args:
            single_assessment: Single chat focus assessment data
            single_ablation: Single pair ablation analysis results
            batch_analysis: Batch analysis results
            agent_results: Agent building results
            foci_list: List of foci
            original_prompt: Original prompt text
            
        Returns:
            Dict with recommendations, analysis_summary, optimized_prompt, and cost_breakdown
        """
        # Build comprehensive analysis summary
        analysis_summary = self.build_comprehensive_analysis_summary(
            single_assessment,
            single_ablation,
            batch_analysis,
            agent_results,
            foci_list,
            original_prompt
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
        
        response = self.provider.chat_completion(
            model=self.model,
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
        
        recommendations = json.loads(response['content'])
        
        # Calculate costs
        total_input_tokens = response['usage']['prompt_tokens'] if 'usage' in response else 0
        total_output_tokens = response['usage']['completion_tokens'] if 'usage' in response else 0
        
        cost_breakdown = self.cost_calculator.calculate_cost(
            total_input_tokens,
            total_output_tokens,
            0,  # No embeddings
            self.model,
            'openai'  # Default, should be provider-specific
        )
        
        return {
            'recommendations': recommendations,
            'analysis_summary': analysis_summary,
            'optimized_prompt': recommendations.get('optimized_prompt', ''),
            'cost_breakdown': cost_breakdown
        }


