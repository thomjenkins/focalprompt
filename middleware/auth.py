#!/usr/bin/env python3
"""
Authentication middleware.

Provides decorators and helpers for protecting routes.
"""

from functools import wraps
from flask import request, jsonify
import os
from services.database import Database
from services.auth_service import AuthService

# Initialize services
db = Database()
secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
auth_service = AuthService(secret_key, db)


def require_auth(f):
    """
    Decorator to require authentication.
    
    Attaches user info to request.user
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get session ID from header or cookie
        session_id = request.headers.get('X-Session-ID') or request.cookies.get('session_id')
        
        if not session_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        # Validate session
        user = auth_service.validate_session(session_id)
        
        if not user:
            return jsonify({'error': 'Invalid or expired session'}), 401
        
        # Attach user to request
        request.user = user
        request.session_id = session_id
        
        return f(*args, **kwargs)
    
    return decorated_function


def optional_auth(f):
    """
    Decorator for optional authentication.
    
    Attaches user info to request.user if authenticated, otherwise None.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        session_id = request.headers.get('X-Session-ID') or request.cookies.get('session_id')
        
        if session_id:
            user = auth_service.validate_session(session_id)
            request.user = user
            request.session_id = session_id
        else:
            request.user = None
            request.session_id = None
        
        return f(*args, **kwargs)
    
    return decorated_function

