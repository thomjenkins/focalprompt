#!/usr/bin/env python3
"""
Authentication middleware.

Provides decorators and helpers for protecting routes.
Session (X-Session-ID / cookie) or API key (Authorization: Bearer fp_live_...).
"""

from functools import wraps
from flask import request, jsonify
import os
from services.database import Database
from services.auth_service import AuthService
from services.api_key_service import ApiKeyService

# Initialize services
db = Database()
secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
auth_service = AuthService(secret_key, db)
api_key_service = ApiKeyService(db)


def _resolve_auth():
    """
    Returns (user_dict or None, api_key_id or None, session_id or None).
    API key (Bearer fp_live_...) is tried first, then session.
    """
    auth_header = request.headers.get('Authorization', '')
    if auth_header and auth_header.lower().startswith('bearer '):
        user, key_id = api_key_service.get_user_for_bearer(auth_header)
        if user:
            return user, key_id, None
    session_id = request.headers.get('X-Session-ID') or request.cookies.get('session_id')
    if session_id:
        user = auth_service.validate_session(session_id)
        if user:
            return user, None, session_id
    return None, None, None


def require_session_auth(f):
    """
    Like require_auth but only browser/session (X-Session-ID or cookie), not API keys.
    Use for creating new API keys so a leaked integration key cannot mint more keys.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        session_id = request.headers.get('X-Session-ID') or request.cookies.get('session_id')
        if not session_id:
            return jsonify({'error': 'Session required. Log in to create an API key.'}), 401
        user = auth_service.validate_session(session_id)
        if not user:
            return jsonify({'error': 'Invalid or expired session'}), 401
        request.user = user
        request.session_id = session_id
        request.api_key_id = None
        return f(*args, **kwargs)
    return decorated_function


def require_auth(f):
    """
    Decorator to require authentication (session or API key).

    Attaches user info to request.user, request.api_key_id (if key), request.session_id (if session).
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user, api_key_id, session_id = _resolve_auth()
        if not user:
            return jsonify({'error': 'Authentication required'}), 401
        request.user = user
        request.api_key_id = api_key_id
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
        user, api_key_id, session_id = _resolve_auth()
        request.user = user
        request.api_key_id = api_key_id
        request.session_id = session_id
        return f(*args, **kwargs)
    return decorated_function
