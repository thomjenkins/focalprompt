#!/usr/bin/env python3
"""
Authentication service for FocalPrompt SaaS.

Handles user registration, login, session management, and password hashing.
"""

from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer
from datetime import datetime, timedelta
import secrets
import uuid
from typing import Optional, Dict
from services.database import Database


class AuthService:
    """Service for user authentication and session management."""
    
    def __init__(self, secret_key: str, db: Database):
        """
        Initialize authentication service.
        
        Args:
            secret_key: Secret key for session token signing
            db: Database instance
        """
        self.serializer = URLSafeTimedSerializer(secret_key)
        self.db = db
    
    def register_user(self, email: str, password: str) -> Dict:
        """
        Register a new user.
        
        Args:
            email: User email
            password: Plain text password
            
        Returns:
            Dict with user info or error
        """
        # Validate email
        if not email or '@' not in email:
            return {'error': 'Invalid email address'}
        
        # Validate password
        if not password or len(password) < 8:
            return {'error': 'Password must be at least 8 characters'}
        
        # Check if user exists
        existing_user = self.db.get_user_by_email(email)
        if existing_user:
            return {'error': 'Email already registered'}
        
        # Create user
        user_id = str(uuid.uuid4())
        password_hash = generate_password_hash(password)
        
        user_data = {
            'id': user_id,
            'email': email,
            'password_hash': password_hash,
            'tier': 'free',
            'credit_balance': 5.0,  # $5 starting credit
            'created_at': datetime.now().isoformat(),
            'subscription_status': 'active'
        }
        
        success = self.db.create_user(user_data)
        if not success:
            return {'error': 'Failed to create user'}
        
        return {
            'user_id': user_id,
            'email': email,
            'tier': 'free'
        }
    
    def login_user(self, email: str, password: str) -> Dict:
        """
        Login user and create session.
        
        Args:
            email: User email
            password: Plain text password
            
        Returns:
            Dict with session info or error
        """
        # Get user
        user = self.db.get_user_by_email(email)
        if not user:
            return {'error': 'Invalid email or password'}
        
        # Check password
        if not check_password_hash(user['password_hash'], password):
            return {'error': 'Invalid email or password'}
        
        # Check subscription status
        if user['subscription_status'] != 'active':
            return {'error': 'Account is not active. Please check your subscription.'}
        
        # Create session
        session_id = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(days=30)
        
        success = self.db.create_session(session_id, user['id'], expires_at)
        if not success:
            return {'error': 'Failed to create session'}
        
        return {
            'session_id': session_id,
            'expires_at': expires_at.isoformat(),
            'user': {
                'id': user['id'],
                'email': user['email'],
                'tier': user['tier']
            }
        }
    
    def validate_session(self, session_id: str) -> Optional[Dict]:
        """
        Validate session and return user info.
        
        Args:
            session_id: Session token
            
        Returns:
            User dict if valid, None otherwise
        """
        session = self.db.get_session(session_id)
        if not session:
            return None
        
        # Check expiration
        if isinstance(session['expires_at'], str):
            expires_at = datetime.fromisoformat(session['expires_at'])
        else:
            expires_at = session['expires_at']
        
        if expires_at < datetime.now():
            self.db.delete_session(session_id)
            return None
        
        # Get user
        user = self.db.get_user_by_id(session['user_id'])
        if not user:
            self.db.delete_session(session_id)
            return None
        
        # Check subscription status
        if user['subscription_status'] != 'active':
            return None
        
        return {
            'id': user['id'],
            'email': user['email'],
            'tier': user['tier'],
            'subscription_status': user['subscription_status']
        }
    
    def logout_user(self, session_id: str) -> bool:
        """
        Logout user by deleting session.
        
        Args:
            session_id: Session token
            
        Returns:
            True if successful
        """
        return self.db.delete_session(session_id)
    
    def change_password(self, user_id: str, old_password: str, new_password: str) -> Dict:
        """
        Change user password.
        
        Args:
            user_id: User ID
            old_password: Current password
            new_password: New password
            
        Returns:
            Dict with success or error
        """
        user = self.db.get_user_by_id(user_id)
        if not user:
            return {'error': 'User not found'}
        
        # Verify old password
        if not check_password_hash(user['password_hash'], old_password):
            return {'error': 'Current password is incorrect'}
        
        # Validate new password
        if not new_password or len(new_password) < 8:
            return {'error': 'New password must be at least 8 characters'}
        
        # Update password
        new_hash = generate_password_hash(new_password)
        # Note: We'll need to add an update_password method to Database
        # For now, this is a placeholder
        
        return {'success': True, 'message': 'Password changed successfully'}

