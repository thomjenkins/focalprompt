#!/usr/bin/env python3
"""
Embedding service for generating text embeddings.

Currently only supports OpenAI embeddings (other providers don't have embedding APIs).
"""

import numpy as np
from typing import List
from openai import OpenAI


class EmbeddingService:
    """Service for generating text embeddings."""
    
    def __init__(self, api_key: str):
        """
        Initialize embedding service.
        
        Args:
            api_key: OpenAI API key (embeddings only supported by OpenAI)
        """
        self.client = OpenAI(api_key=api_key)
        self.model = "text-embedding-3-small"
    
    def get_embedding(self, text: str) -> np.ndarray:
        """
        Get embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            Numpy array of embedding vector
        """
        response = self.client.embeddings.create(
            model=self.model,
            input=text
        )
        return np.array(response.data[0].embedding)
    
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
    
    def get_embedding_with_usage(self, text: str) -> tuple:
        """
        Get embedding and token usage.
        
        Args:
            text: Text to embed
            
        Returns:
            Tuple of (embedding_array, token_count)
        """
        response = self.client.embeddings.create(
            model=self.model,
            input=text
        )
        embedding = np.array(response.data[0].embedding)
        token_count = response.usage.total_tokens if hasattr(response, 'usage') else 0
        return embedding, token_count


