"""
Data models for analysis results.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict


@dataclass
class InfluenceScore:
    """Represents an influence score for a focus."""
    focus: str
    influence: float
    similarity: float
    normalized_influence: float
    is_significant: Optional[bool] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'focus': self.focus,
            'influence': self.influence,
            'similarity': self.similarity,
            'normalized_influence': self.normalized_influence,
            'is_significant': self.is_significant
        }


@dataclass
class AblationResult:
    """Represents a single ablation result."""
    focus_index: int
    focus: str
    prompt_section: str
    ablated_output: str
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'focus_index': self.focus_index,
            'focus': self.focus,
            'prompt_section': self.prompt_section,
            'ablated_output': self.ablated_output
        }


@dataclass
class CostBreakdown:
    """Represents cost breakdown for an operation."""
    chat_completions: Dict
    embeddings: Dict
    total_cost: float
    model: str
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'chat_completions': self.chat_completions,
            'embeddings': self.embeddings,
            'total_cost': self.total_cost,
            'model': self.model
        }


