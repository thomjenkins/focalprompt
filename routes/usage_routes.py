#!/usr/bin/env python3
"""
Usage tracking route handlers.

Provides endpoints for users to check their usage and quotas.
"""

from flask import Blueprint, request, jsonify
from services.database import Database
from services.usage_service import UsageService
from middleware.auth import require_auth

usage_bp = Blueprint('usage', __name__)

# Initialize services
db = Database()
usage_service = UsageService(db)


@usage_bp.route('/api/usage/summary', methods=['GET'])
@require_auth
def get_usage_summary():
    """Get usage summary for current user."""
    try:
        month = request.args.get('month', type=int)
        year = request.args.get('year', type=int)
        
        summary = usage_service.get_usage_summary(
            request.user['id'],
            month,
            year
        )
        
        return jsonify(summary)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@usage_bp.route('/api/usage/quota', methods=['GET'])
@require_auth
def get_quota():
    """Get remaining quota for an endpoint."""
    try:
        endpoint = request.args.get('endpoint')
        
        if not endpoint:
            return jsonify({'error': 'Endpoint required'}), 400
        
        quota = usage_service.get_remaining_quota(
            request.user['id'],
            endpoint
        )
        
        if 'error' in quota:
            return jsonify(quota), 400
        
        return jsonify(quota)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

