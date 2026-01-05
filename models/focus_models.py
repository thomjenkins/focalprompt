"""
Data models for focus-related structures.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict


@dataclass
class Focus:
    """Represents a single focus point."""
    focus: str
    prompt_section: str
    is_dynamic: bool = False
    dynamic_type: Optional[str] = None  # 'chat', 'rag', 'tools', 'other'
    weight: float = 1.0
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'focus': self.focus,
            'prompt_section': self.prompt_section,
            'is_dynamic': self.is_dynamic,
            'dynamic_type': self.dynamic_type,
            'weight': self.weight
        }


@dataclass
class FocusWeight:
    """Represents a focus with weight assignment."""
    focus: str
    weight: float
    explanation: str = ""
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'focus': self.focus,
            'weight': self.weight,
            'explanation': self.explanation
        }


