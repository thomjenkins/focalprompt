#!/usr/bin/env python3
"""
Usage tracking and limit enforcement service.

Tracks API usage and enforces tier-based limits.
"""

import uuid
from typing import Tuple, Optional, Dict
from datetime import datetime
from services.database import Database


class UsageService:
    """Service for tracking usage and enforcing limits."""
    
    # Tier limits per month
    TIER_LIMITS = {
        'free': {
            'assessments_per_month': 10,
            'ablation_per_month': 2,
            'batch_analysis_per_month': 1,
            'agent_builds_per_month': 5
        },
        'starter': {
            'assessments_per_month': 100,
            'ablation_per_month': 20,
            'batch_analysis_per_month': 10,
            'agent_builds_per_month': 50
        },
        'professional': {
            'assessments_per_month': 1000,
            'ablation_per_month': 200,
            'batch_analysis_per_month': 100,
            'agent_builds_per_month': 500
        },
        'enterprise': {
            'assessments_per_month': -1,  # Unlimited
            'ablation_per_month': -1,
            'batch_analysis_per_month': -1,
            'agent_builds_per_month': -1
        }
    }
    
    # Map endpoints to limit keys
    ENDPOINT_LIMITS = {
        '/api/assess': 'assessments_per_month',
        '/api/detect-foci': 'assessments_per_month',
        '/api/detect-dynamic-foci': 'assessments_per_month',
        '/api/generate-output': 'assessments_per_month',
        '/api/ablation-analysis': 'ablation_per_month',
        '/api/batch-analysis-stream': 'batch_analysis_per_month',
        '/api/build-batch-agents-stream': 'agent_builds_per_month',
        '/api/llm-evaluate-batch-agents-stream': 'agent_builds_per_month'
    }
    
    def __init__(self, db: Database):
        """
        Initialize usage service.
        
        Args:
            db: Database instance
        """
        self.db = db
    
    def check_limit(self, user_id: str, endpoint: str) -> Tuple[bool, Optional[str]]:
        """
        Check if user has reached limit for endpoint.
        
        Args:
            user_id: User ID
            endpoint: API endpoint
            
        Returns:
            Tuple of (allowed, error_message)
        """
        # Get user
        user = self.db.get_user_by_id(user_id)
        if not user:
            return False, 'User not found'
        
        tier = user['tier']
        limits = self.TIER_LIMITS.get(tier, self.TIER_LIMITS['free'])
        
        # Get limit key for endpoint
        limit_key = self.ENDPOINT_LIMITS.get(endpoint)
        if not limit_key:
            return True, None  # No limit for this endpoint
        
        limit = limits.get(limit_key)
        if limit == -1:
            return True, None  # Unlimited
        
        # Get current month usage
        usage_count = self.db.get_monthly_usage(user_id, endpoint)
        
        if usage_count >= limit:
            return False, f'Monthly limit reached: {limit} {limit_key.replace("_per_month", "")}'
        
        return True, None
    
    def record_usage(
        self,
        user_id: str,
        endpoint: str,
        tokens_used: int = 0,
        cost: float = 0.0
    ) -> bool:
        """
        Record API usage.
        
        Args:
            user_id: User ID
            endpoint: API endpoint
            tokens_used: Number of tokens used
            cost: Cost in dollars
            
        Returns:
            True if successful
        """
        usage_id = str(uuid.uuid4())
        return self.db.record_usage(usage_id, user_id, endpoint, tokens_used, cost)
    
    def get_usage_summary(self, user_id: str, month: Optional[int] = None, year: Optional[int] = None) -> Dict:
        """
        Get usage summary for user.
        
        Args:
            user_id: User ID
            month: Optional month (1-12)
            year: Optional year
            
        Returns:
            Usage summary dict
        """
        return self.db.get_user_usage_summary(user_id, month, year)
    
    def get_remaining_quota(self, user_id: str, endpoint: str) -> Dict:
        """
        Get remaining quota for an endpoint.
        
        Args:
            user_id: User ID
            endpoint: API endpoint
            
        Returns:
            Dict with limit, used, remaining
        """
        user = self.db.get_user_by_id(user_id)
        if not user:
            return {'error': 'User not found'}
        
        tier = user['tier']
        limits = self.TIER_LIMITS.get(tier, self.TIER_LIMITS['free'])
        limit_key = self.ENDPOINT_LIMITS.get(endpoint)
        
        if not limit_key:
            return {'limit': -1, 'used': 0, 'remaining': -1}
        
        limit = limits.get(limit_key, 0)
        used = self.db.get_monthly_usage(user_id, endpoint)
        
        if limit == -1:
            remaining = -1  # Unlimited
        else:
            remaining = max(0, limit - used)
        
        return {
            'limit': limit,
            'used': used,
            'remaining': remaining,
            'endpoint': endpoint,
            'limit_key': limit_key
        }

