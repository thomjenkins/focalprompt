#!/usr/bin/env python3
"""
Assessor factory for creating and managing FocalAssessor instances.

Replaces global state management with a factory pattern.
Now uses Vercel AI Gateway for all LLM requests.
"""

import os
from typing import Optional
from core.focal_assessor import FocalAssessor
from core.ai_gateway_provider import AIGatewayProvider


class AssessorFactory:
    """Factory for creating FocalAssessor instances."""
    
    def __init__(self):
        """Initialize the factory."""
        self._assessor = None
        self._assessor_model = None
        self._assessor_provider = None
        self._gateway_api_key = None  # Lazy load - don't check at import time
    
    def _get_gateway_api_key(self):
        """Get gateway API key, checking only when needed."""
        if self._gateway_api_key is None:
            self._gateway_api_key = os.getenv("AI_GATEWAY_API_KEY")
            if not self._gateway_api_key:
                # Provide helpful error message
                import sys
                print("ERROR: AI_GATEWAY_API_KEY environment variable not set.", file=sys.stderr)
                print("Please set it in your Vercel project settings:", file=sys.stderr)
                print("1. Go to Vercel Dashboard → Your Project → Settings → Environment Variables", file=sys.stderr)
                print("2. Add AI_GATEWAY_API_KEY with your gateway API key", file=sys.stderr)
                print("3. The key can be found in Settings → AI Gateway", file=sys.stderr)
                raise ValueError(
                    "AI_GATEWAY_API_KEY environment variable not set. "
                    "Please set it in your Vercel project settings. "
                    "You can find your AI Gateway API key in the Vercel dashboard under your project's AI Gateway settings."
                )
        return self._gateway_api_key
    
    def get_assessor(
        self,
        api_key: Optional[str] = None,  # Ignored - we use gateway
        model: Optional[str] = None,
        provider: Optional[str] = None
    ) -> FocalAssessor:
        """
        Get or create the assessor instance using Vercel AI Gateway.
        
        Args:
            api_key: Ignored - we use AI Gateway instead
            model: Model name to use
            provider: Provider name ('openai', 'anthropic', 'google', 'grok')
            
        Returns:
            FocalAssessor instance
        """
        # Use provided provider, or default to openai
        provider = provider or "openai"
        
        # Use provided model, or default based on provider
        if not model:
            from core.llm_providers import defaultModels
            model = defaultModels.get(provider, "gpt-4o-mini")
        
        # Create a new assessor if model or provider changed
        if (self._assessor is None or 
            self._assessor_model != model or 
            self._assessor_provider != provider):
            # Create AI Gateway provider (lazy check for API key)
            gateway_api_key = self._get_gateway_api_key()
            gateway_provider = AIGatewayProvider(gateway_api_key)
            
            # Create assessor with gateway provider
            self._assessor = FocalAssessor(provider_instance=gateway_provider, model=model, provider=provider)
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


