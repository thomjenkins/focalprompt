#!/usr/bin/env python3
"""
Authentication route handlers.

Handles user registration, login, logout, and session management.
"""

from flask import Blueprint, request, jsonify
import os
from services.database import Database
from services.auth_service import AuthService

auth_bp = Blueprint('auth', __name__)

# Initialize services
db = Database()
secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
auth_service = AuthService(secret_key, db)


@auth_bp.route('/api/auth/register', methods=['POST'])
def register():
    """Register a new user."""
    try:
        data = request.json
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        if not email or not password:
            return jsonify({'error': 'Email and password are required'}), 400
        
        result = auth_service.register_user(email, password)
        
        if 'error' in result:
            return jsonify(result), 400
        
        return jsonify(result), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    """Login user and create session."""
    try:
        data = request.json
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        if not email or not password:
            return jsonify({'error': 'Email and password are required'}), 400
        
        result = auth_service.login_user(email, password)
        
        if 'error' in result:
            return jsonify(result), 401
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/api/auth/logout', methods=['POST'])
def logout():
    """Logout user by invalidating session."""
    try:
        session_id = request.headers.get('X-Session-ID') or request.json.get('session_id')
        
        if not session_id:
            return jsonify({'error': 'Session ID required'}), 400
        
        success = auth_service.logout_user(session_id)
        
        if success:
            return jsonify({'message': 'Logged out successfully'})
        else:
            return jsonify({'error': 'Invalid session'}), 401
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/api/auth/me', methods=['GET'])
def get_current_user():
    """Get current user info from session."""
    try:
        session_id = request.headers.get('X-Session-ID') or request.cookies.get('session_id')
        
        if not session_id:
            return jsonify({'error': 'Not authenticated'}), 401
        
        user = auth_service.validate_session(session_id)
        
        if not user:
            return jsonify({'error': 'Invalid or expired session'}), 401
        
        return jsonify({
            'id': user['id'],
            'email': user['email'],
            'tier': user['tier'],
            'subscription_status': user['subscription_status']
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

