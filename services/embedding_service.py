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
    """Service for generating text embeddings (Gateway or OpenAI-compatible)."""
    
    def __init__(
        self,
        gateway_api_key: str = None,
        base_url: str = None,
        model: str = None,
        api_key: str = None,
    ):
        """
        Initialize embedding service.
        
        Args:
            gateway_api_key: Legacy alias for api_key (AI Gateway or OpenAI-compatible)
            api_key: Bearer token
            base_url: OpenAI-compatible /embeddings base (defaults to Gateway URL)
            model: Embedding model id
        """
        from utils.inference_config import resolve_embedding_config
        if gateway_api_key or api_key or base_url or model:
            self.gateway_api_key = api_key or gateway_api_key or os.getenv("AI_GATEWAY_API_KEY")
            self.base_url = (base_url or os.getenv("AI_GATEWAY_URL") or os.getenv("FOCALPROMPT_EMBEDDING_BASE_URL") or "https://ai-gateway.vercel.sh/v1").rstrip('/')
            self.model = model or os.getenv("FOCALPROMPT_EMBEDDING_MODEL") or (
                "openai/text-embedding-3-small"
                if "ai-gateway.vercel.sh" in self.base_url
                else "text-embedding-3-small"
            )
        else:
            cfg = resolve_embedding_config()
            self.gateway_api_key = cfg['api_key']
            self.base_url = cfg['base_url']
            self.model = cfg['model']
        if not self.gateway_api_key:
            raise ValueError(
                "No embedding API key. Set AI_GATEWAY_API_KEY or OPENAI_API_KEY "
                "(or pass api_key=)."
            )
    
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
        Get embeddings for multiple texts using batch API (more efficient).
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of numpy arrays
        """
        if not texts:
            return []
        
        requests = _check_requests()  # Lazy import
        url = f"{self.base_url}/embeddings"
        headers = {
            'Authorization': f'Bearer {self.gateway_api_key}',
            'Content-Type': 'application/json'
        }
        payload = {
            'model': self.model,
            'input': texts  # Send all texts in one request
        }
        
        # Retry logic for rate limits
        max_retries = 3
        retry_delay = 2  # Start with 2 seconds
        
        for attempt in range(max_retries):
            try:
                response = requests.post(url, json=payload, headers=headers, timeout=60)
                response.raise_for_status()
                
                data = response.json()
                # Return list of embeddings
                return [np.array(item['embedding']) for item in data['data']]
                
            except requests.exceptions.HTTPError as e:
                error_code = e.response.status_code if e.response else None
                if error_code == 429:  # Rate limit
                    if attempt < max_retries - 1:
                        # Exponential backoff: 2s, 4s, 8s
                        wait_time = retry_delay * (2 ** attempt)
                        time.sleep(wait_time)
                        continue
                    else:
                        raise Exception(f"Rate limit exceeded for batch embeddings after {max_retries} retries. Please wait a few minutes and try again.")
                else:
                    # Not a rate limit error, re-raise immediately
                    raise
            except Exception as e:
                # Other errors, re-raise immediately
                raise
    
    def batch_embeddings_with_usage(self, texts: List[str]) -> Tuple[List[np.ndarray], int]:
        """
        Get embeddings for multiple texts with token usage (batch API).
        
        Args:
            texts: List of texts to embed
            
        Returns:
            Tuple of (list of embedding arrays, total_token_count)
        """
        if not texts:
            return [], 0
        
        requests = _check_requests()  # Lazy import
        url = f"{self.base_url}/embeddings"
        headers = {
            'Authorization': f'Bearer {self.gateway_api_key}',
            'Content-Type': 'application/json'
        }
        payload = {
            'model': self.model,
            'input': texts  # Send all texts in one request
        }
        
        # Retry logic for rate limits
        max_retries = 3
        retry_delay = 2  # Start with 2 seconds
        
        for attempt in range(max_retries):
            try:
                response = requests.post(url, json=payload, headers=headers, timeout=60)
                response.raise_for_status()
                
                data = response.json()
                embeddings = [np.array(item['embedding']) for item in data['data']]
                token_count = data.get('usage', {}).get('total_tokens', 0)
                return embeddings, token_count
                
            except requests.exceptions.HTTPError as e:
                error_code = e.response.status_code if e.response else None
                if error_code == 429:  # Rate limit
                    if attempt < max_retries - 1:
                        # Exponential backoff: 2s, 4s, 8s
                        wait_time = retry_delay * (2 ** attempt)
                        time.sleep(wait_time)
                        continue
                    else:
                        raise Exception(f"Rate limit exceeded for batch embeddings after {max_retries} retries. Please wait a few minutes and try again.")
                else:
                    # Not a rate limit error, re-raise immediately
                    raise
            except Exception as e:
                # Other errors, re-raise immediately
                raise
    
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


