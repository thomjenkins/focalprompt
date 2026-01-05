#!/usr/bin/env python3
"""
Assessor factory for creating and managing FocalAssessor instances.

Replaces global state management with a factory pattern.
"""

import os
from typing import Optional
from core.focal_assessor import FocalAssessor


class AssessorFactory:
    """Factory for creating FocalAssessor instances."""
    
    def __init__(self):
        """Initialize the factory."""
        self._assessor = None
        self._assessor_api_key = None
        self._assessor_model = None
        self._assessor_provider = None
    
    def get_assessor(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None
    ) -> FocalAssessor:
        """
        Get or create the assessor instance.
        
        Args:
            api_key: API key for the provider
            model: Model name to use
            provider: Provider name ('openai', 'anthropic', 'google', 'grok')
            
        Returns:
            FocalAssessor instance
        """
        # Use provided provider, or default to openai
        provider = provider or "openai"
        
        # Use provided API key, or fall back to environment variable
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("API key not provided and OPENAI_API_KEY environment variable not set")
        
        # Use provided model, or default based on provider
        if not model:
            from core.llm_providers import defaultModels
            model = defaultModels.get(provider, "gpt-4o-mini")
        
        # Create a new assessor if API key, model, or provider changed
        if (self._assessor is None or 
            self._assessor_api_key != api_key or 
            self._assessor_model != model or 
            self._assessor_provider != provider):
            self._assessor = FocalAssessor(api_key=api_key, model=model, provider=provider)
            self._assessor_api_key = api_key
            self._assessor_model = model
            self._assessor_provider = provider
        
        return self._assessor
    
    def clear_cache(self):
        """Clear the cached assessor (force recreation on next get_assessor call)."""
        self._assessor = None
        self._assessor_api_key = None
        self._assessor_model = None
        self._assessor_provider = None


# Global factory instance (can be replaced with dependency injection later)
_assessor_factory = AssessorFactory()


def get_assessor(
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    provider: Optional[str] = None
) -> FocalAssessor:
    """
    Get or create the assessor instance (convenience function).
    
    Args:
        api_key: API key for the provider
        model: Model name to use
        provider: Provider name
        
    Returns:
        FocalAssessor instance
    """
    return _assessor_factory.get_assessor(api_key=api_key, model=model, provider=provider)


