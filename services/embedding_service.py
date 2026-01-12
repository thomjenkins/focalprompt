#!/usr/bin/env python3
"""
Embedding service for generating text embeddings via Vercel AI Gateway.

Uses OpenAI embeddings through the AI Gateway.
"""

import os
import time
import numpy as np
from typing import List, Tuple

# Lazy import - only import requests when actually needed
_requests_available = None

def _check_requests():
    """Check if requests is available, raise error if not."""
    global _requests_available
    if _requests_available is None:
        try:
            import requests
            _requests_available = requests
        except ImportError:
            raise ImportError("requests package not installed. Install with: pip install requests")
    return _requests_available


class EmbeddingService:
    """Service for generating text embeddings via AI Gateway."""
    
    def __init__(self, gateway_api_key: str = None, base_url: str = None):
        """
        Initialize embedding service.
        
        Args:
            gateway_api_key: Vercel AI Gateway API key (defaults to AI_GATEWAY_API_KEY env var)
            base_url: Optional custom gateway URL (defaults to Vercel's gateway)
        """
        self.gateway_api_key = gateway_api_key or os.getenv("AI_GATEWAY_API_KEY")
        if not self.gateway_api_key:
            raise ValueError("AI_GATEWAY_API_KEY not provided and not found in environment variables")
        
        # Vercel AI Gateway endpoint (OpenAI-compatible)
        # Official URL: https://ai-gateway.vercel.sh/v1
        self.base_url = base_url or os.getenv("AI_GATEWAY_URL", "https://ai-gateway.vercel.sh/v1")
        self.base_url = self.base_url.rstrip('/')
        
        # OpenAI embedding model (via gateway)
        self.model = "openai/text-embedding-3-small"
    
    def get_embedding(self, text: str) -> np.ndarray:
        """
        Get embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            Numpy array of embedding vector
        """
        requests = _check_requests()  # Lazy import
        url = f"{self.base_url}/embeddings"
        headers = {
            'Authorization': f'Bearer {self.gateway_api_key}',
            'Content-Type': 'application/json'
        }
        payload = {
            'model': self.model,
            'input': text
        }
        
        # Retry logic for rate limits
        max_retries = 3
        retry_delay = 2  # Start with 2 seconds
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                response = requests.post(url, json=payload, headers=headers, timeout=60)
                response.raise_for_status()
                
                data = response.json()
                return np.array(data['data'][0]['embedding'])
                
            except requests.exceptions.HTTPError as e:
                error_code = e.response.status_code if e.response else None
                if error_code == 429:  # Rate limit
                    if attempt < max_retries - 1:
                        # Exponential backoff: 2s, 4s, 8s
                        wait_time = retry_delay * (2 ** attempt)
                        time.sleep(wait_time)
                        continue
                    else:
                        raise Exception(f"Rate limit exceeded for embeddings after {max_retries} retries. Please wait a few minutes and try again.")
                else:
                    # Not a rate limit error, re-raise immediately
                    raise
            except Exception as e:
                # Other errors, re-raise immediately
                raise
    
    def batch_embeddings(self, texts: List[str]) -> List[np.ndarray]:
        """
        Get embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of numpy arrays
        """
        embeddings = []
        for text in texts:
            embeddings.append(self.get_embedding(text))
        return embeddings
    
    def get_embedding_with_usage(self, text: str) -> Tuple[np.ndarray, int]:
        """
        Get embedding and token usage.
        
        Args:
            text: Text to embed
            
        Returns:
            Tuple of (embedding_array, token_count)
        """
        requests = _check_requests()  # Lazy import
        url = f"{self.base_url}/embeddings"
        headers = {
            'Authorization': f'Bearer {self.gateway_api_key}',
            'Content-Type': 'application/json'
        }
        payload = {
            'model': self.model,
            'input': text
        }
        
        # Retry logic for rate limits
        max_retries = 3
        retry_delay = 2  # Start with 2 seconds
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                response = requests.post(url, json=payload, headers=headers, timeout=60)
                response.raise_for_status()
                
                data = response.json()
                embedding = np.array(data['data'][0]['embedding'])
                token_count = data.get('usage', {}).get('total_tokens', 0)
                return embedding, token_count
                
            except requests.exceptions.HTTPError as e:
                error_code = e.response.status_code if e.response else None
                if error_code == 429:  # Rate limit
                    if attempt < max_retries - 1:
                        # Exponential backoff: 2s, 4s, 8s
                        wait_time = retry_delay * (2 ** attempt)
                        time.sleep(wait_time)
                        continue
                    else:
                        raise Exception(f"Rate limit exceeded for embeddings after {max_retries} retries. Please wait a few minutes and try again.")
                else:
                    # Not a rate limit error, re-raise immediately
                    raise
            except Exception as e:
                # Other errors, re-raise immediately
                raise


